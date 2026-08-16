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

LLM_MODELS is a curated subset of what OpenRouter actually serves, not its full
catalogue - OpenRouter lists hundreds of models and grows weekly, so the honest
version of "every model" is a live fetch of its public `/api/v1/models`
endpoint, cached, behind an adapter. That adapter does not exist yet (see
below), so this hand-checked list is what the builder offers today.

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
    # The same public-pricing figures as the `*_note` strings above, in machine
    # units, so the builder can draw a comparable latency/cost breakdown per leg
    # instead of asking someone to read three sentences per option. Same
    # provenance and same caveat: public pages, not measurements taken here.
    latency_ms: int | None = None
    # STT/TTS only - these vendors bill per minute of audio or per character,
    # both of which reduce to a per-minute figure. Left None for LLM entries,
    # which bill per token and carry the two token fields below instead.
    cost_per_min_usd: float | None = None
    # LLM only.
    cost_per_1m_input_usd: float | None = None
    cost_per_1m_output_usd: float | None = None
    voice_options: tuple[
        str, ...
    ] = ()  # TTS only: known voice/speaker ids, empty tuple otherwise


# Spoken English runs around 150 words per minute, and a word averages close to
# six characters with its trailing space - so a minute of synthesised speech is
# roughly 900 characters. Character-billed TTS vendors are converted to a
# per-minute figure through this constant so every leg of an agent can be
# compared in the same unit; it is an assumption about speech, not a vendor
# quote, and the builder labels the resulting cost as an estimate.
_CHARS_PER_MINUTE_OF_SPEECH = 900

STT_PROVIDERS: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        id="deepgram",
        category="stt",
        name="Deepgram Nova-3",
        vendor="Deepgram",
        cost_note="~$0.0077/min streaming",
        latency_note="~300ms streaming",
        quality_note="Strong English accuracy, built for real-time streaming",
        preview_available=False,
        latency_ms=300,
        # The streaming rate, not the cheaper batch one: a phone call is
        # streaming by definition, so batch pricing would understate it.
        cost_per_min_usd=0.0077,
    ),
    ProviderCatalogEntry(
        id="deepgram-nova-2",
        category="stt",
        name="Deepgram Nova-2",
        vendor="Deepgram",
        cost_note="~$0.0059/min streaming",
        latency_note="~300ms streaming",
        quality_note="The previous generation, cheaper and still fast",
        preview_available=False,
        latency_ms=300,
        cost_per_min_usd=0.0059,
    ),
    ProviderCatalogEntry(
        id="assemblyai",
        category="stt",
        name="AssemblyAI Universal-Streaming",
        vendor="AssemblyAI",
        cost_note="~$0.15/hr of audio (~$0.0025/min)",
        latency_note="~300ms streaming",
        quality_note="Accurate English with strong formatting and punctuation",
        preview_available=False,
        latency_ms=300,
        cost_per_min_usd=0.15 / 60,
    ),
    ProviderCatalogEntry(
        id="openai-whisper",
        category="stt",
        name="Whisper large-v3",
        vendor="OpenAI",
        cost_note="~$0.006/min",
        latency_note="~2-4s (batch only, no streaming endpoint)",
        quality_note="Broad multilingual coverage, but not built for live calls",
        preview_available=False,
        latency_ms=3000,
        cost_per_min_usd=0.006,
    ),
    ProviderCatalogEntry(
        id="groq-whisper",
        category="stt",
        name="Whisper large-v3 Turbo",
        vendor="Groq",
        cost_note="~$0.04/hr of audio (~$0.0007/min)",
        latency_note="~500ms (very fast batch, still not streaming)",
        quality_note="Whisper accuracy at the lowest price on this list",
        preview_available=False,
        latency_ms=500,
        cost_per_min_usd=0.04 / 60,
    ),
    ProviderCatalogEntry(
        id="speechmatics",
        category="stt",
        name="Speechmatics Ursa 2",
        vendor="Speechmatics",
        cost_note="~$0.30/hr of audio (~$0.005/min)",
        latency_note="~500ms streaming",
        quality_note="Strong across accents and noisy lines",
        preview_available=False,
        latency_ms=500,
        cost_per_min_usd=0.30 / 60,
    ),
    ProviderCatalogEntry(
        id="gladia",
        category="stt",
        name="Gladia Solaria",
        vendor="Gladia",
        cost_note="~$0.144/hr of audio (~$0.0024/min)",
        latency_note="~270ms streaming",
        quality_note="Built for telephony audio across 100 languages",
        preview_available=False,
        latency_ms=270,
        cost_per_min_usd=0.144 / 60,
    ),
    ProviderCatalogEntry(
        id="azure-stt",
        category="stt",
        name="Azure Speech to Text",
        vendor="Microsoft Azure",
        cost_note="~$1/hr of audio (~$0.017/min)",
        latency_note="~400ms streaming",
        quality_note="Wide language coverage with enterprise data terms",
        preview_available=False,
        latency_ms=400,
        cost_per_min_usd=1.0 / 60,
    ),
    ProviderCatalogEntry(
        id="google-stt",
        category="stt",
        name="Google Speech-to-Text v2",
        vendor="Google Cloud",
        cost_note="~$0.016/min",
        latency_note="~400ms streaming",
        quality_note="Wide language coverage, telephony-tuned models",
        preview_available=False,
        latency_ms=400,
        cost_per_min_usd=0.016,
    ),
    ProviderCatalogEntry(
        id="sarvam",
        category="stt",
        name="Sarvam Saarika",
        vendor="Sarvam AI",
        cost_note="~$0.35/hr of audio (~$0.006/min)",
        latency_note="~1-2s for a short clip (sync REST, not streaming)",
        quality_note="Strong Indian-language and code-mixed accuracy",
        preview_available=True,
        latency_ms=1500,
        cost_per_min_usd=0.35 / 60,
    ),
)

