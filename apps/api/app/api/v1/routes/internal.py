"""The voice runtime's callback: how a finished call gets back into CallFlow.

Origination returns when a call is *answered*; the conversation then happens in
the LiveKit room, in a different process. This is where that process reports
what happened - the transcript, the structured result, and the terminal status.
Without it every outcome would sit at IN_FLIGHT forever.

**Not a public API.** The caller is CallFlow's own worker, not a person with a
session, so this cannot use `database.as_user()` the way every other route does,
and `privileged.acquire()` must never appear in a request handler (CLAUDE.md).
It follows the exact precedent the deleted CALL-E receiver and
`invitations.py`'s public preview both set: `database.anonymous()` calling one
narrow SECURITY DEFINER function to resolve identity, then the ordinary,
already-RLS-correct `as_user()` path - as the run's own starter - for the write.

Trust is the shared secret in `X-CallFlow-Internal-Key`, compared in constant
time. That is the whole boundary: anyone holding it can write a transcript
against any run, so it belongs in the deployment's environment and nowhere else.
"""

from __future__ import annotations

import logging
import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import config
from app.core.logging import CallContext
from app.database import database
from app.database.repositories import escalations as escalations_repo
from app.database.repositories import runs as runs_repo
from app.database.repositories import voice_agents as voice_agents_repo
from app.domain.collection import handoff_questions, missing_required
from app.domain.entities import (
    NEEDS_A_PERSON_DISPOSITIONS,
    TERMINAL_STATUSES,
    CallOutcome,
    CollectField,
)
from app.domain.triage import triage

log = logging.getLogger("app.api.v1.internal")

router = APIRouter(prefix="/internal/v1", tags=["internal"])

# When an in-flight row is old enough that its worker is certainly gone. The
# carrier enforces `max_call_duration_seconds` on the call itself, so anything
# past that plus a margin for the callback's own retries never reported and
# never will.
_STALE_AFTER_SECONDS = int(config.poll_timeout_seconds) * 2


class CallCompletion(BaseModel):
    """What the worker knows when a call ends.

    `contact_name` and `phone_masked` are echoed back from the participant
    metadata the dial sent, because `call_outcomes` is keyed on
    (run_id, contact_name, phone_masked) - they address the in-flight row this
    completion resolves rather than creating a second one beside it.

    Deliberately *not* CALL-E's payload shape. The old receiver had to dig a
    transcript out of `recipients[].attempts[]` because that was the vendor's
    shape; the worker is ours, so it sends what the domain actually holds.
    """

    contact_name: str
    phone_masked: str
    status: str = Field(description="COMPLETED, FAILED, NO_ANSWER, BUSY, …")
    provider_call_id: str | None = None
    transcript: str | None = None
    summary: str | None = None
    extracted: dict[str, Any] = Field(default_factory=dict)
    #: The org's own business fields, from the agent's collect_fields.
    #: Kept apart from `extracted` so a field an org happened to name
    #: `sentiment` cannot rewrite triage's own input.
    collected: dict[str, Any] = Field(default_factory=dict)
    duration_seconds: int | None = None
    error: str | None = None


def _collect_fields(raw: object) -> list[CollectField]:
    """An agent's `collect_fields` as typed values.

    Tolerant of a non-list: rows written before the column existed read back as
    anything, and a completion report must never be lost because the agent that
    produced it predates a feature.
    """
    if not isinstance(raw, list):
        return []
    return [
        CollectField(**item)
        for item in raw
        if isinstance(item, dict) and item.get("key")
    ]


