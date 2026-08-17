"""Carriers an organisation brings its own account with.

One module per vendor, and nothing outside this package speaks a carrier's
vocabulary. Both vendors authenticate with an id/token pair over HTTP Basic and
return their own error shapes, so the two things worth sharing - what a
configured number looks like, and what a failure is - live here rather than
being invented twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Self, runtime_checkable


class CarrierError(Exception):
    """A carrier refused or could not be reached.

    Carries the vendor's own message because it is the only thing that says
    *why* - "The requested resource was not found" against a phone number SID
    means something an operator can act on. It is surfaced through
    `telephony_provisioning.last_error`, so it must read as an instruction and
    never as a stack trace (CLAUDE.md §5).
    """

    def __init__(self, provider: str, action: str, detail: str) -> None:
        self.provider = provider
        self.action = action
        self.detail = detail
        super().__init__(f"{provider} could not {action}: {detail}")


@dataclass(frozen=True)
class CarrierTrunk:
    """What the carrier created, in CallFlow's own terms.

    `termination_domain` is Plivo-only - Twilio has no analog, and a caller
    that special-cases on `provider` instead of on this being `None` has
    reintroduced the vendor knowledge this package exists to contain.
    """

    provider: str
    trunk_id: str
    termination_domain: str | None = None
    auth_username: str | None = None
    auth_password: str | None = None
    # Everything the carrier told us that CallFlow has no column for. Kept so a
    # failed provisioning run can be diagnosed from the row alone.
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CarrierNumber:
    """One number an organisation already owns on its carrier account.

    `number_ref` is whatever that vendor needs to address the number later, and
    the vendors disagree: Twilio wants a Phone Number SID, Telnyx a number id,
    Plivo and Vonage the E.164 itself. Carrying it alongside `e164` means the
    caller can hand a chosen number straight back to `configure_number()`
    without knowing which vendor convention applies.

    `capabilities` is what the number can actually do. A number without `voice`
    cannot be dialled from, and offering it would be a run that fails at the
    carrier for a reason nobody could see in the picker.
    """

    provider: str
    e164: str
    number_ref: str
    label: str | None = None
    capabilities: frozenset[str] = field(default_factory=frozenset)

    @property
    def can_call(self) -> bool:
        # Empty means the vendor did not say. Treated as capable rather than
        # hiding a number someone can see in their own carrier dashboard.
        return not self.capabilities or "voice" in self.capabilities


@runtime_checkable
class Carrier(Protocol):
    """What every carrier adapter provides.

    Declared rather than merely tested: conformance used to be pinned only by
    `test_telephony_carriers.py`'s "same entry points" parametrisation, which
    catches a missing method but cannot help a caller reason about the set. A
    new vendor now fails type-checking rather than a test three files away.
    """

    outbound_transport: str | None

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, *exc: object) -> None: ...

    async def list_numbers(self) -> list[CarrierNumber]: ...

    async def configure_number(
        self,
        *,
        number_ref: str,
        livekit_sip_host: str,
        label: str,
        auth_username: str,
        auth_password: str,
    ) -> CarrierTrunk: ...

    @staticmethod
    def allowed_addresses() -> list[str]: ...


def sip_uri(host: str, transport: str = "tcp") -> str:
    """The origination URI a carrier is told to send inbound calls to.

    The transport parameter is not decoration: Plivo rejects a URI without one,
    and Twilio's own documented example includes it. Written once here so the
    two adapters cannot drift on the detail most likely to silently break
    inbound audio.
    """
    bare = host.removeprefix("sip:").rstrip("/")
    return f"sip:{bare};transport={transport}"


__all__ = ["Carrier", "CarrierError", "CarrierNumber", "CarrierTrunk", "sip_uri"]
