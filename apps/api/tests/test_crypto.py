"""Encryption for org-owned provider credentials. Pure — no database.

`isolated_config` (conftest.py) pins a real test Fernet key for every test in
the suite, so encrypt()/decrypt() work here without a per-test override.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.core import crypto
from app.core.crypto import CredentialsNotConfigured, decrypt, encrypt


def test_round_trips_the_original_value():
    # Deliberately not shaped like a real vendor credential (e.g. Twilio's
    # AC-prefixed Account SID) — GitHub's secret scanner pattern-matches on
    # format alone and will block a push over a string that merely looks like
    # a credential, even inside a test fixture.
    token = encrypt("plaintext-credential-value-for-testing")
    assert token != "plaintext-credential-value-for-testing"
    assert decrypt(token) == "plaintext-credential-value-for-testing"


def test_two_encryptions_of_the_same_value_differ():
    """Fernet includes a random nonce, so ciphertext never repeats — a stored row
    never reveals that two organisations share the same secret."""
    assert encrypt("same-secret") != encrypt("same-secret")


def test_raises_without_a_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        crypto, "config", dataclasses.replace(crypto.config, provider_credentials_key="")
    )
    with pytest.raises(CredentialsNotConfigured):
        encrypt("anything")


def test_tampered_ciphertext_fails_closed():
    token = encrypt("a-real-secret")
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(CredentialsNotConfigured):
        decrypt(tampered)
