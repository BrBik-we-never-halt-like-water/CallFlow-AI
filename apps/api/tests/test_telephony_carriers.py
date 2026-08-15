"""The Twilio and Plivo adapters, against stubbed HTTP.

No carrier account is needed and none should be: what is under test is the
*shaping* - which endpoints are called, in what order, with what body, and what
a vendor error becomes. A live account would prove the network works, not that
the requests are right.

The two adapters are asserted against the same expectations wherever their
behaviour should match, because a third carrier is meant to be one more file
and nothing else. Where they genuinely differ - Plivo's mandatory transport
parameter, Twilio's inability to authenticate inbound - the difference is
asserted explicitly rather than left implied.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.integrations.telephony import CarrierError, sip_uri
from app.integrations.telephony.plivo import PlivoCarrier
from app.integrations.telephony.twilio import TWILIO_SIGNALLING_CIDRS, TwilioCarrier

LIVEKIT_HOST = "5t4ms1u1nvx.sip.livekit.cloud"


class Recorder:
    """Records every request and answers from a scripted sequence."""

    def __init__(self, *responses: Any) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._responses:
            return self._responses.pop(0)
        return httpx.Response(200, json={"sid": "TK_stub", "trunk_id": "TR_stub", "id": "ID_stub"})

    @property
    def paths(self) -> list[str]:
        return [r.url.path for r in self.requests]

    def body_of(self, index: int) -> dict[str, str]:
        request = self.requests[index]
        raw = request.content.decode()
        if request.headers.get("content-type", "").startswith("application/json"):
            import json

            return json.loads(raw)
        from urllib.parse import parse_qs

        return {k: v[0] for k, v in parse_qs(raw).items()}


def _client(recorder: Recorder) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))


# --- the shared URI rule ------------------------------------------------------


def test_the_sip_uri_always_names_a_transport() -> None:
    """Plivo rejects a URI without one and Twilio's own example includes it.
    Written once so the two adapters cannot drift."""
    assert sip_uri(LIVEKIT_HOST) == f"sip:{LIVEKIT_HOST};transport=tcp"
    assert sip_uri(LIVEKIT_HOST, "tls").endswith(";transport=tls")


def test_the_sip_uri_tolerates_a_host_that_already_has_a_scheme() -> None:
    """The LiveKit console shows the host with and without `sip:` depending on
    where you copy it from - both must produce one well-formed URI."""
    assert sip_uri(f"sip:{LIVEKIT_HOST}") == f"sip:{LIVEKIT_HOST};transport=tcp"


# --- Twilio -------------------------------------------------------------------


async def test_twilio_configures_the_trunk_before_attaching_the_number() -> None:
    """Order matters: until the number is attached, nothing about the org's
    live traffic has changed, so a failure part-way leaves a stray trunk rather
    than a number ringing into nowhere."""
    recorder = Recorder()
    async with TwilioCarrier(
        account_sid="AC123", auth_token="tok", client=_client(recorder)
    ) as carrier:
        result = await carrier.configure_number(
            phone_number_sid="PN123",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    assert "/Trunks" in recorder.paths[0]
    assert recorder.paths[-1].endswith("/PhoneNumbers")
    assert result.provider == "twilio"
    # Twilio has no termination domain; branching on the provider name instead
    # of on this being None is what this field exists to prevent.
    assert result.termination_domain is None


async def test_twilio_sends_the_livekit_uri_with_a_transport() -> None:
    recorder = Recorder()
    async with TwilioCarrier(
        account_sid="AC123", auth_token="tok", client=_client(recorder)
    ) as carrier:
        await carrier.configure_number(
            phone_number_sid="PN123",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    origination = next(
        i for i, p in enumerate(recorder.paths) if p.endswith("/OriginationUrls")
    )
    assert recorder.body_of(origination)["SipUrl"] == f"sip:{LIVEKIT_HOST};transport=tcp"


async def test_twilio_creates_outbound_credentials() -> None:
    """Twilio authenticates outbound even though it cannot authenticate inbound."""
    recorder = Recorder()
    async with TwilioCarrier(
        account_sid="AC123", auth_token="tok", client=_client(recorder)
    ) as carrier:
        await carrier.configure_number(
            phone_number_sid="PN123",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="lk-user",
            auth_password="lk-pass",
        )

    creds = next(i for i, p in enumerate(recorder.paths) if p.endswith("/Credentials.json"))
    body = recorder.body_of(creds)
    assert body["Username"] == "lk-user"
    assert body["Password"] == "lk-pass"


def test_twilio_supplies_ip_ranges_because_it_cannot_authenticate_inbound() -> None:
    """The origination URI is effectively a shared secret, so the LiveKit
    inbound trunk has to be restricted to Twilio's own signalling addresses -
    without them, anyone who learns the URI can deliver calls into an org's
    rooms."""
    addresses = TwilioCarrier.allowed_addresses()

    assert addresses == list(TWILIO_SIGNALLING_CIDRS)
    assert addresses, "an empty allowlist would leave inbound wide open"
    assert all("/" in cidr for cidr in addresses)


def test_twilio_refuses_to_construct_without_credentials() -> None:
    with pytest.raises(CarrierError) as caught:
        TwilioCarrier(account_sid="", auth_token="")
    assert "no Account SID" in str(caught.value)


async def test_a_twilio_error_surfaces_the_vendors_own_message() -> None:
    """`last_error` is shown to an operator verbatim, so a generic "request
    failed" would tell them nothing they can act on (CLAUDE.md §5)."""
    recorder = Recorder(
        httpx.Response(400, json={"message": "PhoneNumberSid is not valid.", "code": 21421})
    )
    async with TwilioCarrier(
        account_sid="AC123", auth_token="tok", client=_client(recorder)
    ) as carrier:
        with pytest.raises(CarrierError) as caught:
            await carrier.configure_number(
                phone_number_sid="bad",
                livekit_sip_host=LIVEKIT_HOST,
                label="Org A",
                auth_username="u",
                auth_password="p",
            )

    message = str(caught.value)
    assert "PhoneNumberSid is not valid." in message
    assert "21421" in message
    assert "Twilio could not create a SIP trunk" in message


