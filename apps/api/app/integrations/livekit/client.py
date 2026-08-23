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

import json as _json
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


#: What to go and do about each transport-level code, for the surfaces that show
#: a provisioning failure to an operator rather than retrying it.
#:
#: The vendor's own `message` is deliberately not used. It is the field that
#: carries the SIP URI and the project host, and a provisioning error is shown in
#: the interface - so the code is translated here instead, where the vendor's
#: vocabulary is already allowed to live.
_TWIRP_CODE_ADVICE: dict[str, str] = {
    "unauthenticated": (
        "the media server rejected CallFlow's own credentials. "
        "LIVEKIT_API_KEY and LIVEKIT_API_SECRET are wrong or belong to a "
        "different project - this is a deployment setting, not your account."
    ),
    "permission_denied": (
        "the media server refused the request. The API key is valid but is not "
        "allowed to manage SIP - check the key's grants, and that SIP is enabled "
        "on the project."
    ),
    "not_found": (
        "the media server has no SIP service on this project. It has to be "
        "enabled there before a number can be pointed at it."
    ),
    # Rewritten twice, and both mistakes are worth recording because they are the
    # same mistake.
    #
    # It first blamed E.164 form or LIVEKIT_SIP_HOST. Reproducing the failure gave
    #   Conflicting inbound SIP Trunks: "<new>" and "ST_…", using the same
    #   number(s) ["+1…"] without AllowedNumbers set
    # - a trunk already carrying the number, and LIVEKIT_SIP_HOST is not even an
    # input to `create_inbound_trunk`, so it sent the reader to a variable that
    # cannot be involved.
    #
    # It was then reworded to name that trunk conflict - and was immediately shown
    # verbatim for a *dispatch rule* conflict one step later, because this string
    # is displayed for whichever step raised. So it now describes the shape of the
    # failure (something is already there) without asserting which object.
    "invalid_argument": (
        "the media server refused something CallFlow tried to create, usually "
        "because an equivalent is already there from an earlier attempt that was "
        "not recorded. Retrying adopts what exists rather than duplicating it; if "
        "it persists, the number may be in the wrong format."
    ),
    "already_exists": (
        "the media server already has a trunk for this number, created by an "
        "earlier attempt whose id was never recorded. Retrying now adopts it "
        "instead of trying to build a second one."
    ),
    "unavailable": (
        "the media server could not be reached. Nothing was created - retry when "
        "it is back."
    ),
    "deadline_exceeded": (
        "the media server did not answer in time. Nothing was created - retry."
    ),
    "resource_exhausted": (
        "the media server is rate-limiting this project. Retry in a minute."
    ),
}


