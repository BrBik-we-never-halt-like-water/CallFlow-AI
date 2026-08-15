"""Pipeline wiring: the right plugin for the providers a voice agent stores.

This is the test the BYO-stack claim rests on. If the registry silently falls
back, or picks one vendor while the agent says another, an operator gets a
transcript that looks fine from an agent they did not configure.

No live room and no vendor packages: the factories are substituted, which is
exactly what makes the registry an abstraction rather than a hard-coded pair.
"""

from __future__ import annotations

from typing import Any

import pytest

from app import pipeline as pipeline_module
from app.pipeline import (
    LLM_PROVIDERS,
    STT_PROVIDERS,
    TTS_PROVIDERS,
    AgentSpec,
    UnknownProvider,
    build_pipeline,
)


class FakePlugin:
    """Stands in for a vendor plugin, remembering which one it claims to be."""

    def __init__(self, vendor: str, spec: AgentSpec) -> None:
        self.vendor = vendor
        self.spec = spec


@pytest.fixture(autouse=True)
def _fake_registries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap every real factory for one that records instead of importing.

    Substituting the whole registry rather than patching imports is deliberate:
    it proves `build_pipeline` reads the registry rather than hard-coding a
    vendor, which is the property under test.
    """
    for registry, kinds in (
        (STT_PROVIDERS, ("sarvam", "deepgram")),
        (TTS_PROVIDERS, ("sarvam", "elevenlabs")),
        (LLM_PROVIDERS, ("openrouter", "openai")),
    ):
        for name in kinds:
            monkeypatch.setitem(
                registry, name, lambda spec, vendor=name: FakePlugin(vendor, spec)
            )


def _spec(**overrides: Any) -> AgentSpec:
    base: dict[str, Any] = {
        "stt_provider": "sarvam",
        "tts_provider": "sarvam",
        "llm_provider": "openrouter",
        "llm_model": "anthropic/claude-sonnet-4",
    }
    base.update(overrides)
    return AgentSpec(**base)


def test_the_configured_providers_are_the_ones_built() -> None:
    built = build_pipeline(_spec())

    assert built.stt.vendor == "sarvam"
    assert built.tts.vendor == "sarvam"
    assert built.llm.vendor == "openrouter"


def test_a_second_vendor_swaps_cleanly() -> None:
    """The whole point of the registry (P1-T11). An abstraction with one
    implementation is not an abstraction."""
    built = build_pipeline(_spec(stt_provider="deepgram", tts_provider="elevenlabs"))

    assert built.stt.vendor == "deepgram"
    assert built.tts.vendor == "elevenlabs"


def test_stt_and_tts_can_come_from_different_vendors() -> None:
    """Nothing forces one vendor across the whole pipeline - an org can use
    Deepgram's recognition with Sarvam's Indic voices."""
    built = build_pipeline(_spec(stt_provider="deepgram", tts_provider="sarvam"))

    assert built.stt.vendor == "deepgram"
    assert built.tts.vendor == "sarvam"


@pytest.mark.parametrize(
    "field,kind",
    [
        ("stt_provider", "speech-to-text"),
        ("tts_provider", "text-to-speech"),
        ("llm_provider", "LLM"),
    ],
)
def test_an_unknown_provider_refuses_rather_than_falling_back(field: str, kind: str) -> None:
    """A silent default would run the call on the wrong voice and never say so."""
    with pytest.raises(UnknownProvider) as caught:
        build_pipeline(_spec(**{field: "not-a-real-vendor"}))

    message = str(caught.value)
    assert kind in message
    assert "not-a-real-vendor" in message
    # Names the alternatives rather than only refusing (CLAUDE.md §5).
    assert "Configured providers are" in message


def test_an_unset_provider_is_refused_too() -> None:
    """An agent half-configured in the Agentic tab must not dial. The schema
    allows the null, so this is where it gets caught."""
    with pytest.raises(UnknownProvider):
        build_pipeline(_spec(stt_provider=""))


def test_every_provider_receives_its_own_credential_and_settings() -> None:
    spec = _spec(
        voice_id="anushka",
        language="hi-IN",
        stt_api_key="stt-key",
        tts_api_key="tts-key",
        llm_api_key="llm-key",
    )
    built = build_pipeline(spec)

    assert built.stt.spec.stt_api_key == "stt-key"
    assert built.tts.spec.voice_id == "anushka"
    assert built.llm.spec.llm_model == "anthropic/claude-sonnet-4"
    assert built.tts.spec.language == "hi-IN"


# --- reading the job's metadata ----------------------------------------------


def test_spec_is_read_from_the_metadata_apps_api_sends() -> None:
    spec = AgentSpec.from_metadata(
        {
            "language": "en-IN",
            "voice_agent": {
                "stt_provider": "Sarvam",
                "tts_provider": "SARVAM",
                "llm_provider": "OpenRouter",
                "llm_model": "anthropic/claude-sonnet-4",
                "voice_id": "anushka",
            },
        }
    )

    # Case-folded: a provider name typed into the Agentic tab should not have to
    # match the registry's capitalisation to work.
    assert spec.stt_provider == "sarvam"
    assert spec.tts_provider == "sarvam"
    assert spec.llm_provider == "openrouter"
    assert spec.voice_id == "anushka"


def test_the_contacts_language_beats_the_agents_default() -> None:
    """An agent configured for Hindi still has to answer a contact flagged
    English - the per-contact value is the more specific one."""
    spec = AgentSpec.from_metadata(
        {"language": "en-IN", "voice_agent": {"language": "hi-IN", "stt_provider": "sarvam"}}
    )
    assert spec.language == "en-IN"


def test_metadata_with_no_voice_agent_yields_a_spec_that_refuses_to_build() -> None:
    """Rather than a spec full of empty strings that fails somewhere later."""
    spec = AgentSpec.from_metadata({})
    with pytest.raises(UnknownProvider):
        build_pipeline(spec)


def test_the_registries_are_the_only_place_a_vendor_is_named() -> None:
    """Adding a vendor must be one registry entry, not an edit in five files -
    CLAUDE.md's Open/Closed section. If this fails, someone hard-coded a branch."""
    source = (pipeline_module.__file__ or "")
    assert source, "pipeline module has no source file"
    with open(source, encoding="utf-8") as handle:
        body = handle.read()

    # `build_pipeline` itself must not mention any vendor by name.
    start = body.index("def build_pipeline")
    end = body.index("__all__")
    for vendor in ("sarvam", "deepgram", "elevenlabs", "openrouter", "openai"):
        assert vendor not in body[start:end].lower(), f"{vendor} is hard-coded in build_pipeline"
