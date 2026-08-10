"""EngineGateway's conformance to the VoiceProvider protocol (VOICE_AGENT_PLATFORM.md P1)."""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.entities import DialFailure
from app.integrations.voice.engine import (
    EngineConnectionError,
    EngineGateway,
    EngineTimeoutError,
    classify_error,
)
from app.integrations.voice.protocol import (
    NotImplementedForProvider,
    VoiceCapability,
    VoiceProvider,
)


@pytest.fixture
def gateway() -> EngineGateway:
    return EngineGateway(api_key="sk_test_dummy")


def test_supports_declares_structured_extraction_and_live_events_only(
    gateway: EngineGateway,
) -> None:
    assert gateway.supports(VoiceCapability.STRUCTURED_EXTRACTION)
    assert gateway.supports(VoiceCapability.LIVE_EVENTS)
    assert not gateway.supports(VoiceCapability.RECORDING)
    assert not gateway.supports(VoiceCapability.CUSTOM_AGENT)


def test_cancel_call_raises_not_implemented(gateway: EngineGateway) -> None:
    with pytest.raises(NotImplementedForProvider):
        gateway.cancel_call("call_123")


class StubVoiceProvider:
    """A second, deliberately different `VoiceProvider` - no vendor behind it,
    just enough to prove the protocol is a real interface rather than a
    description of `EngineGateway`'s own shape. CLAUDE.md's Substitutability
    section calls for exactly this ("write the second adapter, even if it is
    only a stub for tests") - this is that stub, not a third vendor adapter.
    Its capabilities are the inverse of `EngineGateway`'s on purpose, so a test
    written against `VoiceProvider` can't accidentally pass by assuming
    CALL-E's specific `True`/`False` pattern.
    """

    def supports(self, capability: VoiceCapability) -> bool:
        return capability in (VoiceCapability.RECORDING, VoiceCapability.CUSTOM_AGENT)

    def start_call(self, **_: Any) -> dict[str, Any]:
        return {"id": "stub_call_1", "status": "queued"}

    def get_call(self, call_id: str) -> dict[str, Any]:
        return {"id": call_id, "status": "completed"}

    def cancel_call(self, call_id: str) -> None:
        return None

    def list_events(self, call_id: str, *, limit: int | None = None) -> dict[str, Any]:
        raise NotImplementedForProvider("StubVoiceProvider has no live event stream.")


def _accepts_any_voice_provider(provider: VoiceProvider) -> bool:
    """Exists only so both fixtures below can be passed through one
    protocol-typed parameter - the actual point of the test."""
    return provider.supports(VoiceCapability.STRUCTURED_EXTRACTION)


def test_both_providers_satisfy_the_same_protocol(gateway: EngineGateway) -> None:
    stub = StubVoiceProvider()
    assert _accepts_any_voice_provider(gateway) is True
    assert _accepts_any_voice_provider(stub) is False
    with pytest.raises(NotImplementedForProvider):
        stub.list_events("call_123")


def test_classify_error_maps_connection_error_to_provider_unavailable() -> None:
    # CalleConnectionError (raised by the SDK when a request fails before any
    # response comes back - DNS failure, connection refused, TLS error) has no
    # `.code` to look up, unlike CalleAPIError. It must still be classified as
    # a transient, worth-retrying failure rather than falling through to
    # DialFailure.INTERNAL, which retry policy treats as permanent.
    exc = EngineConnectionError("connection refused")
    assert classify_error(exc) is DialFailure.PROVIDER_UNAVAILABLE


def test_classify_error_still_maps_timeout_error_to_timed_out() -> None:
    exc = EngineTimeoutError("timed out")
    assert classify_error(exc) is DialFailure.TIMED_OUT
