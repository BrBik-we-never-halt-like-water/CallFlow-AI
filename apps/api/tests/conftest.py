"""Test isolation.

The suite must not depend on whatever is in a developer's local .env - a real
Fernet key or a stray provider key would otherwise change results depending on
whose machine ran them.
"""

import dataclasses

import pytest

from app.core import config as config_module
from app.core import crypto
from app.domain import safety
from app.services import run_dialer

# A real (but test-only) Fernet key, so encrypt()/decrypt() work by default
# without every test needing its own override.
TEST_FERNET_KEY = "6h_e3OqedgMK59MQ6Om6I5T9fsyHDYnoCEZ7ufYfHdA="


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin config to known defaults for every test."""
    pinned = dataclasses.replace(
        config_module.config,
        provider_credentials_key=TEST_FERNET_KEY,
    )
    # Each module imported `config` by value, so patch every binding.
    for module in (config_module, safety, run_dialer, crypto):
        monkeypatch.setattr(module, "config", pinned, raising=False)
