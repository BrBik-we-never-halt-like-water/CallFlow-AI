"""The provisioning state machine: every legal move, and every illegal one,
plus the parts of the workflow that need no database to check.

Pure - no database, so this runs in CI where the RLS tests cannot. That is the
whole reason the `_run_steps` case at the bottom lives here rather than beside
the rest of the workflow's tests: `test_number_provisioning.py` is gated on
`DATABASE_URL`, which CI never sets, so a regression there is caught by nobody.
"""

from __future__ import annotations

from typing import Any, Self
from uuid import uuid4

import pytest

from app.domain.provisioning import (
    TERMINAL,
    InvalidTransition,
    ProvisioningStatus,
    can_transition,
    check_transition,
    is_terminal,
)
from app.integrations.telephony.plivo import PlivoCarrier
from app.integrations.telephony.twilio import TwilioCarrier

S = ProvisioningStatus

LEGAL = [
    (S.PENDING, S.PROVISIONING),
    (S.PENDING, S.FAILED),
    (S.PROVISIONING, S.VERIFIED),
    (S.PROVISIONING, S.FAILED),
]


@pytest.mark.parametrize("current,target", LEGAL)
def test_declared_moves_are_allowed(current: S, target: S) -> None:
    assert can_transition(current, target)
    check_transition(current, target)  # must not raise


@pytest.mark.parametrize(
    "current,target",
    [pair for pair in ((c, t) for c in S for t in S) if pair not in LEGAL],
)
def test_every_other_move_is_rejected(current: S, target: S) -> None:
    """Exhaustive over the whole 4x4 grid, so adding a status without deciding
    its edges fails here rather than silently defaulting to permitted."""
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        check_transition(current, target)


def test_a_status_cannot_transition_to_itself() -> None:
    """Re-writing the same status would let a second worker "advance" an attempt
    that is already there, which is the double-write this machine exists to stop."""
    for status in S:
        assert not can_transition(status, status)


def test_terminal_states_are_exactly_verified_and_failed() -> None:
    assert TERMINAL == {S.VERIFIED, S.FAILED}
    assert is_terminal(S.VERIFIED)
    assert is_terminal(S.FAILED)
    assert not is_terminal(S.PENDING)
    assert not is_terminal(S.PROVISIONING)


def test_a_failed_attempt_cannot_be_revived() -> None:
    """"Try again" starts a new attempt with a new key. Reviving this row would
    resume a half-built attempt whose trunk ids are already set."""
    with pytest.raises(InvalidTransition):
        check_transition(S.FAILED, S.PROVISIONING)


def test_a_verified_attempt_cannot_be_failed_afterwards() -> None:
    with pytest.raises(InvalidTransition):
        check_transition(S.VERIFIED, S.FAILED)


def test_the_error_names_both_ends_and_what_was_possible() -> None:
    """CLAUDE.md §5: an error says what happened and what to do next."""
    with pytest.raises(InvalidTransition) as caught:
        check_transition(S.PENDING, S.VERIFIED)

    message = str(caught.value)
    assert "verified" in message
    assert "pending" in message
    # Names the legal alternatives rather than just refusing.
    assert "provisioning" in message and "failed" in message


def test_a_terminal_error_says_to_start_a_new_attempt() -> None:
    with pytest.raises(InvalidTransition) as caught:
        check_transition(S.FAILED, S.VERIFIED)

    assert "start a new attempt" in str(caught.value)


def test_status_values_match_the_database_check_constraint() -> None:
    """The enum and `telephony_provisioning_status_check` must not drift - the
    database rejects an unknown value, but only the enum rejects a known value
    reached illegally, so a mismatch disables one guard silently."""
    assert {s.value for s in S} == {"pending", "provisioning", "verified", "failed"}


class _TrunkRecordingGateway:
    """Captures the kwargs the outbound-trunk step actually sends."""

    def __init__(self) -> None:
        self.outbound_kwargs: dict[str, Any] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def create_outbound_trunk(self, **kwargs: Any) -> str:
        self.outbound_kwargs = kwargs
        return "ST_out_1"


async def _outbound_transport_for(carrier_cls: type, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Run `_run_steps` with only the outbound-trunk step left to do."""
    from app.services import number_provisioning as service

    attempt_id = uuid4()
    # Every earlier step already recorded its result, so this resumes straight
    # to the outbound trunk - which is also the path that has no `CarrierTrunk`
    # in scope, the reason the transport has to come off the carrier class.
    row = {
        "id": attempt_id,
        "livekit_inbound_trunk_id": "ST_in_1",
        "livekit_dispatch_rule_id": "SDR_1",
        "carrier_termination_domain": "acme.zt.plivo.com",
        "livekit_outbound_trunk_id": None,
    }

    async def _record(_conn: Any, _attempt_id: Any, **fields: Any) -> dict[str, Any]:
        return {**row, **fields}

    monkeypatch.setattr(service.provisioning_repo, "record_livekit_ids", _record)

    gateway = _TrunkRecordingGateway()
    await service._run_steps(
        None,
        row=row,
        carrier_cls=carrier_cls,
        credentials={},
        phone_number="+15555550100",
        number_ref="+15555550100",
        label="acme",
        sip_host="abc.sip.livekit.cloud",
        username="u",
        password="p",
        gateway_factory=lambda: gateway,
    )
    return gateway.outbound_kwargs["transport"]


@pytest.mark.asyncio
async def test_the_outbound_trunk_names_plivos_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Left to LiveKit's `auto` default, every outbound call to Plivo is
    rejected - and provisioning still reports verified, so the only symptom is
    calls that never connect."""
    assert await _outbound_transport_for(PlivoCarrier, monkeypatch) == "tls"


@pytest.mark.asyncio
async def test_the_outbound_trunk_leaves_twilio_on_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert await _outbound_transport_for(TwilioCarrier, monkeypatch) == "auto"
