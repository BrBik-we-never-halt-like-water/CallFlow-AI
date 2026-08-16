"""Which STT, TTS and LLM a call runs on, resolved from the job's own metadata.

A voice agent stores provider names and credentials; this turns them into plugin
instances. It is the whole of the "BYO stack" promise in one file: a new vendor
is a row in a registry here and nothing else changes.

**Plugins are imported inside the factory, not at module scope.** Each
`livekit-plugins-*` package pulls a substantial dependency tree, and a deployment
whose organisations all use Sarvam should not need Deepgram installed to boot. It
also means this module imports - and so the registry can be tested - with no
vendor packages present at all.

**Arguments are filtered against each plugin's real signature.** There are 40-odd
vendors here and their constructors disagree: some take `language`, some
`language_code`, some neither; ElevenLabs wants `voice_id` where Cartesia wants
`voice`. Rather than hand-maintaining 40 argument lists that nothing checks,
`_construct()` inspects the class it is about to build and passes only what that
class accepts, warning about anything it had to drop. Guessing wrong then costs a
log line instead of a `TypeError` on a live call.

That leaves a handful of vendors whose wiring is genuinely different rather than
just differently named - OpenRouter and Azure go through the OpenAI plugin's own
factories, AWS wants three credentials, PlayAI wants a user id. Those have real
factories below; everything else is data.

There is deliberately no CallFlow-owned `Protocol` over the plugin types.
`livekit-agents` already declares `stt.STT`/`tts.TTS`/`llm.LLM`, and wrapping them
before a working call exists would be inventing an abstraction from one example -
the same discipline `apps/api`'s `voice/protocol.py` documents having learned the
hard way.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("voice-runtime.pipeline")

Factory = Callable[["AgentSpec"], Any]


class UnknownProvider(Exception):
    """Raised instead of silently falling back to a default.

    A call that quietly runs on the wrong voice is worse than one that refuses to
    start: the operator gets a transcript that looks fine and never learns the
    agent they configured was not the agent that spoke.
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
            f"The '{name}' plugin is not installed. Install it with: pip install -e '.[{extra}]'"
        )


@dataclass(frozen=True)
class AgentSpec:
    """The provider choices for one call, as `apps/api` sends them.

    Mirrors the `voice_agents` columns rather than the whole row - this worker
    has no business knowing an agent's name or who created it.

    `credentials` carries whatever fields that vendor declared in the API's
    `domain/providers.py`, by their own names, so a three-field vendor (Azure,
    AWS) arrives intact rather than being squeezed into one `api_key`.
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
    stt_credentials: dict[str, Any] | None = None
    tts_credentials: dict[str, Any] | None = None
    llm_credentials: dict[str, Any] | None = None

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
            stt_credentials=agent.get("stt_credentials"),
            tts_credentials=agent.get("tts_credentials"),
            llm_credentials=agent.get("llm_credentials"),
        )

    def credentials_for(self, kind: str) -> dict[str, Any]:
        """Every stored field for one role, with the single key folded in.

        `*_api_key` is the common case and stays a first-class field; a vendor
        needing more (a region, an endpoint, a user id) sends `*_credentials`
        alongside it. Merging here means a factory reads one mapping instead of
        checking two places.
        """
        extra = getattr(self, f"{kind}_credentials") or {}
        key = getattr(self, f"{kind}_api_key")
        merged = dict(extra)
        if key and "api_key" not in merged:
            merged["api_key"] = key
        return merged


@dataclass(frozen=True)
class PluginSpec:
    """Where a vendor's class lives, and what to try passing it."""

    module: str
    #: The pip extra that installs it, named for the error message.
    extra: str
    #: Fixed arguments the vendor needs regardless of the agent (a default model).
    defaults: dict[str, Any] | None = None


def _construct(spec_: PluginSpec, attr: str, candidates: dict[str, Any]) -> Any:
    """Import the plugin and build `attr`, passing only what it accepts.

    Anything dropped is logged rather than swallowed: a language argument the
    vendor names differently is the difference between a Hindi call and an
    English one, and it should be visible in the worker's log the first time it
    happens rather than inferred from a strange transcript.
    """
    try:
        module = importlib.import_module(f"livekit.plugins.{spec_.module}")
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise MissingPlugin(spec_.module, spec_.extra) from exc

    cls = getattr(module, attr)
    wanted = {**(spec_.defaults or {}), **{k: v for k, v in candidates.items() if v is not None}}
    try:
        accepted = set(inspect.signature(cls).parameters)
    except (TypeError, ValueError):  # pragma: no cover - C-implemented constructor
        return cls(**wanted)

    if "kwargs" in accepted:
        return cls(**wanted)

    passed = {k: v for k, v in wanted.items() if k in accepted}
    dropped = sorted(set(wanted) - set(passed))
    if dropped:
        log.warning(
            "%s.%s does not accept %s - continuing without it",
            spec_.module,
            attr,
            ", ".join(dropped),
        )
    return cls(**passed)


