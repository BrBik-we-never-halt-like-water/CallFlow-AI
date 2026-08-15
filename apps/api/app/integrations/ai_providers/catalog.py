"""The static provider catalog for the Agentic tab's voice-agent builder.

A plain module-level constant is the registry - same convention as
`app/domain/campaigns.py`'s built-in campaign list. No I/O, no network call:
every field here is either a fact about the vendor's public API (`id`,
`voice_options`) or a best-effort, human-written estimate from public
pricing/marketing pages (`cost_note`, `latency_note`, `quality_note`) rather
than a live quote or a measurement taken in this codebase.

Sources checked while writing this (August 2026):
  - Sarvam: https://docs.sarvam.ai/ (TTS + STT REST API references, Bulbul
    and Saarika model pages, pricing page) - see `sarvam.py` for the exact
    endpoints the adapter calls.
  - Deepgram Nova-3: public pricing/model pages (deepgram.com); no adapter
    is built against these in this task, so only display strings were
    checked, not a live endpoint.
  - ElevenLabs: public docs/pricing pages (elevenlabs.io/docs/overview/models);
    same caveat - display strings only.

`preview_available` means: this codebase has a real adapter wired for the
demo/preview action *today*, not that the vendor lacks an API. Deepgram and
ElevenLabs both have perfectly good APIs - nobody has written the adapter
yet, so previewing either would silently fake success (CLAUDE.md non-negotiable
#9), which is exactly what `preview_available=False` exists to prevent.

LLM_MODELS is deliberately `preview_available=False` for every entry, even
though OpenRouter itself supports all of these models today: this task does
not build an OpenRouter adapter, only Sarvam's. Gating "is preview available"
on the catalog keeps `app/services/voice_preview.py`'s dispatch logic to one
real branch (Sarvam) plus a single honest-fallback path, instead of a
special case for "wired vendor but unwired feature". Wiring OpenRouter
preview is a follow-up task; when it lands, flip these to `True` and the
service needs no other change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCatalogEntry:
    id: str  # e.g. "sarvam", "deepgram" - matches ai_provider_credentials.provider check constraint
    category: str  # "stt" | "tts" | "llm"
    name: str  # display name, e.g. "Sarvam Saarika"
    vendor: str  # e.g. "Sarvam AI"
    cost_note: str  # short human string, e.g. "~$0.01/min" - best-effort from public pricing, not a live quote
    latency_note: str  # e.g. "~300ms" - best-effort, not measured
    quality_note: str  # one short phrase, e.g. "Strong Indian-language accuracy"
    preview_available: bool  # whether THIS codebase has a real adapter wired for the demo/preview action today
    voice_options: tuple[
        str, ...
    ] = ()  # TTS only: known voice/speaker ids, empty tuple otherwise


STT_PROVIDERS: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        id="sarvam",
        category="stt",
        name="Sarvam Saarika",
        vendor="Sarvam AI",
        cost_note="~$0.35/hr of audio (~$0.006/min)",
        latency_note="~1-2s for a short clip (sync REST, not streaming)",
        quality_note="Strong Indian-language and code-mixed accuracy",
        preview_available=True,
    ),
    ProviderCatalogEntry(
        id="deepgram",
        category="stt",
        name="Deepgram Nova-3",
        vendor="Deepgram",
        cost_note="~$0.0043-0.0048/min batch, ~$0.0077/min streaming",
        latency_note="~300ms streaming",
        quality_note="Strong English accuracy, built for real-time streaming",
        preview_available=False,
    ),
)

TTS_PROVIDERS: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        id="sarvam",
        category="tts",
        name="Sarvam Bulbul",
        vendor="Sarvam AI",
        cost_note="~$0.18/10k characters",
        latency_note="~1-2s for a short clip (sync REST, not streaming)",
        quality_note="Natural Indian-language and English voices, 11 languages",
        preview_available=True,
        voice_options=(
            "anushka",
            "abhilash",
            "manisha",
            "vidya",
            "arya",
            "karun",
            "hitesh",
        ),
    ),
    ProviderCatalogEntry(
        id="elevenlabs",
        category="tts",
        name="ElevenLabs Flash v2.5",
        vendor="ElevenLabs",
        cost_note="~$0.0484 per 1,000 characters",
        latency_note="~75ms (fastest model, built for real-time agents)",
        quality_note="High naturalness across 32 languages",
        preview_available=False,
        voice_options=("Rachel", "Adam", "Bella"),
    ),
)

LLM_MODELS: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        id="openai/gpt-4o",
        category="llm",
        name="GPT-4o",
        vendor="OpenAI (via OpenRouter)",
        cost_note="~$2.50 / $10 per 1M input/output tokens",
        latency_note="~1-2s first token",
        quality_note="Strong general-purpose reasoning and instruction following",
        preview_available=False,
    ),
    ProviderCatalogEntry(
        id="anthropic/claude-3.5-sonnet",
        category="llm",
        name="Claude 3.5 Sonnet",
        vendor="Anthropic (via OpenRouter)",
        cost_note="~$3 / $15 per 1M input/output tokens",
        latency_note="~1-2s first token",
        quality_note="Strong at following a structured goal script without drifting",
        preview_available=False,
    ),
    ProviderCatalogEntry(
        id="meta-llama/llama-3.3-70b-instruct",
        category="llm",
        name="Llama 3.3 70B Instruct",
        vendor="Meta (via OpenRouter)",
        cost_note="~$0.12 / $0.30 per 1M input/output tokens",
        latency_note="~1s first token",
        quality_note="Good cost/quality tradeoff for straightforward call scripts",
        preview_available=False,
    ),
    ProviderCatalogEntry(
        id="google/gemini-2.0-flash-001",
        category="llm",
        name="Gemini 2.0 Flash",
        vendor="Google (via OpenRouter)",
        cost_note="~$0.10 / $0.40 per 1M input/output tokens",
        latency_note="~500ms first token",
        quality_note="Fast and inexpensive, good for high call volume",
        preview_available=False,
    ),
)


def all_providers() -> tuple[ProviderCatalogEntry, ...]:
    return STT_PROVIDERS + TTS_PROVIDERS + LLM_MODELS


__all__ = [
    "LLM_MODELS",
    "STT_PROVIDERS",
    "TTS_PROVIDERS",
    "ProviderCatalogEntry",
    "all_providers",
]
