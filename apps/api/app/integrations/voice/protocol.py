"""The `VoiceProvider` protocol every voice adapter conforms to.

**Nothing implements this today.** CALL-E was the only production
implementation and it has been removed along with its stub adapter; the
LiveKit client that replaces it lands in RUNBOOK_HET_PART_1.md P1-T5/P1-T6.
The protocol is kept rather than deleted because it is the shape the new
adapters are meant to fit, and because its `supports()`/`VoiceCapability`
split is the pattern ADR-1 says survives the migration.

Treat the method signatures below as a starting point, not a settled
contract: the return type is still `JsonObject`, a raw vendor-shaped payload
rather than a normalised type, because designing that normalisation from a
single vendor's data would be guessing rather than abstracting. Settle it
once LiveKit plus a second real carrier prove the actual shape - the same
"don't abstract before a second implementation exists" discipline this file
already documents.

`VoiceProvider` is a structural `Protocol`: an adapter conforms by having the
right methods, not by inheriting from anything here.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol

JsonObject = dict[str, Any]


class VoiceCapability(str, Enum):
    """What an adapter can actually do. Checked with `supports()` before an
    optional feature is used, rather than assuming every provider implements
    everything - CLAUDE.md's Interface Segregation: prefer `supports(capability)`
    over one fat interface every adapter must implement fully."""

    RECORDING = "recording"
    STRUCTURED_EXTRACTION = "structured_extraction"
    LIVE_EVENTS = "live_events"
    CUSTOM_AGENT = "custom_agent"


class NotImplementedForProvider(NotImplementedError):
    """Raised by a capability a caller didn't check `supports()` for first."""


class VoiceProvider(Protocol):
    def supports(self, capability: VoiceCapability) -> bool: ...

    def start_call(
        self,
        *,
        task: str,
        phone: str,
        result_schema: JsonObject | None = None,
        metadata: JsonObject | None = None,
        webhook_url: str | None = None,
        idempotency_key: str | None = None,
        region: str | None = None,
        language: str | None = None,
    ) -> JsonObject: ...

    def get_call(self, call_id: str) -> JsonObject: ...

    def cancel_call(self, call_id: str) -> None:
        """Raises `NotImplementedForProvider` if this provider has no way to
        cancel an in-flight call - CALL-E's SDK doesn't expose one today."""
        ...

    def list_events(
        self, call_id: str, *, cursor: str | None = None, limit: int | None = None
    ) -> JsonObject:
        """Raises `NotImplementedForProvider` if this provider has no per-turn
        event stream - check `supports(VoiceCapability.LIVE_EVENTS)` first.
        Declaring the capability without a method to exercise it would leave a
        caller with nothing to call once it's typed against this protocol
        instead of the concrete adapter."""
        ...


__all__ = ["NotImplementedForProvider", "VoiceCapability", "VoiceProvider"]