def _stt(spec_: PluginSpec) -> Factory:
    def build(agent: AgentSpec) -> Any:
        creds = agent.credentials_for("stt")
        return _construct(
            spec_,
            "STT",
            {
                **creds,
                "language": agent.language,
                "language_code": agent.language,
                "languages": [agent.language] if agent.language else None,
            },
        )

    return build


def _tts(spec_: PluginSpec, *, voice_args: tuple[str, ...] = ("voice", "voice_id")) -> Factory:
    def build(agent: AgentSpec) -> Any:
        creds = agent.credentials_for("tts")
        candidates: dict[str, Any] = {
            **creds,
            "language": agent.language,
            "language_code": agent.language,
        }
        for name in voice_args:
            candidates.setdefault(name, agent.voice_id)
        return _construct(spec_, "TTS", candidates)

    return build


def _llm(spec_: PluginSpec) -> Factory:
    def build(agent: AgentSpec) -> Any:
        creds = agent.credentials_for("llm")
        return _construct(spec_, "LLM", {**creds, "model": agent.llm_model})

    return build


# --- the vendors whose wiring is genuinely different --------------------------


def _openai_compatible(name: str, factory: str) -> Factory:
    """Vendors served through the OpenAI plugin's own `with_*` factories.

    There is no separate package for OpenRouter, Together, DeepSeek or Perplexity
    - `openai.LLM.with_openrouter()` and friends are the supported wiring (ADR-7),
    not a shortcut around a missing one. Every one of them proxies many models, so
    the model is required: the credential alone does not say which to run.
    """

    def build(agent: AgentSpec) -> Any:
        try:
            from livekit.plugins import openai
        except ImportError as exc:  # pragma: no cover
            raise MissingPlugin(name, "openai") from exc
        if not agent.llm_model:
            raise ValueError(
                f"This voice agent uses {name} but has no model set. "
                "One key proxies many models, so pick one on the agent."
            )
        maker = getattr(openai.LLM, factory, None)
        if maker is None:  # pragma: no cover - an older plugin release
            raise MissingPlugin(name, "openai")
        return maker(model=agent.llm_model, api_key=agent.credentials_for("llm").get("api_key"))

    return build


def _azure_openai_llm(agent: AgentSpec) -> Any:
    """Azure addresses a model by *deployment*, and needs its endpoint."""
    try:
        from livekit.plugins import openai
    except ImportError as exc:  # pragma: no cover
        raise MissingPlugin("azure_openai", "openai") from exc
    creds = agent.credentials_for("llm")
    missing = [k for k in ("api_key", "endpoint", "deployment") if not creds.get(k)]
    if missing:
        raise ValueError(
            "This voice agent uses Azure OpenAI but its credentials are missing: "
            f"{', '.join(missing)}. Reconnect Azure OpenAI on Settings → Integrations."
        )
    return openai.LLM.with_azure(
        model=creds["deployment"],
        azure_endpoint=creds["endpoint"],
        api_key=creds["api_key"],
    )


def _playai_tts(agent: AgentSpec) -> Any:
    """PlayAI authenticates with a user id alongside the key."""
    creds = agent.credentials_for("tts")
    return _construct(
        PluginSpec(module="playai", extra="playai"),
        "TTS",
        {**creds, "voice": agent.voice_id, "user_id": creds.get("user_id")},
    )


def _sarvam_stt(agent: AgentSpec) -> Any:
    creds = agent.credentials_for("stt")
    return _construct(
        PluginSpec(module="sarvam", extra="sarvam"),
        "STT",
        {**creds, "language": agent.language or "en-IN"},
    )


def _sarvam_tts(agent: AgentSpec) -> Any:
    creds = agent.credentials_for("tts")
    return _construct(
        PluginSpec(module="sarvam", extra="sarvam"),
        "TTS",
        {
            **creds,
            "target_language_code": agent.language or "en-IN",
            "speaker": agent.voice_id or "anushka",
        },
    )


# --- the registries -----------------------------------------------------------
# Every key here must exist in `apps/api`'s `domain/providers.py` with a
# non-null `runtime_extra`, and vice versa. `test_dispatch_contract.py` asserts
# that both directions hold - a vendor the catalogue calls connectable and this
# file cannot build is a card that lies.

