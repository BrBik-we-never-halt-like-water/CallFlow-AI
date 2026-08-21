"""Listing the numbers an organisation already owns, per carrier.

The pagination is the point of these tests. Every vendor pages differently -
Twilio follows `next_page_uri`, Plivo counts offsets, Telnyx counts pages,
Vonage counts an index against a total - and a loop that reads only the first
response returns a truncated picker with nothing to say it was truncated. An
operator would see four of their nine numbers and have no way to tell.

Stubbed HTTP throughout: none of the four adapters has been exercised against a
live account (each module's own docstring says so), so what is pinned here is
the request shaping and the paging arithmetic, not the vendor's behaviour.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.integrations.telephony import CarrierError
from app.integrations.telephony.plivo import PlivoCarrier
from app.integrations.telephony.telnyx import TelnyxCarrier
from app.integrations.telephony.twilio import TwilioCarrier
from app.integrations.telephony.vonage import VonageCarrier


class StubTransport(httpx.AsyncBaseTransport):
    """Answers each GET from a queue, recording what was asked for."""

    def __init__(self, responses: list[dict[str, Any]], *, status: int = 200) -> None:
        self._responses = list(responses)
        self._status = status
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = self._responses.pop(0) if self._responses else {}
        return httpx.Response(self._status, json=body, request=request)


def _client(transport: StubTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=transport)


# --- Twilio -----------------------------------------------------------------


async def test_twilio_follows_every_page_rather_than_reading_the_first() -> None:
    transport = StubTransport(
        [
            {
                "incoming_phone_numbers": [
                    {
                        "phone_number": "+15555550100",
                        "sid": "PN100",
                        "friendly_name": "Support line",
                        "capabilities": {"voice": True, "sms": True},
                    }
                ],
                "next_page_uri": "/2010-04-01/Accounts/AC1/IncomingPhoneNumbers.json?Page=1",
            },
            {
                "incoming_phone_numbers": [
                    {
                        "phone_number": "+15555550101",
                        "sid": "PN101",
                        "capabilities": {"voice": True},
                    }
                ],
                "next_page_uri": None,
            },
        ]
    )
    async with TwilioCarrier(
        account_sid="AC1", auth_token="tok", client=_client(transport)
    ) as carrier:
        numbers = await carrier.list_numbers()

    assert [n.e164 for n in numbers] == ["+15555550100", "+15555550101"]
    # The second page is only reached by following the cursor.
    assert len(transport.requests) == 2
    assert "Page=1" in str(transport.requests[1].url)


async def test_twilio_carries_the_sid_because_configure_number_addresses_by_sid() -> None:
    transport = StubTransport(
        [
            {
                "incoming_phone_numbers": [
                    {"phone_number": "+15555550100", "sid": "PN100", "capabilities": {"voice": True}}
                ]
            }
        ]
    )
    async with TwilioCarrier(
        account_sid="AC1", auth_token="tok", client=_client(transport)
    ) as carrier:
        [number] = await carrier.list_numbers()

    assert number.number_ref == "PN100"
    assert number.provider == "twilio"
    assert number.label == "Support line" or number.label is None


async def test_twilio_reports_a_number_without_voice_as_uncallable() -> None:
    transport = StubTransport(
        [
            {
                "incoming_phone_numbers": [
                    {
                        "phone_number": "+15555550100",
                        "sid": "PN100",
                        "capabilities": {"voice": False, "sms": True},
                    }
                ]
            }
        ]
    )
    async with TwilioCarrier(
        account_sid="AC1", auth_token="tok", client=_client(transport)
    ) as carrier:
        [number] = await carrier.list_numbers()

    # Offering it in a picker would be a run that fails at the carrier for a
    # reason nobody could see beforehand.
    assert number.can_call is False


async def test_twilio_surfaces_its_own_message_when_listing_is_refused() -> None:
    transport = StubTransport(
        [{"message": "Authenticate", "code": 20003}], status=401
    )
    async with TwilioCarrier(
        account_sid="AC1", auth_token="tok", client=_client(transport)
    ) as carrier:
        with pytest.raises(CarrierError) as excinfo:
            await carrier.list_numbers()

    # The vendor's wording is the only part that says why.
    assert "Authenticate" in str(excinfo.value)


# --- Plivo ------------------------------------------------------------------


async def test_plivo_advances_by_offset_until_the_total_is_reached() -> None:
    transport = StubTransport(
        [
            {
                "objects": [{"number": "15555550100", "voice_enabled": True, "alias": "Line 1"}],
                "meta": {"total_count": 2},
            },
            {
                "objects": [{"number": "15555550101", "voice_enabled": True}],
                "meta": {"total_count": 2},
            },
        ]
    )
    async with PlivoCarrier(
        auth_id="MA1", auth_token="tok", client=_client(transport)
    ) as carrier:
        numbers = await carrier.list_numbers()

    assert [n.e164 for n in numbers] == ["+15555550100", "+15555550101"]
    assert len(transport.requests) == 2
    assert "offset=1" in str(transport.requests[1].url)


async def test_plivo_normalises_a_number_that_arrives_without_a_plus() -> None:
    transport = StubTransport(
        [{"objects": [{"number": "15555550100", "voice_enabled": True}], "meta": {"total_count": 1}}]
    )
    async with PlivoCarrier(
        auth_id="MA1", auth_token="tok", client=_client(transport)
    ) as carrier:
        [number] = await carrier.list_numbers()

    # `is_e164()` requires the plus, so an unnormalised number would be rejected
    # on its way into a run - the org's own number failing validation.
    assert number.e164 == "+15555550100"


# --- Telnyx -----------------------------------------------------------------


async def test_telnyx_counts_pages_until_total_pages() -> None:
    transport = StubTransport(
        [
            {
                "data": [{"phone_number": "+15555550100", "id": "NB1"}],
                "meta": {"total_pages": 2},
            },
            {
                "data": [{"phone_number": "+15555550101", "id": "NB2"}],
                "meta": {"total_pages": 2},
            },
        ]
    )
    async with TelnyxCarrier(api_key="key", client=_client(transport)) as carrier:
        numbers = await carrier.list_numbers()

    assert [n.number_ref for n in numbers] == ["NB1", "NB2"]
    assert len(transport.requests) == 2


async def test_telnyx_returns_the_id_so_configure_number_skips_its_lookup() -> None:
    transport = StubTransport(
        [{"data": [{"phone_number": "+15555550100", "id": "NB1"}], "meta": {"total_pages": 1}}]
    )
    async with TelnyxCarrier(api_key="key", client=_client(transport)) as carrier:
        [number] = await carrier.list_numbers()

    # `_resolve_number_id` passes an id straight through; handing back the E.164
    # would make every provisioning attempt pay for a lookup it can avoid.
    assert number.number_ref == "NB1"
    assert not number.number_ref.startswith("+")


# --- Vonage -----------------------------------------------------------------


async def test_vonage_prepends_the_plus_it_omits() -> None:
    transport = StubTransport(
        [{"numbers": [{"msisdn": "15555550100", "features": ["VOICE"]}], "count": 1}]
    )
    async with VonageCarrier(
        api_key="key", api_secret="secret", client=_client(transport)
    ) as carrier:
        [number] = await carrier.list_numbers()

    assert number.e164 == "+15555550100"
    # Vonage addresses a number by the number, so the ref carries the plus too.
    assert number.number_ref == "+15555550100"
    assert number.can_call is True


async def test_vonage_stops_once_it_has_the_reported_count() -> None:
    transport = StubTransport(
        [
            {"numbers": [{"msisdn": "15555550100", "features": ["VOICE"]}], "count": 2},
            {"numbers": [{"msisdn": "15555550101", "features": ["VOICE"]}], "count": 2},
            # A third response exists; reaching it would mean the loop ignored
            # `count` and would keep paging a vendor that has nothing left.
            {"numbers": [{"msisdn": "15555550102", "features": ["VOICE"]}], "count": 2},
        ]
    )
    async with VonageCarrier(
        api_key="key", api_secret="secret", client=_client(transport)
    ) as carrier:
        numbers = await carrier.list_numbers()

    assert len(numbers) == 2
    assert len(transport.requests) == 2


# --- Shared invariants ------------------------------------------------------


@pytest.mark.parametrize(
    ("factory", "body"),
    [
        (
            lambda c: TwilioCarrier(account_sid="AC1", auth_token="t", client=c),
            {"incoming_phone_numbers": []},
        ),
        (
            lambda c: PlivoCarrier(auth_id="MA1", auth_token="t", client=c),
            {"objects": [], "meta": {"total_count": 0}},
        ),
        (lambda c: TelnyxCarrier(api_key="k", client=c), {"data": [], "meta": {"total_pages": 1}}),
        (
            lambda c: VonageCarrier(api_key="k", api_secret="s", client=c),
            {"numbers": [], "count": 0},
        ),
    ],
)
async def test_an_account_with_no_numbers_is_an_empty_list_not_an_error(
    factory: Any, body: dict[str, Any]
) -> None:
    """An org that has connected credentials but bought nothing yet is a normal
    state the picker has to render, not a failure."""
    transport = StubTransport([body])
    async with factory(_client(transport)) as carrier:
        assert await carrier.list_numbers() == []


@pytest.mark.parametrize(
    "factory",
    [
        lambda: TwilioCarrier(account_sid="AC1", auth_token="t"),
        lambda: PlivoCarrier(auth_id="MA1", auth_token="t"),
        lambda: TelnyxCarrier(api_key="k"),
        lambda: VonageCarrier(api_key="k", api_secret="s"),
    ],
)
async def test_listing_before_opening_the_adapter_is_an_error_not_a_crash(
    factory: Any,
) -> None:
    """Same guard every other method on these adapters carries: used outside its
    `async with`, it says so rather than failing on a `None` client."""
    carrier = factory()
    with pytest.raises(RuntimeError, match="not open"):
        await carrier.list_numbers()
