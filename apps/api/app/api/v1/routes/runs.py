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

import asyncio
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
from app.core.logging import CallContext
from app.core.rate_limit import limiter
from app.database import database
from app.database.repositories import credits as credits_repo
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import runs as runs_repo
from app.database.repositories import safety_settings as safety_settings_repo
from app.database.repositories import suppressions as suppressions_repo
from app.domain.entities import NEEDS_A_PERSON_DISPOSITIONS, CallOutcome, Contact
from app.domain.safety import (
    apply_run_override,
    is_e164,
    phone_hash,
    resolve_safety_settings,
)
from app.integrations.voice.engine import (
    EngineAPIError,
    EngineConnectionError,
    EngineGateway,
    EngineTimeoutError,
    classify_error,
)
from app.services.campaign_runner import CampaignRunner

log = logging.getLogger("app.api.v1.runs")

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


class ContactIn(BaseModel):
    name: str
    phone: str
    region: str | None = None
    language: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class DeveloperEventOut(BaseModel):
    """One entry from CALL-E's developer event log (`GET /v1/calls/{id}/events`) -
    every status transition with its own timestamp, plus warning/error-level
    diagnostics a 2-second status poll has no way to see at all."""

    id: str
    type: str
    created_at: str
    level: str
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class CallEventsOut(BaseModel):
    events: list[DeveloperEventOut]
    next_cursor: str | None = None


class RunRequest(BaseModel):
    campaign_id: str
    contacts: list[ContactIn]
    # Per-run overrides of this organisation's own safety settings - tighten
    # only, never looser (see `apply_run_override`'s own docstring for why).
    # Both optional; omitting either leaves that guard at the organisation's
    # configured value.
    max_calls_per_run: int | None = Field(default=None, gt=0)
    allowlist: list[str] | None = None


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
    credit_ceiling: int | None,
    credits_used_before_run: int,
) -> None:
    # Empty when either half is unconfigured - falls back to polling only,
    # today's behaviour, unchanged. See `config.webhook_secret`'s own comment
    # for why an unset secret must not send `webhook_url` at all rather than
    # sending one CALL-E would just never successfully deliver to.
    webhook_url = (
        f"{config.public_api_url}/api/v1/webhooks/calle/{config.webhook_secret}"
        if config.public_api_url and config.webhook_secret
        else None
    )
    runner = CampaignRunner(
        run_id=run_id,
        result_schema=result_schema,
        webhook_url=webhook_url,
        suppressed_hashes=suppressed_hashes,
        max_calls_per_run=max_calls_per_run,
        allowlist=allowlist,
        credit_ceiling=credit_ceiling,
        credits_used_before_run=credits_used_before_run,
    )

    async def on_progress(outcome: CallOutcome) -> None:
        record = outcome.model_dump(mode="json")
        record["provider_call_id"] = record.pop("run_id", None)
        async with database.as_user(auth_user_id) as conn:
            call_outcome_id = await runs_repo.append_outcome(
                conn, run_id=run_id, org_id=org_id, outcome=record
            )
            if outcome.disposition in NEEDS_A_PERSON_DISPOSITIONS:
                await escalations_repo.create_for_outcome(
                    conn, org_id=org_id, run_id=run_id, call_outcome_id=call_outcome_id
                )

    async def should_cancel() -> bool:
        async with database.as_user(auth_user_id) as conn:
            return await runs_repo.is_cancel_requested(conn, run_id)

    # Every log line this run produces - in this module, `CampaignRunner`, and
    # `engine.py` - carries `run_id`/`org_id` for the run's whole lifetime, so
    # one run's lines can be grepped together regardless of which contact or
    # module emitted them.
    with CallContext(run_id=run_id, org_id=str(org_id)):
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

    if req.allowlist:
        bad = [n for n in req.allowlist if not is_e164(n)]
        if bad:
            raise HTTPException(
                status_code=400, detail=f"Not valid E.164 numbers: {', '.join(bad)}"
            )

    # Per-run override, tighten-only - see apply_run_override's own docstring.
    # calls_per_window/window_minutes/daily_budget pass through unchanged, so
    # this is safe to apply before the rate-limit check below even though
    # that check only cares about those three fields.
    effective = apply_run_override(
        effective, max_calls_per_run=req.max_calls_per_run, allowlist=req.allowlist
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
        # `None` when nobody has ever set this caller's own allocation - the
        # per-teammate gate then never applies for them, only the org-wide
        # daily budget above does. Resolved once here, not once per contact,
        # the same way suppression/allowlist already are.
        credit_ceiling = await credits_repo.get_enforced_ceiling(conn, user.org_id, user.id)
        credits_used_before_run = (
            await credits_repo.used_today(conn, user.org_id, user.id)
            if credit_ceiling is not None
            else 0
        )

        created = await runs_repo.create_run(
            conn,
            run_id=run_id,
            org_id=user.org_id,
            campaign_id=campaign.id,
            total=len(contacts),
            started_by=user.id,
            idempotency_key=idempotency_key,
            # A permanent snapshot of the exact guards this run is governed
            # by - the same `effective` object used for the dial gate and
            # the rate-limit check above, not a fresh read of
            # org_safety_settings, which can change after the fact and
            # would otherwise silently rewrite this run's own history.
            max_calls_per_run=effective.max_calls_per_run,
            allowlist=effective.allowlist,
            calls_per_window=effective.calls_per_window,
            window_minutes=effective.window_minutes,
            daily_budget=effective.daily_budget,
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
        credit_ceiling=credit_ceiling,
        credits_used_before_run=credits_used_before_run,
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
            "started_by": str(r["started_by"]) if r["started_by"] else None,
            "started_by_name": r["started_by_name"],
            "started_by_avatar_url": r["started_by_avatar_url"],
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


class TeamMemberSummary(BaseModel):
    user_id: str | None
    name: str | None
    avatar_url: str | None
    total_runs: int
    total_calls: int


@router.get(
    "/team-summary",
    response_model=list[TeamMemberSummary],
    dependencies=[Depends(RequirePermission(Permission.RUNS_READ_TEAM))],
)
async def team_summary(user: Annotated[CurrentUser, Depends(current_user)]) -> list[TeamMemberSummary]:
    """Call volume per teammate, for the admin/owner/viewer dashboard chart."""
    async with database.as_user(user.auth_user_id) as conn:
        rows = await runs_repo.summarize_by_member(conn, user.org_id)
    return [
        TeamMemberSummary(
            user_id=str(r["started_by"]) if r["started_by"] else None,
            name=r["started_by_name"],
            avatar_url=r["started_by_avatar_url"],
            total_runs=r["total_runs"],
            total_calls=r["total_calls"],
        )
        for r in rows
    ]


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
            "task_completed": o["task_completed"],
            "completion_confidence_score": o["completion_confidence_score"],
            "completion_confidence_label": o["completion_confidence_label"],
            "evidence": o["evidence"],
            "attempts": o["attempts"],
        }
        for o in outcome_rows
    ]

    started_by = run["started_by"]
    return {
        "id": run["id"],
        "campaign_id": run["campaign_id"],
        "total": run["total"],
        "status": run["status"],
        "started_at": run["started_at"].isoformat(),
        "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
        "error": run["error"],
        "started_by": str(started_by) if started_by else None,
        "started_by_name": run["started_by_name"],
        "started_by_avatar_url": run["started_by_avatar_url"],
        "outcomes": outcomes,
        "stats": _compute_stats(outcomes, run["total"]),
        # Permanent snapshot of this run's actual guards (ISSUES.md it-16) -
        # null on any run created before this field existed, never
        # backfilled from today's org_safety_settings, which would fabricate
        # a history this run never actually had.
        "safety_snapshot": {
            "max_calls_per_run": run["max_calls_per_run"],
            "allowlist": run["allowlist"] or [],
            "calls_per_window": run["calls_per_window"],
            "window_minutes": run["window_minutes"],
            "daily_budget": run["daily_budget"],
        }
        if run["max_calls_per_run"] is not None
        else None,
    }


