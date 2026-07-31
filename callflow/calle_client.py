"""Thin wrapper over the CALL-E SDK.

Contract verified against calle-ai 0.6.0:

    POST /v1/calls   task, recipients[], result_schema, metadata,
                     webhook_url, Idempotency-Key
    GET  /v1/calls/{id}          -> status in {completed, failed, canceled}
    GET  /v1/calls/{id}/events   -> event stream for live progress

CALL-E performs structured extraction natively via `result_schema`, so we do
not parse transcripts ourselves.
"""

from __future__ import annotations

import logging
from typing import Any

from calle import CalleClient
from calle.errors import CalleAPIError, CalleTimeoutError

from .config import config, require_api_key
from .safety import mask

log = logging.getLogger("callflow.calle")

JsonObject = dict[str, Any]

# Terminal statuses returned by GET /v1/calls/{id}.
TERMINAL = {"completed", "failed", "canceled"}


class CalleGateway:
    """Owns the CALL-E connection and translates it into CallFlow AI terms."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = CalleClient(api_key=api_key or require_api_key())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CalleGateway":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

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
        """Create a call. This DIALS — every caller must pass the safety gate first.

        Recipient fields are `phones`, `region`, and `locale`. The API rejects
        anything else with 422 extra_forbidden — notably `language`, which is
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

    def list_events(self, call_id: str, *, limit: int | None = None) -> JsonObject:
        """Event stream for a call — powers live dashboard progress."""
        return self._client.calls.list_events(call_id, limit=limit)


__all__ = ["CalleGateway", "CalleAPIError", "CalleTimeoutError", "TERMINAL"]
