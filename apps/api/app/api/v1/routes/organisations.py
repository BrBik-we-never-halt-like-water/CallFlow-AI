"""Organisations the caller belongs to: create, switch, edit, delete - and the team
inside the active one: members, roles, invitations."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission, current_user
from app.auth.permissions import Permission, can_act_on_member, can_grant_role
from app.core.config import config
from app.database import database
from app.database.models import OrgRole
from app.database.repositories import credits as credits_repo
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import organisations as org_repo
from app.database.repositories import runs as runs_repo
from app.integrations.email.resend import (
    EmailAPIError,
    EmailGateway,
    EmailNotConfigured,
)

router = APIRouter(prefix="/api/v1/organisations", tags=["organisations"])

INVITATION_TTL_DAYS = 7
VALID_ROLES = {"admin", "operator", "viewer", "owner"}
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class OrganisationOut(BaseModel):
    id: str
    name: str
    slug: str
    logo_url: str | None
    role: str


class OrganisationCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OrganisationUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    logo_url: str | None = None


class OnboardingCompleteIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class MemberOut(BaseModel):
    user_id: str
    name: str | None
    email: str
    avatar_url: str | None
    role: str
    joined_at: datetime


class PendingInviteOut(BaseModel):
    id: str
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class TeamOut(BaseModel):
    members: list[MemberOut]
    pending: list[PendingInviteOut]


class InviteIn(BaseModel):
    email: str
    role: str = "operator"


class RoleUpdateIn(BaseModel):
    role: str


class TeamPerformanceOut(BaseModel):
    user_id: str | None
    name: str | None
    avatar_url: str | None
    total_runs: int
    runs_active: int
    runs_completed: int
    runs_failed: int
    total_calls: int
    calls_closed: int
    open_escalations: int
    daily_allocation: int
    credits_used_today: int


class MyCreditsOut(BaseModel):
    daily_allocation: int
    used_today: int


class CreditAllocationIn(BaseModel):
    daily_allocation: int = Field(ge=0)


def _row_to_org(row: asyncpg.Record) -> OrganisationOut:
    return OrganisationOut(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        logo_url=row["logo_url"],
        role=row["role"],
    )


def _validate_role(role: str) -> str:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{role}' isn't a role. Use one of: {', '.join(sorted(VALID_ROLES))}.",
        )
    return role


def _ensure_can_grant(user: CurrentUser, role: str) -> None:
    """Block a grant that would outrank the caller - the admin-to-owner hole.

    `Permission.TEAM_SET_ROLE`/`TEAM_INVITE` only gate that a role can be
    changed at all; Admin holds both, same as Owner. This is the check for
    *which* role, applied before either write reaches the database.
    """
    if can_grant_role(user.role, OrgRole(role)):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Your role ({user.role.value}) can't grant '{role}'. "
            "You can only grant a role below your own - ask an owner to make this change."
        ),
    )


def _ensure_can_act_on(user: CurrentUser, target_current_role: str) -> None:
    """Block acting on a member who outranks the caller - the companion gap
    to `_ensure_can_grant`: an Admin who can't grant `owner`/`admin` shouldn't
    be able to demote or remove someone who already holds it, either. Never
    called for the caller's own row - self-service is `_ensure_can_grant`'s
    job alone.
    """
    if can_act_on_member(user.role, OrgRole(target_current_role)):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Your role ({user.role.value}) can't act on a '{target_current_role}'. "
            "Ask an owner to make this change."
        ),
    )


@router.get("", response_model=list[OrganisationOut])
async def list_mine(user: Annotated[CurrentUser, Depends(current_user)]) -> list[OrganisationOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await org_repo.list_mine(conn)
    return [_row_to_org(r) for r in rows]


@router.post("", response_model=OrganisationOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: OrganisationCreateIn, user: Annotated[CurrentUser, Depends(current_user)]
) -> OrganisationOut:
    async with database.as_user(user.auth_user_id) as conn:
        row = await org_repo.create(conn, body.name)
    return OrganisationOut(
        id=str(row["id"]), name=row["name"], slug=row["slug"], logo_url=row["logo_url"], role="owner"
    )


@router.patch("/me", response_model=OrganisationOut)
async def update_active(
    body: OrganisationUpdateIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.ORG_UPDATE))],
) -> OrganisationOut:
    async with database.as_user(user.auth_user_id) as conn:
        row = await org_repo.update_active(conn, user.org_id, name=body.name, logo_url=body.logo_url)
    return OrganisationOut(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        logo_url=row["logo_url"],
        role=user.role.value,
    )


@router.post("/me/complete-onboarding", response_model=OrganisationOut)
async def complete_onboarding(
    body: OnboardingCompleteIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.ORG_UPDATE))],
) -> OrganisationOut:
    """Confirm the org's name, ending the mandatory first-run setup gate.

    Whoever completes this is the org's owner in the realistic case - a fresh
    signup is always the owner of the organisation the signup trigger just
    created for them.
    """
    async with database.as_user(user.auth_user_id) as conn:
        row = await org_repo.complete_onboarding(conn, user.org_id, body.name)
    return OrganisationOut(
        id=str(row["id"]),
        name=row["name"],
        slug=row["slug"],
        logo_url=row["logo_url"],
        role=user.role.value,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_active(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.ORG_DELETE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        org_count = await org_repo.count_orgs_for_current_user(conn)
        if org_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This is your only organisation. Create another before deleting this one.",
            )
        await org_repo.delete_active(conn, user.org_id)


@router.get("/me/members", response_model=TeamOut)
async def list_team(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.TEAM_READ))],
    q: Annotated[str | None, Query(max_length=120)] = None,
) -> TeamOut:
    async with database.as_user(user.auth_user_id) as conn:
        members = await org_repo.list_members(conn, user.org_id, search=q)
        pending = await org_repo.list_pending_invitations(conn, user.org_id)
    return TeamOut(
        members=[
            MemberOut(
                user_id=str(m["user_id"]),
                name=m["name"],
                email=m["email"],
                avatar_url=m["avatar_url"],
                role=m["role"],
                joined_at=m["joined_at"],
            )
            for m in members
        ],
        pending=[
            PendingInviteOut(
                id=str(p["id"]),
                email=p["email"],
                role=p["role"],
                expires_at=p["expires_at"],
                created_at=p["created_at"],
            )
            for p in pending
        ],
    )


@router.post("/me/invitations", response_model=PendingInviteOut, status_code=status.HTTP_201_CREATED)
async def invite(
    body: InviteIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.TEAM_INVITE))],
) -> PendingInviteOut:
    role = _validate_role(body.role)
    _ensure_can_grant(user, role)
    if not _EMAIL_RE.match(body.email.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That doesn't look like an email address.",
        )
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(days=INVITATION_TTL_DAYS)

    async with database.as_user(user.auth_user_id) as conn:
        row = await org_repo.create_invitation(
            conn,
            org_id=user.org_id,
            email=body.email,
            role=role,
            token=token,
            expires_at=expires_at,
        )

    accept_url = f"{config.site_url}/accept-invite/{token}"
    try:
        await EmailGateway().send_invitation(
            to_email=body.email, org_name=user.org_name, role=role, accept_url=accept_url
        )
    except EmailNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except EmailAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return PendingInviteOut(
        id=str(row["id"]),
        email=row["email"],
        role=row["role"],
        expires_at=row["expires_at"],
        created_at=row["created_at"],
    )


@router.delete("/me/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    invitation_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.TEAM_INVITE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await org_repo.revoke_invitation(conn, user.org_id, invitation_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")


@router.patch("/me/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def set_member_role(
    member_user_id: UUID,
    body: RoleUpdateIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.TEAM_SET_ROLE))],
) -> None:
    role = _validate_role(body.role)
    _ensure_can_grant(user, role)
    async with database.as_user(user.auth_user_id) as conn:
        try:
            if member_user_id != user.id:
                current_role = await org_repo.get_member_role(conn, user.org_id, member_user_id)
                if current_role is not None:
                    _ensure_can_act_on(user, current_role)
            await org_repo.set_member_role(conn, user.org_id, member_user_id, role)
        except asyncpg.exceptions.RestrictViolationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.delete("/me/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    member_user_id: UUID, user: Annotated[CurrentUser, Depends(current_user)]
) -> None:
    # Leaving your own organisation needs no special permission - the RLS delete
    # policy already allows it. Removing someone else does.
    if member_user_id != user.id and not user.can(Permission.TEAM_REMOVE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your role ({user.role.value}) cannot remove other teammates. "
                "It requires the team:remove permission - ask an owner or admin."
            ),
        )
    async with database.as_user(user.auth_user_id) as conn:
        try:
            if member_user_id != user.id:
                current_role = await org_repo.get_member_role(conn, user.org_id, member_user_id)
                if current_role is not None:
                    _ensure_can_act_on(user, current_role)
                # Removing someone else reassigns their org data to the caller
                # and deletes their account entirely - a different, heavier
                # operation than leaving your own org (below).
                await org_repo.remove_teammate_and_reassign_data(
                    conn, user.org_id, member_user_id
                )
            else:
                await org_repo.remove_member(conn, user.org_id, member_user_id)
        except asyncpg.exceptions.RestrictViolationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc


@router.get("/me/team-performance", response_model=list[TeamPerformanceOut])
async def team_performance(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.RUNS_READ_TEAM))],
) -> list[TeamPerformanceOut]:
    """Calls, run status, open escalations, and credits - one row per
    teammate, for the admin/owner/viewer dashboard panel. Four separate
    aggregates (runs, escalations, credit allocations, credit usage), each
    already correctly scoped by its own RLS policy and each one query - not
    a used_today lookup per member - merged here in Python rather than one
    giant join, so each stays a straightforward query in its own repository.
    """
    async with database.as_user(user.auth_user_id) as conn:
        performance_rows = await runs_repo.team_performance(conn, user.org_id)
        open_by_member = {
            r["member_id"]: r["open_escalations"]
            for r in await escalations_repo.open_counts_by_member(conn, user.org_id)
            if r["member_id"] is not None
        }
        allocations = {
            r["user_id"]: r["daily_allocation"]
            for r in await credits_repo.list_allocations(conn, user.org_id)
        }
        used_today_by_member = {
            r["started_by"]: r["used_today"]
            for r in await credits_repo.used_today_by_member(conn, user.org_id)
            if r["started_by"] is not None
        }
        results = [
            TeamPerformanceOut(
                user_id=str(row["started_by"]) if row["started_by"] else None,
                name=row["started_by_name"],
                avatar_url=row["started_by_avatar_url"],
                total_runs=row["total_runs"],
                runs_active=row["runs_active"],
                runs_completed=row["runs_completed"],
                runs_failed=row["runs_failed"],
                total_calls=row["total_calls"],
                calls_closed=row["calls_closed"],
                open_escalations=open_by_member.get(row["started_by"], 0),
                daily_allocation=allocations.get(row["started_by"], 0),
                credits_used_today=used_today_by_member.get(row["started_by"], 0),
            )
            for row in performance_rows
        ]
    return results


@router.get("/me/members/me/credits", response_model=MyCreditsOut)
async def my_credits(user: Annotated[CurrentUser, Depends(current_user)]) -> MyCreditsOut:
    """Your own credit allocation and today's usage - no permission beyond
    being signed in, since RLS already scopes `member_credit_allocations`
    to your own row (or the whole org, for admin/owner/viewer)."""
    async with database.as_user(user.auth_user_id) as conn:
        allocation = await credits_repo.get_allocation(conn, user.org_id, user.id)
        used = await credits_repo.used_today(conn, user.org_id, user.id)
    return MyCreditsOut(daily_allocation=allocation, used_today=used)


@router.patch("/me/members/{member_user_id}/credits", status_code=status.HTTP_204_NO_CONTENT)
async def set_member_credits(
    member_user_id: UUID,
    body: CreditAllocationIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.CREDITS_WRITE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        role = await org_repo.get_member_role(conn, user.org_id, member_user_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")
        await credits_repo.set_allocation(
            conn,
            org_id=user.org_id,
            user_id=member_user_id,
            daily_allocation=body.daily_allocation,
            updated_by=user.id,
        )
