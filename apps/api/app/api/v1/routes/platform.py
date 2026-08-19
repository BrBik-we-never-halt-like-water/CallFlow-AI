"""The cross-tenant support surface. `docs/PLATFORM_ADMIN.md`.

Every route here answers **404** to anyone without the capability, never 403: a
prober should not learn that a privileged tier exists, let alone which one they
were short of.

The dependencies are the affordance. The boundary is inside the `SECURITY DEFINER`
functions these call, because Postgres grants function EXECUTE to PUBLIC unless
revoked - so the check that actually stops an ordinary user is the one in the
database, not the one on the decorator.

Writes are enumerated one endpoint at a time and each takes a mandatory `reason`
that lands in `platform_audit_log` in the same transaction as the change.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.platform import (
    PlatformAdmin,
    PlatformCapability,
    RequirePlatformCapability,
)
from app.database import database
from app.database.repositories import platform as platform_repo

# What the definer functions raise when they refuse for a reason worth showing.
# `raise ... using errcode = '22023'` becomes InvalidParameterValueError; a bare
# `raise` would be RaiseError. Both are caught, because which one a given check
# uses is a detail of the SQL and must not decide whether the API 400s or 500s.
# 42501 is deliberately absent: that is "not permitted", and letting it fall
# through keeps the 404-not-403 behaviour the dependencies establish.
REFUSALS = (asyncpg.exceptions.RaiseError, asyncpg.exceptions.InvalidParameterValueError)

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])

# The limits an override may set. Declared once so the request model, the SQL
# function's own check, and `domain/plans.py` cannot drift into three lists.
OVERRIDABLE = (
    "max_voice_agents",
    "max_seats",
    "max_organisations",
    "max_ai_integrations",
    "daily_call_budget",
)


class PlatformOrgOut(BaseModel):
    org_id: str
    name: str
    slug: str
    plan_id: str
    has_override: bool
    member_count: int
    agent_count: int
    run_count: int
    created_at: str


class OverrideOut(BaseModel):
    """`null` means "no override on this limit, use the plan". A limit named in
    `unlimited` has no ceiling - which a null cannot express, since null already
    means unspecified."""

    org_id: str
    max_voice_agents: int | None
    max_seats: int | None
    max_organisations: int | None
    max_ai_integrations: int | None
    daily_call_budget: int | None
    llm_spend_limit_usd: float | None
    unlimited: list[str]
    note: str | None
    updated_at: str


class SetPlanIn(BaseModel):
    plan_id: str
    reason: str = Field(min_length=4, max_length=500)


class SetOverrideIn(BaseModel):
    max_voice_agents: int | None = Field(default=None, ge=0)
    max_seats: int | None = Field(default=None, ge=0)
    max_organisations: int | None = Field(default=None, ge=0)
    max_ai_integrations: int | None = Field(default=None, ge=0)
    daily_call_budget: int | None = Field(default=None, ge=0)
    llm_spend_limit_usd: Decimal | None = Field(default=None, ge=0)
    unlimited: list[str] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=500)
    reason: str = Field(min_length=4, max_length=500)


class AuditEntryOut(BaseModel):
    id: str
    actor_user_id: str | None
    action: str
    target_org_id: str | None
    reason: str
    created_at: str


def _org_out(row: asyncpg.Record) -> PlatformOrgOut:
    return PlatformOrgOut(
        org_id=str(row["org_id"]),
        name=row["name"],
        slug=row["slug"],
        plan_id=row["plan_id"],
        has_override=row["has_override"],
        member_count=row["member_count"],
        agent_count=row["agent_count"],
        run_count=row["run_count"],
        created_at=row["created_at"].isoformat(),
    )


def _override_out(row: asyncpg.Record) -> OverrideOut:
    return OverrideOut(
        org_id=str(row["org_id"]),
        max_voice_agents=row["max_voice_agents"],
        max_seats=row["max_seats"],
        max_organisations=row["max_organisations"],
        max_ai_integrations=row["max_ai_integrations"],
        daily_call_budget=row["daily_call_budget"],
        llm_spend_limit_usd=(
            float(row["llm_spend_limit_usd"])
            if row["llm_spend_limit_usd"] is not None
            else None
        ),
        unlimited=list(row["unlimited"]),
        note=row["note"],
        updated_at=row["updated_at"].isoformat(),
    )


@router.get("/organisations", response_model=list[PlatformOrgOut])
async def list_organisations(
    admin: Annotated[
        PlatformAdmin, Depends(RequirePlatformCapability(PlatformCapability.ORGS_READ))
    ],
    search: str | None = None,
) -> list[PlatformOrgOut]:
    """Every organisation, with its plan and usage counts. No customer data.

    `orgs:read` is deliberately a lower bar than `data:read` - knowing a customer
    exists and what they pay for is not the same as reading their calls.
    """
    async with database.as_user(admin.auth_user_id) as conn:
        rows = await platform_repo.list_organisations(conn, search=search)
    return [_org_out(row) for row in rows]


@router.get("/organisations/{org_id}/entitlements", response_model=OverrideOut | None)
async def get_override(
    org_id: UUID,
    admin: Annotated[
        PlatformAdmin, Depends(RequirePlatformCapability(PlatformCapability.ORGS_READ))
    ],
) -> OverrideOut | None:
    """`null` is the normal answer: most organisations are on their plan's numbers."""
    async with database.as_user(admin.auth_user_id) as conn:
        row = await platform_repo.get_override(conn, org_id)
    return _override_out(row) if row else None


