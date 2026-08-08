"""Dry-run preview outcomes.

A preview must show the full pipeline without dialing, and must never be
mistakable for a real call result.
"""

from callflow.campaigns import APPOINTMENT_REMINDER, TRAVEL_DISCOVERY
from callflow.models import Contact, Disposition
from callflow.orchestrator import CampaignRunner
from callflow.samples import sample_outcome


class ExplodingGateway:
    """Fails loudly if a dry run touches the network at all."""

    def __getattr__(self, name: str):
        raise AssertionError(f"dry run must not call gateway.{name}")


def _preview(contact: Contact, campaign=TRAVEL_DISCOVERY):
    runner = CampaignRunner(gateway=ExplodingGateway(), dry_run=True)  # type: ignore[arg-type]
    return runner.run_one(campaign, contact)


def test_preview_is_always_flagged_as_sample() -> None:
    for name in ("Aditi", "Rahul", "Priya", "Vikram"):
        result = _preview(Contact(name=name, phone="+15555550100"))
        assert result.extracted["is_sample"] is True, f"{name} preview not flagged"


def test_preview_places_no_call() -> None:
    # ExplodingGateway raises on any attribute access, so reaching the end
    # proves nothing was dialed.
    result = _preview(Contact(name="Aditi", phone="+15555550100"))
    assert result.run_id is None
    assert result.dry_run is True


def test_preview_includes_campaign_specific_fields() -> None:
    result = _preview(Contact(name="Aditi", phone="+15555550100"))
    for key in ("destination", "travel_date", "party_size"):
        assert key in result.extracted, f"missing {key}"


def test_preview_fields_match_the_chosen_campaign() -> None:
    result = _preview(
        Contact(name="Aditi", phone="+15555550100"), APPOINTMENT_REMINDER
    )
    assert "confirmed" in result.extracted
    # Travel fields must not leak into an appointment preview.
    assert "destination" not in result.extracted


def test_preview_runs_real_triage() -> None:
    """The preview disposition must come from the same logic a real call uses.

    Uses one runner across the batch, as the app does   profiles advance per
    row so a short list demonstrates several outcomes.
    """
    runner = CampaignRunner(gateway=ExplodingGateway(), dry_run=True)  # type: ignore[arg-type]
    contacts = [
        Contact(name=name, phone="+15555550100")
        for name in ("Aditi", "Rahul", "Priya", "Vikram")
    ]

    results = runner.run(TRAVEL_DISCOVERY, contacts)
    seen = {r.disposition for r in results}

    assert Disposition.SKIPPED not in seen
    # A useful demo shows more than one outcome, including an escalation.
    assert len(seen) > 1, f"every preview produced the same disposition: {seen}"
    assert Disposition.ESCALATED in seen, "no preview demonstrates a human handoff"


def test_preview_is_stable_for_the_same_contact() -> None:
    """A demo that changes on every refresh is confusing to present."""
    a = _preview(Contact(name="Aditi", phone="+15555550100"))
    b = _preview(Contact(name="Aditi", phone="+15555550100"))
    assert a.extracted == b.extracted


def test_builtin_outcome_fields_match_their_schemas() -> None:
    """`outcome_fields` drives the UI and previews; the schema drives the engine.

    They drift silently   a built-in once declared schema properties with no
    matching `outcome_fields`, so its preview showed nothing campaign-specific.
    """
    from callflow.campaigns import REGISTRY, SCHEMAS
    from callflow.schemas import BASE_PROPERTIES

    for campaign_id, campaign in REGISTRY.items():
        schema_extra = set(SCHEMAS[campaign_id]["properties"]) - set(BASE_PROPERTIES)
        assert set(campaign.outcome_fields) == schema_extra, (
            f"{campaign_id}: outcome_fields {set(campaign.outcome_fields)} "
            f"does not match schema extras {schema_extra}"
        )


def test_sample_outcome_carries_the_triage_fields() -> None:
    result = sample_outcome(TRAVEL_DISCOVERY, Contact(name="Aditi", phone="+15555550100"))
    for key in ("outcome", "sentiment", "frustration_signals", "summary"):
        assert key in result
