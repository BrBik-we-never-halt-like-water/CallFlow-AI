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
from app.domain.entitlements import (
    check_org_create_allowed,
    check_seat_available,
)
from app.integrations.email.resend import (
    EmailAPIError,
    EmailGateway,
    EmailNotConfigured,
)
from app.services import billing
from app.services import credit as credit_service

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
    #: `None` means nobody has set a usage-credit share for this teammate, so
    #: only the organisation-wide balance governs them - distinct from `0`,
    #: which blocks them entirely.
    credit_cap_paise: int | None
    credit_spent_paise: int


class MyCreditsOut(BaseModel):
    credit_cap_paise: int | None
    credit_spent_paise: int


class CreditCapIn(BaseModel):
    #: `null` explicitly sets "uncapped" (only the org-wide balance governs);
    #: omitting the field is not an option this model allows - the client
    #: always states what it wants, never relies on "unset" meaning
    #: "unchanged," which is what makes a single nullable field safe to reuse
    #: for both "set a cap" and "clear it" without a second endpoint shape.
    monthly_credit_cap_paise: int | None = Field(default=None, ge=0)


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
        # Counted per *user*, not per organisation - the only entitlement that is.
        # `create_organisation()` checks again inside itself, because it is SECURITY
        # DEFINER and Postgres grants EXECUTE to PUBLIC unless revoked.
        effective = await billing.resolve_plan(conn, user.org_id, user.org_plan_id)
        billing.refuse(
            check_org_create_allowed(
                entitlements=effective.entitlements,
                plan_name=billing.plan_name(effective.plan_id),
                owned_org_count=await org_repo.count_owned_orgs_for_current_user(conn),
            )
        )
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
        # A pending invitation holds a seat, so an admin cannot over-invite and
        # disappoint people one accept at a time. This is the courtesy, not the
        # guard: `enforce_seat_limit` re-checks on the membership insert itself,
        # because a downgrade can land between the invitation and the click.
        members, pending = await org_repo.seat_usage(conn, user.org_id)
        effective = await billing.resolve_plan(conn, user.org_id, user.org_plan_id)
        billing.refuse(
            check_seat_available(
                entitlements=effective.entitlements,
                plan_name=billing.plan_name(effective.plan_id),
                member_count=members,
                pending_invite_count=pending,
            )
        )
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
    """Calls, run status, open escalations, and usage-credit share - one row
    per *current* teammate, plus one synthetic row for whatever a removed
    teammate's runs left behind. Four separate aggregates (members, runs,
    escalations, credit status), each already correctly scoped by its own RLS
    policy and each one query, merged here in Python rather than one giant
    join, so each stays a straightforward query in its own repository.

    Deliberately **not** built by iterating `runs_repo.team_performance()`'s
    rows: that query is `from runs`, so it has no row at all for a teammate
    who has never started one - a brand-new operator, or an owner who only
    manages billing. Their credit cap would then never appear here even
    though it was saved correctly, because this endpoint - not the write -
    would be silently excluding them. `org_repo.list_members()` is the base
    set instead, so every current member gets a row, with zero run/call stats
    where there is nothing to report.
    """
    async with database.as_user(user.auth_user_id) as conn:
        members = await org_repo.list_members(conn, user.org_id)
        performance_rows = await runs_repo.team_performance(conn, user.org_id)
        perf_by_member = {
            row["started_by"]: row for row in performance_rows if row["started_by"] is not None
        }
        open_by_member = {
            r["member_id"]: r["open_escalations"]
            for r in await escalations_repo.open_counts_by_member(conn, user.org_id)
            if r["member_id"] is not None
        }
        # One (cap, spend) pair per member, computed the same way the run gate
        # itself checks it - see `credit_service.member_credit_cap_status`.
        # Sequential, not a batch query: this panel is small (one org's team),
        # and adding a batch form of `credit_member_spend` for a page nobody
        # has reported as slow is the kind of premature abstraction the
        # per-member cap itself was almost left out for.
        credit_status_by_member = {
            member["user_id"]: await credit_service.member_credit_cap_status(
                conn, org_id=user.org_id, user_id=member["user_id"]
            )
            for member in members
        }

        def _row_for(member_id: UUID, name: str | None, avatar_url: str | None) -> TeamPerformanceOut:
            perf = perf_by_member.get(member_id)
            cap_paise, spent_paise = credit_status_by_member.get(member_id, (None, 0))
            return TeamPerformanceOut(
                user_id=str(member_id),
                name=name,
                avatar_url=avatar_url,
                total_runs=perf["total_runs"] if perf else 0,
                runs_active=perf["runs_active"] if perf else 0,
                runs_completed=perf["runs_completed"] if perf else 0,
                runs_failed=perf["runs_failed"] if perf else 0,
                total_calls=perf["total_calls"] if perf else 0,
                calls_closed=perf["calls_closed"] if perf else 0,
                open_escalations=open_by_member.get(member_id, 0),
                credit_cap_paise=cap_paise,
                credit_spent_paise=spent_paise,
            )

        results = [
            _row_for(member["user_id"], member["name"], member["avatar_url"]) for member in members
        ]

        # Runs started by someone no longer a member still happened and still
        # count toward the team's totals - `runs_repo.team_performance()`
        # groups every one of those under a single `started_by is null` row
        # rather than dropping them, and this preserves that one synthetic
        # row. It has no member to hold a credit cap, so it carries none.
        orphaned = next((r for r in performance_rows if r["started_by"] is None), None)
        if orphaned is not None:
            results.append(
                TeamPerformanceOut(
                    user_id=None,
                    name=orphaned["started_by_name"],
                    avatar_url=orphaned["started_by_avatar_url"],
                    total_runs=orphaned["total_runs"],
                    runs_active=orphaned["runs_active"],
                    runs_completed=orphaned["runs_completed"],
                    runs_failed=orphaned["runs_failed"],
                    total_calls=orphaned["total_calls"],
                    calls_closed=orphaned["calls_closed"],
                    open_escalations=open_by_member.get(None, 0),
                    credit_cap_paise=None,
                    credit_spent_paise=0,
                )
            )
    return results


