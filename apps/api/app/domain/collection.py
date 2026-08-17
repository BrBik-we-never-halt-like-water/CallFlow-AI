"""Did the call come back with what the agent was asked to find out?

Pure: no I/O, no vendor, no database - `triage()`'s own standard, and the reason
both can be tested against a dict instead of a transcript.

ADR-5's point 3, and the gap it names: a field could already be marked
`required`, but that value was used exactly once - to build the schema the model
was asked to satisfy - and nothing ever re-checked the answer against it. A call
could come back with none of the required fields and still be recorded as
`auto_closed` because the status said `completed`.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol


class RequiredField(Protocol):
    """Structural, so this module needs no import from `entities`."""

    key: str
    description: str
    required: bool


def is_present(value: Any) -> bool:
    """Whether a collected answer counts as an answer.

    The distinction a bare falsiness check gets wrong: `False` and `0` are real
    answers. A yes/no field answered "no" was *collected*, and treating it as
    missing would escalate a call that went perfectly and send a person to ask a
    question the contact has already answered.

    Empty strings and whitespace are missing, because that is what a model
    returns when it has nothing - and `None` is missing because that is what the
    absence of a key looks like once it has been `.get()`.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    # Everything else - including False, 0, [], {} - is a value the agent
    # reported. An empty list from a list-valued field is a deliberate "none".
    return True


def missing_required(
    fields: Sequence[RequiredField], collected: dict[str, Any] | None
) -> list[str]:
    """The required keys the call ended without, in the agent's own order.

    Order matters a little: it is read back to a person as the list of things to
    ask, and the agent's field order is the order it would have asked them in.
    """
    answers = collected or {}
    return [
        field.key
        for field in fields
        if field.required and not is_present(answers.get(field.key))
    ]


def handoff_questions(
    fields: Sequence[RequiredField],
    *,
    missing: Sequence[str],
    wants_human: bool = False,
    do_not_call: bool = False,
) -> list[str]:
    """What a person still has to ask, in plain words.

    Written for whoever picks up the "needs a person" queue: a list of field
    names is a database row, and "Ask which destination they have in mind" is an
    instruction. Falls back to the key when a field has no description, because
    naming the gap badly still beats not naming it.

    The opt-out and callback lines come last and are not questions about data -
    they are the reason the call was escalated in the first place, and a person
    should handle them before asking for anything.
    """
    by_key = {field.key: field for field in fields}
    questions: list[str] = []

    for key in missing:
        field = by_key.get(key)
        description = (field.description or "").strip() if field else ""
        if description:
            # Descriptions are written as noun phrases ("Which destination they
            # have in mind"), so this reads as an instruction without needing the
            # author to have phrased it as one.
            questions.append(f"Ask: {description}")
        else:
            questions.append(f"Ask for {key.replace('_', ' ')}.")

    if wants_human:
        questions.append("They asked to speak to a person - call them back.")
    if do_not_call:
        questions.append("They asked not to be called again - confirm and suppress.")

    return questions


__all__ = ["RequiredField", "handoff_questions", "is_present", "missing_required"]
