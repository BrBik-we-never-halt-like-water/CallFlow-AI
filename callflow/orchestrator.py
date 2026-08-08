"""Campaign orchestration: contacts in, typed outcomes out.

Flow per contact:
    safety gate -> render goal -> [dry run stops here] -> engine create
                -> poll to terminal -> extract typed result -> triage

Dry-run mode renders and validates everything without spending a credit or
ringing a real phone.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Iterable
from typing import Any

from .config import config
from .engine_client import TERMINAL, EngineGateway
from .models import CallOutcome, Campaign, Contact, Disposition
from .safety import check_dial_allowed, mask
from .samples import sample_outcome
from .triage import triage

log = logging.getLogger("callflow.orchestrator")

JsonObject = dict[str, Any]
ProgressHook = Callable[[CallOutcome], None]


def _live_label(status: str) -> str:
    """Human-readable text for an in-flight call status."""
    return {
        "queued": "Queued with the voice engine…",
        "scheduled": "Scheduled…",
        "dialing": "Dialing…",
        "ringing": "Ringing…",
        "in_progress": "In conversation…",
        "connected": "In conversation…",
    }.get(status, f"{status.replace('_', ' ').capitalize()}…")


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
    """Pull the engine's structured extraction out of the call payload.

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
        gateway: EngineGateway | None = None,
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
        # Walks the sample profiles in order so a preview shows varied
        # outcomes rather than the same row repeated.
        self._preview_index = 0

    @property
    def gateway(self) -> EngineGateway:
        if self._gateway is None:
            self._gateway = EngineGateway()
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
            # `on_progress` doubles as the live-status sink so an in-flight
            # call is visible while it happens, not only once it ends.
            outcome = self.run_one(campaign, contact, on_status=on_progress)
            outcomes.append(outcome)
            if on_progress:
                on_progress(outcome)
        return outcomes

    def _poll_until_done(
        self,
        call_id: str,
        *,
        on_status: ProgressHook | None,
        base: CallOutcome,
    ) -> JsonObject:
        """Poll a call to completion, reporting each status change.

        The SDK's own `wait_for_result` blocks silently. Polling here lets the
        dashboard show `queued → ringing → in_progress` while the call happens,
        instead of a frozen spinner until it ends.
        """
        deadline = time.monotonic() + config.poll_timeout_seconds
        last_status = ""

        while time.monotonic() < deadline:
            call = self.gateway.get_call(call_id)
            status = str(call.get("status", "")).lower()

            if status in TERMINAL:
                return call

            if status and status != last_status and on_status is not None:
                last_status = status
                on_status(
                    base.model_copy(
                        update={
                            "status": status.upper(),
                            "run_id": call_id,
                            "dry_run": False,
                            "disposition": Disposition.IN_FLIGHT,
                            "disposition_reason": _live_label(status),
                        }
                    )
                )

            time.sleep(2.0)

        raise TimeoutError(f"Call {call_id} did not finish within the timeout.")

    def run_one(
        self,
        campaign: Campaign,
        contact: Contact,
        *,
        on_status: ProgressHook | None = None,
    ) -> CallOutcome:
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
            # Run a sample result through the real triage logic. Nothing is
            # dialed, but the preview shows the full pipeline   extraction,
            # sentiment, and the disposition each outcome would get. The
            # `is_sample` flag makes the UI label it as preview data.
            extracted = sample_outcome(campaign, contact, self._preview_index)
            self._preview_index += 1
            preview = base.model_copy(
                update={
                    "status": "PREVIEW",
                    "extracted": extracted,
                    "summary": extracted.get("summary"),
                    "transcript": goal,
                }
            )
            return triage(preview, escalate_on_negative=campaign.escalate_on_negative)

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

            # Surface the row as soon as the call is placed. Otherwise the
            # dashboard shows nothing for the whole call   which reads as a
            # hang when a conversation runs for minutes.
            if on_status is not None:
                on_status(
                    base.model_copy(
                        update={
                            "status": str(created.get("status", "queued")).upper(),
                            "run_id": call_id,
                            "dry_run": False,
                            "disposition": Disposition.IN_FLIGHT,
                            "disposition_reason": "Dialing…",
                        }
                    )
                )

            final = self._poll_until_done(call_id, on_status=on_status, base=base)

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
