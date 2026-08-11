"""Safety guardrails must fail closed."""

import dataclasses

import pytest

from app.domain import safety
from app.domain.safety import (
    EffectiveSafety,
    apply_run_override,
    assert_e164,
    check_dial_allowed,
    is_e164,
    mask,
    resolve_safety_settings,
)


@pytest.mark.parametrize(
    "phone,valid",
    [
        ("+15555550100", True),
        ("+441632960100", True),
        ("5555550100", False),      # no country code
        ("+0123456789", False),     # leading zero after +
        ("+1 555 555 0100", False),  # spaces
        ("", False),
        ("+123", False),            # too short
    ],
)
def test_is_e164(phone: str, valid: bool) -> None:
    assert is_e164(phone) is valid


def test_assert_e164_raises_with_masked_number() -> None:
    # Use digits that do not appear in the error message's example number,
    # so we test the masking rather than the hint text.
    with pytest.raises(ValueError) as exc:
        assert_e164("4402255880")
    message = str(exc.value)
    assert "4402255880" not in message
    assert "*" in message


def test_mask_hides_the_middle() -> None:
    masked = mask("+15555550100")
    assert masked.startswith("+15")
    assert masked.endswith("100")
    assert "5555550" not in masked


def test_mask_short_input() -> None:
    assert mask("+91") == "***"


@pytest.mark.parametrize(
    "phone",
    ["+15555550100", "5555550100", "+441632960100", "1234567", "+919876543210"],
)
def test_mask_always_hides_at_least_half(phone: str) -> None:
    masked = mask(phone)
    assert masked.count("*") >= len(phone) / 2


def test_gate_rejects_invalid_number() -> None:
    result = check_dial_allowed("5555550100", 0)
    assert result.allowed is False


def test_gate_rejects_past_ceiling() -> None:
    result = check_dial_allowed("+15555550100", 999)
    assert result.allowed is False
    assert "ceiling" in result.reason


def test_gate_allows_valid_number_under_ceiling() -> None:
    assert check_dial_allowed("+15555550100", 0).allowed is True


def test_gate_respects_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    # Config is frozen, so swap in a replaced copy rather than mutating it.
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, allowlist=["+15555550199"])
    )
    assert safety.check_dial_allowed("+15555550100", 0).allowed is False
    assert safety.check_dial_allowed("+15555550199", 0).allowed is True


def test_gate_ignores_credits_when_no_per_teammate_ceiling_is_set() -> None:
    # `None` means "nobody has ever set this caller's allocation" - the
    # org-wide daily budget is the only gate in that case, not zero calls.
    result = check_dial_allowed("+15555550100", 0, credits_remaining=None)
    assert result.allowed is True


def test_gate_rejects_when_credits_are_exhausted() -> None:
    result = check_dial_allowed("+15555550100", 0, credits_remaining=0)
    assert result.allowed is False
    assert "credit" in result.reason


def test_gate_allows_when_credits_remain() -> None:
    assert check_dial_allowed("+15555550100", 0, credits_remaining=1).allowed is True


def test_resolve_safety_settings_falls_back_when_org_never_configured() -> None:
    """`None` (no `org_safety_settings` row at all) means "use the deployment
    default" - the one case this function is actually meant to fall back on."""
    effective = resolve_safety_settings(
        allowlist=None,
        max_calls_per_run=None,
        calls_per_window=None,
        window_minutes=None,
        daily_budget=None,
    )
    assert effective.allowlist == frozenset(safety.config.allowlist)
    assert effective.max_calls_per_run == safety.config.max_calls_per_run
    assert effective.daily_budget == safety.config.daily_call_budget


def test_resolve_safety_settings_an_explicitly_cleared_allowlist_stays_cleared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An org that clears its own allowlist means "no restriction" - it must
    not silently fall back to the deployment's `CALLFLOW_ALLOWLIST`. Regression
    for a bug where `[] if allowlist else config.allowlist` treated an
    explicitly emptied override the same as "never configured"."""
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, allowlist=["+15555550199"])
    )
    effective = resolve_safety_settings(
        allowlist=[],
        max_calls_per_run=None,
        calls_per_window=None,
        window_minutes=None,
        daily_budget=None,
    )
    assert effective.allowlist == frozenset()


def test_resolve_safety_settings_org_override_wins_over_deployment_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, max_calls_per_run=3)
    )
    effective = resolve_safety_settings(
        allowlist=None,
        max_calls_per_run=10,
        calls_per_window=None,
        window_minutes=None,
        daily_budget=None,
    )
    assert effective.max_calls_per_run == 10


def _effective(
    *,
    allowlist: frozenset[str] = frozenset(),
    max_calls_per_run: int = 10,
    calls_per_window: int = 5,
    window_minutes: int = 60,
    daily_budget: int = 20,
) -> EffectiveSafety:
    return EffectiveSafety(
        allowlist=allowlist,
        max_calls_per_run=max_calls_per_run,
        calls_per_window=calls_per_window,
        window_minutes=window_minutes,
        daily_budget=daily_budget,
    )


def test_run_override_can_lower_the_ceiling() -> None:
    result = apply_run_override(_effective(max_calls_per_run=10), max_calls_per_run=3)
    assert result.max_calls_per_run == 3


def test_run_override_cannot_raise_the_ceiling_above_the_organisations_own() -> None:
    """The whole point of a per-org ceiling is that starting a run can't
    bypass it - a request for more is silently capped, not honoured."""
    result = apply_run_override(_effective(max_calls_per_run=10), max_calls_per_run=999)
    assert result.max_calls_per_run == 10


def test_run_override_ceiling_omitted_keeps_the_organisations_own() -> None:
    result = apply_run_override(_effective(max_calls_per_run=10))
    assert result.max_calls_per_run == 10


def test_run_override_allowlist_narrows_a_non_empty_organisation_allowlist() -> None:
    """A run-level allowlist can only intersect with the organisation's own -
    it can never add a number the organisation itself excludes."""
    result = apply_run_override(
        _effective(allowlist=frozenset({"+15555550100", "+15555550101"})),
        allowlist=["+15555550100", "+15555550199"],
    )
    assert result.allowlist == frozenset({"+15555550100"})


def test_run_override_allowlist_applies_directly_when_organisation_has_none() -> None:
    """An empty organisation allowlist means "no restriction" - a run-level
    list is then a real, standalone restriction, not an intersection with
    nothing (which would wrongly produce an empty, unusable allowlist)."""
    result = apply_run_override(
        _effective(allowlist=frozenset()), allowlist=["+15555550100"]
    )
    assert result.allowlist == frozenset({"+15555550100"})


def test_run_override_allowlist_omitted_keeps_the_organisations_own() -> None:
    org_allowlist = frozenset({"+15555550100"})
    result = apply_run_override(_effective(allowlist=org_allowlist))
    assert result.allowlist == org_allowlist


def test_run_override_never_touches_rate_or_budget_fields() -> None:
    """Only max_calls_per_run and allowlist are per-run overridable - the
    rate window and daily budget are whole-organisation resources shared
    across every run today, not this run's own limit."""
    base = _effective(calls_per_window=5, window_minutes=60, daily_budget=20)
    result = apply_run_override(base, max_calls_per_run=1, allowlist=["+15555550100"])
    assert result.calls_per_window == 5
    assert result.window_minutes == 60
    assert result.daily_budget == 20