@router.get("/{run_id}/calls/{provider_call_id}/events", response_model=CallEventsOut)
async def get_call_events(
    run_id: str,
    provider_call_id: str,
    user: Annotated[CurrentUser, Depends(current_user)],
    cursor: str | None = None,
) -> CallEventsOut:
    """CALL-E's developer event log for one call - on demand, not fetched
    automatically for every call. Most calls never need this level of detail,
    and fetching it unconditionally would double the request volume against
    CALL-E for data most calls don't need inspected. Richer than the coarse
    status polling `CampaignRunner` already surfaces: every transition gets
    its own timestamp here (a fast run of states between two 2-second polls
    can otherwise never be seen at all), plus warning/error-level
    diagnostics polling has no way to see regardless of interval.
    """
    async with database.as_user(user.auth_user_id) as conn:
        run = await runs_repo.get_run(conn, user.org_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        outcome_rows = await runs_repo.list_outcomes(conn, run_id)

    # Confirms this call id actually belongs to a contact in *this* run,
    # itself scoped to the caller's own org by the lookups above - a caller
    # cannot probe an arbitrary CALL-E call id through their own session.
    if not any(o["provider_call_id"] == provider_call_id for o in outcome_rows):
        raise HTTPException(status_code=404, detail="Call not found in this run")

    if not config.api_key:
        raise HTTPException(
            status_code=400, detail="No Voice API key is configured - cannot reach the voice engine."
        )

    gateway = EngineGateway()
    try:
        raw = await asyncio.to_thread(gateway.list_events, provider_call_id, cursor=cursor)
    except (EngineAPIError, EngineTimeoutError, EngineConnectionError) as exc:
        failure = classify_error(exc)
        raise HTTPException(
            status_code=502, detail=f"Could not reach the voice engine: {failure.value}"
        ) from exc
    finally:
        gateway.close()

    raw_events = raw.get("data") if isinstance(raw, dict) else None
    events = [
        DeveloperEventOut(
            id=str(event.get("id", "")),
            type=str(event.get("type", "")),
            created_at=str(event.get("created_at", "")),
            level=str(event.get("level", "")),
            status=str(event.get("status", "")),
            message=str(event.get("message", "")),
            details=event.get("details") or {},
        )
        for event in raw_events
        if isinstance(event, dict)
    ] if isinstance(raw_events, list) else []
    next_cursor = raw.get("next_cursor") if isinstance(raw, dict) else None
    return CallEventsOut(events=events, next_cursor=next_cursor)
