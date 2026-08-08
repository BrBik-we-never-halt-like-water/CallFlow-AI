"""Result schemas passed to the engine's native `result_schema` parameter.

The engine performs structured extraction server-side during/after the call, so
CallFlow AI never regex-scrapes a transcript. Each campaign declares the typed
contract it expects back.
"""

from __future__ import annotations

from typing import Any

JsonObject = dict[str, Any]

# Every campaign inherits these fields so triage logic is uniform.
BASE_PROPERTIES: JsonObject = {
    "outcome": {
        "type": "string",
        "enum": ["interested", "not_interested", "callback_requested", "no_decision"],
        "description": "The contact's overall decision on this call.",
    },
    "sentiment": {
        "type": "string",
        "enum": ["positive", "neutral", "negative"],
        "description": "Emotional tone of the contact during the conversation.",
    },
    "frustration_signals": {
        "type": "boolean",
        "description": "True if the contact was angry, rude, repeatedly interrupted, or asked to stop being called.",
    },
    "wants_human_callback": {
        "type": "boolean",
        "description": "True if the contact explicitly asked to speak to a human.",
    },
    "do_not_call": {
        "type": "boolean",
        "description": "True if the contact asked never to be contacted again.",
    },
    "summary": {
        "type": "string",
        "description": "Two-sentence factual summary of what was agreed or refused.",
    },
}

BASE_REQUIRED = ["outcome", "sentiment", "frustration_signals", "summary"]


def build_result_schema(
    extra_properties: JsonObject | None = None,
    extra_required: list[str] | None = None,
) -> JsonObject:
    """Compose a campaign-specific schema on top of the shared triage fields.

    `extra_required` is a campaign's own fields marked required in the editor -
    appended rather than replacing `BASE_REQUIRED`, so a campaign can never make
    triage's own fields optional.
    """
    properties = {**BASE_PROPERTIES, **(extra_properties or {})}
    required = [*BASE_REQUIRED, *(extra_required or [])]
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


# --- Demo vertical: travel ------------------------------------------------

TRAVEL_PROPERTIES: JsonObject = {
    "service_interest": {
        "type": "string",
        "enum": ["flight", "hotel", "tour", "package", "none"],
        "description": "Which travel service the contact wants.",
    },
    "destination": {"type": "string", "description": "Destination city or country, if stated."},
    "travel_date": {"type": "string", "description": "Preferred travel date in YYYY-MM-DD, if stated."},
    "party_size": {"type": "integer", "description": "Number of travellers, if stated."},
    "budget_inr": {"type": "number", "description": "Stated budget in INR, if any."},
    "ready_for_quote": {
        "type": "boolean",
        "description": "True if enough trip detail was gathered for a consultant to prepare a quote.",
    },
}

TRAVEL_SCHEMA = build_result_schema(TRAVEL_PROPERTIES)
