"""Which STT, TTS and LLM a call runs on, resolved from the job's own metadata.

A voice agent stores provider names and credentials; this turns them into
plugin instances. It is the whole of the "BYO stack" promise in one file: a new
vendor is an entry in a registry here and nothing else changes.

**Plugins are imported inside their factory, not at module scope.** Each
`livekit-plugins-*` package pulls a substantial dependency tree, and a
deployment whose organisations all use Sarvam should not need Deepgram
installed to boot. It also means this module imports - and so the registry can
be tested - with no vendor packages present at all.

There is deliberately no CallFlow-owned `Protocol` over the plugin types yet.
`livekit-agents` already declares `stt.STT`/`tts.TTS`/`llm.LLM`, and wrapping
them before a working call exists would be inventing an abstraction from one
example - the same discipline `apps/api`'s `voice/protocol.py` documents having
learned the hard way.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# provider name -> factory. `Any` rather than the plugin base classes because
# importing those here would defeat the lazy import below.
Factory = Callable[..., Any]


class UnknownProvider(Exception):
    """Raised instead of silently falling back to a default.

    A call that quietly runs on the wrong voice is worse than one that refuses
    to start: the operator gets a transcript that looks fine and never learns
    the agent they configured was not the agent that spoke.
    """

    def __init__(self, kind: str, name: str, known: list[str]) -> None:
        super().__init__(
            f"No {kind} provider named '{name}'. "
            f"Configured providers are: {', '.join(known) or 'none'}."
        )


class MissingPlugin(Exception):
    """A known provider whose package is not installed in this deployment."""

    def __init__(self, name: str, extra: str) -> None:
        super().__init__(
            f"The '{name}' plugin is not installed. "
            f"Install it with: pip install -e '.[{extra}]'"
        )


@dataclass(frozen=True)
class AgentSpec:
    """The provider choices for one call, as `apps/api` sends them.

    Mirrors the `voice_agents` columns rather than the whole row - this worker
    has no business knowing an agent's name or who created it.
    """

    stt_provider: str
    tts_provider: str
    llm_provider: str
    llm_model: str | None = None
    voice_id: str | None = None
    language: str | None = None
    stt_api_key: str | None = None
    tts_api_key: str | None = None
    llm_api_key: str | None = None

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> AgentSpec:
        agent = metadata.get("voice_agent") or {}
        return cls(
            stt_provider=str(agent.get("stt_provider") or "").lower(),
            tts_provider=str(agent.get("tts_provider") or "").lower(),
            llm_provider=str(agent.get("llm_provider") or "").lower(),
            llm_model=agent.get("llm_model"),
            voice_id=agent.get("voice_id"),
            # The contact's language beats the agent's default: an agent
            # configured for Hindi still has to answer a contact flagged as
            # English.
            language=metadata.get("language") or agent.get("language"),
            stt_api_key=agent.get("stt_api_key"),
            tts_api_key=agent.get("tts_api_key"),
            llm_api_key=agent.get("llm_api_key"),
        )


def _sarvam_stt(spec: AgentSpec) -> Any:
    try:
        from livekit.plugins import sarvam
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise MissingPlugin("sarvam", "sarvam") from exc
    return sarvam.STT(language=spec.language or "en-IN", api_key=spec.stt_api_key)


def _sarvam_tts(spec: AgentSpec) -> Any:
    try:
        from livekit.plugins import sarvam
    except ImportError as exc:  # pragma: no cover
        raise MissingPlugin("sarvam", "sarvam") from exc
    return sarvam.TTS(
        target_language_code=spec.language or "en-IN",
        speaker=spec.voice_id or "anushka",
        api_key=spec.tts_api_key,
    )


def _deepgram_stt(spec: AgentSpec) -> Any:
    """The second STT vendor, which is the point of it existing (P1-T11).

    An abstraction with one implementation is not an abstraction - CLAUDE.md's
    Substitutability rule. Deepgram proves the registry actually swaps.
    """
    try:
        from livekit.plugins import deepgram
    except ImportError as exc:  # pragma: no cover
        raise MissingPlugin("deepgram", "deepgram") from exc
    return deepgram.STT(model="nova-3", language=spec.language or "en", api_key=spec.stt_api_key)


def _elevenlabs_tts(spec: AgentSpec) -> Any:
    """The second TTS vendor, for the same reason as Deepgram above."""
    try:
        from livekit.plugins import elevenlabs
    except ImportError as exc:  # pragma: no cover
        raise MissingPlugin("elevenlabs", "elevenlabs") from exc
    return elevenlabs.TTS(voice_id=spec.voice_id, api_key=spec.tts_api_key)


def _openrouter_llm(spec: AgentSpec) -> Any:
    """OpenRouter through the OpenAI plugin's own factory.

    There is no separate OpenRouter plugin package - `with_openrouter()` on the
    OpenAI plugin is the supported wiring (ADR-7). `llm_model` is required
    because one OpenRouter key proxies many models, so the credential alone does
    not say which to run.
    """
    try:
        from livekit.plugins import openai
    except ImportError as exc:  # pragma: no cover
        raise MissingPlugin("openrouter", "openai") from exc
    if not spec.llm_model:
        raise ValueError(
            "This voice agent uses OpenRouter but has no model set. "
            "One key proxies many models, so pick one on the agent."
        )
    return openai.LLM.with_openrouter(model=spec.llm_model, api_key=spec.llm_api_key)


def _openai_llm(spec: AgentSpec) -> Any:
    try:
        from livekit.plugins import openai
    except ImportError as exc:  # pragma: no cover
        raise MissingPlugin("openai", "openai") from exc
    return openai.LLM(model=spec.llm_model or "gpt-4o-mini", api_key=spec.llm_api_key)


STT_PROVIDERS: dict[str, Factory] = {
    "sarvam": _sarvam_stt,
    "deepgram": _deepgram_stt,
}

TTS_PROVIDERS: dict[str, Factory] = {
    "sarvam": _sarvam_tts,
    "elevenlabs": _elevenlabs_tts,
}

LLM_PROVIDERS: dict[str, Factory] = {
    "openrouter": _openrouter_llm,
    "openai": _openai_llm,
}


def _resolve(registry: dict[str, Factory], kind: str, name: str, spec: AgentSpec) -> Any:
    factory = registry.get(name)
    if factory is None:
        raise UnknownProvider(kind, name, sorted(registry))
    return factory(spec)


@dataclass
class Pipeline:
    stt: Any
    tts: Any
    llm: Any


def build_pipeline(spec: AgentSpec) -> Pipeline:
    """Resolve all three providers, or raise naming the one that failed.

    All three are resolved before any is used, so a misconfigured TTS is
    discovered now rather than after the contact has already said hello.
    """
    return Pipeline(
        stt=_resolve(STT_PROVIDERS, "speech-to-text", spec.stt_provider, spec),
        tts=_resolve(TTS_PROVIDERS, "text-to-speech", spec.tts_provider, spec),
        llm=_resolve(LLM_PROVIDERS, "LLM", spec.llm_provider, spec),
    )


__all__ = [
    "LLM_PROVIDERS",
    "STT_PROVIDERS",
    "TTS_PROVIDERS",
    "AgentSpec",
    "MissingPlugin",
    "Pipeline",
    "UnknownProvider",
    "build_pipeline",
]
