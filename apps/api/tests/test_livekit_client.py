"""The LiveKit boundary, against a stub client.

No LiveKit account is needed for any of this and none should ever be: these
tests assert the *translation* - our arguments into the SDK's request objects,
and the SDK's failures into `DialFailure` - which is the whole job of a vendor
boundary. A live account would prove the network works, not that the mapping is
right.

The stub is the "second implementation" CLAUDE.md's Substitutability rule asks
for. It exists so the gateway is proven to depend on a narrow, declared surface
rather than on whatever `LiveKitAPI` happens to expose.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.entities import DialFailure
from app.integrations.livekit.client import (
    EngineError,
    LiveKitGateway,
    SipTransport,
    classify_error,
)


class StubSip:
    """Records every request object it is handed, and answers with fake ids."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.calls: list[tuple[str, Any]] = []
        self._fail_with = fail_with

    def _maybe_fail(self) -> None:
        if self._fail_with is not None:
            raise self._fail_with

    async def create_sip_inbound_trunk(self, request: Any) -> Any:
        self.calls.append(("inbound", request))
        self._maybe_fail()
        return type("Info", (), {"sip_trunk_id": "ST_inbound_1"})()

    async def create_sip_outbound_trunk(self, request: Any) -> Any:
        self.calls.append(("outbound", request))
        self._maybe_fail()
        return type("Info", (), {"sip_trunk_id": "ST_outbound_1"})()

    async def create_sip_dispatch_rule(self, request: Any) -> Any:
        self.calls.append(("dispatch", request))
        self._maybe_fail()
        return type("Info", (), {"sip_dispatch_rule_id": "SDR_1"})()

    async def create_sip_participant(self, request: Any) -> Any:
        self.calls.append(("participant", request))
        self._maybe_fail()
        return type(
            "Info",
            (),
            {
                "participant_id": "PA_1",
                "participant_identity": request.participant_identity,
                "sip_call_id": "SCL_1",
            },
        )()


class StubClient:
    def __init__(self, sip: StubSip) -> None:
        self.sip = sip
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _gateway(sip: StubSip | None = None) -> tuple[LiveKitGateway, StubSip, list[StubClient]]:
    stub_sip = sip or StubSip()
    made: list[StubClient] = []

    def factory(*, url: str, api_key: str, api_secret: str) -> StubClient:
        client = StubClient(stub_sip)
        made.append(client)
        return client

    gateway = LiveKitGateway(
        url="wss://test.livekit.cloud",
        api_key="k",
        api_secret="s",
        client_factory=factory,
    )
    return gateway, stub_sip, made


def _twirp(code: str, *, sip_status: int | None = None) -> EngineError:
    metadata = {} if sip_status is None else {"sip_status_code": str(sip_status)}
    return EngineError(code, "stub failure", status=500, metadata=metadata)


# --- configuration ------------------------------------------------------------


def test_an_unconfigured_gateway_refuses_to_construct() -> None:
    """Fails at construction, not at the first API call - so a misconfigured
    deployment is discovered before it has half-created a trunk."""
    with pytest.raises(RuntimeError) as caught:
        LiveKitGateway(url="", api_key="", api_secret="")

    message = str(caught.value)
    assert "LIVEKIT_URL" in message and "LIVEKIT_API_KEY" in message


def test_using_the_gateway_unopened_is_an_error_not_a_crash() -> None:
    gateway, _, _ = _gateway()
    with pytest.raises(RuntimeError) as caught:
        _ = gateway._sip
    assert "async with" in str(caught.value)


async def test_the_session_is_closed_on_exit() -> None:
    """The SDK owns an aiohttp session; leaking one per call leaks sockets."""
    gateway, _, made = _gateway()
    async with gateway:
        pass
    assert made[0].closed is True


async def test_the_session_is_closed_even_when_the_body_raises() -> None:
    gateway, _, made = _gateway()
    with pytest.raises(ValueError):
        async with gateway:
            raise ValueError("boom")
    assert made[0].closed is True


