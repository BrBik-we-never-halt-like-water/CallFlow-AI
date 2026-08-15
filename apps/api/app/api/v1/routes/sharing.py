"""Peer-to-peer campaign/escalation sharing - role-based UI roadmap, Phase 4.

An operator can ask for a teammate's campaign or to take over their
escalation; only the resource's actual owner can decide. Approving a
**campaign** request clones it (`created_by = requester`, a new id,
independent from that point on - edits after this never write back to the
original). Approving an **escalation** request reassigns it
(`assigned_to = requester`) - one real event, not a fork, unlike a
reusable campaign template.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission, current_user
from app.auth.permissions import Permission
from app.database import database
from app.database.repositories import campaigns as campaigns_repo
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import sharing as sharing_repo
from app.domain.campaigns import BUILT_IN_IDS, slugify

router = APIRouter(prefix="/api/v1/share-requests", tags=["sharing"])

_RESOURCE_TYPES = {"campaign", "escalation"}


def _require_uuid(value: str, *, what: str) -> None:
    """An escalation's `resource_id` reaches a `::uuid` cast inside
    `resolve_resource_owner()` (`SECURITY DEFINER`, `plpgsql`) - a
    non-UUID string there raises an uncaught Postgres error, surfacing as
    an unhandled 500. Validated here instead, matching the friendly-400
    convention `escalations.py`'s own `assign_escalation` already uses for
    `user_id`."""
    try:
        UUID(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{what} must be a UUID."
        ) from exc


class ShareRequestIn(BaseModel):
    resource_type: str
    resource_id: str
    message: str | None = Field(default=None, max_length=280)


class ShareRequestOut(BaseModel):
    id: str
    resource_type: str
    resource_id: str
    # Null when this connection's RLS can't resolve it - always true for the
    # requester's own sent rows, before it's approved. See `list_for_org`'s
    # own docstring.
    resource_name: str | None = None
    status: str
    message: str | None
    created_at: datetime
    decided_at: datetime | None
    requested_by: str
    requested_by_name: str | None
    owner_user_id: str
    owner_name: str | None


def _row_to_out(row) -> ShareRequestOut:
    return ShareRequestOut(
        id=str(row["id"]),
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        resource_name=row["resource_name"],
        status=row["status"],
        message=row["message"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
        requested_by=str(row["requested_by"]),
        requested_by_name=row["requested_by_name"],
        owner_user_id=str(row["owner_user_id"]),
        owner_name=row["owner_name"],
    )


@router.get("", response_model=list[ShareRequestOut])
async def list_share_requests(
    user: Annotated[CurrentUser, Depends(current_user)],
) -> list[ShareRequestOut]:
    """Own sent requests, plus any directed at this user to decide - RLS
    (`share_requests_select`) does the actual narrowing; no permission
    check needed beyond being signed in."""
    async with database.as_user(user.auth_user_id) as conn:
        rows = await sharing_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=ShareRequestOut, status_code=status.HTTP_201_CREATED)
async def create_share_request(
    body: ShareRequestIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SHARING_REQUEST))],
) -> ShareRequestOut:
    if body.resource_type not in _RESOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"resource_type must be one of: {', '.join(sorted(_RESOURCE_TYPES))}.",
        )
    if body.resource_type == "escalation":
        _require_uuid(body.resource_id, what="resource_id")

    async with database.as_user(user.auth_user_id) as conn:
        # Resolved server-side, never trusted from the client - the whole
        # point of this lookup is that the requester's own RLS scope
        # wouldn't let them see this resource (or its owner) at all.
        owner_id = await sharing_repo.resolve_resource_owner(
            conn,
            org_id=user.org_id,
            resource_type=body.resource_type,
            resource_id=body.resource_id,
        )
        if owner_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {body.resource_type} with that id in this organisation.",
            )
        if owner_id == user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already own this - there's nothing to request.",
            )
        try:
            row = await sharing_repo.create_request(
                conn,
                org_id=user.org_id,
                resource_type=body.resource_type,
                resource_id=body.resource_id,
                requested_by=user.id,
                owner_user_id=owner_id,
                message=body.message,
            )
        except asyncpg.exceptions.UniqueViolationError as exc:
            if exc.constraint_name == "share_requests_one_pending_idx":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You already have a pending request for this.",
                ) from exc
            raise
    # `row` has no joined names yet (this connection just created it) - the
    # requester already knows their own name; `owner_name` is the one gap,
    # left null rather than paying for a second query for a value the
    # response barely needs (the owner's name mattered for *choosing* who
    # to ask, which the directory already showed).
    return ShareRequestOut(
        id=str(row["id"]),
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        status=row["status"],
        message=row["message"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
        requested_by=str(row["requested_by"]),
        requested_by_name=user.name,
        owner_user_id=str(row["owner_user_id"]),
        owner_name=None,
    )


async def _decide(
    request_id: UUID, user: CurrentUser, *, approve: bool
) -> None:
    """The atomic `decide()` transition runs *before* the grant, not after -
    two concurrent decisions on the same request must not both perform the
    grant (a clone, or a reassignment) before one of them loses the race.
    Everything here shares one `database.as_user()` transaction
    (`session.py`'s own guarantee: "a handler commits all of its writes or
    none"), so if the grant step raises after `decide()` already ran, the
    whole transaction - including that `decide()` - rolls back, leaving the
    request genuinely still pending rather than "approved" with no actual
    grant behind it.
    """
    async with database.as_user(user.auth_user_id) as conn:
        existing = await sharing_repo.get_for_org(conn, user.org_id, request_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
        # Belt-and-suspenders on top of RLS (`share_requests_update` already
        # restricts the UPDATE to owner_user_id = self) - fails with the
        # actual reason instead of a silent no-op 404.
        if str(existing["owner_user_id"]) != str(user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the person who owns this can decide on it.",
            )
        if existing["status"] != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This request was already {existing['status']}.",
            )

        # Ownership can move between the request being made and being
        # decided (an admin reassigns the escalation elsewhere; the
        # campaign's creator leaves and their work gets reassigned). The
        # stamped-in `owner_user_id` on this row is who *was* the owner, not
        # necessarily who still is - re-resolved here rather than trusted.
        # A stale request is auto-rejected (this caller's RLS grant to
        # update the row is still valid, even though they're no longer the
        # real owner) rather than left permanently pending with no one able
        # to act on it.
        current_owner = await sharing_repo.resolve_resource_owner(
            conn,
            org_id=user.org_id,
            resource_type=existing["resource_type"],
            resource_id=existing["resource_id"],
        )
        if current_owner is None or str(current_owner) != str(existing["owner_user_id"]):
            await sharing_repo.decide(
                conn, org_id=user.org_id, request_id=request_id, approve=False
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ownership of this changed since the request was made - it's been closed.",
            )

        decided = await sharing_repo.decide(
            conn, org_id=user.org_id, request_id=request_id, approve=approve
        )
        if decided is None:
            # Someone else's decision on this same request won the race.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This request was just decided by someone else.",
            )

        if approve:
            if existing["resource_type"] == "campaign":
                await _clone_campaign(
                    conn,
                    org_id=user.org_id,
                    campaign_id=existing["resource_id"],
                    new_owner=existing["requested_by"],
                )
            else:
                updated = await escalations_repo.assign(
                    conn,
                    org_id=user.org_id,
                    escalation_id=UUID(existing["resource_id"]),
                    assigned_to=existing["requested_by"],
                    assigned_by=user.id,
                )
                if updated is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="That escalation no longer exists, or is no longer open.",
                    )


async def _clone_campaign(conn, *, org_id: UUID, campaign_id: str, new_owner: UUID) -> None:
    original = await campaigns_repo.get_org_campaign(conn, org_id, campaign_id)
    if original is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That campaign no longer exists."
        )

    existing = await campaigns_repo.list_org_campaigns(conn, org_id)
    taken = {r["id"] for r in existing} | BUILT_IN_IDS
    base = slugify(f"{original['name']} (shared)")
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1

    # The dedup above stays a plain, RLS-scoped read (the approver already
    # has full read access to their own campaign and can list the org's ids
    # to avoid a slug collision) - only the actual privileged write goes
    # through the `SECURITY DEFINER` path. See `clone_for_share()`'s own
    # docstring for why a plain insert can't work here.
    await campaigns_repo.clone_for_share(
        conn,
        org_id=org_id,
        source_campaign_id=campaign_id,
        new_campaign_id=candidate,
        new_owner=new_owner,
    )


@router.post("/{request_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
async def approve_share_request(
    request_id: UUID, user: Annotated[CurrentUser, Depends(current_user)]
) -> None:
    await _decide(request_id, user, approve=True)


@router.post("/{request_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_share_request(
    request_id: UUID, user: Annotated[CurrentUser, Depends(current_user)]
) -> None:
    await _decide(request_id, user, approve=False)
