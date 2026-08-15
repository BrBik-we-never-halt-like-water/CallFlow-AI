"""Thin wrapper over the voice engine SDK.

This module is the only place in the codebase that touches the upstream
vendor SDK. Everything above it speaks in CallFlow terms - `EngineGateway`,
`EngineAPIError` - so no vendor name reaches the API surface or the UI.

Contract verified against the pinned SDK version:

    POST /v1/calls   task, recipients[], result_schema, metadata,
                     webhook_url, Idempotency-Key
    GET  /v1/calls/{id}          -> status in {completed, failed, canceled}
    GET  /v1/calls/{id}/events   -> event stream for live progress

The engine performs structured extraction natively via `result_schema`, so we
do not parse transcripts ourselves.
"""

from __future__ import annotations

import logging
from typing import Any, Self

from calle import CalleClient as _VendorClient
from calle.errors import CalleAPIError as EngineAPIError
from calle.errors import CalleConnectionError as EngineConnectionError
from calle.errors import CalleTimeoutError as EngineTimeoutError

from app.core.config import config, require_api_key
from app.domain.entities import DialFailure
from app.domain.safety import mask
from app.integrations.voice.protocol import NotImplementedForProvider, VoiceCapability

log = logging.getLogger("callflow.engine")

JsonObject = dict[str, Any]

# Terminal statuses returned by GET /v1/calls/{id}.
TERMINAL = {"completed", "failed", "canceled"}

# The engine's own error codes (its full documented taxonomy - see CALLE.md §4),
# mapped onto CallFlow's internal one. Anything not listed here - including any
# new code the engine adds later - falls through to INTERNAL rather than raising
# a KeyError, per CLAUDE.md's fail-closed rule: an unmapped code should never be
# treated as if it were a known, safe-to-retry failure.
#
# Five of the engine's 24 documented codes are Goals-only (`goal_not_published`,
# `goal_not_executable`, `goal_not_ready`, `schema_override_not_allowed`,
# `variables_invalid`) and deliberately absent - the Goals API isn't integrated,
# so they can never actually be raised against this codebase. Every other code
# is mapped explicitly below, even where the result is the same INTERNAL
# fallback an unmapped code would already get, so a future reader can see this
# code was considered rather than wondering if it was missed.
_ERROR_CODE_MAP: dict[str, DialFailure] = {
    "invalid_phone": DialFailure.INVALID_NUMBER,
    "invalid_recipient": DialFailure.INVALID_NUMBER,
    "no_recipients": DialFailure.INVALID_NUMBER,
    "unsupported_region": DialFailure.INVALID_NUMBER,
    "unsupported_language": DialFailure.INVALID_NUMBER,
    "rate_limit_exceeded": DialFailure.RATE_LIMITED,
    "insufficient_balance": DialFailure.INSUFFICIENT_BALANCE,
    "recipient_blocked": DialFailure.POLICY_VIOLATION,
    "policy_violation": DialFailure.POLICY_VIOLATION,
    "unauthorized": DialFailure.UNAUTHORIZED,
    "forbidden": DialFailure.UNAUTHORIZED,
    "provider_unavailable": DialFailure.PROVIDER_UNAVAILABLE,
    # `call_not_ready`/`not_found` only ever occur on a poll (`GET /v1/calls/{id}`
    # for a call that hasn't been indexed yet) - a real but short-lived
    # read-after-write race, never a `start_call` response - so they get the
    # same transient, retryable treatment as `provider_unavailable`.
    "call_not_ready": DialFailure.PROVIDER_UNAVAILABLE,
    "not_found": DialFailure.PROVIDER_UNAVAILABLE,
    # A malformed request, an idempotency-key/payload mismatch, or a
    # `result_schema` the engine's structured-extraction can't honour are all
    # configuration problems, not something a retry or a different phone
    # number fixes - fails closed to INTERNAL like the unmapped default, but
    # explicitly, since each is a distinct, real, reachable code.
    "invalid_request": DialFailure.INTERNAL,
    "idempotency_conflict": DialFailure.INTERNAL,
    "result_schema_invalid": DialFailure.INTERNAL,
    "recipient_result_schema_invalid": DialFailure.INTERNAL,
    "internal_error": DialFailure.INTERNAL,
}


