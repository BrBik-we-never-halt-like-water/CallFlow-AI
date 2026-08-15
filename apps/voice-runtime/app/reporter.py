"""Reporting a finished call back to `apps/api`.

The worker does not touch Postgres. `apps/api` owns connection pooling, the
RLS role switch, and log redaction, and a second codebase reaching into the
database directly would duplicate all three - which is how the "only two ways
into the database" rule (CLAUDE.md §4b) quietly stops being true. So this is an
authenticated HTTP call to `/internal/v1/runs/{run_id}/complete` instead.

Delivery is retried, because the alternative is losing a real conversation. A
transcript that never arrives is worse than most failures here: the call
happened, the contact spoke, and the operator sees a row stuck at "In
conversation…" forever with no way to find out what was said.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import config

log = logging.getLogger("voice-runtime.reporter")

# Retried: the API is briefly unreachable, restarting, or overloaded. Not
# retried: anything 4xx, which means this payload will never be accepted no
# matter how many times it is sent - a bad secret, an unknown run, a status the
# API rejects. Hammering those wastes the retry budget a transient outage needs.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class ReportFailed(Exception):
    """The call happened but its result could not be delivered."""


async def report_completion(
    run_id: str,
    payload: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    sleep: Any = asyncio.sleep,
) -> None:
    """POST one finished call, retrying transient failures until the budget runs out.

    Idempotent on the API's side (the upsert is keyed on run + contact), so a
    retry after a dropped response updates the same row rather than adding one -
    which is what makes retrying safe rather than merely hopeful.
    """
    url = f"{config.api_base_url}/internal/v1/runs/{run_id}/complete"
    headers = {"X-CallFlow-Internal-Key": config.internal_api_secret}

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=15.0)
    deadline = config.report_retry_seconds
    delay = 1.0
    waited = 0.0
    last_detail = "no attempt was made"

    try:
        while True:
            try:
                response = await http.post(url, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                last_detail = f"{type(exc).__name__}"
            else:
                if response.status_code < 300:
                    log.info("reported completion for run %s", run_id)
                    return
                last_detail = f"HTTP {response.status_code}"
                if response.status_code not in _RETRYABLE_STATUS:
                    # A 4xx will never become a 2xx. Say so plainly rather than
                    # burning the budget and reporting a timeout instead of the
                    # real reason.
                    raise ReportFailed(
                        f"The API rejected this call's result ({last_detail}). "
                        "Check CALLFLOW_INTERNAL_API_SECRET and that the run still exists."
                    )

            if waited >= deadline:
                raise ReportFailed(
                    f"Could not deliver this call's result after {int(waited)}s "
                    f"({last_detail}). The conversation happened but was not recorded."
                )

            log.warning("report for run %s failed (%s) - retrying", run_id, last_detail)
            await sleep(delay)
            waited += delay
            delay = min(delay * 2, 15.0)
    finally:
        if owns_client:
            await http.aclose()


__all__ = ["ReportFailed", "report_completion"]