def explain_error(exc: Exception) -> str | None:
    """One sentence an operator can act on, or `None` if this is not ours.

    Returns `None` rather than a fallback so a caller can tell "a media-server
    error I can describe" from "an exception I know nothing about" - the second
    should not be dressed up as the first.
    """
    if not isinstance(exc, EngineError):
        return None
    code = str(getattr(exc, "code", "") or "").lower()
    advice = _TWIRP_CODE_ADVICE.get(code)
    if advice is not None:
        return f"Couldn't set up the call route: {advice}"
    # A code with no entry still beats the class name: `unknown` and `internal`
    # are the vendor saying so, and naming them lets a support conversation
    # start somewhere.
    return (
        f"Couldn't set up the call route: the media server returned "
        f"'{code or 'an unnamed error'}'. Nothing about your account is wrong - "
        "retry, and report the code if it persists."
    )


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
        agent_name: str | None = None,
        client_factory: _VendorClientFactory | None = None,
    ) -> None:
        self._url = url if url is not None else config.livekit_url
        self._api_key = api_key if api_key is not None else config.livekit_api_key
        self._api_secret = api_secret if api_secret is not None else config.livekit_api_secret
        # Which registered worker to put in the room. Empty means "don't
        # dispatch" - useful for a verification call that only needs to prove
        # the trunk carries audio, with no conversation to hold.
        self._agent_name = agent_name if agent_name is not None else config.livekit_agent_name
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
        return self._open_client.sip

    @property
    def _dispatch(self) -> Any:
        return self._open_client.agent_dispatch

    @property
    def _open_client(self) -> Any:
        if self._client is None:
            raise RuntimeError(
                "LiveKitGateway is not open. Use `async with LiveKitGateway() as gateway:`."
            )
        return self._client

    async def find_inbound_trunk(self, number: str) -> str | None:
        """The id of an existing inbound trunk already carrying `number`, if any.

        Exists because LiveKit refuses a second trunk for a number it already
        has, and a trunk it created that CallFlow failed to record is
        unreachable: provisioning reads its own column, sees null, tries to
        create, and is refused - identically, on every retry, forever. That is
        not hypothetical, it is how a dev number got stuck (`ISSUES.md` #188).

        Matching on the E.164 is safe as a tenancy boundary even though one
        LiveKit project is shared by every organisation: a phone number is
        globally unique and reaches this code only after the org's *own* carrier
        credentials confirmed the org holds it. A trunk carrying that number is
        this number's trunk.
        """
        existing = await self._sip.list_inbound_trunk(
            _vendor_api.ListSIPInboundTrunkRequest()
        )
        for trunk in existing.items:
            if number in list(trunk.numbers):
                return str(trunk.sip_trunk_id)
        return None

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
        info = await self._sip.create_inbound_trunk(
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
        info = await self._sip.create_outbound_trunk(
            _vendor_api.CreateSIPOutboundTrunkRequest(trunk=trunk)
        )
        return str(info.sip_trunk_id)

    async def find_dispatch_rule(self, trunk_id: str) -> str | None:
        """The id of an existing dispatch rule already routing `trunk_id`, if any.

        The companion to `find_inbound_trunk`, and needed for the same reason one
        step later: adopting the trunk moves the failure to this step, where a
        rule an earlier attempt created but never recorded blocks it identically.
        Keyed on the trunk rather than the number - a rule names trunks, and the
        trunk is the thing this attempt has just established it owns.
        """
        existing = await self._sip.list_dispatch_rule(
            _vendor_api.ListSIPDispatchRuleRequest()
        )
        for rule in existing.items:
            if trunk_id in list(rule.trunk_ids):
                return str(rule.sip_dispatch_rule_id)
        return None

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
        info = await self._sip.create_dispatch_rule(
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
        metadata: dict[str, Any] | None = None,
        wait_until_answered: bool = True,
        max_call_duration_seconds: int | None = None,
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

        `metadata` is how the worker learns what this call is for - the rendered
        prompt, the agent, the contact's own context. It is JSON-encoded and
        attached to the **agent dispatch**, which is where the worker reads it
        from (`ctx.job.metadata`). **It must never carry the dialled number**:
        it reaches LiveKit's own logs and dashboards, outside CallFlow's
        redaction filter.

        The dispatch is created *before* the call, deliberately. An answered
        call with no agent in the room is a person saying "hello?" into silence;
        dispatching first means the worker is already waiting. LiveKit holds a
        dispatch for a room that does not exist yet, so the ordering is safe.

        It is also undone if the dial then fails. A surviving dispatch puts a
        worker into a room nobody will ever join; it waits out its answer
        timeout and POSTs NO_ANSWER, overwriting the accurate busy-or-
        unreachable outcome `classify_error()` produced from the carrier's own
        SIP status.

        `max_call_duration_seconds` is a hard ceiling the carrier enforces even
        if the worker hangs - without it, a wedged agent bills for a call that
        never ends.
        """
        dispatch_id = ""
        if self._agent_name:
            dispatch = await self._dispatch.create_dispatch(
                _vendor_api.CreateAgentDispatchRequest(
                    agent_name=self._agent_name,
                    room=room_name,
                    metadata=_json.dumps(metadata) if metadata else "",
                )
            )
            dispatch_id = str(getattr(dispatch, "id", "") or "")

        request = _vendor_api.CreateSIPParticipantRequest(
            sip_trunk_id=trunk_id,
            sip_call_to=phone,
            room_name=room_name,
            participant_identity=participant_identity,
            participant_name=participant_name or participant_identity,
            wait_until_answered=wait_until_answered,
        )
        if max_call_duration_seconds is not None:
            request.max_call_duration.FromSeconds(max_call_duration_seconds)

        try:
            info = await self._sip.create_sip_participant(request)
        except Exception:
            await self._cancel_dispatch(dispatch_id, room_name)
            raise
        return {
            "participant_id": str(getattr(info, "participant_id", "") or ""),
            "participant_identity": str(getattr(info, "participant_identity", "") or ""),
            "room_name": room_name,
            "sip_call_id": str(getattr(info, "sip_call_id", "") or ""),
        }

    async def _cancel_dispatch(self, dispatch_id: str, room_name: str) -> None:
        """Best effort, and deliberately so.

        The caller is already unwinding a failed dial and has a classified,
        accurate failure to report. Letting a cleanup error replace it would
        turn "486 Busy Here" into an internal error, which is strictly worse
        information. A dispatch that outlives this is logged and left.
        """
        if not dispatch_id:
            return
        try:
            await self._dispatch.delete_dispatch(dispatch_id, room_name)
        except Exception:  # noqa: BLE001 - see the docstring: nothing here may mask the dial's own failure
            log.warning(
                "dial failed and its agent dispatch %s could not be cancelled - "
                "a worker may join room %s and find nobody",
                dispatch_id,
                room_name,
            )


__all__ = [
    "EngineError",
    "LiveKitGateway",
    "SipTransport",
    "classify_error",
    "explain_error",
]