# --- request translation ------------------------------------------------------


async def test_inbound_trunk_passes_numbers_and_allowed_addresses() -> None:
    gateway, sip, _ = _gateway()
    async with gateway as g:
        trunk_id = await g.create_inbound_trunk(
            name="Org A", numbers=["+15555550100"], allowed_addresses=["1.2.3.4/32"]
        )

    assert trunk_id == "ST_inbound_1"
    kind, request = sip.calls[0]
    assert kind == "inbound"
    assert list(request.trunk.numbers) == ["+15555550100"]
    assert list(request.trunk.allowed_addresses) == ["1.2.3.4/32"]


async def test_outbound_trunk_carries_the_explicit_transport() -> None:
    """Plivo rejects an origination URI with no transport; Twilio infers one.
    Sending it explicitly is what makes the same code work for both."""
    gateway, sip, _ = _gateway()
    async with gateway as g:
        await g.create_outbound_trunk(
            name="Org A out",
            address="org-a.zt.plivo.com",
            numbers=["+15555550100"],
            auth_username="user",
            auth_password="pass",
            transport=SipTransport.TCP,
        )

    _, request = sip.calls[0]
    assert request.trunk.address == "org-a.zt.plivo.com"
    assert request.trunk.auth_username == "user"
    # The vendor enum value for TCP, resolved from our own plain-string constant.
    assert request.trunk.transport != 0


async def test_dispatch_rule_gives_each_caller_their_own_room() -> None:
    """A direct rule would drop two unrelated callers into one conversation."""
    gateway, sip, _ = _gateway()
    async with gateway as g:
        rule_id = await g.create_dispatch_rule(
            name="Org A rule", room_prefix="org-a", trunk_ids=["ST_inbound_1"]
        )

    assert rule_id == "SDR_1"
    _, request = sip.calls[0]
    assert request.dispatch_rule.rule.dispatch_rule_individual.room_prefix == "org-a"
    assert list(request.dispatch_rule.trunk_ids) == ["ST_inbound_1"]


async def test_start_call_waits_until_answered_by_default() -> None:
    """Without this the SDK returns as soon as the INVITE is sent, and a busy
    number is indistinguishable from a connected one - which would make every
    classification below meaningless."""
    gateway, sip, _ = _gateway()
    async with gateway as g:
        result = await g.start_call(
            trunk_id="ST_outbound_1",
            phone="+15555550100",
            room_name="run-abc-contact-1",
            participant_identity="contact-1",
        )

    _, request = sip.calls[0]
    assert request.wait_until_answered is True
    assert request.sip_call_to == "+15555550100"
    assert request.room_name == "run-abc-contact-1"
    assert result["room_name"] == "run-abc-contact-1"
    assert result["sip_call_id"] == "SCL_1"


async def test_start_call_uses_the_room_name_it_was_given() -> None:
    """The worker is dispatched into the same room, so the name cannot be
    invented here - two places inventing it is how they stop matching."""
    gateway, sip, _ = _gateway()
    async with gateway as g:
        await g.start_call(
            trunk_id="T",
            phone="+15555550101",
            room_name="agreed-room",
            participant_identity="contact-2",
            participant_name="Priya",
        )

    _, request = sip.calls[0]
    assert request.room_name == "agreed-room"
    assert request.participant_name == "Priya"


# --- error classification -----------------------------------------------------


@pytest.mark.parametrize(
    "sip_status,expected",
    [
        (486, DialFailure.BUSY),
        (600, DialFailure.BUSY),
        (480, DialFailure.NO_ANSWER),
        (408, DialFailure.NO_ANSWER),
        (404, DialFailure.INVALID_NUMBER),
        (484, DialFailure.INVALID_NUMBER),
        (403, DialFailure.UNAUTHORIZED),
        (407, DialFailure.UNAUTHORIZED),
        (402, DialFailure.INSUFFICIENT_BALANCE),
        (603, DialFailure.POLICY_VIOLATION),
        (503, DialFailure.PROVIDER_UNAVAILABLE),
        (500, DialFailure.INTERNAL),
    ],
)
def test_sip_status_codes_map_to_the_shared_taxonomy(
    sip_status: int, expected: DialFailure
) -> None:
    assert classify_error(_twirp("internal", sip_status=sip_status)) is expected


