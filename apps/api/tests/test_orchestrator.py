"""Orchestrator behaviour: every run dials for real, guarded by the safety gate."""

from typing import Any

import pytest

from app.domain.campaigns import TRAVEL_DISCOVERY
from app.domain.entities import Contact, Disposition
from app.services.campaign_runner import CampaignRunner, _extract_result, render_goal


class ExplodingGateway:
    """Fails loudly if a guarded call reaches the gateway at all."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"a blocked contact must not call gateway.{name}")


class FakeGateway:
    """Completes a call immediately with a canned structured result."""

    def start_call(self, **_: Any) -> dict[str, Any]:
        return {"id": "call_test123", "status": "queued"}

    def get_call(self, call_id: str) -> dict[str, Any]:
        return {
            "id": call_id,
            "status": "completed",
            "structured_result": {
                "outcome": "interested",
                "sentiment": "positive",
                "frustration_signals": False,
                "summary": "Wants a Bali package.",
            },
        }


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _instant(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.campaign_runner.asyncio.sleep", _instant)


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


async def test_call_completes_and_masks_the_phone() -> None:
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]
    contact = Contact(name="Aditi", phone="+15555550100", context={"enquiry_note": "Bali"})

    result = await runner.run_one(TRAVEL_DISCOVERY, contact)

    assert result.disposition is Disposition.AUTO_CLOSED
    assert result.run_id == "call_test123"
    assert "5555550" not in result.phone_masked


async def test_ceiling_blocks_further_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import dataclasses

    from app.domain import safety

    # Config is frozen, so swap in a replaced copy rather than mutating it.
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, max_calls_per_run=0)
    )
    runner = CampaignRunner(gateway=ExplodingGateway())  # type: ignore[arg-type]
    result = await runner.run_one(TRAVEL_DISCOVERY, Contact(name="A", phone="+15555550100"))
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED


async def test_suppressed_number_is_blocked() -> None:
    from app.domain.safety import phone_hash

    contact = Contact(name="A", phone="+15555550100")
    runner = CampaignRunner(
        gateway=ExplodingGateway(),  # type: ignore[arg-type]
        suppressed_hashes=frozenset({phone_hash(contact.phone)}),
    )
    result = await runner.run_one(TRAVEL_DISCOVERY, contact)
    assert result.status == "BLOCKED"
    assert result.disposition is Disposition.SKIPPED
    assert "suppression" in (result.disposition_reason or "")


async def test_run_processes_every_contact() -> None:
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]
    contacts = [
        Contact(name="A", phone="+15555550100"),
        Contact(name="B", phone="+15555550101"),
    ]
    assert len(await runner.run(TRAVEL_DISCOVERY, contacts)) == 2


async def test_progress_hook_fires_per_contact() -> None:
    """Each contact fires at least once — a "dialing" event, then the resolved
    outcome — and always in contact order, never interleaved."""
    seen: list[str] = []
    runner = CampaignRunner(gateway=FakeGateway())  # type: ignore[arg-type]

    async def on_progress(outcome: Any) -> None:
        seen.append(outcome.contact_name)

    await runner.run(
        TRAVEL_DISCOVERY,
        [Contact(name="A", phone="+15555550100"), Contact(name="B", phone="+15555550101")],
        on_progress=on_progress,
    )
    assert seen == ["A", "A", "B", "B"]


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
