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
from app.core.logging import CallContext
from app.core.rate_limit import limiter
from app.database import database
from app.database.repositories import credits as credits_repo
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import runs as runs_repo
from app.database.repositories import safety_settings as safety_settings_repo
from app.database.repositories import suppressions as suppressions_repo
from app.domain.entities import NEEDS_A_PERSON_DISPOSITIONS, CallOutcome, Contact
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
    credit_ceiling: int | None,
    credits_used_before_run: int,
) -> None:
    runner = CampaignRunner(
        result_schema=result_schema,
        suppressed_hashes=suppressed_hashes,
        max_calls_per_run=max_calls_per_run,
        allowlist=allowlist,
        credit_ceiling=credit_ceiling,
        credits_used_before_run=credits_used_before_run,
        run_id=run_id,
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

    # Every log line this run produces - in this module and `CampaignRunner` -
    # carries `run_id`/`org_id` for the run's whole lifetime, so one run's
    # lines can be grepped together regardless of which contact or module
    # emitted them.
    with CallContext(run_id=run_id, org_id=str(org_id)):
        try:
            await runner.run(campaign, contacts, on_progress=on_progress)
            # Deliberately not `finish_run()`. Origination returns when a call
            # is answered, not when it ends, so at this point conversations are
            # still running - closing the run here would show it completed
            # while its own rows still read "In conversation…". Whichever
            # worker callback settles the last contact closes it instead
            # (`finish_if_all_settled`). This still handles the case where every
            # contact was blocked or failed to dial: those settle immediately,
            # so the check below closes the run right away.
            async with database.as_user(auth_user_id) as conn:
                await runs_repo.finish_if_all_settled(conn, run_id)
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
        credit_ceiling=credit_ceiling,
        credits_used_before_run=credits_used_before_run,
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
            "started_by": str(r["started_by"]) if r["started_by"] else None,
            "started_by_name": r["started_by_name"],
            "started_by_avatar_url": r["started_by_avatar_url"],
        }
        for r in rows
    ]


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
    resolved = [o for o in outcomes if o["disposition"] != "in_flight"]
    escalated = sum(1 for o in resolved if o["disposition"] == "escalated")

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
        "stats": {
            "completed": len(resolved),
            "total": run["total"],
            "escalated": escalated,
            "auto_closed": sum(1 for o in outcomes if o["disposition"] == "auto_closed"),
            "needs_human_pct": round(100 * escalated / len(outcomes)) if outcomes else 0,
        },
    }


