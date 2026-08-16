"""Delivering a finished call's result.

A transcript that never arrives is worse than most failures here: the call
happened, the contact spoke, and the operator is left with a row stuck at "In
conversation…" and no way to find out what was said. So the retry behaviour is
worth asserting properly - including what must *not* be retried.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app import reporter as reporter_module
from app.reporter import ReportFailed, report_completion


@pytest.fixture(autouse=True)
def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    monkeypatch.setattr(
        reporter_module,
        "config",
        dataclasses.replace(
            reporter_module.config,
            api_base_url="https://api.test",
            internal_api_secret="secret",
            report_retry_seconds=10,
        ),
    )


class Recorder:
    """A transport that answers with a scripted sequence of results."""

    def __init__(self, *results: Any) -> None:
        self._results = list(results)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        result = self._results.pop(0) if self._results else httpx.Response(200)
        if isinstance(result, Exception):
            raise result
        return result


def _client(recorder: Recorder) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))


async def _noop_sleep(_seconds: float) -> None:
    return None


async def test_a_successful_report_sends_the_payload_and_the_secret() -> None:
    recorder = Recorder(httpx.Response(200, json={"ok": True}))
    async with _client(recorder) as http:
        await report_completion("run_abc", {"status": "COMPLETED"}, client=http, sleep=_noop_sleep)

    assert len(recorder.requests) == 1
    request = recorder.requests[0]
    assert request.url.path == "/internal/v1/runs/run_abc/complete"
    assert request.headers["X-CallFlow-Internal-Key"] == "secret"


async def test_a_transient_failure_is_retried_until_it_succeeds() -> None:
    recorder = Recorder(
        httpx.Response(503),
        httpx.ConnectError("connection refused"),
        httpx.Response(200),
    )
    async with _client(recorder) as http:
        await report_completion("run_abc", {}, client=http, sleep=_noop_sleep)

    assert len(recorder.requests) == 3


async def test_a_rejected_payload_is_not_retried() -> None:
    """A 4xx will never become a 2xx. Retrying wastes the budget a real outage
    needs, and reports a timeout instead of the actual reason."""
    recorder = Recorder(httpx.Response(401))
    async with _client(recorder) as http:
        with pytest.raises(ReportFailed) as caught:
            await report_completion("run_abc", {}, client=http, sleep=_noop_sleep)

    assert len(recorder.requests) == 1
    assert "CALLFLOW_INTERNAL_API_SECRET" in str(caught.value)


async def test_giving_up_says_the_conversation_happened_but_was_not_recorded() -> None:
    """The operator needs to know a real call is missing, not just "error"."""
    recorder = Recorder(*[httpx.Response(503) for _ in range(50)])
    async with _client(recorder) as http:
        with pytest.raises(ReportFailed) as caught:
            await report_completion("run_abc", {}, client=http, sleep=_noop_sleep)

    assert "was not recorded" in str(caught.value)


async def test_retries_are_bounded_rather_than_infinite() -> None:
    """`report_retry_seconds` is a real ceiling - a wedged API must not pin a
    worker forever, because the process is also holding a LiveKit job slot."""
    recorder = Recorder(*[httpx.Response(500) for _ in range(500)])
    async with _client(recorder) as http:
        with pytest.raises(ReportFailed):
            await report_completion("run_abc", {}, client=http, sleep=_noop_sleep)

    # Backoff doubles from 1s to a 15s cap against a 10s budget: a handful of
    # attempts, not hundreds.
    assert len(recorder.requests) < 10
