"""CallFlow's own provider keys, used when an organisation has connected none.

The property that matters most here is the ordering: an organisation's own key
must always win, so connecting one in Integrations moves the spend back to the
customer. That half is asserted in `test_run_dispatch_keys.py`, against the real
resolver; this file covers the lookup itself.

Every test sets the environment explicitly rather than reading the developer's
own `.env` - a machine that happens to hold a key must not make a test pass that
would fail in CI, and one that holds none must not make a test fail.
"""

from __future__ import annotations

import pytest

from app.core.platform_keys import platform_key, providers_with_platform_keys


def test_a_provider_with_a_platform_key_resolves_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SARVAM_API_KEY", "sk-platform-sarvam")

    assert platform_key("sarvam") == "sk-platform-sarvam"


def test_a_provider_with_no_platform_key_resolves_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)

    assert platform_key("sarvam") is None


def test_an_unknown_provider_has_no_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """A provider absent from the map gets no key, so the run refuses naming it
    rather than dialling and failing at the first API call."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "sk-should-not-be-found")

    assert platform_key("deepgram") is None


def test_smallest_is_deliberately_not_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SMALLEST_API_KEY` is in the environment but `smallest` is not a provider
    this codebase knows - it is in neither the catalogue nor the
    `ai_provider_credentials.provider` check constraint, so no agent can be
    configured for it. Pinned so adding the key is never mistaken for adding the
    provider."""
    monkeypatch.setenv("SMALLEST_API_KEY", "sk-platform-smallest")

    assert platform_key("smallest") is None


def test_an_empty_or_whitespace_key_is_not_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """`SARVAM_API_KEY=` in a .env is "unset", not "the empty string is my key" -
    treating it as present would dispatch a blank credential and fail mid-call."""
    for value in ("", "   "):
        monkeypatch.setenv("SARVAM_API_KEY", value)
        assert platform_key("sarvam") is None


def test_provider_ids_are_matched_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-platform")

    assert platform_key("OpenRouter") == "sk-or-platform"


def test_sarvam_covers_both_speech_legs(monkeypatch: pytest.MonkeyPatch) -> None:
    """One vendor key sells both Saarika (STT) and Bulbul (TTS), and the
    catalogue lists `sarvam` under both categories - so an agent using it for
    both legs must resolve on one key rather than needing two."""
    monkeypatch.setenv("SARVAM_API_KEY", "sk-platform-sarvam")

    assert platform_key("sarvam") == "sk-platform-sarvam"


def test_a_missing_or_blank_provider_name_never_raises() -> None:
    """Called with whatever is on the agent row, which is nullable."""
    assert platform_key("") is None


def test_the_available_set_reflects_only_keys_actually_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env in (
        "SARVAM_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-platform")

    available = providers_with_platform_keys()

    assert "openrouter" in available
    assert "sarvam" not in available


def test_a_key_added_without_a_restart_is_picked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read from the environment per call, not cached at import - a deployment
    that adds a key should not need a restart to start using it."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert platform_key("groq-whisper") is None

    monkeypatch.setenv("GROQ_API_KEY", "sk-groq-platform")
    assert platform_key("groq-whisper") == "sk-groq-platform"
