"""Orchestrator behaviour, including the dry-run path that places no calls."""

from typing import Any

import pytest

from callflow.campaigns import TRAVEL_DISCOVERY
from callflow.models import Contact, Disposition
from callflow.orchestrator import CampaignRunner, _extract_result, render_goal


def test_render_goal_substitutes_contact_fields() -> None:
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})
    goal = render_goal(TRAVEL_DISCOVERY, contact)
    assert "Aditi" in goal
    assert "Bali" in goal


def test_render_goal_tolerates_missing_context_key() -> None:
    # A contact with no enquiry_note must not crash the whole campaign.
    contact = Contact(name="Rahul", phone="+15555550101")
    goal = render_goal(TRAVEL_DISCOVERY, contact)
    assert "Rahul" in goal
    assert "{enquiry_note}" not in goal


def test_invalid_phone_rejected_at_model_level() -> None:
    with pytest.raises(ValueError):
        Contact(name="Bad", phone="5555550100")


def test_dry_run_places_no_call() -> None:
    """The gateway must never be touched in dry-run mode."""

    class ExplodingGateway:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"dry run must not call gateway.{name}")

    runner = CampaignRunner(gateway=ExplodingGateway(), dry_run=True)  # type: ignore[arg-type]
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    result = runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.dry_run is True
    assert result.status == "PREVIEW"
    assert result.run_id is None
    # The preview must be flagged, or it could be mistaken for a real result.
    assert result.extracted["is_sample"] is True


def test_dry_run_masks_phone_in_output() -> None:
    runner = CampaignRunner(dry_run=True)
    contact = Contact(name="Aditi", phone="+15555550100")
    result = runner.run_one(TRAVEL_DISCOVERY, contact)
    assert "5555550" not in result.phone_masked


def test_ceiling_blocks_further_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    from callflow import safety

    # Config is frozen, so swap in a replaced copy rather than mutating it.
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, max_calls_per_run=0)
    )
    runner = CampaignRunner(dry_run=True)
    result = runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED


def test_run_processes_every_contact() -> None:
    runner = CampaignRunner(dry_run=True)
    contacts = [
        Contact(name="A", phone="+15555550100"),
        Contact(name="B", phone="+15555550101"),
    ]
    assert len(runner.run(TRAVEL_DISCOVERY, contacts)) == 2


def test_progress_hook_fires_per_contact() -> None:
    seen: list[str] = []
    runner = CampaignRunner(dry_run=True)
    runner.run(
        TRAVEL_DISCOVERY,
        [Contact(name="A", phone="+15555550100"), Contact(name="B", phone="+15555550101")],
        on_progress=lambda o: seen.append(o.contact_name),
    )
    assert seen == ["A", "B"]


@pytest.mark.parametrize(
    "payload,expected_key",
    [
        ({"result": {"outcome": "interested"}}, "outcome"),
        ({"structured_result": {"outcome": "interested"}}, "outcome"),
        ({"recipients": [{"result": {"outcome": "interested"}}]}, "outcome"),
        ({"result": {"data": {"outcome": "interested"}}}, "outcome"),
    ],
)
def test_extract_result_handles_known_shapes(payload: dict, expected_key: str) -> None:
    assert expected_key in _extract_result(payload)


def test_extract_result_returns_empty_when_absent() -> None:
    assert _extract_result({"status": "completed"}) == {}
