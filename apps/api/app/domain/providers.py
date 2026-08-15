"""Which third-party accounts an organisation can connect, and how.

One list, because the same set has to agree in three places: the API's request
validation, the settings UI, and whatever a `voice_agent` row is allowed to name
in its `stt_provider`/`tts_provider`/`llm_provider` columns. When those drift, a
provider is selectable somewhere it cannot actually be stored.

Pure data, no I/O - the database deliberately holds no allow-list of its own
(`provider_credentials.provider` is a plain non-empty check, widened in the
ADR-4 migration precisely so adding a vendor is an app change rather than a
migration). This module *is* that application-layer list.

**`ConnectMethod` is the honest half.** Only some vendors offer a login flow:
OpenRouter has documented OAuth PKCE, and Twilio has Connect Apps. Plivo,
Sarvam, Deepgram and ElevenLabs issue API keys and nothing else. A "Connect
with …" button that silently opens a paste-your-key dialog would be a success
state for something that did not happen (CLAUDE.md non-negotiable #9), so the
method is declared per provider and the interface reflects it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProviderRole(str, Enum):
    """What the credential is *for*.

    Mirrors `voice_agents`' own columns rather than inventing a second
    taxonomy - an org needs one from each role before a call can happen, and
    that is the thing the settings page has to make obvious.
    """

    TELEPHONY = "telephony"
    SPEECH = "speech"
    INTELLIGENCE = "intelligence"


class ConnectMethod(str, Enum):
    OAUTH = "oauth"
    """The vendor hosts a login and hands back a key. Verified, not assumed."""

    API_KEY = "api_key"
    """The operator pastes a key. The only option most vendors offer."""


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    role: ProviderRole
    connect: ConnectMethod
    summary: str
    # What the two stored halves are called in the vendor's own console. A
    # single-secret vendor leaves `identifier_label` None, and the interface
    # shows one field instead of two - asking for an "identifier" that does not
    # exist is how a form gets abandoned.
    identifier_label: str | None
    secret_label: str
    docs_url: str


PROVIDERS: tuple[ProviderSpec, ...] = (
    ProviderSpec(
        id="twilio",
        name="Twilio",
        role=ProviderRole.TELEPHONY,
        # Twilio Connect exists, but it requires CallFlow to register a Connect
        # App and have it approved. Until that is actually set up, claiming a
        # login flow here would be claiming something that does not work.
        connect=ConnectMethod.API_KEY,
        summary="Dial from your own Twilio number.",
        identifier_label="Account SID",
        secret_label="Auth token",
        docs_url="https://console.twilio.com",
    ),
    ProviderSpec(
        id="plivo",
        name="Plivo",
        role=ProviderRole.TELEPHONY,
        connect=ConnectMethod.API_KEY,
        summary="Dial from your own Plivo number.",
        identifier_label="Auth ID",
        secret_label="Auth token",
        docs_url="https://console.plivo.com",
    ),
    ProviderSpec(
        id="sarvam",
        name="Sarvam",
        role=ProviderRole.SPEECH,
        connect=ConnectMethod.API_KEY,
        summary="Speech recognition and voices built for Indian languages.",
        identifier_label=None,
        secret_label="API subscription key",
        docs_url="https://dashboard.sarvam.ai",
    ),
    ProviderSpec(
        id="deepgram",
        name="Deepgram",
        role=ProviderRole.SPEECH,
        connect=ConnectMethod.API_KEY,
        summary="Fast English speech recognition.",
        identifier_label=None,
        secret_label="API key",
        docs_url="https://console.deepgram.com",
    ),
    ProviderSpec(
        id="elevenlabs",
        name="ElevenLabs",
        role=ProviderRole.SPEECH,
        connect=ConnectMethod.API_KEY,
        summary="Expressive voices, for when the voice is the product.",
        identifier_label=None,
        secret_label="API key",
        docs_url="https://elevenlabs.io/app/settings/api-keys",
    ),
    ProviderSpec(
        id="openrouter",
        name="OpenRouter",
        role=ProviderRole.INTELLIGENCE,
        # The one genuine login flow here - documented PKCE, verified against
        # OpenRouter's own OAuth guide before this was written.
        connect=ConnectMethod.OAUTH,
        summary="One account, hundreds of models. The agent's reasoning.",
        identifier_label=None,
        secret_label="API key",
        docs_url="https://openrouter.ai/keys",
    ),
)

BY_ID: dict[str, ProviderSpec] = {p.id: p for p in PROVIDERS}
PROVIDER_IDS: frozenset[str] = frozenset(BY_ID)


def spec(provider_id: str) -> ProviderSpec | None:
    return BY_ID.get(provider_id)


__all__ = [
    "BY_ID",
    "PROVIDERS",
    "PROVIDER_IDS",
    "ConnectMethod",
    "ProviderRole",
    "ProviderSpec",
    "spec",
]