def _require_internal_key(
    x_callflow_internal_key: Annotated[str | None, Header()] = None,
) -> None:
    """Fails closed on an unset secret, so a misconfigured deployment refuses
    writes rather than accepting anonymous ones.

    A **dependency**, not a call inside the handler, and the difference is the
    point: FastAPI resolves dependencies before it validates the request body,
    so an unauthenticated caller gets the same bare 404 whatever it sends.
    Called from inside the handler, every malformed request answered 422 naming
    the field that was wrong - handing anyone who could reach the port the exact
    schema of an internal endpoint, one field at a time (`ISSUES.md` #154).
    """
    if not config.internal_api_secret:
        log.error("internal callback rejected: CALLFLOW_INTERNAL_API_SECRET is not set")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    presented = x_callflow_internal_key
    if not presented or not secrets.compare_digest(presented, config.internal_api_secret):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post(
    "/runs/{run_id}/complete",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_internal_key)],
)
async def complete_call(
    run_id: str,
    payload: CallCompletion,
) -> dict[str, bool]:
    """Record one finished call and, if it was the last, close the run.

    Idempotent (CLAUDE.md non-negotiable #6): the write is
    `append_outcome`'s upsert on (run_id, contact_name, phone_masked), so a
    worker that retries after a dropped response updates the same row rather
    than adding a duplicate. Closing the run is idempotent for its own reason -
    see `finish_if_all_settled`.

    A 404 for both a bad key and an unknown run: a caller without the secret
    learns nothing about which run ids exist.
    """
    # Checked here rather than inferred from the triaged disposition: `triage()`
    # assigns a bucket to any status it is given, so a worker reporting
    # "RINGING" would be recorded as a settled outcome and the row would never
    # resolve. The declared terminal set is the authority (CLAUDE.md #7).
    status_value = payload.status.upper()
    if status_value not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"'{payload.status}' is not a terminal call status. "
                f"Expected one of: {', '.join(sorted(TERMINAL_STATUSES))}."
            ),
        )

    async with database.anonymous() as conn:
        owner = await runs_repo.lookup_owner_for_webhook(conn, run_id)
    if owner is None:
        log.warning("internal completion references an unresolvable run %s", run_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown run")

    with CallContext(run_id=run_id, org_id=str(owner["org_id"])):
        async with database.as_user(str(owner["auth_user_id"])) as conn:
            agent_id = owner["voice_agent_id"]
            agent_row = (
                await voice_agents_repo.get_org_agent(conn, owner["org_id"], agent_id)
                if agent_id
                else None
            )
            if agent_row is None:
                # `runs.voice_agent_id` is ON DELETE RESTRICT, so this should not
                # be reachable - but a run started before ADR-8 has no agent at
                # all, and the conversation still happened. Keep the transcript
                # rather than 500 on a real call; a missing agent just means no
                # fields to check completeness against.
                log.warning("run %s has no resolvable agent", run_id)
                fields: list[CollectField] = []
            else:
                fields = _collect_fields(agent_row["collect_fields"])

            # Which required answers the call ended without. Computed here, in
            # the one place that has both the agent's contract and the call's
            # result - `triage()` stays pure and is handed the answer rather than
            # learning what a schema is (ADR-5).
            missing = missing_required(fields, payload.collected)

            outcome = triage(
                CallOutcome(
                    contact_name=payload.contact_name,
                    phone_masked=payload.phone_masked,
                    voice_agent_id=str(agent_id) if agent_id else None,
                    status=status_value,
                    run_id=payload.provider_call_id,
                    transcript=payload.transcript,
                    summary=payload.summary or payload.extracted.get("summary"),
                    extracted=payload.extracted,
                    collected=payload.collected,
                    missing_required_fields=missing,
                    handoff_questions=handoff_questions(
                        fields,
                        missing=missing,
                        wants_human=bool(payload.extracted.get("wants_human_callback")),
                        do_not_call=bool(payload.extracted.get("do_not_call")),
                    ),
                    duration_seconds=payload.duration_seconds,
                    error=payload.error,
                ),
                # A campaign used to carry this per-campaign. No agent-level
                # equivalent exists yet, so it takes the safer default: a
                # negative call is worth one retry rather than being auto-closed.
                escalate_on_negative=True,
            )

            record = outcome.model_dump(mode="json")
            record["provider_call_id"] = record.pop("run_id", None)
            call_outcome_id = await runs_repo.append_outcome(
                conn, run_id=run_id, org_id=owner["org_id"], outcome=record
            )
            # The only place a real conversation can raise one. `run_one()`
            # returns while the call is still in flight, so the disposition it
            # reports is never a needs-a-person one - the escalation check that
            # lives beside the run's own progress write can only ever fire for
            # a contact that failed to dial. Without this, triage would run,
            # decide someone has to call back, and nothing would ever act on it.
            if outcome.disposition in NEEDS_A_PERSON_DISPOSITIONS:
                await escalations_repo.create_for_outcome(
                    conn,
                    org_id=owner["org_id"],
                    run_id=run_id,
                    call_outcome_id=call_outcome_id,
                )
            closed = await runs_repo.finish_if_all_settled(
                conn, run_id, stale_after_seconds=_STALE_AFTER_SECONDS
            )

    if closed:
        log.info("run %s closed - every contact has settled", run_id)
    return {"ok": True, "run_closed": closed}
