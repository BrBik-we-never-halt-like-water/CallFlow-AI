"""Test isolation.

The suite must not depend on whatever is in a developer's local .env — an
allowlist set for real-call testing would otherwise fail unrelated tests.
"""

import dataclasses

import pytest

from app.core import config as config_module
from app.core import crypto
from app.domain import safety
from app.services import campaign_runner

# A real (but test-only) Fernet key, so encrypt()/decrypt() work by default
# without every test needing its own override.
TEST_FERNET_KEY = "6h_e3OqedgMK59MQ6Om6I5T9fsyHDYnoCEZ7ufYfHdA="


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin config to known defaults for every test."""
    pinned = dataclasses.replace(
        config_module.config,
        max_calls_per_run=5,
        allowlist=[],
        provider_credentials_key=TEST_FERNET_KEY,
    )
    # Each module imported `config` by value, so patch every binding.
    for module in (config_module, safety, campaign_runner, crypto):
        monkeypatch.setattr(module, "config", pinned, raising=False)
