"""Campaign orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> render goal -> [dry run stops here] -> CALL-E create
                -> poll to terminal -> extract typed result -> triage

Dry-run mode renders and validates everything without spending a credit or
ringing a real phone, which is also the dry-run path the
awesome-phone-call-agents contribution rules require.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Iterable

from .calle_client import CalleGateway
from .config import config
from .models import Campaign, CallOutcome, Contact, Disposition
from .safety import check_dial_allowed, mask
from .triage import triage

log = logging.getLogger("callflow.orchestrator")

JsonObject = dict[str, Any]
ProgressHook = Callable[[CallOutcome], None]


def render_goal(campaign: Campaign, contact: Contact) -> str:
    """Fill the campaign template with contact data.

    Uses format_map with a defaulting dict so a missing context key degrades to
    an empty string instead of crashing a whole campaign run.
    """

    class _Safe(dict):
        def __missing__(self, key: str) -> str:
            return ""

    fields = _Safe(name=contact.name, phone=contact.phone, **contact.context)
    return campaign.goal_template.format_map(fields)


def _extract_result(call: JsonObject) -> JsonObject:
    """Pull CALL-E's structured extraction out of the call payload.

    The API has returned this under a few different keys across versions, so we
    check the known candidates rather than assuming one shape.
    """
    for key in ("result", "structured_result", "results", "output", "data"):
        value = call.get(key)
        if isinstance(value, dict) and value:
            # Some shapes nest the payload one level deeper.
            for inner in ("result", "structured_result", "data"):
                nested = value.get(inner)
                if isinstance(nested, dict) and nested:
                    return nested
            return value

    # Batch shape: recipients[0].result
    recipients = call.get("recipients")
    if isinstance(recipients, list) and recipients:
        first = recipients[0]
        if isinstance(first, dict):
            for key in ("result", "structured_result", "data"):
                value = first.get(key)
                if isinstance(value, dict) and value:
                    return value
    return {}


def _extract_transcript(call: JsonObject) -> str | None:
    for key in ("transcript", "transcript_text", "asr_transcript"):
        value = call.get(key)
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            parts = [
                f"{turn.get('speaker', turn.get('role', '?'))}: {turn.get('text', turn.get('content', ''))}"
                for turn in value
                if isinstance(turn, dict)
            ]
            if parts:
                return "\n".join(parts)
    return None


class CampaignRunner:
    def __init__(
        self,
        gateway: CalleGateway | None = None,
        *,
        dry_run: bool | None = None,
        result_schema: JsonObject | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.dry_run = config.dry_run if dry_run is None else dry_run
        self.result_schema = result_schema
        self.webhook_url = webhook_url
        # In dry-run we never need a live client, so don't demand an API key.
        self._gateway = gateway
        self._calls_made = 0

    @property
    def gateway(self) -> CalleGateway:
        if self._gateway is None:
            self._gateway = CalleGateway()
        return self._gateway

    def run(
        self,
        campaign: Campaign,
        contacts: Iterable[Contact],
        *,
        on_progress: ProgressHook | None = None,
    ) -> list[CallOutcome]:
        outcomes: list[CallOutcome] = []
        for contact in contacts:
            outcome = self.run_one(campaign, contact)
            outcomes.append(outcome)
            if on_progress:
                on_progress(outcome)
        return outcomes

    def run_one(self, campaign: Campaign, contact: Contact) -> CallOutcome:
        base = CallOutcome(
            contact_name=contact.name,
            phone_masked=mask(contact.phone),
            campaign_id=campaign.id,
            dry_run=self.dry_run,
        )

        goal = render_goal(campaign, contact)

        # --- Safety gate: fails closed, runs before anything can dial. ------
        gate = check_dial_allowed(contact.phone, self._calls_made)
        if not gate.allowed:
            return base.model_copy(
                update={
                    "status": "BLOCKED",
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": gate.reason,
                }
            )

        if self.dry_run:
            return base.model_copy(
                update={
                    "status": "DRY_RUN",
                    "disposition": Disposition.SKIPPED,
                    "disposition_reason": "Dry run — validated goal and safety gate, no call placed.",
                    "summary": goal,
                }
            )

        metadata = {
            "call-e/customerMetadata": {
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "contact_name": contact.name,
                **contact.context,
            }
        }

        try:
            created = self.gateway.start_call(
                task=goal,
                phone=contact.phone,
                result_schema=self.result_schema,
                metadata=metadata,
                webhook_url=self.webhook_url,
                idempotency_key=f"{campaign.id}-{contact.phone}-{uuid.uuid4().hex[:8]}",
                region=contact.region or campaign.region,
                language=contact.language or campaign.language,
            )
            self._calls_made += 1

            call_id = str(created.get("id", ""))
            final = self.gateway.wait_for_result(call_id, interval_seconds=5.0)

        except Exception as exc:  # network, auth, timeout, API error
            log.exception("call failed for %s", mask(contact.phone))
            return base.model_copy(
                update={
                    "status": "FAILED",
                    "error": f"{type(exc).__name__}: {exc}",
                    "disposition": Disposition.UNREACHABLE,
                    "disposition_reason": "Call could not be completed due to an error.",
                }
            )

        extracted = _extract_result(final)
        resolved = base.model_copy(
            update={
                "status": str(final.get("status", "unknown")).upper(),
                "run_id": call_id,
                "transcript": _extract_transcript(final),
                "summary": extracted.get("summary") or final.get("summary"),
                "extracted": extracted,
                "duration_seconds": final.get("duration_seconds"),
            }
        )
        return triage(resolved, escalate_on_negative=campaign.escalate_on_negative)
