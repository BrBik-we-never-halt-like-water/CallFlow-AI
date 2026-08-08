"""Deployment config parsing.

Render's `fromService … property: host` injects a bare hostname with no
scheme. CORS matching is exact, so a missing scheme silently blocks every
browser request   worth a test.
"""

import pytest

from callflow.config import _origins


def test_bare_hostname_gets_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_ORIGINS", "callflow-web.onrender.com")
    assert _origins("X_ORIGINS") == ["https://callflow-web.onrender.com"]


def test_existing_scheme_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_ORIGINS", "http://localhost:3000")
    assert _origins("X_ORIGINS") == ["http://localhost:3000"]


def test_trailing_slash_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    # A trailing slash never matches an Origin header and is painful to debug.
    monkeypatch.setenv("X_ORIGINS", "https://callflow-web.onrender.com/")
    assert _origins("X_ORIGINS") == ["https://callflow-web.onrender.com"]


def test_multiple_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "X_ORIGINS", "callflow-web.onrender.com, https://example.com/ ,http://localhost:3000"
    )
    assert _origins("X_ORIGINS") == [
        "https://callflow-web.onrender.com",
        "https://example.com",
        "http://localhost:3000",
    ]


def test_unset_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("X_ORIGINS", raising=False)
    assert _origins("X_ORIGINS") == []
