"""Phone-number guardrails.

Outbound calling requires E.164 formatting, masked numbers in any summary
output, and an explicit consent step before dialing. Everything here enforces
that, and fails closed.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.config import config

E164 = re.compile(r"^\+[1-9]\d{7,14}$")


def is_e164(phone: str) -> bool:
    return bool(E164.match(phone))


def mask(phone: str) -> str:
    """Mask a number for logs, transcripts, and user-facing summaries.

    At least half the characters are always hidden, so short or malformed
    inputs cannot leak most of a real number through an error message.
    """
    if len(phone) <= 6:
        return "***"

    # Reveal at most 3 leading and 3 trailing chars, and never more than half.
    reveal = min(3, len(phone) // 4)
    hidden = len(phone) - (2 * reveal)
    return f"{phone[:reveal]}{'*' * hidden}{phone[-reveal:]}"


def phone_hash(phone: str) -> str:
    """The suppression list's enforcement key.

    SHA-256 over the E.164 number plus a per-deployment pepper, computed here
    so the pepper never enters the database and a leaked table alone can't be
    reversed into phone numbers.
    """
    return hashlib.sha256(f"{phone}{config.phone_hash_pepper}".encode()).hexdigest()


def assert_e164(phone: str) -> str:
    if not is_e164(phone):
        raise ValueError(
            f"Phone number must be E.164 (e.g. +15555550100), got: {mask(phone)}"
        )
    return phone


@dataclass(frozen=True)
class GateResult:
    allowed: bool
    reason: str = ""


@dataclass(frozen=True)
class EffectiveSafety:
    """An organisation's safety numbers, with the deployment defaults already
    merged in - the one place that merge happens, so display (Settings ->
    Safety, the run composer's guard bar) and enforcement (`check_dial_allowed`,
    the rate limiter) can never resolve two different answers for the same org."""

    allowlist: frozenset[str]
    max_calls_per_run: int
    calls_per_window: int
    window_minutes: int
    daily_budget: int


def resolve_safety_settings(
    *,
    allowlist: Iterable[str] | None,
    max_calls_per_run: int | None,
    calls_per_window: int | None,
    window_minutes: int | None,
    daily_budget: int | None,
) -> EffectiveSafety:
    """Merge an organisation's override onto the deployment's env-var defaults.

    Every field is `is not None`-checked, never truthiness - an org's explicit
    choice must win even when that choice is `[]` or `0`. An empty allowlist is
    a real, meaningful, intentional value ("no restriction, any number may be
    dialled"; Settings -> Safety says exactly this), not "unset" - a bare `or`
    here previously reinstated the deployment's own `CALLFLOW_ALLOWLIST` the
    moment an org cleared theirs, silently enforcing a restriction the org had
    just turned off.
    """
    return EffectiveSafety(
        allowlist=frozenset(allowlist) if allowlist is not None else frozenset(config.allowlist),
        max_calls_per_run=(
            max_calls_per_run if max_calls_per_run is not None else config.max_calls_per_run
        ),
        calls_per_window=(
            calls_per_window if calls_per_window is not None else config.rate_limit_calls
        ),
        window_minutes=(
            window_minutes
            if window_minutes is not None
            else config.rate_limit_window_seconds // 60
        ),
        daily_budget=daily_budget if daily_budget is not None else config.daily_call_budget,
    )


def check_dial_allowed(
    phone: str,
    calls_made_so_far: int,
    *,
    is_suppressed: bool = False,
    max_calls_per_run: int | None = None,
    allowlist: Iterable[str] | None = None,
) -> GateResult:
    """Final gate before a number is dialed.

    Takes the suppression verdict, the per-run ceiling, and the allowlist as plain
    values rather than looking any of them up itself - this module does no I/O, by
    design (CLAUDE.md §3, S). `max_calls_per_run`/`allowlist` default to the
    deployment's env-var config when omitted; the caller passes an organisation's
    own override (`org_safety_settings`) when one exists, resolved once per run,
    the same way the suppression verdict already is.
    """
    if is_suppressed:
        return GateResult(False, f"{mask(phone)} opted out and is on the suppression list")

    if not is_e164(phone):
        return GateResult(False, f"not a valid E.164 number ({mask(phone)})")

    ceiling = max_calls_per_run if max_calls_per_run is not None else config.max_calls_per_run
    if calls_made_so_far >= ceiling:
        return GateResult(
            False,
            f"per-run call ceiling reached ({ceiling}). "
            "Raise it in Settings → Safety to continue.",
        )

    # A non-empty allowlist means development mode: only these numbers are dialable.
    effective_allowlist = allowlist if allowlist is not None else config.allowlist
    if effective_allowlist and phone not in effective_allowlist:
        return GateResult(False, f"{mask(phone)} is not on the allowlist")

    return GateResult(True)
