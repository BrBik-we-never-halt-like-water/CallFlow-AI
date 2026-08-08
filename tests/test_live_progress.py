"""Live-call progress reporting.

A conversation can run for minutes. Without intermediate updates the dashboard
shows an empty table the whole time, which reads as a hang   so the row must
appear when the call is placed and update as the status changes.
"""

from typing import Any

from callflow.campaigns import TRAVEL_DISCOVERY
from callflow.models import CallOutcome, Contact, Disposition
from callflow.orchestrator import CampaignRunner
from callflow.store import RunStore


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
    monkeypatch.setattr("callflow.orchestrator.time.sleep", lambda _s: None)
    return CampaignRunner(gateway=FakeGateway(statuses), dry_run=False)  # type: ignore[arg-type]


def test_row_appears_before_the_call_finishes(monkeypatch) -> None:
    seen: list[CallOutcome] = []
    runner = _runner(["ringing", "in_progress", "completed"], monkeypatch)

    runner.run_one(
        TRAVEL_DISCOVERY,
        Contact(name="Aditi", phone="+15555550100"),
        on_status=seen.append,
    )

    assert seen, "no progress was reported while the call was running"
    assert seen[0].disposition is Disposition.IN_FLIGHT
    assert seen[0].run_id == "call_test123"


def test_progress_labels_are_human_readable(monkeypatch) -> None:
    seen: list[CallOutcome] = []
    runner = _runner(["ringing", "in_progress", "completed"], monkeypatch)

    runner.run_one(
        TRAVEL_DISCOVERY,
        Contact(name="Aditi", phone="+15555550100"),
        on_status=seen.append,
    )

    labels = [o.disposition_reason for o in seen]
    assert "Dialing…" in labels
    assert any("Ringing" in (label or "") for label in labels)
    assert any("conversation" in (label or "") for label in labels)


def test_final_outcome_is_triaged_not_in_flight(monkeypatch) -> None:
    runner = _runner(["ringing", "completed"], monkeypatch)

    result = runner.run_one(
        TRAVEL_DISCOVERY, Contact(name="Aditi", phone="+15555550100")
    )

    assert result.disposition is Disposition.AUTO_CLOSED
    assert result.extracted["outcome"] == "interested"


def test_store_updates_the_row_instead_of_duplicating() -> None:
    """One call reports several times; that must not create several rows."""
    store = RunStore()
    run_id = store.create_run("travel-discovery", total=1, dry_run=False)

    for status, disposition in [
        ("QUEUED", Disposition.IN_FLIGHT),
        ("RINGING", Disposition.IN_FLIGHT),
        ("COMPLETED", Disposition.AUTO_CLOSED),
    ]:
        store.append_outcome(
            run_id,
            CallOutcome(
                contact_name="Aditi",
                phone_masked="+15******100",
                campaign_id="travel-discovery",
                status=status,
                disposition=disposition,
            ),
        )

    run = store.get(run_id)
    assert run is not None
    assert len(run["outcomes"]) == 1, "each status update created a new row"
    assert run["outcomes"][0]["status"] == "COMPLETED"


def test_different_contacts_get_their_own_rows() -> None:
    store = RunStore()
    run_id = store.create_run("travel-discovery", total=2, dry_run=False)

    for name, masked in [("Aditi", "+15******100"), ("Rahul", "+15******101")]:
        store.append_outcome(
            run_id,
            CallOutcome(
                contact_name=name,
                phone_masked=masked,
                campaign_id="travel-discovery",
                status="COMPLETED",
            ),
        )

    run = store.get(run_id)
    assert run is not None
    assert len(run["outcomes"]) == 2
