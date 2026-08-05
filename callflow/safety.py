"""Phone-number guardrails.

Outbound calling requires E.164 formatting, masked numbers in any summary
output, and an explicit consent step before dialing. Everything here enforces
that, and fails closed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import config

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


def check_dial_allowed(phone: str, calls_made_so_far: int) -> GateResult:
    """Final gate before a number is dialed.

    Called once per contact, immediately before run_call.
    """
    if not is_e164(phone):
        return GateResult(False, f"not a valid E.164 number ({mask(phone)})")

    if calls_made_so_far >= config.max_calls_per_run:
        return GateResult(
            False,
            f"per-run call ceiling reached ({config.max_calls_per_run}). "
            "Raise CALLFLOW_MAX_CALLS_PER_RUN to continue.",
        )

    # A non-empty allowlist means development mode: only these numbers are dialable.
    if config.allowlist and phone not in config.allowlist:
        return GateResult(False, f"{mask(phone)} is not in CALLFLOW_ALLOWLIST")

    return GateResult(True)
