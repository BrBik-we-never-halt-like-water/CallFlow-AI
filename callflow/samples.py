"""Sample outcomes for dry-run previews.

Dry run must never place a call, but an empty results table hides everything
the product actually does — extraction, sentiment, triage. These generate a
plausible outcome per contact so the whole pipeline is visible without dialing.

Every record produced here is flagged `is_sample: true` and the UI labels it,
so a preview can never be mistaken for a real call result.
"""

from __future__ import annotations

from typing import Any

from .models import Campaign, Contact

# Deliberately varied so a preview shows all three triage paths rather than
# three identical green rows.
_PROFILES: list[dict[str, Any]] = [
    {
        "outcome": "interested",
        "sentiment": "positive",
        "frustration_signals": False,
        "wants_human_callback": False,
        "do_not_call": False,
        "summary": "Keen to go ahead and asked for options by the end of the week.",
    },
    {
        "outcome": "callback_requested",
        "sentiment": "negative",
        "frustration_signals": False,
        "wants_human_callback": False,
        "do_not_call": False,
        "summary": "Said it was a bad time and asked to be called back next week.",
    },
    {
        "outcome": "not_interested",
        "sentiment": "negative",
        "frustration_signals": True,
        "wants_human_callback": True,
        "do_not_call": False,
        "summary": "Annoyed at being contacted again and asked to speak to a person.",
    },
    {
        "outcome": "no_decision",
        "sentiment": "neutral",
        "frustration_signals": False,
        "wants_human_callback": False,
        "do_not_call": False,
        "summary": "Wanted to think it over before committing to anything.",
    },
]

# Plausible values for the campaign-specific fields the built-ins extract.
_FIELD_SAMPLES: dict[str, list[Any]] = {
    "destination": ["Bali", "Dubai", "Singapore", "Phuket"],
    "travel_date": ["2026-12-18", "2027-01-09", "2026-11-24", "2027-02-14"],
    "party_size": [2, 4, 3, 6],
    "budget_inr": [180000, 240000, 95000, 320000],
    "service_interest": ["package", "flight", "hotel", "tour"],
    "ready_for_quote": [True, True, False, False],
    "confirmed": [True, False, False, True],
    "reschedule_to": ["", "Thursday afternoon", "next Monday", ""],
    "cancelled": [False, False, True, False],
    "arrived_on_time": [True, False, True, True],
    "satisfaction": [5, 2, 4, 3],
    "will_renew": [True, False, False, True],
}


def _slot(contact: Contact, index: int) -> int:
    """Pick a stable profile for a contact.

    Position-based, so a short list walks through the profiles in order and a
    preview reliably shows more than one outcome — including an escalation,
    which is the point of the triage demo. A name hash was tried first and
    clustered badly: three contacts could all land on the same profile.

    Stable for a given row, so the same CSV always previews identically.
    """
    return index % len(_PROFILES)


def sample_outcome(
    campaign: Campaign, contact: Contact, index: int = 0
) -> dict[str, Any]:
    """Build a realistic-but-fake extraction result for one contact."""
    slot = _slot(contact, index)
    result: dict[str, Any] = dict(_PROFILES[slot])

    # Fill whatever extra fields this campaign declared.
    for key in campaign.outcome_fields:
        options = _FIELD_SAMPLES.get(key)
        if options:
            result[key] = options[slot % len(options)]

    # Marks this as preview data everywhere it travels.
    result["is_sample"] = True
    return result