@router.get("/me/members/me/credits", response_model=MyCreditsOut)
async def my_credits(user: Annotated[CurrentUser, Depends(current_user)]) -> MyCreditsOut:
    """Your own usage-credit share and spend - no permission beyond being
    signed in, since RLS already scopes `member_credit_allocations` to your
    own row (or the whole org, for admin/owner/viewer)."""
    async with database.as_user(user.auth_user_id) as conn:
        cap_paise, spent_paise = await credit_service.member_credit_cap_status(
            conn, org_id=user.org_id, user_id=user.id
        )
    return MyCreditsOut(
        credit_cap_paise=cap_paise,
        credit_spent_paise=spent_paise,
    )


@router.patch("/me/members/{member_user_id}/credit-cap", status_code=status.HTTP_204_NO_CONTENT)
async def set_member_credit_cap(
    member_user_id: UUID,
    body: CreditCapIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.CREDITS_WRITE))],
) -> None:
    """One teammate's share of the organisation's usage credit, in money.

    Refused above the plan's own per-period grant: a share larger than the
    whole organisation ever receives in a period is not a real ceiling on
    anyone, and reads as a promise the balance cannot keep - a teammate told
    they have ₹5,000 to spend when the org receives ₹850 a month would only
    discover the difference the hard way, at the run gate.
    """
    async with database.as_user(user.auth_user_id) as conn:
        role = await org_repo.get_member_role(conn, user.org_id, member_user_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

        cap_paise = body.monthly_credit_cap_paise
        if cap_paise is not None:
            effective = await billing.resolve_plan(conn, user.org_id, user.org_plan_id)
            plan_allowance = effective.entitlements.monthly_credit_paise
            if plan_allowance is not None and cap_paise > plan_allowance:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{billing.plan_name(effective.plan_id)} grants only "
                        f"₹{plan_allowance // 100:,} of usage credit a period - a "
                        "teammate's share can't be set higher than that."
                    ),
                )

        await credits_repo.set_credit_cap(
            conn,
            org_id=user.org_id,
            user_id=member_user_id,
            cap_paise=cap_paise,
            updated_by=user.id,
        )
