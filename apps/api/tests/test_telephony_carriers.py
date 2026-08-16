"""The four carrier adapters, against stubbed HTTP.

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
from app.integrations.telephony.telnyx import TelnyxCarrier
from app.integrations.telephony.twilio import TWILIO_SIGNALLING_CIDRS, TwilioCarrier
from app.integrations.telephony.vonage import VonageCarrier

LIVEKIT_HOST = "5t4ms1u1nvx.sip.livekit.cloud"


def test_only_plivo_demands_an_explicit_outbound_transport() -> None:
    """The value `number_provisioning` hands LiveKit's outbound trunk.

    Plivo rejects a termination URI that does not name a transport, so leaving
    LiveKit on its `auto` default fails every outbound call to it - silently,
    since provisioning itself still reports success. Twilio infers one, and
    says so by declaring nothing.
    """
    assert PlivoCarrier.outbound_transport == "tls"
    assert TwilioCarrier.outbound_transport is None


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
            number_ref="PN123",
            livekit_sip_host=LIVEKIT_HOST,
            label="Org A",
            auth_username="u",
            auth_password="p",
        )

    assert "/Trunks" in recorder.paths[0]
    assert recorder.paths[-1].endswith("/PhoneNumbers")
    assert result.provider == "twilio"
    # Twilio's trunk domain is what LiveKit's outbound trunk dials, so it fills
    # the same slot Plivo's termination domain does - the provisioning workflow
    # gets one uniform marker instead of branching on the provider name.
    assert result.termination_domain == "org-a.pstn.twilio.com"


async def test_twilio_sends_the_livekit_uri_with_a_transport() -> None:
    recorder = Recorder()
    async with TwilioCarrier(
        account_sid="AC123", auth_token="tok", client=_client(recorder)
    ) as carrier:
        await carrier.configure_number(
            number_ref="PN123",
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
            number_ref="PN123",
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
                number_ref="bad",
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
                    number_ref="PN123",
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
            number_ref="+15555550100",
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
            number_ref="+15555550100",
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
            number_ref="+15555550100",
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
            number_ref="+15555550100",
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
                number_ref="+15555550100",
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


# --- Telnyx -------------------------------------------------------------------


async def test_telnyx_creates_one_connection_and_attaches_the_number_last() -> None:
    """Telnyx has a single credential connection where Twilio has a trunk plus
    origination URLs - but the ordering rule is the same, and for the same
    reason: nothing about live traffic changes until the number is attached."""
    recorder = Recorder(
        httpx.Response(200, json={"data": {"id": "CN_1", "inbound": {"sip_subdomain": "org-a"}}}),
        httpx.Response(200, json={"data": {"id": "PN_1"}}),
    )
    async with TelnyxCarrier(api_key="KEY123", client=_client(recorder)) as carrier:
        trunk = await carrier.configure_number(
            number_ref="1234567890",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="cf-user",
            auth_password="cf-pass",
        )

    assert recorder.paths == ["/v2/credential_connections", "/v2/phone_numbers/1234567890"]
    assert trunk.trunk_id == "CN_1"
    assert trunk.termination_domain == "org-a.sip.telnyx.com"


async def test_telnyx_authenticates_with_a_bearer_token_not_basic_auth() -> None:
    """The one adapter here that does - getting it wrong 401s every call."""
    recorder = Recorder(httpx.Response(200, json={"data": {"id": "CN_1", "inbound": {}}}))
    async with TelnyxCarrier(api_key="KEY123", client=_client(recorder)) as carrier:
        await carrier.configure_number(
            number_ref="PN_existing",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.requests[0].headers["authorization"] == "Bearer KEY123"


async def test_telnyx_sends_the_livekit_uri_with_its_transport() -> None:
    recorder = Recorder(httpx.Response(200, json={"data": {"id": "CN_1", "inbound": {}}}))
    async with TelnyxCarrier(api_key="KEY123", client=_client(recorder)) as carrier:
        await carrier.configure_number(
            number_ref="PN_1",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.body_of(0)["webhook_event_url"] == sip_uri(LIVEKIT_HOST, "tls")


async def test_telnyx_reuses_a_connection_the_operator_already_has() -> None:
    """An org already running Telnyx should not get a second connection beside
    the one it configured itself."""
    recorder = Recorder(httpx.Response(200, json={"data": {"id": "PN_1"}}))
    async with TelnyxCarrier(
        api_key="KEY123", connection_id="CN_existing", client=_client(recorder)
    ) as carrier:
        trunk = await carrier.configure_number(
            number_ref="PN_1",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.paths == ["/v2/phone_numbers/PN_1"]
    assert trunk.trunk_id == "CN_existing"


async def test_telnyx_looks_up_a_number_given_in_e164() -> None:
    """Telnyx updates numbers by id; operators hold E.164."""
    recorder = Recorder(
        httpx.Response(200, json={"data": {"id": "CN_1", "inbound": {}}}),
        httpx.Response(200, json={"data": [{"id": "PN_looked_up"}]}),
        httpx.Response(200, json={"data": {"id": "PN_looked_up"}}),
    )
    async with TelnyxCarrier(api_key="KEY123", client=_client(recorder)) as carrier:
        await carrier.configure_number(
            number_ref="+15555550100",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.paths[-1] == "/v2/phone_numbers/PN_looked_up"


async def test_telnyx_says_so_when_the_number_is_not_on_the_account() -> None:
    recorder = Recorder(
        httpx.Response(200, json={"data": {"id": "CN_1", "inbound": {}}}),
        httpx.Response(200, json={"data": []}),
    )
    async with TelnyxCarrier(api_key="KEY123", client=_client(recorder)) as carrier:
        with pytest.raises(CarrierError) as caught:
            await carrier.configure_number(
                number_ref="+15555550100",
                livekit_sip_host=LIVEKIT_HOST,
                label="org-a",
                auth_username="u",
                auth_password="p",
            )

    assert "not on this Telnyx account" in str(caught.value)


async def test_the_telnyx_error_message_survives_into_the_failure() -> None:
    """It is the only part that says what to fix, and it reaches the operator
    verbatim through `telephony_provisioning.last_error`."""
    recorder = Recorder(
        httpx.Response(422, json={"errors": [{"detail": "Subdomain already in use."}]})
    )
    async with TelnyxCarrier(api_key="KEY123", client=_client(recorder)) as carrier:
        with pytest.raises(CarrierError) as caught:
            await carrier.configure_number(
                number_ref="PN_1",
                livekit_sip_host=LIVEKIT_HOST,
                label="org-a",
                auth_username="u",
                auth_password="p",
            )

    assert "Subdomain already in use." in str(caught.value)


# --- Vonage -------------------------------------------------------------------


async def test_vonage_creates_the_domain_before_linking_the_number() -> None:
    recorder = Recorder(
        httpx.Response(200, json={"id": "DM_1"}),
        httpx.Response(200, json={"error-code": "200"}),
    )
    async with VonageCarrier(api_key="vk", api_secret="vs", client=_client(recorder)) as carrier:
        trunk = await carrier.configure_number(
            number_ref="+15555550100",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="cf-user",
            auth_password="cf-pass",
        )

    assert recorder.paths == ["/v1/networks/sip/domains", "/number/update"]
    assert trunk.trunk_id == "DM_1"
    assert trunk.termination_domain == "org-a.sip.vonage.com"


async def test_vonage_derives_the_country_from_the_dialling_code() -> None:
    """Vonage's number-update call demands it, and an operator connecting their
    own number should not have to restate where it is."""
    recorder = Recorder(httpx.Response(200, json={"id": "DM_1"}))
    async with VonageCarrier(api_key="vk", api_secret="vs", client=_client(recorder)) as carrier:
        await carrier.configure_number(
            number_ref="+919876543210",
            livekit_sip_host=LIVEKIT_HOST,
            label="org-a",
            auth_username="u",
            auth_password="p",
        )

    assert recorder.body_of(1)["country"] == "IN"
    assert recorder.body_of(1)["msisdn"] == "919876543210"


async def test_the_vonage_error_message_survives_into_the_failure() -> None:
    recorder = Recorder(httpx.Response(401, json={"error_text": "Authentication failed."}))
    async with VonageCarrier(api_key="vk", api_secret="vs", client=_client(recorder)) as carrier:
        with pytest.raises(CarrierError) as caught:
            await carrier.configure_number(
                number_ref="+15555550100",
                livekit_sip_host=LIVEKIT_HOST,
                label="org-a",
                auth_username="u",
                auth_password="p",
            )

    assert "Authentication failed." in str(caught.value)


# --- every adapter, held to the same shape ------------------------------------

ADAPTERS = [TwilioCarrier, PlivoCarrier, TelnyxCarrier, VonageCarrier]


@pytest.mark.parametrize("carrier_cls", ADAPTERS)
def test_every_adapter_exposes_the_same_entry_points(carrier_cls: Any) -> None:
    """The provisioning workflow calls these on whichever adapter it holds. A
    fifth carrier is meant to be one more file and nothing else."""
    assert callable(carrier_cls.configure_number)
    assert carrier_cls.allowed_addresses() is not None
    assert hasattr(carrier_cls, "outbound_transport")


def _required_args(carrier_cls: Any) -> list[str]:
    import inspect

    return [
        name
        for name, p in inspect.signature(carrier_cls).parameters.items()
        if p.default is inspect.Parameter.empty and name != "client"
    ]


@pytest.mark.parametrize("carrier_cls", ADAPTERS)
def test_every_adapter_refuses_to_construct_without_credentials(carrier_cls: Any) -> None:
    """Fails at construction rather than on the first request, so a
    misconfigured org is told before anything has been half-created."""
    with pytest.raises(CarrierError):
        carrier_cls(**dict.fromkeys(_required_args(carrier_cls), ""))


def test_every_carrier_in_the_catalogue_has_an_adapter() -> None:
    """The settings page offers these; `CARRIERS` is what can actually be
    configured. A carrier in one and not the other is a card that lies."""
    from app.domain.providers import ProviderRole, for_role
    from app.services.number_provisioning import CARRIERS

    offered = {p.id for p in for_role(ProviderRole.TELEPHONY)}

    assert offered == set(CARRIERS)


def test_every_carriers_declared_fields_are_its_constructor_arguments() -> None:
    """`routes/telephony.py` passes the stored fields straight through, so the
    field names in `domain/providers.py` *are* the adapter's keyword arguments.
    A rename on either side is a TypeError on a live provisioning run."""
    import inspect

    from app.domain.providers import ProviderRole, for_role
    from app.services.number_provisioning import CARRIERS

    for spec_ in for_role(ProviderRole.TELEPHONY):
        accepted = set(inspect.signature(CARRIERS[spec_.id]).parameters)
        declared = {f.key for f in spec_.fields}
        assert declared <= accepted, f"{spec_.id}: {sorted(declared - accepted)} not accepted"
