"""Symmetric encryption for org-owned third-party credentials.

Twilio and Plivo credentials are the only place this codebase stores a secret it
must later read back in plaintext - everywhere else (API keys, passwords) only a
hash is kept. `PROVIDER_CREDENTIALS_KEY` never enters the database, matching
`SUPABASE_SECRET_KEY`'s handling.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import config

__all__ = ["CredentialsNotConfigured", "decrypt", "encrypt"]


class CredentialsNotConfigured(RuntimeError):
    """Raised when PROVIDER_CREDENTIALS_KEY is unset and a caller needs it."""


def _fernet() -> Fernet:
    if not config.provider_credentials_key:
        raise CredentialsNotConfigured(
            "PROVIDER_CREDENTIALS_KEY is not set on this deployment - provider "
            "credentials can't be stored or read until it is."
        )
    return Fernet(config.provider_credentials_key.encode("utf-8"))


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialsNotConfigured(
            "Stored credentials could not be decrypted - PROVIDER_CREDENTIALS_KEY "
            "may have changed since they were saved."
        ) from exc
