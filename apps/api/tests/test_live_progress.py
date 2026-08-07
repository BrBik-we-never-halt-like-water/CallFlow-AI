"""Live-call progress reporting.

A conversation can run for minutes. Without intermediate updates the dashboard
shows an empty table the whole time, which reads as a hang — so the row must
appear when the call is placed and update as the status changes.

The upsert-by-contact behaviour that used to live in the in-memory `RunStore`
now lives in `runs_repo.append_outcome`'s SQL (`ON CONFLICT ... DO UPDATE`) —
that needs a real Postgres connection to exercise and isn't covered here; this
file only tests `CampaignRunner`, which has no I/O of its own to fake.
"""

from typing import Any

from app.domain.campaigns import TRAVEL_DISCOVERY
from app.domain.entities import CallOutcome, Contact, Disposition
from app.services.campaign_runner import CampaignRunner


class FakeGateway:
    """Walks a call through queued → ringing → in_progress → completed."""

    def __init__(self, statuses: list[str]) -> None:
        self._statuses = statuses
        self._i = 0

    def start_call(self, **_: Any) -> dict[str, Any]:
        return {"id": "call_test123", "status": "queued"}

    def get_call(self, call_id: str) -> dict[str, Any]:
        status = self._statuses[min(self._i, len(self._statuses) - 1)]
        self._i += 1
        payload: dict[str, Any] = {"id": call_id, "status": status}
        if status == "completed":
            payload["structured_result"] = {
                "outcome": "interested",
                "sentiment": "positive",
                "frustration_signals": False,
                "summary": "Wants a Bali package.",
            }
        return payload


def _runner(statuses: list[str], monkeypatch) -> CampaignRunner:
    # Don't actually sleep between polls.
    monkeypatch.setattr("app.services.campaign_runner.asyncio.sleep", _no_sleep)
    return CampaignRunner(gateway=FakeGateway(statuses))  # type: ignore[arg-type]


async def _no_sleep(_seconds: float) -> None:
    return None


async def test_row_appears_before_the_call_finishes(monkeypatch) -> None:
    seen: list[CallOutcome] = []
    runner = _runner(["ringing", "in_progress", "completed"], monkeypatch)

    async def on_status(outcome: CallOutcome) -> None:
        seen.append(outcome)

    await runner.run_one(
        TRAVEL_DISCOVERY,
        Contact(name="Aditi", phone="+15555550100"),
        on_status=on_status,
    )

    assert seen, "no progress was reported while the call was running"
    assert seen[0].disposition is Disposition.IN_FLIGHT
    assert seen[0].run_id == "call_test123"


async def test_progress_labels_are_human_readable(monkeypatch) -> None:
    seen: list[CallOutcome] = []
    runner = _runner(["ringing", "in_progress", "completed"], monkeypatch)

    async def on_status(outcome: CallOutcome) -> None:
        seen.append(outcome)

    await runner.run_one(
        TRAVEL_DISCOVERY,
        Contact(name="Aditi", phone="+15555550100"),
        on_status=on_status,
    )

    labels = [o.disposition_reason for o in seen]
    assert "Dialing…" in labels
    assert any("Ringing" in (label or "") for label in labels)
    assert any("conversation" in (label or "") for label in labels)


async def test_final_outcome_is_triaged_not_in_flight(monkeypatch) -> None:
    runner = _runner(["ringing", "completed"], monkeypatch)

    result = await runner.run_one(
        TRAVEL_DISCOVERY, Contact(name="Aditi", phone="+15555550100")
    )

    assert result.disposition is Disposition.AUTO_CLOSED
    assert result.extracted["outcome"] == "interested"
