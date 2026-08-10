"""The `VoiceProvider` protocol every voice adapter conforms to.

CALL-E (`engine.py`) is the only *production* implementation today.
`tests/test_engine.py`'s `StubVoiceProvider` is the second, non-vendor one
CLAUDE.md's Substitutability section calls for ("write the second adapter,
even if it is only a stub for tests") - it exists so this protocol is proven
to fit more than one shape of provider, not just described in terms of
`EngineGateway`'s own methods.

`campaign_runner.py` still imports `EngineGateway` by name rather than this
protocol, though - the return type below is still `JsonObject`, the raw,
CALL-E-shaped payload, not a normalised type, because designing that
normalisation from a single *real* vendor's data would be guessing, not
abstracting. That switch-over happens once a second production adapter
(Twilio or Plivo, `VOICE_AGENT_PLATFORM.md` P5) exists to prove the real shape.

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

    def list_events(self, call_id: str, *, limit: int | None = None) -> JsonObject:
        """Raises `NotImplementedForProvider` if this provider has no per-turn
        event stream - check `supports(VoiceCapability.LIVE_EVENTS)` first.
        Declaring the capability without a method to exercise it would leave a
        caller with nothing to call once it's typed against this protocol
        instead of the concrete adapter."""
        ...


__all__ = ["NotImplementedForProvider", "VoiceCapability", "VoiceProvider"]