STT_PROVIDERS: dict[str, Factory] = {
    "deepgram": _stt(PluginSpec("deepgram", "deepgram", {"model": "nova-3"})),
    "assemblyai": _stt(PluginSpec("assemblyai", "assemblyai")),
    "gladia": _stt(PluginSpec("gladia", "gladia")),
    "speechmatics": _stt(PluginSpec("speechmatics", "speechmatics")),
    "soniox": _stt(PluginSpec("soniox", "soniox")),
    "sarvam": _sarvam_stt,
    "azure_speech": _stt(PluginSpec("azure", "azure")),
    "clova": _stt(PluginSpec("clova", "clova")),
    "gnani": _stt(PluginSpec("gnani", "gnani")),
    "rtzr": _stt(PluginSpec("rtzr", "rtzr")),
    "spitch": _stt(PluginSpec("spitch", "spitch")),
    "baseten": _stt(PluginSpec("baseten", "baseten")),
    "fal": _stt(PluginSpec("fal", "fal")),
    "openai": _stt(PluginSpec("openai", "openai")),
    "groq": _stt(PluginSpec("groq", "groq")),
    "google": _stt(PluginSpec("google", "google")),
    "aws_bedrock": _stt(PluginSpec("aws", "aws")),
    "elevenlabs": _stt(PluginSpec("elevenlabs", "elevenlabs")),
    "cartesia": _stt(PluginSpec("cartesia", "cartesia")),
}

TTS_PROVIDERS: dict[str, Factory] = {
    "elevenlabs": _tts(PluginSpec("elevenlabs", "elevenlabs")),
    "cartesia": _tts(PluginSpec("cartesia", "cartesia")),
    "playai": _playai_tts,
    "lmnt": _tts(PluginSpec("lmnt", "lmnt")),
    "rime": _tts(PluginSpec("rime", "rime")),
    "hume": _tts(PluginSpec("hume", "hume")),
    "inworld": _tts(PluginSpec("inworld", "inworld")),
    "neuphonic": _tts(PluginSpec("neuphonic", "neuphonic")),
    "resemble": _tts(PluginSpec("resemble", "resemble")),
    "speechify": _tts(PluginSpec("speechify", "speechify")),
    "murf": _tts(PluginSpec("murf", "murf")),
    "smallestai": _tts(PluginSpec("smallestai", "smallestai")),
    "fishaudio": _tts(PluginSpec("fishaudio", "fishaudio")),
    "upliftai": _tts(PluginSpec("upliftai", "upliftai")),
    "sarvam": _sarvam_tts,
    "deepgram": _tts(PluginSpec("deepgram", "deepgram", {"model": "aura-2-thalia-en"})),
    "azure_speech": _tts(PluginSpec("azure", "azure")),
    "spitch": _tts(PluginSpec("spitch", "spitch")),
    "gnani": _tts(PluginSpec("gnani", "gnani")),
    "minimax": _tts(PluginSpec("minimax", "minimax")),
    "openai": _tts(PluginSpec("openai", "openai")),
    "google": _tts(PluginSpec("google", "google")),
    "aws_bedrock": _tts(PluginSpec("aws", "aws")),
}

LLM_PROVIDERS: dict[str, Factory] = {
    "openrouter": _openai_compatible("OpenRouter", "with_openrouter"),
    "together": _openai_compatible("Together AI", "with_together"),
    "deepseek": _openai_compatible("DeepSeek", "with_deepseek"),
    "perplexity": _openai_compatible("Perplexity", "with_perplexity"),
    "azure_openai": _azure_openai_llm,
    "openai": _llm(PluginSpec("openai", "openai", {"model": "gpt-4o-mini"})),
    "anthropic": _llm(PluginSpec("anthropic", "anthropic")),
    "google": _llm(PluginSpec("google", "google")),
    "groq": _llm(PluginSpec("groq", "groq")),
    "xai": _llm(PluginSpec("xai", "xai")),
    "mistral": _llm(PluginSpec("mistralai", "mistralai")),
    "cerebras": _llm(PluginSpec("cerebras", "cerebras")),
    "fireworks": _llm(PluginSpec("fireworksai", "fireworksai")),
    "minimax": _llm(PluginSpec("minimax", "minimax")),
    "aws_bedrock": _llm(PluginSpec("aws", "aws")),
}


def _resolve(registry: dict[str, Factory], kind: str, name: str, agent: AgentSpec) -> Any:
    factory = registry.get(name)
    if factory is None:
        raise UnknownProvider(kind, name, sorted(registry))
    return factory(agent)


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


#: Every provider this worker can drive, in any role. `apps/api` treats this as
#: the definition of "wired".
SUPPORTED_PROVIDERS: frozenset[str] = frozenset(
    {*STT_PROVIDERS, *TTS_PROVIDERS, *LLM_PROVIDERS}
)


__all__ = [
    "LLM_PROVIDERS",
    "STT_PROVIDERS",
    "SUPPORTED_PROVIDERS",
    "TTS_PROVIDERS",
    "AgentSpec",
    "MissingPlugin",
    "Pipeline",
    "PluginSpec",
    "UnknownProvider",
    "build_pipeline",
]
