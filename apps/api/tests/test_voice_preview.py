"""Preview orchestration must resolve every failure path to an honest
`PreviewResult` - never raise, never fabricate success. `voice_preview.py`'s
own docstring lists five failure paths (unknown provider, no key configured,
no preview adapter wired, a bad stored key, a vendor error); these tests pin
the first three, which never touch a network call or real crypto, and are
exactly where CLAUDE.md non-negotiable #9 (never show a success state for
something that did not happen) matters most: conflating "you haven't
connected a key" with "we haven't built this preview yet" would tell a user
who already connected a key to go connect one again.
"""

from __future__ import annotations

from app.services.voice_preview import preview_stt, preview_tts


async def test_preview_tts_rejects_an_unknown_provider() -> None:
    result = await preview_tts(provider="not-a-real-vendor", encrypted_api_key=None, text="hello")
    assert result.available is False
    assert "not-a-real-vendor" in (result.reason or "")


async def test_preview_stt_rejects_an_unknown_provider() -> None:
    result = await preview_stt(
        provider="not-a-real-vendor", encrypted_api_key="anything", audio_base64="ZGF0YQ=="
    )
    assert result.available is False
    assert "not-a-real-vendor" in (result.reason or "")


async def test_preview_tts_with_no_key_configured_never_raises_and_says_connect_a_key() -> None:
    """The single most important test in this file: an org that has never
    connected a Sarvam key must get an honest "connect your key" reason -
    never a raised exception, never a fabricated success."""
    result = await preview_tts(provider="sarvam", encrypted_api_key=None, text="hello")
    assert result.available is False
    assert result.audio_base64 is None
    reason = (result.reason or "").lower()
    assert "connect" in reason
    assert "api key" in reason


async def test_preview_stt_with_no_key_configured_never_raises_and_says_connect_a_key() -> None:
    result = await preview_stt(provider="sarvam", encrypted_api_key=None, audio_base64="ZGF0YQ==")
    assert result.available is False
    assert result.transcript is None
    reason = (result.reason or "").lower()
    assert "connect" in reason
    assert "api key" in reason


async def test_preview_stt_for_a_provider_without_a_wired_adapter_is_distinct_from_no_key() -> None:
    """Deepgram has no preview adapter wired at all (`catalog.py`'s
    `preview_available=False`), even with a key present - this reason must
    never read like "connect your key", the exact conflation CLAUDE.md
    non-negotiable #9 forbids. `preview_available` is checked before
    `decrypt()` is ever called, so a placeholder ciphertext never touches
    real crypto or the network."""
    result = await preview_stt(
        provider="deepgram", encrypted_api_key="fake-ciphertext", audio_base64="ZGF0YQ=="
    )
    assert result.available is False
    assert result.transcript is None
    reason = (result.reason or "").lower()
    assert "wired up yet" in reason
    assert "connect" not in reason


async def test_preview_tts_for_a_provider_without_a_wired_adapter_is_distinct_from_no_key() -> None:
    """Same case for TTS: ElevenLabs has no adapter wired, even with a key
    present (`catalog.py`'s `preview_available=False`)."""
    result = await preview_tts(
        provider="elevenlabs", encrypted_api_key="fake-ciphertext", text="hello"
    )
    assert result.available is False
    assert result.audio_base64 is None
    reason = (result.reason or "").lower()
    assert "wired up yet" in reason
    assert "connect" not in reason
