"""Safety guardrails must fail closed."""

import pytest

from app.domain.safety import assert_e164, check_dial_allowed, is_e164, mask


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
    import dataclasses

    from app.domain import safety

    # Config is frozen, so swap in a replaced copy rather than mutating it.
    monkeypatch.setattr(
        safety, "config", dataclasses.replace(safety.config, allowlist=["+15555550199"])
    )
    assert safety.check_dial_allowed("+15555550100", 0).allowed is False
    assert safety.check_dial_allowed("+15555550199", 0).allowed is True