@router.put("/organisations/{org_id}/plan", status_code=status.HTTP_204_NO_CONTENT)
async def set_plan(
    org_id: UUID,
    body: SetPlanIn,
    admin: Annotated[
        PlatformAdmin,
        Depends(RequirePlatformCapability(PlatformCapability.ENTITLEMENTS_WRITE)),
    ],
) -> None:
    """Set a plan for a deal closed offline.

    Does **not** touch `org_subscriptions`: there is no gateway subscription behind
    an invoiced deal, and inventing one would make Billing offer to cancel
    something that does not exist. The organisation's plan and its subscription are
    already separate, with the subscription as the source of truth only when there
    is one.
    """
    async with database.as_user(admin.auth_user_id) as conn:
        try:
            await platform_repo.set_plan(
                conn, org_id=org_id, plan_id=body.plan_id, reason=body.reason
            )
        except REFUSALS as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=_detail(exc)
            ) from exc


@router.put(
    "/organisations/{org_id}/entitlements", status_code=status.HTTP_204_NO_CONTENT
)
async def set_override(
    org_id: UUID,
    body: SetOverrideIn,
    admin: Annotated[
        PlatformAdmin,
        Depends(RequirePlatformCapability(PlatformCapability.ENTITLEMENTS_WRITE)),
    ],
) -> None:
    """Write or clear this organisation's agreed limits.

    Sending every limit as null with an empty `unlimited` clears the override
    entirely, which is why there is no separate delete endpoint: clearing is the
    same decision as changing, and needs the same reason on the record.
    """
    unknown = sorted(set(body.unlimited) - set(OVERRIDABLE))
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not a limit this schema enforces: {', '.join(unknown)}.",
        )

    async with database.as_user(admin.auth_user_id) as conn:
        try:
            await platform_repo.set_entitlements(
                conn,
                org_id=org_id,
                max_voice_agents=body.max_voice_agents,
                max_seats=body.max_seats,
                max_organisations=body.max_organisations,
                max_ai_integrations=body.max_ai_integrations,
                daily_call_budget=body.daily_call_budget,
                llm_spend_limit_usd=body.llm_spend_limit_usd,
                unlimited=body.unlimited,
                note=body.note,
                reason=body.reason,
            )
        except REFUSALS as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=_detail(exc)
            ) from exc


class PlatformRunOut(BaseModel):
    id: str
    status: str
    campaign_name: str | None
    calls: int
    created_at: str
    finished_at: str | None


@router.get("/organisations/{org_id}/runs", response_model=list[PlatformRunOut])
async def list_org_runs(
    org_id: UUID,
    reason: str,
    admin: Annotated[
        PlatformAdmin, Depends(RequirePlatformCapability(PlatformCapability.DATA_READ))
    ],
) -> list[PlatformRunOut]:
    """One organisation's recent runs, for answering "what happened on this call".

    The only endpoint that uses `database.as_platform_reader`, and the reason that
    primitive exists: this reads another tenant's rows through RLS rather than around
    it. `platform_can_read` on `runs_select` is what makes them visible, the
    transaction is read-only so Postgres refuses any write regardless of policy, and
    the session is audited before the connection is handed over.

    `reason` is a required query parameter rather than a body field because this is a
    GET, and it is required at all because an all-orgs session is only
    reconstructable later through the reason someone gave for opening it. No
    unaudited read path exists.

    No transcripts and no phone numbers: those need `pii:reveal`, which CLAUDE.md
    §4 #4 keeps as a separate permissioned action. Dispositions, statuses and
    timings answer most support questions without either.
    """
    if len(reason.strip()) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Say why you're opening this organisation - it goes in the audit log.",
        )

    async with database.as_platform_reader(admin.auth_user_id, reason=reason) as conn:
        rows = await platform_repo.recent_runs(conn, org_id)

    return [
        PlatformRunOut(
            id=str(row["id"]),
            status=row["status"],
            campaign_name=row["campaign_name"],
            calls=row["calls"],
            created_at=row["created_at"].isoformat(),
            finished_at=row["finished_at"].isoformat() if row["finished_at"] else None,
        )
        for row in rows
    ]


@router.get("/audit", response_model=list[AuditEntryOut])
async def read_audit(
    admin: Annotated[
        PlatformAdmin, Depends(RequirePlatformCapability(PlatformCapability.ORGS_READ))
    ],
    limit: int = 100,
) -> list[AuditEntryOut]:
    """Every platform action, newest first.

    `before_state`/`after_state` are recorded but not returned: they can hold a
    customer's agreed commercial terms, and the log is read far more often to answer
    "who touched this" than "what exactly changed".
    """
    async with database.as_user(admin.auth_user_id) as conn:
        rows = await platform_repo.read_audit(conn, limit=limit)
    return [
        AuditEntryOut(
            id=str(row["id"]),
            actor_user_id=str(row["actor_user_id"]) if row["actor_user_id"] else None,
            action=row["action"],
            target_org_id=str(row["target_org_id"]) if row["target_org_id"] else None,
            reason=row["reason"],
            created_at=row["created_at"].isoformat(),
        )
        for row in rows
    ]


def _detail(exc: asyncpg.PostgresError) -> str:
    """The function's own sentence, never `str(exc)` - an asyncpg error can carry
    the statement that failed, and a route must not hand that to a browser."""
    message = getattr(exc, "message", None)
    return message or "That change could not be applied."