def classify_error(exc: EngineAPIError | EngineConnectionError | EngineTimeoutError) -> DialFailure:
    """The one place an engine error becomes a `DialFailure` - so retry policy,
    the outcome's stored `error`, and any future second voice provider all agree
    on what a failure means, instead of each re-deriving it from a raw string."""
    if isinstance(exc, EngineTimeoutError):
        return DialFailure.TIMED_OUT
    if isinstance(exc, EngineConnectionError):
        # Raised by the SDK when the request fails before any response comes
        # back (DNS failure, connection refused, TLS error) - there's no
        # vendor error code to look up because the vendor never answered.
        # That's a reachability problem, not evidence the number or the
        # request itself is bad, so it gets the same treatment as the
        # documented `provider_unavailable` code.
        return DialFailure.PROVIDER_UNAVAILABLE
    return _ERROR_CODE_MAP.get(exc.code, DialFailure.INTERNAL)


_SUPPORTED: frozenset[VoiceCapability] = frozenset(
    {VoiceCapability.STRUCTURED_EXTRACTION, VoiceCapability.LIVE_EVENTS}
)


class EngineGateway:
    """Owns the voice-engine connection and translates it into CallFlow terms.

    Conforms to `app.integrations.voice.protocol.VoiceProvider` structurally -
    CALL-E is the only implementation today (`VOICE_AGENT_PLATFORM.md` P1).
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._client = _VendorClient(api_key=api_key or require_api_key())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def supports(self, capability: VoiceCapability) -> bool:
        return capability in _SUPPORTED

    def cancel_call(self, call_id: str) -> None:
        """CALL-E's SDK exposes `create`, `create_and_wait`, `get`,
        `list_events`, and `wait_for_result` - no cancel. Raise rather than
        silently no-op, so a caller who didn't check `supports()` first finds
        out immediately instead of believing a call was cancelled when it
        wasn't."""
        raise NotImplementedForProvider("CALL-E has no way to cancel an in-flight call.")

    def start_call(
        self,
        *,
        task: str,
        phone: str,
        result_schema: JsonObject | None = None,
        metadata: JsonObject | None = None,
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
        region: str | None = None,
        language: str | None = None,
    ) -> JsonObject:
        """Create a call. This DIALS - every caller must pass the safety gate first.

        Recipient fields are `phones`, `region`, and `locale`. The API rejects
        anything else with 422 extra_forbidden - notably `language`, which is
        NOT a valid key despite reading like one.
        """
        recipient: JsonObject = {"phone": phone}
        if region or config.default_region:
            recipient["region"] = region or config.default_region
        if language or config.default_language:
            recipient["locale"] = language or config.default_language

        log.info("dialing %s", mask(phone))
        return self._client.calls.create(
            task=task,
            recipient=recipient,
            result_schema=result_schema,
            metadata=metadata,
            webhook_url=webhook_url,
            idempotency_key=idempotency_key,
        )

    def get_call(self, call_id: str) -> JsonObject:
        return self._client.calls.get(call_id)

    def wait_for_result(
        self,
        call_id: str,
        *,
        interval_seconds: float | None = None,
        timeout_seconds: float | None = None,
    ) -> JsonObject:
        return self._client.calls.wait_for_result(
            call_id,
            interval_seconds=interval_seconds or 5.0,
            timeout_seconds=timeout_seconds or config.poll_timeout_seconds,
        )

    def list_events(
        self, call_id: str, *, cursor: str | None = None, limit: int | None = None
    ) -> JsonObject:
        """Event stream for a call - powers live dashboard progress.

        The endpoint is cursor-paginated; forwarding it is what lets a caller
        actually reach past the first page on a long-running call.
        """
        return self._client.calls.list_events(call_id, cursor=cursor, limit=limit)


__all__ = [
    "TERMINAL",
    "EngineAPIError",
    "EngineConnectionError",
    "EngineGateway",
    "EngineTimeoutError",
    "classify_error",
]
