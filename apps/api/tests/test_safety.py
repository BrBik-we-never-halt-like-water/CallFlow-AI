"""Number handling, and the one gate that still stands before a dial.

The cost guards this file used to cover - the allowlist, the per-run ceiling,
the rate limiter, the daily budget, per-teammate credits - were removed at the
product owner's direction while a replacement security layer is designed, and
their tests went with them.

**The suppression list was kept, and is the reason `check_dial_allowed` still
exists.** It had no test here before; it does now, because it is the only thing
left between a started run and a person who asked never to be called again.
`is_e164`/`mask` remain covered: masking is a standing guarantee (CLAUDE.md #4),
and E.164 validation is still real input validation on uploads even though it no
longer refuses a dial.
"""

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


def test_the_gate_refuses_someone_who_opted_out() -> None:
    """The whole reason this function survived the removal of everything else."""
    result = check_dial_allowed("+15555550100", is_suppressed=True)

    assert result.allowed is False
    assert "opted out" in result.reason


def test_the_refusal_reason_never_contains_the_full_number() -> None:
    """It is written to a call record and read back to a person, so it goes
    through the shared mask like every other user-facing number (CLAUDE.md #4)."""
    result = check_dial_allowed("+15555550100", is_suppressed=True)

    assert "5555550100" not in result.reason
    assert "*" in result.reason


def test_the_gate_allows_a_number_nobody_has_opted_out_of() -> None:
    assert check_dial_allowed("+15555550100").allowed is True


def test_the_gate_no_longer_refuses_on_formatting() -> None:
    """E.164 validation was removed from the dial path deliberately. It is still
    real input validation on uploads (`domain/spreadsheet.py`) - it is simply no
    longer this function's job, and a test asserting the old behaviour would
    fail the next person who reads it as a spec."""
    assert check_dial_allowed("5555550100").allowed is True


def test_the_gate_fails_closed_on_an_unresolvable_suppression_verdict() -> None:
    """A caller that cannot reach the suppression list must pass True, not omit
    the argument. Pins the contract: True always refuses, whatever the number."""
    assert check_dial_allowed("+15555550100", is_suppressed=True).allowed is False
    assert check_dial_allowed("5555550100", is_suppressed=True).allowed is False
