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

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.v1.routes.campaigns import resolve_campaign
from app.core.config import config
from app.core.logging import CallContext
from app.database import database
from app.database.repositories import runs as runs_repo
from app.domain.entities import TERMINAL_STATUSES, CallOutcome
from app.domain.triage import triage

log = logging.getLogger("app.api.v1.internal")

router = APIRouter(prefix="/internal/v1", tags=["internal"])


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
    duration_seconds: int | None = None
    error: str | None = None


def _require_internal_key(presented: str | None) -> None:
    """Fails closed on an unset secret, so a misconfigured deployment refuses
    writes rather than accepting anonymous ones."""
    if not config.internal_api_secret:
        log.error("internal callback rejected: CALLFLOW_INTERNAL_API_SECRET is not set")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not presented or not secrets.compare_digest(presented, config.internal_api_secret):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.post("/runs/{run_id}/complete", status_code=status.HTTP_200_OK)
async def complete_call(
    run_id: str,
    payload: CallCompletion,
    x_callflow_internal_key: Annotated[str | None, Header()] = None,
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
    _require_internal_key(x_callflow_internal_key)

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
            resolved = await resolve_campaign(conn, owner["org_id"], owner["campaign_id"])
            if resolved is None:
                # The campaign was deleted mid-run. The call still happened, so
                # the transcript is still worth keeping - triage just cannot ask
                # this campaign whether negative sentiment should escalate, so
                # it takes the safer default.
                log.warning("run %s references a campaign that no longer resolves", run_id)
                escalate_on_negative = True
            else:
                escalate_on_negative = resolved[0].escalate_on_negative

            outcome = triage(
                CallOutcome(
                    contact_name=payload.contact_name,
                    phone_masked=payload.phone_masked,
                    campaign_id=owner["campaign_id"],
                    status=status_value,
                    run_id=payload.provider_call_id,
                    transcript=payload.transcript,
                    summary=payload.summary or payload.extracted.get("summary"),
                    extracted=payload.extracted,
                    duration_seconds=payload.duration_seconds,
                    error=payload.error,
                ),
                escalate_on_negative=escalate_on_negative,
            )

            record = outcome.model_dump(mode="json")
            record["provider_call_id"] = record.pop("run_id", None)
            await runs_repo.append_outcome(
                conn, run_id=run_id, org_id=owner["org_id"], outcome=record
            )
            closed = await runs_repo.finish_if_all_settled(conn, run_id)

    if closed:
        log.info("run %s closed - every contact has settled", run_id)
    return {"ok": True, "run_closed": closed}
