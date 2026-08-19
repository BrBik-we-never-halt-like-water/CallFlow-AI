"""Phone-number handling, and the one gate that still stands before a dial.

Masking (`mask`) and the suppression key (`phone_hash`) are the load-bearing
parts. `is_e164`/`assert_e164` remain because uploads and the safety endpoint
still validate what a person typed - but they are input validation, not a dial
gate, and nothing here refuses a dial on formatting any more.

**The cost and testing guards are gone on purpose.** The allowlist, the per-run
ceiling, the rate limiter, the daily budget and per-teammate credits were all
removed at the product owner's direction: a replacement security layer is being
designed, and half-removed guards spread across five files are worse than none.
The suppression list was deliberately kept and is the only reason this function
still exists - "never call me again" is a promise to a person, not a spending
cap, so it survives a rewrite of everything around it.
"""

from __future__ import annotations

import hashlib
import re
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





def check_dial_allowed(
    phone: str,
    *,
    is_suppressed: bool = False,
) -> GateResult:
    """The last check before a number is dialled: has this person opted out?

    Takes the suppression verdict as a plain value rather than looking it up -
    this module does no I/O, by design (CLAUDE.md §3, S), which is what keeps it
    unit-testable without a database.

    Every other guard this function used to apply - the allowlist, the per-run
    ceiling, the rate limiter's budget, per-teammate credits, and E.164
    validation - was removed deliberately (see the module docstring). What
    remains is the one check that protects a person rather than a bill, and it
    still fails closed: a caller that cannot resolve the suppression verdict
    must pass `is_suppressed=True`, not omit it.
    """
    if is_suppressed:
        return GateResult(False, f"{mask(phone)} opted out and is on the suppression list")

    return GateResult(True)
