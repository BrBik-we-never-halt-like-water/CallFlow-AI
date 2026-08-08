"""Test isolation.

The suite must not depend on whatever is in a developer's local .env   an
allowlist set for real-call testing would otherwise fail unrelated tests.
"""

import dataclasses

import pytest

from callflow import config as config_module
from callflow import orchestrator, safety


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin config to known defaults for every test."""
    pinned = dataclasses.replace(
        config_module.config,
        dry_run=True,
        max_calls_per_run=5,
        allowlist=[],
    )
    # Each module imported `config` by value, so patch every binding.
    for module in (config_module, safety, orchestrator):
        monkeypatch.setattr(module, "config", pinned, raising=False)
