"""Generating and hashing CallFlow API keys. Pure — no I/O, no database.

Mirrors how `CALLFLOW_OWNER_KEY` is already checked elsewhere: never compare or
store a plaintext key, only its hash.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

KEY_PREFIX = "cfk_"
# "cfk_" plus 8 more characters — enough to tell two keys apart in a list,
# nowhere near enough to guess the rest.
PREFIX_DISPLAY_LEN = len(KEY_PREFIX) + 8


@dataclass(frozen=True)
class GeneratedApiKey:
    full_key: str
    """Shown to the caller exactly once. Never persisted or logged."""
    key_prefix: str
    key_hash: str


def generate_api_key() -> GeneratedApiKey:
    full_key = KEY_PREFIX + secrets.token_urlsafe(32)
    return GeneratedApiKey(
        full_key=full_key,
        key_prefix=full_key[:PREFIX_DISPLAY_LEN],
        key_hash=hash_api_key(full_key),
    )


def hash_api_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


def looks_like_api_key(token: str) -> bool:
    return token.startswith(KEY_PREFIX)
