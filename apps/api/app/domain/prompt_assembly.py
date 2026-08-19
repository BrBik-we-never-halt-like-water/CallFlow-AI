"""What one contact's agent is told before their phone rings.

Pure: no I/O, no vendor, no database. The successor to `goal_rendering.py`'s
`render_goal()`, which filled a *campaign's* goal template; the agent's
`system_prompt` now plays that role, and `_Safe` is carried over verbatim
because the property it provides is what stops one bad spreadsheet cell from
killing a whole run.

The shape of the problem: one agent calls many people, and each call has to be
about *that* person. A travel agent dialling three enquiries needs to open with
Dubai for the first, Malaysia for the second and Spain for the third, from one
configuration. That per-contact detail arrives as `Contact.context` - already an
open dict, already spread into the dispatch metadata - and this module is where
it becomes instructions.

Five blocks, in this order, and the order is the design:

1. **identity** - the agent's own `system_prompt`, first and verbatim, so its
   persona is not diluted by CallFlow's framing.
2. **this person** - who is being called and what the call is about. Before the
   field list, because the agent should know *whose* case it is before it knows
   what to extract.
3. **what else we know** - the remaining context columns.
4. **what to find out** - `collect_fields`, required ones marked, so the agent's
   conversational priority matches what triage will escalate on.
5. **how to behave** - CallFlow's fixed rules, last, where the most recent
   instruction sits in context.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger("app.domain.prompt_assembly")

#: Context keys CallFlow owns. A spreadsheet column by any of these names is
#: dropped rather than rendered: `run_dialer`'s metadata dict spreads
#: `contact.context` first precisely so a column called `goal` cannot rewrite the
#: agent's instructions, and the same discipline has to hold here or the prompt
#: becomes the way in that the metadata dict is not.
RESERVED_CONTEXT_KEYS = frozenset(
    {
        "goal",
        "prompt",
        "detail",
        "name",
        "phone",
        "phone_masked",
        "run_id",
        "voice_agent",
        "voice_agent_id",
        "agent_name",
        "collect_schema",
        "language",
        "max_call_duration_seconds",
        "contact_name",
    }
)

#: The column carrying free text about what this particular call is for.
DETAIL_KEY = "detail"

_DEFAULT_IDENTITY = (
    "You are a professional assistant making a phone call on behalf of the "
    "organisation that scheduled it."
)

_NO_DETAIL = "No specific detail was recorded for this contact."

#: What a placeholder renders as when the contact has no value for it. Only for
#: the ones the agent is likely to build a sentence around: "you are calling
#: {name} about {note}" with an empty note reads as "about ." and invites the
#: model to fill the gap with something it invented. Anything not named here
#: still renders empty, which is right for a placeholder used as a bare value.
_PLACEHOLDER_FALLBACKS: dict[str, str] = {
    "note": "no specific detail was recorded",
    "detail": "no specific detail was recorded",
}

_BEHAVIOUR = """--- HOW TO BEHAVE ---
- If they ask to end the call, say a brief goodbye and end the call immediately.
  Do not ask another question first.
- If they ask never to be called again, acknowledge it, record that, and end the
  call.
- If they ask for a person, say a colleague will call them back, record that, and
  close warmly.
- Never promise a price, a date, an email, or a message. None of that is yours to
  commit to.
- Speak only about this person's own case, above. Do not invent detail."""

_TYPE_WORDS = {
    "string": "text",
    "number": "a number",
    "integer": "a whole number",
    "boolean": "yes or no",
}


class _Safe(dict):
    """A missing placeholder renders empty instead of raising.

    Carried over unchanged from `goal_rendering.py`. An operator writes
    `{booking_ref}` into an agent's prompt and later renames the spreadsheet
    column; without this, every call in the run dies on a `KeyError` instead of
    one sentence reading slightly short.

    An empty value is treated the same as a missing key: a column present in the
    sheet but blank for this row is, to the agent, exactly as absent as one that
    was never there.
    """

    def __missing__(self, key: str) -> str:
        return _PLACEHOLDER_FALLBACKS.get(key, "")

    def __getitem__(self, key: str) -> Any:
        value = super().get(key)
        if value is None or not str(value).strip():
            return self.__missing__(key)
        return value


