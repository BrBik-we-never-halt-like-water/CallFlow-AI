"""Real, persisted "needs a person" items - Phase 2 of the role-based UI
roadmap. Replaces a computed, unpersisted label (ISSUES.md #7): assigning or
resolving one now survives a page reload."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.database import database
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import organisations as org_repo
from app.database.repositories import sharing as sharing_repo

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])


class EscalationOut(BaseModel):
    """A superset of the `Outcome` shape (`GET /api/v1/runs/{id}`'s per-call
    records) plus the escalation's own lifecycle fields - so the frontend can
    feed one of these anywhere an `Outcome` is expected (the transcript
    sheet, the lamp helpers) with no adapter needed. `escalation_status` is
    the escalation's own open/resolved state; `status` is the call's own
    status, same field the `Outcome` type already uses that name for.
    """

    id: str
    run_id: str
    campaign_id: str
    escalation_status: str
    contact_name: str
    phone_masked: str
    status: str
    provider_call_id: str | None
    disposition: str
    disposition_reason: str | None
    sentiment: str
    sentiment_reason: str | None
    transcript: str | None
    summary: str | None
    duration_seconds: float | None
    error: str | None
    extracted: dict[str, Any]
    created_at: datetime
    assigned_to: str | None
    assigned_to_name: str | None
    assigned_by: str | None
    assigned_by_name: str | None
    resolved_by: str | None
    resolved_by_name: str | None
    resolved_at: datetime | None


class AssignIn(BaseModel):
    user_id: str


class EscalationDirectoryEntryOut(BaseModel):
    id: str
    contact_name: str
    campaign_name: str
    owner_user_id: str | None
    owner_name: str | None


def _row_to_out(row) -> EscalationOut:
    return EscalationOut(
        id=str(row["id"]),
        run_id=row["run_id"],
        campaign_id=row["campaign_id"],
        escalation_status=row["escalation_status"],
        contact_name=row["contact_name"],
        phone_masked=row["phone_masked"],
        status=row["status"],
        provider_call_id=row["provider_call_id"],
        disposition=row["disposition"],
        disposition_reason=row["disposition_reason"],
        sentiment=row["sentiment"],
        sentiment_reason=row["sentiment_reason"],
        transcript=row["transcript"],
        summary=row["summary"],
        duration_seconds=row["duration_seconds"],
        error=row["error"],
        extracted=row["extracted"] or {},
        created_at=row["created_at"],
        assigned_to=str(row["assigned_to"]) if row["assigned_to"] else None,
        assigned_to_name=row["assigned_to_name"],
        assigned_by=str(row["assigned_by"]) if row["assigned_by"] else None,
        assigned_by_name=row["assigned_by_name"],
        resolved_by=str(row["resolved_by"]) if row["resolved_by"] else None,
        resolved_by_name=row["resolved_by_name"],
        resolved_at=row["resolved_at"],
    )


@router.get("", response_model=list[EscalationOut])
async def list_escalations(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.ESCALATIONS_READ))],
) -> list[EscalationOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await escalations_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.get("/directory", response_model=list[EscalationDirectoryEntryOut])
async def escalation_directory(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SHARING_REQUEST))],
) -> list[EscalationDirectoryEntryOut]:
    """Contact name + campaign + current owner, for every **open** escalation
    org-wide - no transcript, no disposition detail. Lets an operator see
    what else is waiting so they can offer to help (Phase 4), without the
    content their own `GET /api/v1/escalations` correctly keeps hidden.
    Gated on `SHARING_REQUEST` (not just any signed-in user, unlike the
    campaign directory) - deliberately, since this one surfaces which
    customers are currently frustrated org-wide, a step more sensitive than
    a campaign's mere existence.
    """
    async with database.as_user(user.auth_user_id) as conn:
        rows = await sharing_repo.list_escalation_directory(conn, user.org_id)
    return [
        EscalationDirectoryEntryOut(
            id=str(r["id"]),
            contact_name=r["contact_name"],
            campaign_name=r["campaign_name"],
            owner_user_id=str(r["owner_user_id"]) if r["owner_user_id"] else None,
            owner_name=r["owner_name"],
        )
        for r in rows
    ]


@router.post("/{escalation_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign_escalation(
    escalation_id: UUID,
    body: AssignIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.ESCALATIONS_ASSIGN))],
) -> None:
    try:
        assignee_id = UUID(body.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="user_id must be a UUID."
        ) from exc

    async with database.as_user(user.auth_user_id) as conn:
        role = await org_repo.get_member_role(conn, user.org_id, assignee_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That person isn't a member of this organisation.",
            )
        updated = await escalations_repo.assign(
            conn,
            org_id=user.org_id,
            escalation_id=escalation_id,
            assigned_to=assignee_id,
            assigned_by=user.id,
        )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found, or it's already resolved.",
        )


@router.post("/{escalation_id}/resolve", status_code=status.HTTP_204_NO_CONTENT)
async def resolve_escalation(
    escalation_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.ESCALATIONS_RESOLVE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        updated = await escalations_repo.resolve(
            conn, org_id=user.org_id, escalation_id=escalation_id, resolved_by=user.id
        )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Escalation not found, or it's already resolved.",
        )
