"""Starting and reading runs - org-scoped, persisted.

Every run dials for real. There is no dry-run mode (CLAUDE.md, ADR-3) - the
guards that actually stand between "started a run" and "rang a real phone" are
the per-run ceiling, the allowlist, per-organisation rate limiting, that
organisation's own daily budget, and the suppression list, all enforced in
`check_dial_allowed()` and below. Every one of these can be overridden per
organisation (`org_safety_settings`) or falls back to the deployment's env-var
defaults - `resolve_safety_settings()` is the one place that merge happens.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.v1.routes.campaigns import resolve_campaign
from app.auth.dependencies import CurrentUser, RequirePermission, current_user
from app.auth.permissions import Permission
from app.core.config import config
from app.core.rate_limit import limiter
from app.database import database
from app.database.repositories import runs as runs_repo
from app.database.repositories import safety_settings as safety_settings_repo
from app.database.repositories import suppressions as suppressions_repo
from app.domain.entities import CallOutcome, Contact
from app.domain.safety import phone_hash, resolve_safety_settings
from app.services.campaign_runner import CampaignRunner

log = logging.getLogger("app.api.v1.runs")

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


class ContactIn(BaseModel):
    name: str
    phone: str
    region: str | None = None
    language: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    campaign_id: str
    contacts: list[ContactIn]


def _is_owner(request: Request) -> bool:
    """True when the caller presents the owner key, lifting all rate limits."""
    if not config.owner_key:
        return False
    presented = request.headers.get("x-callflow-owner-key", "")
    return secrets.compare_digest(presented, config.owner_key)


async def _run_and_persist(
    *,
    run_id: str,
    org_id: UUID,
    auth_user_id: str,
    campaign: Any,
    result_schema: dict[str, Any],
    contacts: list[Contact],
    suppressed_hashes: frozenset[str],
    max_calls_per_run: int | None,
    allowlist: frozenset[str] | None,
) -> None:
    runner = CampaignRunner(
        run_id=run_id,
        result_schema=result_schema,
        suppressed_hashes=suppressed_hashes,
        max_calls_per_run=max_calls_per_run,
        allowlist=allowlist,
    )

    async def on_progress(outcome: CallOutcome) -> None:
        record = outcome.model_dump(mode="json")
        record["provider_call_id"] = record.pop("run_id", None)
        async with database.as_user(auth_user_id) as conn:
            await runs_repo.append_outcome(conn, run_id=run_id, org_id=org_id, outcome=record)

    async def should_cancel() -> bool:
        async with database.as_user(auth_user_id) as conn:
            return await runs_repo.is_cancel_requested(conn, run_id)

    try:
        await runner.run(campaign, contacts, on_progress=on_progress, should_cancel=should_cancel)
        async with database.as_user(auth_user_id) as conn:
            await runs_repo.finish_run(conn, run_id, status="canceled" if runner.canceled else None)
    except Exception as exc:
        log.exception("run %s failed", run_id)
        async with database.as_user(auth_user_id) as conn:
            await runs_repo.finish_run(conn, run_id, error=f"{type(exc).__name__}: {exc}")


@router.post("", status_code=status.HTTP_200_OK)
async def start_run(
    req: RunRequest,
    request: Request,
    background: BackgroundTasks,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.RUNS_START))],
) -> dict[str, Any]:
    # A replay of an already-accepted request returns the original run and
    # does nothing else - no new dial, no rate-limit charge, no second row.
    # Checked first, and cheaply, so a retried/double-submitted request never
    # reaches anything with a side effect (CLAUDE.md non-negotiable #6).
    idempotency_key = request.headers.get("idempotency-key") or None
    if idempotency_key:
        async with database.as_user(user.auth_user_id) as conn:
            existing = await runs_repo.get_run_by_idempotency_key(
                conn, user.org_id, idempotency_key
            )
        if existing is not None:
            return {"run_id": existing["id"], "total": existing["total"]}

    async with database.as_user(user.auth_user_id) as conn:
        resolved = await resolve_campaign(conn, user.org_id, req.campaign_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Unknown campaign: {req.campaign_id}")
    campaign, result_schema = resolved

    if not req.contacts:
        raise HTTPException(status_code=400, detail="At least one contact is required.")

    try:
        contacts = [Contact(**c.model_dump()) for c in req.contacts]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not config.api_key:
        raise HTTPException(
            status_code=400, detail="No Voice API key is configured - cannot place calls."
        )

    async with database.as_user(user.auth_user_id) as conn:
        safety_row = await safety_settings_repo.get_for_org(conn, user.org_id)
    effective = resolve_safety_settings(
        allowlist=safety_row["allowlist"] if safety_row else None,
        max_calls_per_run=safety_row["max_calls_per_run"] if safety_row else None,
        calls_per_window=safety_row["calls_per_window"] if safety_row else None,
        window_minutes=safety_row["window_minutes"] if safety_row else None,
        daily_budget=safety_row["daily_budget"] if safety_row else None,
    )

    # Resolved before the rate-limit check (not after) so a suppressed
    # contact - who check_dial_allowed will skip regardless - never reserves
    # a slot from the daily budget or rate window for a call that will never
    # actually be placed.
    async with database.as_user(user.auth_user_id) as conn:
        suppressed: set[str] = set()
        for contact in contacts:
            digest = phone_hash(contact.phone)
            if await suppressions_repo.is_suppressed(conn, user.org_id, digest):
                suppressed.add(digest)

    dialable = len(contacts) - len(suppressed)
    verdict = limiter.check(
        str(user.org_id),
        calls=dialable,
        is_owner=_is_owner(request),
        rate_limit_calls=effective.calls_per_window,
        rate_limit_window_seconds=effective.window_minutes * 60,
        daily_call_budget=effective.daily_budget,
    )
    if not verdict.allowed:
        raise HTTPException(
            status_code=429,
            detail=verdict.reason,
            headers=(
                {"Retry-After": str(verdict.retry_after_seconds)}
                if verdict.retry_after_seconds
                else None
            ),
        )

    run_id = uuid.uuid4().hex[:12]
    async with database.as_user(user.auth_user_id) as conn:
        created = await runs_repo.create_run(
            conn,
            run_id=run_id,
            org_id=user.org_id,
            campaign_id=campaign.id,
            total=len(contacts),
            started_by=user.id,
            idempotency_key=idempotency_key,
        )

    if not created:
        # Lost a race to a concurrent, identically-keyed request - it already
        # created the real run. Return that one instead of starting a second.
        limiter.release(str(user.org_id), dialable)
        async with database.as_user(user.auth_user_id) as conn:
            existing = await runs_repo.get_run_by_idempotency_key(
                conn, user.org_id, idempotency_key  # type: ignore[arg-type]
            )
        assert existing is not None
        return {"run_id": existing["id"], "total": existing["total"]}

    background.add_task(
        _run_and_persist,
        run_id=run_id,
        org_id=user.org_id,
        auth_user_id=user.auth_user_id,
        campaign=campaign,
        result_schema=result_schema,
        contacts=contacts,
        suppressed_hashes=frozenset(suppressed),
        max_calls_per_run=effective.max_calls_per_run,
        allowlist=effective.allowlist,
    )
    return {"run_id": run_id, "total": len(contacts)}


@router.post("/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.RUNS_START))],
) -> dict[str, Any]:
    """Stops a run from dialling any further contacts.

    Reuses `RUNS_START`: whoever is trusted to spend the organisation's money
    starting a real run is trusted to stop one early, and there is no
    narrower existing permission for "manage a run in progress" worth adding
    just for this. Cannot interrupt a call already in conversation - there is
    no `cancel_call()` on the voice engine (VOICE_AGENT_PLATFORM.md) - so the
    background loop finishes whatever contact it is currently dialling and
    then stops before starting the next one.
    """
    async with database.as_user(user.auth_user_id) as conn:
        run = await runs_repo.get_run(conn, user.org_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        if run["status"] not in ("running", "canceling"):
            raise HTTPException(
                status_code=400,
                detail=f"This run already {run['status']} - there's nothing left to cancel.",
            )
        new_status = await runs_repo.request_cancel(conn, user.org_id, run_id)
    return {"status": new_status}


@router.get("")
async def list_runs(user: Annotated[CurrentUser, Depends(current_user)]) -> list[dict[str, Any]]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await runs_repo.list_runs(conn, user.org_id)
    return [
        {
            "id": r["id"],
            "campaign_id": r["campaign_id"],
            "total": r["total"],
            "status": r["status"],
            "started_at": r["started_at"].isoformat(),
            "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
            "error": r["error"],
            "completed": r["completed"],
        }
        for r in rows
    ]


def _compute_stats(outcomes: list[dict[str, Any]], total: int) -> dict[str, Any]:
    """Pure summary of a run's outcomes so far.

    Every rate is computed over *resolved* outcomes (disposition != in_flight)
    - an in-flight call is not progress yet, and counting it in the
    denominator diluted `needs_human_pct` while a run was still going
    (ISSUES.md #8). `in_flight` is reported on its own instead, rather than
    folded into either side of a percentage. Split out as a pure function,
    with no I/O, specifically so this is testable with plain dicts instead of
    a database (CLAUDE.md: split the decision from the I/O).
    """
    resolved = [o for o in outcomes if o["disposition"] != "in_flight"]
    escalated = sum(1 for o in resolved if o["disposition"] == "escalated")
    return {
        "completed": len(resolved),
        "total": total,
        "escalated": escalated,
        "auto_closed": sum(1 for o in resolved if o["disposition"] == "auto_closed"),
        "needs_human_pct": round(100 * escalated / len(resolved)) if resolved else 0,
        "in_flight": len(outcomes) - len(resolved),
    }


@router.get("/{run_id}")
async def get_run(
    run_id: str, user: Annotated[CurrentUser, Depends(current_user)]
) -> dict[str, Any]:
    async with database.as_user(user.auth_user_id) as conn:
        run = await runs_repo.get_run(conn, user.org_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        outcome_rows = await runs_repo.list_outcomes(conn, run_id)

    outcomes = [
        {
            "contact_name": o["contact_name"],
            "phone_masked": o["phone_masked"],
            "campaign_id": run["campaign_id"],
            "status": o["status"],
            "run_id": run_id,
            "provider_call_id": o["provider_call_id"],
            "transcript": o["transcript"],
            "summary": o["summary"],
            "sentiment": o["sentiment"],
            "sentiment_reason": o["sentiment_reason"],
            "extracted": o["extracted"],
            "disposition": o["disposition"],
            "disposition_reason": o["disposition_reason"],
            "error": o["error"],
            "duration_seconds": o["duration_seconds"],
            "created_at": o["created_at"].isoformat(),
        }
        for o in outcome_rows
    ]

    return {
        "id": run["id"],
        "campaign_id": run["campaign_id"],
        "total": run["total"],
        "status": run["status"],
        "started_at": run["started_at"].isoformat(),
        "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
        "error": run["error"],
        "outcomes": outcomes,
        "stats": _compute_stats(outcomes, run["total"]),
    }
