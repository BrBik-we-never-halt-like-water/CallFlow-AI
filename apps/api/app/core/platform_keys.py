"""CallFlow's own provider keys, used when an organisation has connected none.

The product decision this implements: an organisation that has not brought its
own STT/TTS/LLM credentials still gets working calls, billed to CallFlow, so
building an agent does not begin with collecting five API keys.

**An organisation's own key always wins.** This is a fallback, checked only when
`ai_provider_credentials` holds nothing for that provider - so connecting a key
in Integrations immediately moves the spend back to the customer without any
other change.

Read from the API's environment rather than from the database, deliberately:

- A platform key in `ai_provider_credentials` would be reachable by every code
  path that reads credentials, including ones scoped to an organisation. Keeping
  it in the process environment means the only way to it is this module.
- It is not an organisation's property, so it has no `org_id` to be scoped by,
  and a row without a tenant in a tenant-scoped table is a leak waiting to be
  written.

Nothing here ever returns a key to an HTTP response. `resolve_run_plan()` puts
it into the dispatch metadata that goes to the voice runtime, which is the same
path an organisation's own decrypted key already takes.
"""

from __future__ import annotations

import logging
import os

log = logging.getLogger("app.core.platform_keys")

#: Provider id (as stored in `voice_agents.{stt,tts,llm}_provider`, and as the
#: `ai_provider_credentials.provider` check constraint allows) → the environment
#: variable holding CallFlow's own key for it.
#:
#: Only providers CallFlow actually holds a key for appear here. A provider
#: absent from this map has no fallback, and an agent configured for it refuses
#: with the same "connect it in Integrations" message as before - which is the
#: honest answer, not a silent failure at the first API call.
_ENV_BY_PROVIDER: dict[str, str] = {
    # STT and TTS both - Sarvam sells one key for Saarika and Bulbul, and the
    # catalogue lists `sarvam` under both categories for that reason.
    "sarvam": "SARVAM_API_KEY",
    # STT
    "groq-whisper": "GROQ_API_KEY",
    "google-stt": "GEMINI_API_KEY",
    # TTS
    "google-tts": "GEMINI_API_KEY",
    # LLM - one key covers every model on the marketplace, which is why an
    # agent stores `llm_provider="openrouter"` plus a separate `llm_model`.
    "openrouter": "OPENROUTER_API_KEY",
}
# Deliberately absent, despite `SMALLEST_API_KEY` being in the environment:
# `smallest` is not a provider id this codebase knows. It is in neither the
# catalogue (`integrations/ai_providers/catalog.py`) nor the
# `ai_provider_credentials.provider` check constraint, so no agent can be
# configured for it and a fallback entry would never be reached. Adding the
# provider is a separate change - a catalogue entry, a migration widening the
# constraint, and an adapter in the voice runtime.


def platform_key(provider: str) -> str | None:
    """CallFlow's own key for `provider`, or None if it holds none.

    Read from the environment on every call rather than cached at import: a
    deployment that adds a key should not need a restart to start using it, and
    this is one dictionary lookup on a path that is about to place a phone call.
    """
    env_name = _ENV_BY_PROVIDER.get((provider or "").lower())
    if env_name is None:
        return None
    value = os.getenv(env_name, "").strip()
    return value or None


def providers_with_platform_keys() -> frozenset[str]:
    """Which providers this deployment can fall back on right now.

    For the diagnostic surfaces - a provider listed here works without the
    organisation connecting anything.
    """
    return frozenset(
        provider for provider, env in _ENV_BY_PROVIDER.items() if os.getenv(env, "").strip()
    )


__all__ = ["platform_key", "providers_with_platform_keys"]
