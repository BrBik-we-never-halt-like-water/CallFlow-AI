"""Preview orchestration for the Agentic tab's STT/TTS provider picker.

Decrypts an org's stored API key and calls the matching vendor adapter to
produce a one-shot audio/transcript sample. This is `services/`, not
`domain/`, because it does real I/O (decryption, an HTTP call to a vendor) -
`domain/` stays pure per CLAUDE.md's dependency rule, the same split
`campaign_runner.py` draws between orchestration and the pure logic in
`domain/outcome_extraction.py` and `domain/goal_rendering.py`.

The route layer (a later task) owns fetching the org's
`ai_provider_credentials` row via the Task 2 repository and passing the
encrypted key in - this module never touches `app.database`.

`preview_tts`/`preview_stt` never let a vendor exception or a stack trace
escape uncaught: every failure path - unknown provider, missing key, no
preview adapter wired, a bad stored key, a vendor error - resolves to a
`PreviewResult(available=False, reason=...)` with a distinct, honest reason
per CLAUDE.md non-negotiable #9. Conflating "you haven't connected a key"
with "we haven't built this preview yet" would tell a user who already
connected a key to go connect one again, which is exactly the dishonest-UI
failure that rule exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.crypto import CredentialsNotConfigured, decrypt
from app.integrations.ai_providers import catalog
from app.integrations.ai_providers.catalog import ProviderCatalogEntry
from app.integrations.ai_providers.protocol import AdapterUnavailable
from app.integrations.ai_providers.sarvam import SarvamAdapter

__all__ = ["PreviewResult", "preview_stt", "preview_tts"]


@dataclass(frozen=True)
class PreviewResult:
    available: bool
    reason: str | None = None
    audio_base64: str | None = None
    transcript: str | None = None


def _find_entry(provider: str, category: str) -> ProviderCatalogEntry | None:
    return next(
        (
            entry
            for entry in catalog.all_providers()
            if entry.id == provider and entry.category == category
        ),
        None,
    )


async def preview_tts(
    *,
    provider: str,
    encrypted_api_key: str | None,
    text: str,
    voice_id: str | None = None,
) -> PreviewResult:
    entry = _find_entry(provider, "tts")
    if entry is None:
        return PreviewResult(available=False, reason=f"Unknown provider: {provider}")
    if encrypted_api_key is None:
        return PreviewResult(
            available=False,
            reason=f"Connect your {entry.vendor} API key first to preview this.",
        )
    if not entry.preview_available:
        return PreviewResult(
            available=False,
            reason=(
                f"Live preview for {entry.name} isn't wired up yet - you can still "
                "select it for your agent."
            ),
        )

    try:
        api_key = decrypt(encrypted_api_key)
    except CredentialsNotConfigured:
        return PreviewResult(
            available=False,
            reason="Stored credentials could not be read - reconnect your API key.",
        )

    try:
        if provider != "sarvam":
            # Only Sarvam has a real adapter in this task. A catalog entry with
            # preview_available=True but no branch here would otherwise silently
            # do nothing - fail closed instead, per CLAUDE.md's non-negotiable #2.
            raise AdapterUnavailable(
                f"No preview adapter wired for provider: {provider}"
            )
        audio_base64 = await SarvamAdapter().synthesize_sample(
            api_key=api_key, text=text, voice_id=voice_id
        )
    except AdapterUnavailable as exc:
        return PreviewResult(available=False, reason=str(exc))

    return PreviewResult(available=True, audio_base64=audio_base64)


async def preview_stt(
    *,
    provider: str,
    encrypted_api_key: str | None,
    audio_base64: str,
    language: str | None = None,
) -> PreviewResult:
    entry = _find_entry(provider, "stt")
    if entry is None:
        return PreviewResult(available=False, reason=f"Unknown provider: {provider}")
    if encrypted_api_key is None:
        return PreviewResult(
            available=False,
            reason=f"Connect your {entry.vendor} API key first to preview this.",
        )
    if not entry.preview_available:
        return PreviewResult(
            available=False,
            reason=(
                f"Live preview for {entry.name} isn't wired up yet - you can still "
                "select it for your agent."
            ),
        )

    try:
        api_key = decrypt(encrypted_api_key)
    except CredentialsNotConfigured:
        return PreviewResult(
            available=False,
            reason="Stored credentials could not be read - reconnect your API key.",
        )

    try:
        if provider != "sarvam":
            raise AdapterUnavailable(
                f"No preview adapter wired for provider: {provider}"
            )
        transcript = await SarvamAdapter().transcribe_sample(
            api_key=api_key, audio_base64=audio_base64, language=language
        )
    except AdapterUnavailable as exc:
        return PreviewResult(available=False, reason=str(exc))

    return PreviewResult(available=True, transcript=transcript)
