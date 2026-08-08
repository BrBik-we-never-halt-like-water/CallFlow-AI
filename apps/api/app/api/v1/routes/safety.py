"""An organisation's own overrides for the safety guards - the write side
`ISSUES.md` flagged as missing: every value in Settings -> Safety used to be the
deployment's env vars, shared and unsaveable. `GET` also carries this
organisation's real, live rate-limit usage, which `/api/health` can no longer
report per-org now that the limiter is keyed by organisation, not by IP."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.core.rate_limit import limiter
from app.database import database
from app.database.repositories import safety_settings as safety_repo
from app.domain.safety import is_e164, resolve_safety_settings

router = APIRouter(prefix="/api/v1/safety", tags=["safety"])


class SafetySettingsOut(BaseModel):
    allowlist: list[str]
    max_calls_per_run: int
    calls_per_window: int
    window_minutes: int
    daily_budget: int
    used_today: int


class SafetySettingsIn(BaseModel):
    allowlist: list[str] = Field(default_factory=list)
    max_calls_per_run: int = Field(gt=0)
    calls_per_window: int = Field(gt=0)
    window_minutes: int = Field(gt=0)
    daily_budget: int = Field(gt=0)


def _to_out(row: asyncpg.Record | None, org_id: UUID) -> SafetySettingsOut:
    effective = resolve_safety_settings(
        allowlist=row["allowlist"] if row else None,
        max_calls_per_run=row["max_calls_per_run"] if row else None,
        calls_per_window=row["calls_per_window"] if row else None,
        window_minutes=row["window_minutes"] if row else None,
        daily_budget=row["daily_budget"] if row else None,
    )
    usage = limiter.snapshot(
        str(org_id),
        rate_limit_calls=effective.calls_per_window,
        rate_limit_window_seconds=effective.window_minutes * 60,
        daily_call_budget=effective.daily_budget,
    )
    return SafetySettingsOut(
        allowlist=sorted(effective.allowlist),
        max_calls_per_run=effective.max_calls_per_run,
        calls_per_window=effective.calls_per_window,
        window_minutes=effective.window_minutes,
        daily_budget=effective.daily_budget,
        used_today=usage["used_today"],
    )


@router.get("", response_model=SafetySettingsOut)
async def get_settings(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SAFETY_READ))],
) -> SafetySettingsOut:
    async with database.as_user(user.auth_user_id) as conn:
        row = await safety_repo.get_for_org(conn, user.org_id)
    return _to_out(row, user.org_id)


@router.patch("", response_model=SafetySettingsOut)
async def update_settings(
    body: SafetySettingsIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SAFETY_WRITE))],
) -> SafetySettingsOut:
    bad = [n for n in body.allowlist if not is_e164(n)]
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Not valid E.164 numbers: {', '.join(bad)}",
        )

    async with database.as_user(user.auth_user_id) as conn:
        row = await safety_repo.upsert(
            conn,
            user.org_id,
            allowlist=body.allowlist,
            max_calls_per_run=body.max_calls_per_run,
            calls_per_window=body.calls_per_window,
            window_minutes=body.window_minutes,
            daily_budget=body.daily_budget,
        )
    return _to_out(row, user.org_id)
