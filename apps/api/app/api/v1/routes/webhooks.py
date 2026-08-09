"""CALL-E's terminal-event webhook - the fast path; polling
(`CampaignRunner._poll_until_done`) stays the backstop for anything this
receiver misses (a dropped delivery, a deployment with no webhook configured).

No signed-in user is behind a request here - CALL-E's server is the caller,
not a person with a session - so this cannot use `database.as_user()` the way
every other route does, and `privileged.acquire()` must never appear in a
request handler (CLAUDE.md). Follows the exact precedent
`api/v1/routes/invitations.py`'s public preview already set:
`database.anonymous()` calling one narrow SECURITY DEFINER function
(`lookup_run_owner_for_webhook`, migration `202608091200`) to resolve identity,
then handing off to the ordinary, already-RLS-correct `database.as_user()`
path - using the run's own starter - for the actual write.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.api.v1.routes.campaigns import resolve_campaign
from app.core.config import config
from app.database import database
from app.database.repositories import runs as runs_repo
from app.domain.outcome_extraction import (
    _resolve_outcome,
    base_outcome_from_webhook_payload,
)

log = logging.getLogger("app.api.v1.webhooks")

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class CalleWebhookPayload(BaseModel):
    event: str
    data: dict[str, Any]


@router.post("/calle/{secret}", status_code=status.HTTP_200_OK)
async def calle_webhook(
    secret: str, payload: CalleWebhookPayload, request: Request
) -> dict[str, bool]:
    """CALL-E treats any 2xx as delivered and ignores the response body - the
    `{"ok": ...}` returned below is for readability, not for CALL-E's benefit.

    Unsigned by CALL-E (its SDK's own docs: the HMAC `verify`/`unwrap` helpers
    are deprecated, "must not be used to parse current deliveries") - trust
    comes entirely from `secret` matching the value only this deployment and
    CALL-E know, compared in constant time. A wrong secret gets 404, not
    401/403, so a prober learns nothing about whether the path itself means
    anything.

    Every failure mode past the secret check acks with 200 rather than
    raising: a webhook CALL-E cannot attribute to a known run isn't evidence
    of a broken request on CALL-E's side, and polling already exists as the
    backstop for exactly this call's own eventual resolution - there is
    nothing a non-2xx response here would fix that logging it and moving on
    doesn't already handle just as well, and a 4xx/5xx would make CALL-E
    retry a delivery this deployment can never make sense of regardless.
    """
    if not config.webhook_secret or not secrets.compare_digest(secret, config.webhook_secret):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    event_id = request.headers.get("CALL-E-Event-Id", "unknown")
    call = payload.data
    metadata = call.get("metadata")
    run_id = metadata.get("run_id") if isinstance(metadata, dict) else None
    if not run_id:
        log.warning("calle webhook %s has no run_id in metadata - ignoring", event_id)
        return {"ok": True}

    async with database.anonymous() as conn:
        owner = await runs_repo.lookup_owner_for_webhook(conn, run_id)
    if owner is None:
        log.warning("calle webhook %s references an unresolvable run %s", event_id, run_id)
        return {"ok": True}

    base = base_outcome_from_webhook_payload(call)
    if base is None:
        log.warning(
            "calle webhook %s payload is missing what a CampaignRunner-placed call always has",
            event_id,
        )
        return {"ok": True}

    async with database.as_user(str(owner["auth_user_id"])) as conn:
        resolved = await resolve_campaign(conn, owner["org_id"], owner["campaign_id"])
        if resolved is None:
            log.warning(
                "calle webhook %s references a campaign that no longer resolves", event_id
            )
            return {"ok": True}
        campaign, _result_schema = resolved

        outcome = _resolve_outcome(base, call, escalate_on_negative=campaign.escalate_on_negative)
        record = outcome.model_dump(mode="json")
        record["provider_call_id"] = record.pop("run_id", None)
        await runs_repo.append_outcome(
            conn, run_id=run_id, org_id=owner["org_id"], outcome=record
        )

    return {"ok": True}