TTS_PROVIDERS: tuple[ProviderCatalogEntry, ...] = (
    ProviderCatalogEntry(
        id="elevenlabs",
        category="tts",
        name="ElevenLabs Flash v2.5",
        vendor="ElevenLabs",
        cost_note="~$0.0484 per 1,000 characters",
        latency_note="~75ms (fastest model, built for real-time agents)",
        quality_note="High naturalness across 32 languages",
        preview_available=False,
        latency_ms=75,
        cost_per_min_usd=0.0484 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Rachel", "Adam", "Bella", "Antoni", "Elli", "Josh"),
    ),
    ProviderCatalogEntry(
        id="elevenlabs-turbo",
        category="tts",
        name="ElevenLabs Turbo v2.5",
        vendor="ElevenLabs",
        cost_note="~$0.0968 per 1,000 characters",
        latency_note="~250ms",
        quality_note="Warmer delivery than Flash, at twice the price",
        preview_available=False,
        latency_ms=250,
        cost_per_min_usd=0.0968 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Rachel", "Adam", "Bella", "Antoni", "Elli", "Josh"),
    ),
    ProviderCatalogEntry(
        id="cartesia",
        category="tts",
        name="Cartesia Sonic-2",
        vendor="Cartesia",
        cost_note="~$0.032 per 1,000 characters",
        latency_note="~90ms",
        quality_note="Very low latency with steady, natural pacing",
        preview_available=False,
        latency_ms=90,
        cost_per_min_usd=0.032 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Brooke", "Caleb", "Sophie"),
    ),
    ProviderCatalogEntry(
        id="deepgram-aura",
        category="tts",
        name="Deepgram Aura-2",
        vendor="Deepgram",
        cost_note="~$0.030 per 1,000 characters",
        latency_note="~150ms",
        quality_note="Clear conversational English, tuned for phone lines",
        preview_available=False,
        latency_ms=150,
        cost_per_min_usd=0.030 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Thalia", "Andromeda", "Helena", "Apollo", "Orion"),
    ),
    ProviderCatalogEntry(
        id="rime",
        category="tts",
        name="Rime Mist v2",
        vendor="Rime",
        cost_note="~$0.0060 per 1,000 characters",
        latency_note="~100ms",
        quality_note="Casual, spoken-sounding delivery rather than announcer",
        preview_available=False,
        latency_ms=100,
        cost_per_min_usd=0.0060 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Marissa", "Allison", "Colin", "Rainforest"),
    ),
    ProviderCatalogEntry(
        id="playht",
        category="tts",
        name="PlayHT Play 3.0 Mini",
        vendor="PlayHT",
        cost_note="~$0.030 per 1,000 characters",
        latency_note="~140ms",
        quality_note="Large stock voice library with cloning support",
        preview_available=False,
        latency_ms=140,
        cost_per_min_usd=0.030 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Angelo", "Deedee", "Jennifer", "Samara"),
    ),
    ProviderCatalogEntry(
        id="openai-tts",
        category="tts",
        name="OpenAI TTS-1",
        vendor="OpenAI",
        cost_note="~$0.015 per 1,000 characters",
        latency_note="~400ms",
        quality_note="Consistent, neutral delivery in a small voice set",
        preview_available=False,
        latency_ms=400,
        cost_per_min_usd=0.015 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("alloy", "echo", "fable", "onyx", "nova", "shimmer"),
    ),
    ProviderCatalogEntry(
        id="azure-tts",
        category="tts",
        name="Azure Neural TTS",
        vendor="Microsoft Azure",
        cost_note="~$0.016 per 1,000 characters",
        latency_note="~300ms",
        quality_note="Hundreds of neural voices with enterprise data terms",
        preview_available=False,
        latency_ms=300,
        cost_per_min_usd=0.016 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Jenny", "Guy", "Aria", "Davis", "Neerja"),
    ),
    ProviderCatalogEntry(
        id="google-tts",
        category="tts",
        name="Google Chirp 3 HD",
        vendor="Google Cloud",
        cost_note="~$0.030 per 1,000 characters",
        latency_note="~300ms",
        quality_note="Natural prosody across a very wide language set",
        preview_available=False,
        latency_ms=300,
        cost_per_min_usd=0.030 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Achernar", "Aoede", "Charon", "Kore", "Puck"),
    ),
    ProviderCatalogEntry(
        id="lmnt",
        category="tts",
        name="LMNT Blizzard",
        vendor="LMNT",
        cost_note="~$0.020 per 1,000 characters",
        latency_note="~110ms",
        quality_note="Low latency with steady quality on long turns",
        preview_available=False,
        latency_ms=110,
        cost_per_min_usd=0.020 / 1_000 * _CHARS_PER_MINUTE_OF_SPEECH,
        voice_options=("Amy", "Dalton", "Miles", "Zeke"),
    ),
    ProviderCatalogEntry(
        id="sarvam",
        category="tts",
        name="Sarvam Bulbul",
        vendor="Sarvam AI",
        cost_note="~$0.18/10k characters",
        latency_note="~1-2s for a short clip (sync REST, not streaming)",
        quality_note="Natural Indian-language and English voices, 11 languages",
        preview_available=True,
        latency_ms=1500,
        cost_per_min_usd=0.18 / 10_000 * _CHARS_PER_MINUTE_OF_SPEECH,
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
)

def _llm(
    model_id: str,
    name: str,
    vendor: str,
    inp: float,
    out: float,
    latency_ms: int,
    quality: str,
) -> ProviderCatalogEntry:
    """One OpenRouter-routed model.

    Every LLM entry has the same shape - an OpenRouter model path, the two
    token prices, a first-token estimate and a one-line note - so spelling all
    eight keyword arguments out per model would be sixteen lines of noise
    apiece across a list this long.
    """
    return ProviderCatalogEntry(
        id=model_id,
        category="llm",
        name=name,
        vendor=vendor,
        cost_note=f"~${inp:g} / ${out:g} per 1M input/output tokens",
        latency_note=(
            f"~{latency_ms / 1000:g}s first token"
            if latency_ms >= 1000
            else f"~{latency_ms}ms first token"
        ),
        quality_note=quality,
        preview_available=False,
        latency_ms=latency_ms,
        cost_per_1m_input_usd=inp,
        cost_per_1m_output_usd=out,
    )


LLM_MODELS: tuple[ProviderCatalogEntry, ...] = (
    # OpenAI
    _llm("openai/gpt-4o", "GPT-4o", "OpenAI", 2.50, 10.00, 1500,
         "Strong general-purpose reasoning and instruction following"),
    _llm("openai/gpt-4o-mini", "GPT-4o mini", "OpenAI", 0.15, 0.60, 600,
         "Cheap and quick, enough for short scripted calls"),
    _llm("openai/gpt-4.1", "GPT-4.1", "OpenAI", 2.00, 8.00, 700,
         "Better instruction adherence than 4o at a similar price"),
    _llm("openai/gpt-4.1-mini", "GPT-4.1 mini", "OpenAI", 0.40, 1.60, 500,
         "A strong default for high call volume"),
    _llm("openai/gpt-4.1-nano", "GPT-4.1 nano", "OpenAI", 0.10, 0.40, 400,
         "The fastest OpenAI option, for very simple scripts"),
    _llm("openai/gpt-5", "GPT-5", "OpenAI", 1.25, 10.00, 1600,
         "Handles ambiguous callers without losing the goal"),
    _llm("openai/gpt-5-mini", "GPT-5 mini", "OpenAI", 0.25, 2.00, 700,
         "Most of GPT-5's judgement at a fraction of the cost"),
    _llm("openai/o4-mini", "o4-mini", "OpenAI", 1.10, 4.40, 2500,
         "Reasons before answering, so slower on the first token"),

    # Anthropic
    _llm("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", "Anthropic", 3.00, 15.00, 1500,
         "Strong at following a structured goal script without drifting"),
    _llm("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku", "Anthropic", 0.80, 4.00, 700,
         "Holds a script closely at a fraction of Sonnet's cost"),
    _llm("anthropic/claude-3.7-sonnet", "Claude 3.7 Sonnet", "Anthropic", 3.00, 15.00, 1200,
         "Better at long multi-turn calls than 3.5"),
    _llm("anthropic/claude-sonnet-4", "Claude Sonnet 4", "Anthropic", 3.00, 15.00, 1000,
         "Handles long, branching calls without losing the thread"),
    _llm("anthropic/claude-sonnet-4.5", "Claude Sonnet 4.5", "Anthropic", 3.00, 15.00, 1000,
         "The most reliable script-follower on this list"),
    _llm("anthropic/claude-haiku-4.5", "Claude Haiku 4.5", "Anthropic", 1.00, 5.00, 500,
         "Near-Sonnet quality at Haiku speed"),
    _llm("anthropic/claude-opus-4.1", "Claude Opus 4.1", "Anthropic", 15.00, 75.00, 2000,
         "Deepest reasoning here, priced for calls that justify it"),

    # Google
    _llm("google/gemini-2.0-flash-001", "Gemini 2.0 Flash", "Google", 0.10, 0.40, 500,
         "Fast and inexpensive, good for high call volume"),
    _llm("google/gemini-2.5-flash", "Gemini 2.5 Flash", "Google", 0.30, 2.50, 600,
         "Noticeably better reasoning than 2.0 Flash, still quick"),
    _llm("google/gemini-2.5-flash-lite", "Gemini 2.5 Flash Lite", "Google", 0.10, 0.40, 350,
         "The lowest first-token latency Google offers"),
    _llm("google/gemini-2.5-pro", "Gemini 2.5 Pro", "Google", 1.25, 10.00, 1500,
         "The most capable Gemini, for calls that need judgement"),

    # Meta
    _llm("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", "Meta", 0.12, 0.30, 1000,
         "Good cost and quality tradeoff for straightforward scripts"),
    _llm("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B", "Meta", 0.02, 0.03, 400,
         "The cheapest option here, for very simple scripts"),
    _llm("meta-llama/llama-3.1-70b-instruct", "Llama 3.1 70B", "Meta", 0.12, 0.30, 900,
         "The previous 70B generation, widely available"),
    _llm("meta-llama/llama-4-maverick", "Llama 4 Maverick", "Meta", 0.15, 0.60, 700,
         "Open-weight with quality close to the paid mid-tier"),
    _llm("meta-llama/llama-4-scout", "Llama 4 Scout", "Meta", 0.08, 0.30, 500,
         "Small, quick, and very cheap per call"),

    # DeepSeek
    _llm("deepseek/deepseek-chat", "DeepSeek V3", "DeepSeek", 0.14, 0.28, 1000,
         "Among the cheapest models that still follow a long prompt"),
    _llm("deepseek/deepseek-chat-v3.1", "DeepSeek V3.1", "DeepSeek", 0.20, 0.80, 900,
         "Sharper than V3 at holding a persona"),
    _llm("deepseek/deepseek-r1", "DeepSeek R1", "DeepSeek", 0.40, 2.00, 3000,
         "Reasons step by step, too slow for live turns"),
    _llm("deepseek/deepseek-r1-distill-llama-70b", "DeepSeek R1 Distill 70B", "DeepSeek", 0.10, 0.40, 800,
         "R1's reasoning distilled into a fast 70B"),

    # Mistral
    _llm("mistralai/mistral-large", "Mistral Large", "Mistral", 2.00, 6.00, 900,
         "Strong multilingual reasoning, European data residency"),
    _llm("mistralai/mistral-small", "Mistral Small 3", "Mistral", 0.10, 0.30, 500,
         "Quick and cheap with solid European language coverage"),
    _llm("mistralai/mistral-nemo", "Mistral Nemo", "Mistral", 0.03, 0.07, 400,
         "Very cheap, best kept to short predictable calls"),
    _llm("mistralai/magistral-medium-2506", "Magistral Medium", "Mistral", 2.00, 5.00, 1200,
         "Mistral's reasoning model, for harder objections"),

    # xAI
    _llm("x-ai/grok-3", "Grok 3", "xAI", 3.00, 15.00, 1200,
         "Conversational register, strong general knowledge"),
    _llm("x-ai/grok-3-mini", "Grok 3 Mini", "xAI", 0.30, 0.50, 700,
         "Fast, with a looser conversational register"),
    _llm("x-ai/grok-4-fast", "Grok 4 Fast", "xAI", 0.20, 0.50, 500,
         "The quickest xAI option for live calls"),

    # Alibaba
    _llm("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B", "Alibaba", 0.13, 0.40, 900,
         "Strong Chinese and English for the price"),
    _llm("qwen/qwen3-235b-a22b", "Qwen3 235B", "Alibaba", 0.13, 0.60, 1000,
         "Large mixture-of-experts, strong multilingual coverage"),
    _llm("qwen/qwen3-30b-a3b", "Qwen3 30B", "Alibaba", 0.08, 0.29, 600,
         "Small and quick with good multilingual range"),

    # Amazon
    _llm("amazon/nova-pro-v1", "Nova Pro", "Amazon", 0.80, 3.20, 900,
         "AWS-native, competitive on price for long calls"),
    _llm("amazon/nova-lite-v1", "Nova Lite", "Amazon", 0.06, 0.24, 500,
         "Very cheap, fine for confirm-and-collect calls"),

    # Cohere
    _llm("cohere/command-a", "Command A", "Cohere", 2.50, 10.00, 900,
         "Built for retrieval-heavy, business-facing conversations"),

    # Moonshot
    _llm("moonshotai/kimi-k2", "Kimi K2", "Moonshot", 0.14, 2.49, 1100,
         "Open-weight, strong at tool use mid-call"),

    # Z.ai
    _llm("z-ai/glm-4.6", "GLM-4.6", "Z.ai", 0.40, 1.75, 800,
         "Cheap frontier-class option, strong bilingual output"),
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
