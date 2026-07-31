"""User-defined campaigns."""

import pytest

from callflow import campaigns as mod
from callflow.campaigns import (
    BUILT_IN_IDS,
    delete_campaign,
    register_campaign,
    slugify,
    unique_id,
)

GOAL = (
    "You are CallFlow AI calling {name} about their recent order. Ask whether it "
    "arrived on time and whether they are happy with it. Thank them and close."
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Undo any campaigns a test registers."""
    before = set(mod.REGISTRY)
    yield
    for cid in set(mod.REGISTRY) - before:
        mod.REGISTRY.pop(cid, None)
        mod.SCHEMAS.pop(cid, None)


def test_slugify() -> None:
    assert slugify("Renewal Outreach!") == "renewal-outreach"
    assert slugify("  多  ") == "campaign"


def test_unique_id_avoids_collisions() -> None:
    a = register_campaign(name="Order Check", goal_template=GOAL)
    b = register_campaign(name="Order Check", goal_template=GOAL)
    assert a.id != b.id
    assert b.id.endswith("-2")


def test_registered_campaign_is_runnable() -> None:
    c = register_campaign(name="Order Check", goal_template=GOAL)
    assert mod.get_campaign(c.id) is c
    assert c.id in mod.SCHEMAS


def test_custom_fields_extend_the_shared_schema() -> None:
    c = register_campaign(
        name="Order Check",
        goal_template=GOAL,
        extra_fields=[
            {"key": "arrived_on_time", "type": "boolean", "description": "Did it arrive on time"},
            {"key": "rating", "type": "integer", "description": "Satisfaction 1-5"},
        ],
    )
    props = mod.SCHEMAS[c.id]["properties"]
    # Custom fields present...
    assert props["arrived_on_time"]["type"] == "boolean"
    assert props["rating"]["type"] == "integer"
    # ...and the triage fields survive, so escalation still works.
    for shared in ("sentiment", "frustration_signals", "do_not_call", "summary"):
        assert shared in props


def test_bad_field_type_falls_back_to_string() -> None:
    c = register_campaign(
        name="Order Check",
        goal_template=GOAL,
        extra_fields=[{"key": "note", "type": "nonsense"}],
    )
    assert mod.SCHEMAS[c.id]["properties"]["note"]["type"] == "string"


def test_field_keys_are_normalised() -> None:
    c = register_campaign(
        name="Order Check",
        goal_template=GOAL,
        extra_fields=[{"key": "Arrived On Time!", "type": "boolean"}],
    )
    assert "arrived_on_time" in mod.SCHEMAS[c.id]["properties"]


def test_blank_field_keys_are_dropped() -> None:
    c = register_campaign(
        name="Order Check",
        goal_template=GOAL,
        extra_fields=[{"key": "  ", "type": "string"}],
    )
    props = mod.SCHEMAS[c.id]["properties"]
    assert "" not in props


def test_delete_removes_campaign_and_schema() -> None:
    c = register_campaign(name="Order Check", goal_template=GOAL)
    delete_campaign(c.id)
    assert c.id not in mod.REGISTRY
    assert c.id not in mod.SCHEMAS


def test_built_ins_cannot_be_deleted() -> None:
    for cid in BUILT_IN_IDS:
        with pytest.raises(ValueError):
            delete_campaign(cid)


def test_delete_unknown_raises() -> None:
    with pytest.raises(KeyError):
        delete_campaign("does-not-exist")
