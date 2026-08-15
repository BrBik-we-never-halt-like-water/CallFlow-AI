"""The only file that imports the LiveKit server SDK.

Every vendor name is aliased on the way in, so nothing above this module speaks
LiveKit's vocabulary - the same treatment the deleted `engine.py` gave CALL-E,
and a repo-wide non-negotiable (CLAUDE.md §2/§3).

Two things worth knowing before changing anything here.

**The SDK is async.** CALL-E's client was blocking, so every call site wrapped
it in `asyncio.to_thread`. LiveKit's is aiohttp-based and must not be - awaiting
it directly is both correct and cheaper. Do not reintroduce `to_thread`.

**Errors carry two layers.** A `TwirpError` has a transport-level `code`
(`unavailable`, `invalid_argument`, …) and, when the failure happened on the
phone call itself, a `sip_status_code` in its metadata. The SIP status is the
more specific of the two and wins - "486 Busy Here" tells an operator something
that "internal" never could. `classify_error()` is the single place that
decision is made, and it maps onto `DialFailure`, the taxonomy that already
exists, rather than inventing a parallel one.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, Self

from livekit import api as _vendor_api
from livekit.api import TwirpError as EngineError

from app.core.config import config
from app.domain.entities import DialFailure

log = logging.getLogger("app.integrations.livekit")

# SIP response codes we can say something specific about. Anything absent falls
# through to the Twirp code, then to INTERNAL - unmapped never means "fine".
_SIP_STATUS_FAILURES: dict[int, DialFailure] = {
    401: DialFailure.UNAUTHORIZED,
    402: DialFailure.INSUFFICIENT_BALANCE,
    403: DialFailure.UNAUTHORIZED,
    404: DialFailure.INVALID_NUMBER,
    407: DialFailure.UNAUTHORIZED,
    408: DialFailure.NO_ANSWER,
    480: DialFailure.NO_ANSWER,
    484: DialFailure.INVALID_NUMBER,
    485: DialFailure.INVALID_NUMBER,
    486: DialFailure.BUSY,
    500: DialFailure.INTERNAL,
    502: DialFailure.PROVIDER_UNAVAILABLE,
    503: DialFailure.PROVIDER_UNAVAILABLE,
    504: DialFailure.PROVIDER_UNAVAILABLE,
    600: DialFailure.BUSY,
    603: DialFailure.POLICY_VIOLATION,
    604: DialFailure.INVALID_NUMBER,
    607: DialFailure.POLICY_VIOLATION,
}

_TWIRP_CODE_FAILURES: dict[str, DialFailure] = {
    "invalid_argument": DialFailure.INVALID_NUMBER,
    "malformed": DialFailure.INVALID_NUMBER,
    "not_found": DialFailure.INVALID_NUMBER,
    "unauthenticated": DialFailure.UNAUTHORIZED,
    "permission_denied": DialFailure.UNAUTHORIZED,
    "resource_exhausted": DialFailure.RATE_LIMITED,
    "unavailable": DialFailure.PROVIDER_UNAVAILABLE,
    "bad_route": DialFailure.PROVIDER_UNAVAILABLE,
    "deadline_exceeded": DialFailure.TIMED_OUT,
    "canceled": DialFailure.TIMED_OUT,
}


def _sip_status_of(exc: EngineError) -> int | None:
    """The upstream SIP response code, when the failure reached the phone network.

    LiveKit passes it as a string in Twirp metadata; a value that isn't an
    integer is treated as absent rather than crashing the classifier, because a
    classifier that raises turns a bad call into a 500.
    """
    raw = (getattr(exc, "metadata", None) or {}).get("sip_status_code")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def classify_error(exc: Exception) -> DialFailure:
    """Map a vendor failure onto CallFlow's own taxonomy.

    Fails closed: anything unrecognised becomes INTERNAL, which is *not* in
    `_RETRYABLE_FAILURES`, so an error this code has never seen stops the
    attempt rather than being retried on the assumption it is transient.
    """
    if not isinstance(exc, EngineError):
        return DialFailure.INTERNAL

    sip_status = _sip_status_of(exc)
    if sip_status is not None and sip_status in _SIP_STATUS_FAILURES:
        return _SIP_STATUS_FAILURES[sip_status]

    code = str(getattr(exc, "code", "") or "").lower()
    return _TWIRP_CODE_FAILURES.get(code, DialFailure.INTERNAL)


class SipTransport(str):
    """The transport a carrier's origination URI must name.

    Plivo rejects an origination URI without an explicit transport parameter;
    Twilio infers one. Kept as plain strings rather than the SDK's enum so
    callers outside this package never import a vendor type.
    """

    AUTO = "auto"
    TCP = "tcp"
    TLS = "tls"
    UDP = "udp"


_TRANSPORTS = {
    SipTransport.AUTO: _vendor_api.SIP_TRANSPORT_AUTO,
    SipTransport.TCP: _vendor_api.SIP_TRANSPORT_TCP,
    SipTransport.TLS: _vendor_api.SIP_TRANSPORT_TLS,
    SipTransport.UDP: _vendor_api.SIP_TRANSPORT_UDP,
}


class _VendorClientFactory(Protocol):
    """What `LiveKitGateway` needs from the SDK, so a test can supply its own.

    Narrower than the real client on purpose: a stub implements this, not the
    whole of `LiveKitAPI`. CLAUDE.md's Substitutability rule - "write the second
    adapter, even if it is only a stub for tests".
    """

    def __call__(self, *, url: str, api_key: str, api_secret: str) -> Any: ...


def _default_factory(*, url: str, api_key: str, api_secret: str) -> Any:
    return _vendor_api.LiveKitAPI(url=url, api_key=api_key, api_secret=api_secret)


class LiveKitGateway:
    """CallFlow's view of LiveKit: trunks, dispatch rules, and placing a call.

    One instance per unit of work, not a long-lived singleton - the underlying
    client owns an aiohttp session that must be closed, which is what
    `async with` here is for.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        api_key: str | None = None,
        api_secret: str | None = None,
        client_factory: _VendorClientFactory | None = None,
    ) -> None:
        self._url = url if url is not None else config.livekit_url
        self._api_key = api_key if api_key is not None else config.livekit_api_key
        self._api_secret = api_secret if api_secret is not None else config.livekit_api_secret
        self._client_factory = client_factory or _default_factory
        self._client: Any | None = None

        if not (self._url and self._api_key and self._api_secret):
            raise RuntimeError(
                "LiveKit is not configured. Set LIVEKIT_URL, LIVEKIT_API_KEY and "
                "LIVEKIT_API_SECRET before placing calls or connecting a number."
            )

    async def __aenter__(self) -> Self:
        self._client = self._client_factory(
            url=self._url, api_key=self._api_key, api_secret=self._api_secret
        )
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _sip(self) -> Any:
        if self._client is None:
            raise RuntimeError(
                "LiveKitGateway is not open. Use `async with LiveKitGateway() as gateway:`."
            )
        return self._client.sip

    async def create_inbound_trunk(
        self, *, name: str, numbers: list[str], allowed_addresses: list[str] | None = None
    ) -> str:
        """Register the org's number so calls *to* it reach LiveKit. Returns the trunk id.

        `allowed_addresses` restricts which hosts may deliver to this trunk. It
        is the only authentication an inbound Twilio trunk can have - Twilio does
        not support username/password on origination - so leaving it empty means
        anyone who learns the URI can deliver calls into the org's rooms.
        """
        trunk = _vendor_api.SIPInboundTrunkInfo(
            name=name,
            numbers=numbers,
            allowed_addresses=allowed_addresses or [],
        )
        info = await self._sip.create_sip_inbound_trunk(
            _vendor_api.CreateSIPInboundTrunkRequest(trunk=trunk)
        )
        return str(info.sip_trunk_id)

    async def create_outbound_trunk(
        self,
        *,
        name: str,
        address: str,
        numbers: list[str],
        auth_username: str | None = None,
        auth_password: str | None = None,
        transport: str = SipTransport.AUTO,
    ) -> str:
        """Register the carrier CallFlow dials *out* through. Returns the trunk id.

        `transport` is not cosmetic: Plivo rejects an origination URI that does
        not name one explicitly, while Twilio infers it.
        """
        trunk = _vendor_api.SIPOutboundTrunkInfo(
            name=name,
            address=address,
            numbers=numbers,
            auth_username=auth_username or "",
            auth_password=auth_password or "",
            transport=_TRANSPORTS[transport],
        )
        info = await self._sip.create_sip_outbound_trunk(
            _vendor_api.CreateSIPOutboundTrunkRequest(trunk=trunk)
        )
        return str(info.sip_trunk_id)

    async def create_dispatch_rule(
        self, *, name: str, room_prefix: str, trunk_ids: list[str]
    ) -> str:
        """Route inbound calls on these trunks into their own room each.

        Individual, not direct: a shared room would put two unrelated callers
        into the same conversation.
        """
        rule = _vendor_api.SIPDispatchRule(
            dispatch_rule_individual=_vendor_api.SIPDispatchRuleIndividual(
                room_prefix=room_prefix
            )
        )
        info = await self._sip.create_sip_dispatch_rule(
            _vendor_api.CreateSIPDispatchRuleRequest(
                dispatch_rule=_vendor_api.SIPDispatchRuleInfo(
                    name=name, rule=rule, trunk_ids=trunk_ids
                )
            )
        )
        return str(info.sip_dispatch_rule_id)

    async def start_call(
        self,
        *,
        trunk_id: str,
        phone: str,
        room_name: str,
        participant_identity: str,
        participant_name: str | None = None,
        wait_until_answered: bool = True,
    ) -> dict[str, Any]:
        """Place one outbound call into `room_name`.

        `wait_until_answered=True` is what makes failures classifiable at all:
        without it LiveKit returns as soon as the INVITE is sent and a busy or
        unreachable number looks identical to a connected one. With it, the
        carrier's SIP status arrives as a `TwirpError` this module can map.

        The caller passes `room_name` rather than having one generated here, so
        the same name can be handed to the agent worker's dispatch - the worker
        and the caller have to agree on it, and inventing it in two places is
        how they stop agreeing.
        """
        request = _vendor_api.CreateSIPParticipantRequest(
            sip_trunk_id=trunk_id,
            sip_call_to=phone,
            room_name=room_name,
            participant_identity=participant_identity,
            participant_name=participant_name or participant_identity,
            wait_until_answered=wait_until_answered,
        )
        info = await self._sip.create_sip_participant(request)
        return {
            "participant_id": str(getattr(info, "participant_id", "") or ""),
            "participant_identity": str(getattr(info, "participant_identity", "") or ""),
            "room_name": room_name,
            "sip_call_id": str(getattr(info, "sip_call_id", "") or ""),
        }


__all__ = [
    "EngineError",
    "LiveKitGateway",
    "SipTransport",
    "classify_error",
]
