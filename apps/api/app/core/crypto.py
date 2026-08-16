"""Symmetric encryption for org-owned third-party credentials.

Provider credentials are the only place this codebase stores a secret it must
later read back in plaintext - everywhere else (API keys, passwords) only a hash
is kept. `PROVIDER_CREDENTIALS_KEY` never enters the database, matching
`SUPABASE_SECRET_KEY`'s handling.

`pack_fields`/`unpack_fields` are the shape credentials are stored in: one
ciphertext per row holding the whole JSON object, rather than one per field.
Per-field encryption would leave the field *names* in plaintext, which is enough
to tell an attacker reading the table which vendor a row is for and how it
authenticates.
"""

from __future__ import annotations

import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import config

__all__ = [
    "CredentialsNotConfigured",
    "decrypt",
    "encrypt",
    "pack_fields",
    "unpack_fields",
]


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


def pack_fields(fields: dict[str, str]) -> str:
    """One provider's credentials, as the single ciphertext a row stores."""
    return encrypt(json.dumps(fields, separators=(",", ":"), sort_keys=True))


def unpack_fields(row: object) -> dict[str, str]:
    """Read a credential row back, whichever shape it was written in.

    Rows written before `c8e1f4a29b76` carry `identifier_encrypted` and
    `secret_encrypted` instead of `fields_encrypted`. Those are returned under
    the generic `identifier`/`secret` keys, and the caller maps them onto the
    provider's own field names - only `routes/integrations.py` knows enough to
    do that, and only until the last legacy row is rewritten.

    Takes the row rather than the columns so a caller cannot accidentally pass
    the two legacy values while a `fields_encrypted` sits unread beside them.
    """
    packed = _column(row, "fields_encrypted")
    if packed:
        loaded = json.loads(decrypt(packed))
        if not isinstance(loaded, dict):
            raise CredentialsNotConfigured(
                "Stored credentials are not in the expected shape - reconnect this provider."
            )
        return {str(k): str(v) for k, v in loaded.items()}

    legacy: dict[str, str] = {}
    identifier = _column(row, "identifier_encrypted")
    secret = _column(row, "secret_encrypted")
    if identifier:
        legacy["identifier"] = decrypt(identifier)
    if secret:
        legacy["secret"] = decrypt(secret)
    return legacy


def _column(row: object, name: str) -> str | None:
    try:
        value = row[name]  # type: ignore[index]
    except (KeyError, TypeError):
        return None
    return str(value) if value else None