class CollectField(Protocol):
    """One thing the agent has to come back with.

    Structural, not a class to instantiate: `entities.CollectField` is the
    canonical type, and depending on it by shape rather than by import keeps this
    module free to be read and tested on its own. Anything carrying these four
    attributes renders.
    """

    key: str
    type: str
    description: str
    required: bool


@dataclass(frozen=True)
class PromptContact:
    """Just the parts of a contact this module reads.

    Narrower than `entities.Contact` on purpose (CLAUDE.md §3, interface
    segregation): prompt assembly has no business seeing a phone number, and
    cannot leak one into an instruction if it never receives it.
    """

    name: str
    context: dict[str, Any]


def visible_context(context: dict[str, Any]) -> dict[str, Any]:
    """The spreadsheet's own columns, minus the ones CallFlow owns.

    Logs the *names* it dropped, never the values - a discarded column may hold
    exactly the personal detail that must not reach a log line (CLAUDE.md #5).
    """
    dropped = sorted(k for k in context if k.lower() in RESERVED_CONTEXT_KEYS)
    if dropped:
        log.warning("ignored reserved context columns: %s", ", ".join(dropped))
    return {
        key: value
        for key, value in context.items()
        if key.lower() not in RESERVED_CONTEXT_KEYS
    }


def _humanise(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").strip().capitalize()


def _identity_block(system_prompt: str | None, contact: PromptContact) -> str:
    """The agent's own words, with this contact's data filled in.

    `format_map` also interprets `{}` and `{0}`, which `_Safe` cannot help with -
    a prompt containing a literal brace (a JSON example, say) raises `IndexError`
    or `ValueError` rather than a `KeyError`. Falling back to the unrendered text
    keeps a slightly-wrong prompt from becoming a run where every call fails.
    """
    identity = (system_prompt or "").strip() or _DEFAULT_IDENTITY
    fields = _Safe(name=contact.name, **contact.context)
    try:
        return identity.format_map(fields)
    except (IndexError, KeyError, ValueError):
        log.warning("agent prompt has un-renderable braces; sending it verbatim")
        return identity


def _fields_block(fields: list[CollectField]) -> str:
    lines = []
    for field in fields:
        kind = _TYPE_WORDS.get(field.type, field.type)
        marker = ", required" if field.required else ""
        description = f": {field.description.strip()}" if field.description.strip() else ""
        lines.append(f"- {field.key} ({kind}{marker}){description}")
    return "\n".join(lines)


def render_call_prompt(
    *,
    system_prompt: str | None,
    contact: PromptContact,
    collect_fields: list[CollectField] | None = None,
    run_instruction: str | None = None,
) -> str:
    """Everything the agent is told, for this one contact.

    Assembled by Python over real lists rather than one big template, so a
    missing block is an omitted section instead of a labelled empty one - an
    empty "WHAT ELSE WE KNOW" heading is noise the model has to reason past.
    """
    context = visible_context(contact.context)
    detail = str(contact.context.get(DETAIL_KEY) or "").strip() or _NO_DETAIL

    blocks = [
        _identity_block(system_prompt, contact),
        "\n".join(
            [
                "--- WHO YOU ARE CALLING ---",
                f"You are calling {contact.name.strip() or 'this person'}.",
                f"What this call is about: {detail}",
            ]
        ),
    ]

    if context:
        known = "\n".join(f"{_humanise(k)}: {v}" for k, v in context.items())
        blocks.append(f"--- WHAT ELSE WE KNOW ---\n{known}")

    if run_instruction and run_instruction.strip():
        blocks.append(f"--- FOR THIS RUN ---\n{run_instruction.strip()}")

    if collect_fields:
        blocks.append(
            "--- WHAT YOU MUST FIND OUT ---\n"
            "This is what the call is for. Ask for each of these, in this order, "
            "until you have them all:\n"
            + _fields_block(collect_fields)
            + "\n\nAsk about one at a time and wait for the answer before moving on - "
            "this is a phone call, and all of them in one breath is not a "
            "conversation. Record each answer as soon as you hear it. Do not guess "
            "a value, and do not ask for something you already have. Once you have "
            "them all, thank them and end the call."
        )

    blocks.append(_BEHAVIOUR)
    return "\n\n".join(blocks)


__all__ = [
    "DETAIL_KEY",
    "RESERVED_CONTEXT_KEYS",
    "CollectField",
    "PromptContact",
    "render_call_prompt",
    "visible_context",
]