async def test_an_unreachable_twilio_says_so_rather_than_raising_a_transport_error() -> None:
    recorder = Recorder()

    def explode(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns lookup failed")

    async with httpx.AsyncClient(transport=httpx.MockTransport(explode)) as http:
        carrier = TwilioCarrier(account_sid="AC123", auth_token="tok", client=http)
        async with carrier:
            with pytest.raises(CarrierError) as caught:
                await carrier.configure_number(
                    phone_number_sid="PN123",
                    livekit_sip_host=LIVEKIT_HOST,
                    label="Org A",
                    auth_username="u",
                    auth_password="p",
                )

    assert "could not be reached" in str(caught.value)
    assert recorder.requests == []


# --- Plivo --------------------------------------------------------------------


async def test_plivo_registers_the_uri_before_the_trunk_that_points_at_it() -> None:
    recorder = Recorder()
    async with PlivoCarrier(auth_id="MA123", auth_token="tok", client=_client(recorder)) as carrier:
        result = await carrier.configure_number(
            phone_number="+15555550100",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.paths[0].endswith("/Zentrunk/Uri/")
    assert recorder.paths[-1].startswith("/v1/Account/MA123/Number/")
    assert result.provider == "plivo"


async def test_plivo_defaults_to_tls_and_always_sends_a_transport() -> None:
    """Inbound SIP signalling carries the dialled number, so the encrypted
    transport is the right default when the carrier supports one."""
    recorder = Recorder()
    async with PlivoCarrier(auth_id="MA123", auth_token="tok", client=_client(recorder)) as carrier:
        await carrier.configure_number(
            phone_number="+15555550100",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.body_of(0)["uri"] == f"sip:{LIVEKIT_HOST};transport=tls"


async def test_plivo_returns_a_termination_domain_for_outbound() -> None:
    """The half Twilio has no analog for - LiveKit's outbound trunk dials this."""
    recorder = Recorder(
        httpx.Response(200, json={"uri_id": "URI1"}),
        httpx.Response(200, json={"trunk_id": "TRIN"}),
        httpx.Response(200, json={"credential_id": "CRED1"}),
        httpx.Response(
            200, json={"trunk_id": "TROUT", "termination_sip_domain": "trout.zt.plivo.com"}
        ),
        httpx.Response(200, json={}),
    )
    async with PlivoCarrier(auth_id="MA123", auth_token="tok", client=_client(recorder)) as carrier:
        result = await carrier.configure_number(
            phone_number="+15555550100",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    assert result.termination_domain == "trout.zt.plivo.com"
    assert result.trunk_id == "TRIN"
    assert result.details["outbound_trunk_id"] == "TROUT"


async def test_plivo_falls_back_to_the_conventional_termination_domain() -> None:
    """Plivo's domain is `<trunk_id>.zt.plivo.com` by construction, so a
    response that omits it is recoverable rather than fatal."""
    recorder = Recorder(
        httpx.Response(200, json={"uri_id": "URI1"}),
        httpx.Response(200, json={"trunk_id": "TRIN"}),
        httpx.Response(200, json={"credential_id": "CRED1"}),
        httpx.Response(200, json={"trunk_id": "TROUT"}),
        httpx.Response(200, json={}),
    )
    async with PlivoCarrier(auth_id="MA123", auth_token="tok", client=_client(recorder)) as carrier:
        result = await carrier.configure_number(
            phone_number="+15555550100",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    assert result.termination_domain == "TROUT.zt.plivo.com"


def test_plivo_needs_no_ip_allowlist_and_says_so_with_an_empty_list() -> None:
    """Its outbound trunk authenticates, so LiveKit does not have to fall back
    to addresses. An empty list rather than a missing method means the
    provisioning workflow can call either adapter without knowing which."""
    assert PlivoCarrier.allowed_addresses() == []


async def test_a_plivo_error_surfaces_the_vendors_own_message() -> None:
    recorder = Recorder(httpx.Response(404, json={"error": "not found"}))
    async with PlivoCarrier(auth_id="MA123", auth_token="tok", client=_client(recorder)) as carrier:
        with pytest.raises(CarrierError) as caught:
            await carrier.configure_number(
                phone_number="+15555550100",
                livekit_sip_host=LIVEKIT_HOST,
                label="Org A",
                auth_username="u",
                auth_password="p",
            )

    assert "not found" in str(caught.value)
    assert "Plivo could not register the LiveKit SIP address" in str(caught.value)


def test_plivo_refuses_to_construct_without_credentials() -> None:
    with pytest.raises(CarrierError) as caught:
        PlivoCarrier(auth_id="", auth_token="")
    assert "no Auth ID" in str(caught.value)


# --- what makes a third carrier cheap ----------------------------------------


def test_both_adapters_expose_the_same_entry_points() -> None:
    """The provisioning workflow picks an adapter and calls it. If these ever
    diverge, it starts needing to know which vendor it is holding."""
    for adapter in (TwilioCarrier, PlivoCarrier):
        assert hasattr(adapter, "configure_number")
        assert hasattr(adapter, "allowed_addresses")
        assert hasattr(adapter, "__aenter__")
