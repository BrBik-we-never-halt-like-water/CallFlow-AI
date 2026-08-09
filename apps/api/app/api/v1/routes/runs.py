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
from app.database.repositories import runs as runs_repo
from app.database.repositories import safety_settings as safety_settings_repo
from app.database.repositories import suppressions as suppressions_repo
from app.domain.entities import CallOutcome, Contact
from app.domain.safety import phone_hash, resolve_safety_settings
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
        result_schema=result_schema,
        webhook_url=webhook_url,
        suppressed_hashes=suppressed_hashes,
        max_calls_per_run=max_calls_per_run,
        allowlist=allowlist,
        run_id=run_id,
    )

    async def on_progress(outcome: CallOutcome) -> None:
        record = outcome.model_dump(mode="json")
        record["provider_call_id"] = record.pop("run_id", None)
        async with database.as_user(auth_user_id) as conn:
            await runs_repo.append_outcome(conn, run_id=run_id, org_id=org_id, outcome=record)

    # Every log line this run produces - in this module, `CampaignRunner`, and
    # `engine.py` - carries `run_id`/`org_id` for the run's whole lifetime, so
    # one run's lines can be grepped together regardless of which contact or
    # module emitted them.
    with CallContext(run_id=run_id, org_id=str(org_id)):
        try:
            await runner.run(campaign, contacts, on_progress=on_progress)
            async with database.as_user(auth_user_id) as conn:
                await runs_repo.finish_run(conn, run_id)
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

    verdict = limiter.check(
        str(user.org_id),
        calls=len(contacts),
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
        suppressed: set[str] = set()
        for contact in contacts:
            digest = phone_hash(contact.phone)
            if await suppressions_repo.is_suppressed(conn, user.org_id, digest):
                suppressed.add(digest)

        await runs_repo.create_run(
            conn,
            run_id=run_id,
            org_id=user.org_id,
            campaign_id=campaign.id,
            total=len(contacts),
            started_by=user.id,
        )

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
    resolved = [o for o in outcomes if o["disposition"] != "in_flight"]
    escalated = sum(1 for o in resolved if o["disposition"] == "escalated")

    return {
        "id": run["id"],
        "campaign_id": run["campaign_id"],
        "total": run["total"],
        "status": run["status"],
        "started_at": run["started_at"].isoformat(),
        "finished_at": run["finished_at"].isoformat() if run["finished_at"] else None,
        "error": run["error"],
        "outcomes": outcomes,
        "stats": {
            "completed": len(resolved),
            "total": run["total"],
            "escalated": escalated,
            "auto_closed": sum(1 for o in outcomes if o["disposition"] == "auto_closed"),
            "needs_human_pct": round(100 * escalated / len(outcomes)) if outcomes else 0,
        },
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