@pytest.mark.parametrize(
    "code,expected",
    [
        ("invalid_argument", DialFailure.INVALID_NUMBER),
        ("unauthenticated", DialFailure.UNAUTHORIZED),
        ("permission_denied", DialFailure.UNAUTHORIZED),
        ("resource_exhausted", DialFailure.RATE_LIMITED),
        ("unavailable", DialFailure.PROVIDER_UNAVAILABLE),
        ("deadline_exceeded", DialFailure.TIMED_OUT),
    ],
)
def test_twirp_codes_map_when_there_is_no_sip_status(
    code: str, expected: DialFailure
) -> None:
    assert classify_error(_twirp(code)) is expected


def test_the_sip_status_wins_over_the_transport_code() -> None:
    """A busy line arrives as a transport-level `internal` carrying "486". The
    specific answer is the useful one: "internal" would tell an operator we
    broke, when in fact the person was on another call."""
    assert classify_error(_twirp("internal", sip_status=486)) is DialFailure.BUSY


def test_an_unmapped_code_fails_closed_to_internal() -> None:
    """A LiveKit error this code has never seen must not be treated as a
    known-safe, retryable failure - INTERNAL is deliberately not retryable."""
    assert classify_error(_twirp("a_brand_new_code_from_the_future")) is DialFailure.INTERNAL


def test_an_unmapped_sip_status_falls_through_to_the_transport_code() -> None:
    """499 means nothing to us, but `unavailable` still does."""
    assert classify_error(_twirp("unavailable", sip_status=499)) is (
        DialFailure.PROVIDER_UNAVAILABLE
    )


def test_a_non_vendor_exception_is_internal() -> None:
    assert classify_error(ConnectionError("dns lookup failed")) is DialFailure.INTERNAL


def test_a_junk_sip_status_does_not_crash_the_classifier() -> None:
    """A classifier that raises turns a failed call into a 500. Garbage metadata
    is treated as absent."""
    exc = EngineError("unavailable", "?", status=500, metadata={"sip_status_code": "not-a-number"})
    assert classify_error(exc) is DialFailure.PROVIDER_UNAVAILABLE


def test_missing_metadata_entirely_is_handled() -> None:
    exc = EngineError("unavailable", "?", status=500)
    assert classify_error(exc) is DialFailure.PROVIDER_UNAVAILABLE


async def test_a_failing_call_raises_the_vendor_error_for_the_caller_to_classify() -> None:
    """The gateway does not swallow and translate in place - `campaign_runner`
    decides what a failure means for a run, and needs the exception to do it."""
    gateway, _, _ = _gateway(StubSip(fail_with=_twirp("internal", sip_status=486)))

    with pytest.raises(EngineError) as caught:
        async with gateway as g:
            await g.start_call(
                trunk_id="T", phone="+15555550100", room_name="r", participant_identity="c"
            )

    assert classify_error(caught.value) is DialFailure.BUSY


def test_every_dial_failure_is_reachable_from_some_vendor_error() -> None:
    """A taxonomy value nothing can produce is dead vocabulary. Every member
    must be reachable, or it should not exist."""
    from app.integrations.livekit.client import (
        _SIP_STATUS_FAILURES,
        _TWIRP_CODE_FAILURES,
    )

    produced = set(_SIP_STATUS_FAILURES.values()) | set(_TWIRP_CODE_FAILURES.values())
    assert produced == set(DialFailure), f"unreachable: {set(DialFailure) - produced}"
