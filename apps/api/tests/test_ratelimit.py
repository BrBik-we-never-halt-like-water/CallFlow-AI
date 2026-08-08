"""Per-organisation rate limiting.

These caps are the only thing standing between a signed-in caller and draining
the engine balance or dialling a number too fast, so they are tested like the
safety gate: fail closed, no off-by-one. Also pinned here: two different keys
(organisations) must never share a bucket — they used to, when this was IP-keyed
with one process-global daily counter (`ISSUES.md`), and two unrelated paying
organisations on the same deployment could rate-limit each other.
"""

import dataclasses

import pytest

from app.core import rate_limit as mod
from app.core.rate_limit import RateLimiter


@pytest.fixture
def limited(monkeypatch: pytest.MonkeyPatch) -> RateLimiter:
    """A limiter allowing 2 calls per IP per hour, 5 per day."""
    monkeypatch.setattr(
        mod,
        "config",
        dataclasses.replace(
            mod.config,
            rate_limit_calls=2,
            rate_limit_window_seconds=3600,
            daily_call_budget=5,
            owner_key="secret",
        ),
    )
    return RateLimiter()


def test_first_call_allowed(limited: RateLimiter) -> None:
    assert limited.check("1.1.1.1", calls=1).allowed is True


def test_limit_is_inclusive(limited: RateLimiter) -> None:
    assert limited.check("1.1.1.1", calls=1).allowed is True
    assert limited.check("1.1.1.1", calls=1).allowed is True
    # Third call in the window is refused.
    assert limited.check("1.1.1.1", calls=1).allowed is False


def test_batch_larger_than_limit_is_refused_atomically(limited: RateLimiter) -> None:
    # A 5-contact run must not partially consume the 2-call allowance.
    assert limited.check("1.1.1.1", calls=5).allowed is False
    # The allowance is untouched, so a valid run still works.
    assert limited.check("1.1.1.1", calls=2).allowed is True


def test_keys_are_independent(limited: RateLimiter) -> None:
    limited.check("1.1.1.1", calls=2)
    assert limited.check("2.2.2.2", calls=1).allowed is True


def test_daily_budget_caps_its_own_key(limited: RateLimiter) -> None:
    # Budget is 5/day; five calls from the same key exhausts that key's own budget.
    # Override the per-window ceiling (2) so it isn't what actually refuses the 5th
    # call — this test is about the daily bucket, not the window one.
    for _ in range(5):
        assert limited.check("org-a", calls=1, rate_limit_calls=99).allowed is True
    verdict = limited.check("org-a", calls=1, rate_limit_calls=99)
    assert verdict.allowed is False
    assert "daily" in verdict.reason.lower()


def test_daily_budget_is_not_shared_across_keys(limited: RateLimiter) -> None:
    # A different key (organisation) gets its own budget, not what's left of
    # someone else's — the bug this used to have when the bucket was global.
    for _ in range(5):
        limited.check("org-a", calls=1, rate_limit_calls=99)
    assert limited.check("org-a", calls=1, rate_limit_calls=99).allowed is False
    assert limited.check("org-b", calls=1, rate_limit_calls=99).allowed is True


def test_owner_bypasses_every_limit(limited: RateLimiter) -> None:
    for _ in range(50):
        assert limited.check("1.1.1.1", calls=10, is_owner=True).allowed is True
    # Owner traffic must not consume the public budget.
    assert limited.check("2.2.2.2", calls=1).allowed is True


def test_refusal_explains_how_to_proceed(limited: RateLimiter) -> None:
    limited.check("1.1.1.1", calls=2)
    verdict = limited.check("1.1.1.1", calls=1)
    assert verdict.allowed is False
    assert "limit" in verdict.reason.lower()
    assert verdict.retry_after_seconds > 0


def test_release_returns_slots(limited: RateLimiter) -> None:
    limited.check("1.1.1.1", calls=2)
    assert limited.check("1.1.1.1", calls=1).allowed is False
    limited.release("1.1.1.1", 2)
    assert limited.check("1.1.1.1", calls=1).allowed is True


def test_window_expiry_frees_the_allowance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mod,
        "config",
        dataclasses.replace(
            mod.config, rate_limit_calls=1, rate_limit_window_seconds=60, daily_call_budget=99
        ),
    )
    limiter = RateLimiter()

    clock = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: clock[0])

    assert limiter.check("1.1.1.1", calls=1).allowed is True
    assert limiter.check("1.1.1.1", calls=1).allowed is False

    clock[0] += 61  # window passes
    assert limiter.check("1.1.1.1", calls=1).allowed is True


def test_snapshot_reports_usage(limited: RateLimiter) -> None:
    limited.check("1.1.1.1", calls=2)
    snap = limited.snapshot("1.1.1.1")
    assert snap["used_today"] == 2
    assert snap["daily_budget"] == 5


def test_snapshot_is_per_key(limited: RateLimiter) -> None:
    limited.check("org-a", calls=2)
    limited.check("org-b", calls=1)
    assert limited.snapshot("org-a")["used_today"] == 2
    assert limited.snapshot("org-b")["used_today"] == 1
