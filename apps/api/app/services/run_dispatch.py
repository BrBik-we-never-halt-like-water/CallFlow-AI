"""Turning a run's choices into what the dialer needs.

This is the seam that was missing. `RunDialer` has always accepted the lines to
dial from and the `voice_agent` metadata dict the worker reads, and its own
docstrings said they were "resolved by the caller" - but nothing ever resolved
them, so every contact was refused before the phone rang. The dial path existed;
this is the piece that fills it.

`services/`, not `domain/`, because it does real I/O: two repository reads and a
decryption per provider. What it produces is inert data, so everything downstream
of it stays pure and testable.

Fails closed, and every refusal names the thing to go and fix. A run that cannot
be resolved must not start: the alternative is a phone ringing with no worker
able to answer it, which is a person saying "hello?" into silence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from app.core.crypto import CredentialsNotConfigured, decrypt
from app.core.platform_keys import platform_key
from app.database.repositories import ai_provider_credentials as ai_credentials_repo
from app.database.repositories import telephony_numbers as numbers_repo
from app.database.repositories import voice_agents as voice_agents_repo
from app.domain.entities import CollectField, RunAgent
from app.domain.number_allocation import DialLine
from app.domain.numbers import NumberStatus, is_diallable

log = logging.getLogger("app.services.run_dispatch")

JsonObject = dict[str, Any]

#: The three legs a call runs on. Named once so adding a fourth is one edit.
_LEGS = ("stt", "tts", "llm")


class RunNotDispatchable(Exception):
    """A run cannot start, with the sentence to show the person starting it.

    Carries user-facing text on purpose: every construction site here already
    knows exactly what is missing, and re-deriving that in the route would mean
    the route knowing about agents, numbers and credentials all over again.
    """


@dataclass(frozen=True)
class RunPlan:
    """Everything `RunDialer` needs, resolved once per run.

    Resolved once rather than per contact for the same reason the allowlist and
    the suppression set are: a hundred contacts should not mean a hundred
    credential decryptions.
    """

    agent: RunAgent
    lines: tuple[DialLine, ...]
    #: The opaque dict the worker reads through `AgentSpec.from_metadata`. Opaque
    #: on purpose - it holds decrypted keys, so nothing but the dialer and the
    #: worker should look inside it, and it never reaches a log line.
    voice_agent: JsonObject
    allocation_strategy: str
    run_instruction: str | None


def _collect_fields(raw: object) -> list[CollectField]:
    """`collect_fields` as typed values.

    Tolerant of a non-list because rows written before the column existed read
    back as anything: the jsonb codec gives a real list, but a legacy row could
    hold a string, and a run should not fail on an agent that simply predates the
    feature.
    """
    if not isinstance(raw, list):
        return []
    fields: list[CollectField] = []
    for item in raw:
        if isinstance(item, dict) and item.get("key"):
            fields.append(CollectField(**item))
    return fields


def _join_human(items: list[str]) -> str:
    """`a`, `a and b`, `a, b and c` - the same shape `triage.py` uses."""
    if len(items) == 1:
        return items[0]
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _decrypted_key(row: asyncpg.Record | None) -> str | None:
    """One provider's API key, or None when it is not connected.

    A stored-but-undecryptable key returns None rather than raising: the caller
    turns a missing key into a refusal naming the provider, which is a better
    message than "decryption failed" and does not leak whether a row exists.
    """
    if row is None:
        return None
    try:
        return decrypt(row["api_key_encrypted"])
    except (CredentialsNotConfigured, KeyError):
        log.warning("a stored provider credential could not be decrypted")
        return None


async def _voice_agent_metadata(
    conn: asyncpg.Connection, *, org_id: UUID, agent: asyncpg.Record
) -> JsonObject:
    """The provider half of the dispatch, shaped for the worker.

    The key names here are the contract `AgentSpec.from_metadata()` reads on the
    other side of the process boundary, and `test_dispatch_contract.py` exists
    because the two halves were once written apart and every dispatched job died
    resolving providers. Change a name here and that test is what catches it.
    """
    metadata: JsonObject = {
        "stt_provider": agent["stt_provider"],
        "tts_provider": agent["tts_provider"],
        "llm_provider": agent["llm_provider"],
        "llm_model": agent["llm_model"],
        "voice_id": agent["voice_id"],
    }

    # Whose key paid for each leg, so a run on CallFlow's own keys is
    # attributable afterwards rather than indistinguishable from one on the
    # customer's. Names and providers only - never a key, not even partially.
    on_platform_keys: list[str] = []

    for leg in _LEGS:
        provider = agent[f"{leg}_provider"]
        if not provider:
            continue
        row = await ai_credentials_repo.get_credential(conn, org_id, provider)
        key = _decrypted_key(row)
        if key is None:
            # The organisation has connected nothing usable for this provider,
            # so CallFlow's own key carries the call. An org key always wins:
            # connecting one in Integrations moves the spend back to the
            # customer with no other change (`core/platform_keys.py`).
            key = platform_key(provider)
            if key is not None:
                on_platform_keys.append(f"{leg}:{provider}")
        metadata[f"{leg}_api_key"] = key

    if on_platform_keys:
        log.info(
            "org %s is dialling on CallFlow's own provider keys for %s",
            org_id,
            ", ".join(on_platform_keys),
        )

    return metadata


def _missing_legs(agent: asyncpg.Record) -> list[str]:
    return [leg for leg in _LEGS if not agent[f"{leg}_provider"]]


async def resolve_run_plan(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    voice_agent_id: UUID,
    number_ids: list[UUID],
    allocation_strategy: str = "round_robin",
    run_instruction: str | None = None,
) -> RunPlan:
    """What this run dials with, or a refusal saying what to fix.

    Every read goes through the caller's own RLS-scoped connection, so an agent
    or a number belonging to another organisation simply is not found - the
    refusal is then "pick one" rather than a permission error that confirms the
    row exists.
    """
    agent_row = await voice_agents_repo.get_org_agent(conn, org_id, voice_agent_id)
    if agent_row is None:
        raise RunNotDispatchable(
            "That agent no longer exists. Pick another one, or build a new agent."
        )

    missing = _missing_legs(agent_row)
    if missing:
        legs = ", ".join(missing)
        raise RunNotDispatchable(
            f"This agent has no {legs} provider set. Finish setting it up in "
            "Agents, then start the run again."
        )

    if not number_ids:
        raise RunNotDispatchable(
            "Pick at least one number for this run to call from."
        )

    rows = await numbers_repo.list_by_ids(conn, org_id, number_ids)
    found = {row["id"] for row in rows}
    unknown = [str(n) for n in number_ids if n not in found]
    if unknown:
        # RLS hid them, or they were deleted between picking and starting.
        raise RunNotDispatchable(
            "One of the numbers picked for this run is no longer available. "
            "Choose the numbers again."
        )

    lines: list[DialLine] = []
    unverified: list[str] = []
    for row in rows:
        status = NumberStatus(row["status"])
        trunk = row["livekit_outbound_trunk_id"]
        # Both conditions, not either: `is_diallable` is the status rule, and the
        # trunk is what actually carries the call. A verified row with no trunk
        # would be a provisioning bug, and dialling it would fail at LiveKit with
        # the phone already ringing.
        if is_diallable(status) and trunk:
            lines.append(
                DialLine(
                    number_id=str(row["id"]),
                    phone_e164=row["phone_e164"],
                    outbound_trunk_id=trunk,
                )
            )
        else:
            unverified.append(row["phone_e164"])

    if not lines:
        raise RunNotDispatchable(
            "None of the numbers picked for this run is connected yet. Connect "
            "one in Integrations, then start the run again."
        )

    if unverified:
        # Not a refusal: the run has somewhere to dial from, and stopping it
        # because one of several numbers is unconnected would be worse than
        # proceeding on the ones that work. Logged as masked, never printed.
        log.info(
            "run skipping %d unconnected number(s) of %d picked",
            len(unverified),
            len(rows),
        )

    agent = RunAgent(
        id=str(agent_row["id"]),
        name=agent_row["name"],
        system_prompt=agent_row["system_prompt"],
        collect_fields=_collect_fields(agent_row["collect_fields"]),
    )

    voice_agent = await _voice_agent_metadata(conn, org_id=org_id, agent=agent_row)

    # Refused here rather than discovered by the worker mid-call. Without a key
    # the runtime cannot build that leg of the pipeline, so the call would
    # connect and the contact would hear silence - the worst possible place to
    # find out. Names the provider, because "connect Sarvam" is actionable and
    # "the run failed" is not.
    keyless = [
        agent_row[f"{leg}_provider"]
        for leg in _LEGS
        if agent_row[f"{leg}_provider"] and not voice_agent.get(f"{leg}_api_key")
    ]
    if keyless:
        raise RunNotDispatchable(
            f"No API key for {_join_human(sorted(set(keyless)))}. Connect it in "
            "Integrations, then start the run again."
        )

    return RunPlan(
        agent=agent,
        lines=tuple(lines),
        voice_agent=voice_agent,
        allocation_strategy=allocation_strategy,
        run_instruction=run_instruction,
    )


__all__ = ["RunNotDispatchable", "RunPlan", "resolve_run_plan"]
