"""Built-in campaign definitions.

Travel is the demo vertical. The engine underneath is campaign-agnostic — a new
vertical is a goal template plus a result schema, nothing more.
"""

from __future__ import annotations

import re
from typing import Any

from .models import Campaign
from .schemas import TRAVEL_SCHEMA, build_result_schema

TRAVEL_DISCOVERY = Campaign(
    id="travel-discovery",
    name="Travel enquiry follow-up",
    goal_template=(
        "You are CallFlow AI, a friendly travel consultant calling {name} back about "
        "their holiday enquiry.\n\n"
        "Open by greeting them by name and confirming this is a good time to talk. "
        "If they say it is not, apologise, ask when to call back, and end politely.\n\n"
        "Your objective is to understand their trip so a consultant can prepare a quote. "
        "Find out, conversationally and without interrogating them:\n"
        "  - which destination they have in mind\n"
        "  - roughly when they want to travel\n"
        "  - how many people are travelling\n"
        "  - whether they need flights, a hotel, a tour, or a full package\n"
        "  - their rough budget, only if they offer it comfortably\n\n"
        "Known context: {enquiry_note}\n\n"
        "If they sound annoyed or say it is a bad time, do not push. Apologise once, "
        "offer to have a human colleague call them, and close warmly.\n\n"
        "Close by thanking them for the details, telling them you will share "
        "everything with the travel consultants, and that a colleague will get "
        "back to them with options. Thank them by name and end the call.\n\n"
        "Do not promise a WhatsApp message, an email, a price, or a specific "
        "callback time — none of that is yours to commit to."
    ),
    # Must mirror TRAVEL_PROPERTIES in schemas.py — this is what the dashboard
    # lists and what dry-run previews populate.
    outcome_fields={
        "service_interest": "flight | hotel | tour | package | none",
        "destination": "destination city or country",
        "travel_date": "YYYY-MM-DD",
        "party_size": "number of travellers",
        "budget_inr": "stated budget in INR",
        "ready_for_quote": "true if a consultant has enough to quote",
    },
    region="IN",
    language="en",
    escalate_on_negative=True,
)

APPOINTMENT_REMINDER = Campaign(
    id="appointment-reminder",
    name="Appointment confirmation",
    goal_template=(
        "You are CallFlow AI calling {name} to confirm their appointment on "
        "{appointment_time}.\n\n"
        "Greet them by name, state the appointment date and time clearly, and ask "
        "whether they can still make it.\n\n"
        "If they confirm, thank them and end. If they cannot make it, ask what day "
        "and time would suit them better. If they want to cancel, accept it without "
        "pushing back and confirm the cancellation.\n\n"
        "Keep the call under two minutes. Do not give any medical, legal, or "
        "financial advice — if asked, say a colleague will follow up."
    ),
    # Must mirror the extra properties in SCHEMAS below — this is what the
    # dashboard lists and what dry-run previews populate.
    outcome_fields={
        "confirmed": "true if the appointment was confirmed",
        "reschedule_to": "preferred new slot, if given",
        "cancelled": "true if the contact cancelled",
    },
    region="IN",
    language="en",
    escalate_on_negative=True,
)

REGISTRY: dict[str, Campaign] = {
    TRAVEL_DISCOVERY.id: TRAVEL_DISCOVERY,
    APPOINTMENT_REMINDER.id: APPOINTMENT_REMINDER,
}

SCHEMAS: dict[str, dict[str, Any]] = {
    TRAVEL_DISCOVERY.id: TRAVEL_SCHEMA,
    APPOINTMENT_REMINDER.id: build_result_schema(
        {
            "confirmed": {"type": "boolean", "description": "True if the appointment was confirmed."},
            "reschedule_to": {"type": "string", "description": "Preferred new slot, if given."},
            "cancelled": {"type": "boolean", "description": "True if the contact cancelled."},
        }
    ),
}

# Campaigns shipped with the app cannot be deleted from the dashboard.
BUILT_IN_IDS = frozenset(REGISTRY)

# JSON-schema types a user may pick for a custom extraction field.
FIELD_TYPES = {"string", "boolean", "integer", "number"}


def get_campaign(campaign_id: str) -> Campaign:
    if campaign_id not in REGISTRY:
        raise KeyError(f"Unknown campaign: {campaign_id}. Known: {', '.join(REGISTRY)}")
    return REGISTRY[campaign_id]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "campaign"


def unique_id(name: str) -> str:
    base = slugify(name)
    candidate = base
    n = 2
    while candidate in REGISTRY:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def register_campaign(
    *,
    name: str,
    goal_template: str,
    extra_fields: list[dict[str, str]] | None = None,
    region: str | None = None,
    language: str | None = None,
    escalate_on_negative: bool = True,
) -> Campaign:
    """Add a user-defined campaign to the registry.

    `extra_fields` are appended to the shared triage schema, so every campaign
    still returns sentiment/frustration/opt-out regardless of what else the
    author asks the engine to extract.
    """
    properties: dict[str, Any] = {}
    outcome_fields: dict[str, str] = {}

    for field in extra_fields or []:
        key = slugify(field.get("key", "")).replace("-", "_")
        if not key:
            continue
        ftype = field.get("type", "string")
        if ftype not in FIELD_TYPES:
            ftype = "string"
        description = field.get("description", "").strip() or f"The contact's {key.replace('_', ' ')}."
        properties[key] = {"type": ftype, "description": description}
        outcome_fields[key] = description

    campaign = Campaign(
        id=unique_id(name),
        name=name.strip(),
        goal_template=goal_template.strip(),
        outcome_fields=outcome_fields,
        region=region,
        language=language,
        escalate_on_negative=escalate_on_negative,
    )

    REGISTRY[campaign.id] = campaign
    SCHEMAS[campaign.id] = build_result_schema(properties)
    return campaign


def delete_campaign(campaign_id: str) -> None:
    if campaign_id in BUILT_IN_IDS:
        raise ValueError("Built-in campaigns cannot be deleted.")
    if campaign_id not in REGISTRY:
        raise KeyError(f"Unknown campaign: {campaign_id}")
    REGISTRY.pop(campaign_id)
    SCHEMAS.pop(campaign_id, None)
