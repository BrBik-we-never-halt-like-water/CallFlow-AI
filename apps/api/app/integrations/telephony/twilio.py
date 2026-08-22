"""The only file that calls Twilio's REST API.

Uses `httpx` against Twilio's documented endpoints rather than the `twilio`
SDK: the surface needed here is four POSTs, and the SDK is a large dependency
for that. The boundary rule still holds - nothing outside this module knows a
Twilio SID exists.

**Twilio's inbound trunks cannot authenticate with a username and password**
(ADR-2 open item #5). Twilio only authenticates *outbound* traffic (Termination)
with a credential list; for *inbound* (Origination) it simply sends to the URI
it was given. So the origination URI is effectively a shared secret, and the
protection that matters is on LiveKit's side: the inbound trunk is created with
`allowed_addresses` restricted to Twilio's signalling IPs. That is why
`configure_number()` returns those addresses rather than leaving the caller to
find them - the LiveKit trunk is not safe to create without them.

⚠️ The endpoint paths below follow Twilio's published Trunking v1 API but have
not been exercised against a live account yet - no Twilio credentials exist for
this project (RUNBOOK_HET_PART_1.md §2). The request *shaping* is tested against
a stub; the paths themselves are the thing to verify first when an account
arrives.
"""

from __future__ import annotations

import logging
from typing import Any, Self

import httpx

from app.integrations.telephony import (
    CarrierError,
    CarrierNumber,
    CarrierTrunk,
    sip_uri,
)

log = logging.getLogger("app.integrations.telephony.twilio")

_TRUNKING = "https://trunking.twilio.com/v1"
_API = "https://api.twilio.com/2010-04-01"

# A ceiling on pagination, not an expected count. 100 pages at 100 per page is
# far past any real account, and it means a vendor bug cannot hold the request
# open indefinitely.
_MAX_NUMBER_PAGES = 100

# Twilio signals from a published, stable set of ranges. Restricting the LiveKit
# inbound trunk to these is the only thing standing between a leaked origination
# URI and anyone delivering calls into an organisation's rooms - see the module
# docstring for why Twilio itself cannot help here.
# Source: Twilio's "SIP trunking signalling IP addresses" documentation.
TWILIO_SIGNALLING_CIDRS: tuple[str, ...] = (
    "54.172.60.0/23",
    "54.244.51.0/24",
    "54.171.127.192/26",
    "35.156.191.128/25",
    "54.65.63.192/26",
    "54.169.127.128/26",
    "54.252.254.64/26",
    "177.71.206.192/26",
)


class TwilioCarrier:
    """Configures an organisation's own Twilio account to talk to LiveKit."""

    # Twilio infers the transport, so LiveKit's outbound trunk is left on its
    # own default. See `PlivoCarrier.outbound_transport` for why this exists.
    outbound_transport: str | None = None

    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not (account_sid and auth_token):
            raise CarrierError(
                "Twilio", "authenticate", "no Account SID and Auth Token are stored for this org."
            )
        self._account_sid = account_sid
        self._auth = (account_sid, auth_token)
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> Self:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, *_exc: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _post(self, url: str, data: dict[str, Any], *, action: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("TwilioCarrier is not open. Use `async with TwilioCarrier(...)`.")
        try:
            response = await self._client.post(url, data=data, auth=self._auth)
        except httpx.HTTPError as exc:
            raise CarrierError("Twilio", action, f"could not be reached ({type(exc).__name__}).") from exc

        if response.status_code >= 300:
            raise CarrierError("Twilio", action, _detail(response))
        return response.json()

    async def _find(self, url: str, collection: str, match: dict[str, str], *, action: str) -> dict[str, Any] | None:
        """The existing object this attempt already created, if there is one.

        `configure_number()` makes five things and returns after the fifth, so a
        failure at the third leaves the first two behind with nothing recording
        them - `telephony_provisioning` only learns the carrier's ids once the
        whole carrier step succeeds. A retry then hits *Trunk Domain already
        exists* (Twilio 21248) and can never get past it, because the domain is
        derived from the label and so is the same every time.

        Looking first makes the step resumable without a second ledger: the
        objects are named deterministically from the org-scoped label, so
        finding one means this attempt made it earlier.
        """
        if self._client is None:
            raise RuntimeError("TwilioCarrier is not open. Use `async with TwilioCarrier(...)`.")
        try:
            response = await self._client.get(url, auth=self._auth)
        except httpx.HTTPError as exc:
            raise CarrierError("Twilio", action, f"could not be reached ({type(exc).__name__}).") from exc
        if response.status_code >= 300:
            raise CarrierError("Twilio", action, _detail(response))
        items = response.json().get(collection) or []
        return next(
            (i for i in items if all(i.get(k) == v for k, v in match.items())),
            None,
        )

    async def _get(self, url: str, *, action: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("TwilioCarrier is not open. Use `async with TwilioCarrier(...)`.")
        try:
            response = await self._client.get(url, auth=self._auth)
        except httpx.HTTPError as exc:
            raise CarrierError("Twilio", action, f"could not be reached ({type(exc).__name__}).") from exc
        if response.status_code >= 300:
            raise CarrierError("Twilio", action, _detail(response))
        return response.json()

    async def list_numbers(self) -> list[CarrierNumber]:
        """The voice-capable numbers already on this Twilio account.

        Followed page by page rather than reading the first response only:
        Twilio returns 50 per page by default and puts the rest behind
        `next_page_uri`, so an account with more numbers than that would show a
        truncated picker with no indication anything was missing. The loop is
        bounded because a vendor that kept returning a next page would
        otherwise hang the request.
        """
        numbers: list[CarrierNumber] = []
        url: str | None = (
            f"{_API}/Accounts/{self._account_sid}/IncomingPhoneNumbers.json?PageSize=100"
        )

        for _ in range(_MAX_NUMBER_PAGES):
            if url is None:
                break
            body = await self._get(url, action="list the numbers on this account")
            for item in body.get("incoming_phone_numbers") or []:
                e164 = (item.get("phone_number") or "").strip()
                sid = (item.get("sid") or "").strip()
                if not (e164 and sid):
                    continue
                capabilities = {
                    name
                    for name, enabled in (item.get("capabilities") or {}).items()
                    if enabled
                }
                numbers.append(
                    CarrierNumber(
                        provider="twilio",
                        e164=e164,
                        number_ref=sid,
                        label=(item.get("friendly_name") or "").strip() or None,
                        capabilities=frozenset(capabilities),
                    )
                )
            # Twilio returns this as a path, not an absolute URL.
            next_page = body.get("next_page_uri")
            url = f"https://api.twilio.com{next_page}" if next_page else None

        return numbers

    async def configure_number(
        self,
        *,
        number_ref: str,
        livekit_sip_host: str,
        label: str,
        auth_username: str,
        auth_password: str,
        attach_number: bool = True,
    ) -> CarrierTrunk:
        """Point a Twilio number at LiveKit, both directions.

        `number_ref` is the Twilio **Phone Number SID** (`PN…`), not the number
        itself - Twilio addresses numbers by SID. Named uniformly across the
        adapters so the provisioning workflow does not branch on the provider;
        each adapter documents what its own carrier expects.

        Ordered so the trunk exists before anything is attached to it, and the
        number is associated *last* - until that final step nothing about the
        organisation's live traffic has changed, so an earlier failure leaves a
        stray empty trunk rather than a number that rings into nowhere.

        `attach_number=False` stops before that last step, which makes the whole
        call **non-destructive**: everything created is new, and the number keeps
        whatever was already routing it. That is outbound-only - CallFlow can
        dial *from* the number, because Twilio validates an outbound caller ID
        against the account rather than against the trunk, but calls *to* it
        still reach wherever they reached before. It is the right setting for an
        organisation keeping an existing IVR on a number it also wants to dial
        out from, and for verifying against a number already in production use.
        """
        domain = f"{_slug(label)}.pstn.twilio.com"
        trunk = await self._find(
            f"{_TRUNKING}/Trunks",
            "trunks",
            {"domain_name": domain},
            action="look for an existing SIP trunk",
        ) or await self._post(
            f"{_TRUNKING}/Trunks",
            {"FriendlyName": f"CallFlow {label}", "DomainName": domain},
            action="create a SIP trunk",
        )
        trunk_sid = str(trunk.get("sid", ""))

        # Twilio accepts duplicate origination URLs on one trunk, and a duplicate
        # would double-deliver every inbound call.
        existing_uri = await self._find(
            f"{_TRUNKING}/Trunks/{trunk_sid}/OriginationUrls",
            "origination_urls",
            {"sip_url": sip_uri(livekit_sip_host)},
            action="look for an existing origination URI",
        )
        if not existing_uri:
            await self._post(
                f"{_TRUNKING}/Trunks/{trunk_sid}/OriginationUrls",
                {
                    "FriendlyName": "CallFlow LiveKit",
                    "SipUrl": sip_uri(livekit_sip_host),
                    "Weight": 1,
                    "Priority": 1,
                    "Enabled": "true",
                },
                action="route inbound calls to LiveKit",
            )

        # Outbound is the half Twilio *can* authenticate, so it does.
        credential_list = await self._find(
            f"{_API}/Accounts/{self._account_sid}/SIP/CredentialLists.json",
            "credential_lists",
            {"friendly_name": f"CallFlow {label}"},
            action="look for an existing credential list",
        ) or await self._post(
            f"{_API}/Accounts/{self._account_sid}/SIP/CredentialLists.json",
            {"FriendlyName": f"CallFlow {label}"},
            action="create a credential list",
        )
        credential_list_sid = str(credential_list.get("sid", ""))

        # The password is derived from the attempt's own key, so a resumed
        # attempt presents the identical one and there is nothing to rotate.
        existing_credential = await self._find(
            f"{_API}/Accounts/{self._account_sid}/SIP/CredentialLists/{credential_list_sid}/Credentials.json",
            "credentials",
            {"username": auth_username},
            action="look for existing outbound credentials",
        )
        if not existing_credential:
            await self._post(
                f"{_API}/Accounts/{self._account_sid}/SIP/CredentialLists/{credential_list_sid}/Credentials.json",
                {"Username": auth_username, "Password": auth_password},
                action="store outbound credentials",
            )

        attached = await self._find(
            f"{_TRUNKING}/Trunks/{trunk_sid}/CredentialLists",
            "credential_lists",
            {"sid": credential_list_sid},
            action="look for credentials already on the trunk",
        )
        if not attached:
            await self._post(
                f"{_TRUNKING}/Trunks/{trunk_sid}/CredentialLists",
                {"CredentialListSid": credential_list_sid},
                action="attach outbound credentials to the trunk",
            )

        if attach_number:
            await self._post(
                f"{_TRUNKING}/Trunks/{trunk_sid}/PhoneNumbers",
                {"PhoneNumberSid": number_ref},
                action="attach the phone number to the trunk",
            )

        log.info(
            "configured Twilio trunk %s (inbound %s)",
            trunk_sid,
            "attached" if attach_number else "left where it was",
        )
        return CarrierTrunk(
            provider="twilio",
            trunk_id=trunk_sid,
            # Twilio has no separately-named "termination domain" the way Plivo
            # does, but the trunk's own domain plays exactly that role: it is the
            # address LiveKit's outbound trunk dials. Returning it here rather
            # than leaving the field None keeps the provisioning workflow from
            # branching on the provider name, and gives it one uniform marker
            # for "the carrier half is done".
            termination_domain=domain,
            auth_username=auth_username,
            auth_password=auth_password,
            details={"credential_list_sid": credential_list_sid},
        )

    @staticmethod
    def allowed_addresses() -> list[str]:
        """What the LiveKit inbound trunk must be restricted to.

        Not optional: Twilio cannot authenticate inbound traffic, so without
        this an origination URI is the only thing protecting the organisation's
        rooms from anyone who learns it.
        """
        return list(TWILIO_SIGNALLING_CIDRS)


def _detail(response: httpx.Response) -> str:
    """Twilio's own message, which is the only part that says why."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}."
    message = body.get("message") or body.get("detail") or ""
    code = body.get("code")
    suffix = f" (Twilio code {code})" if code else ""
    return f"{message}{suffix}" if message else f"HTTP {response.status_code}."


def _slug(label: str) -> str:
    """A DNS label Twilio will accept for the trunk domain.

    Twilio requires the domain to be globally unique and to end in
    `pstn.twilio.com`, so a collision here is a real failure mode - the caller
    passes a label already scoped to the organisation.
    """
    cleaned = [c.lower() if c.isalnum() else "-" for c in label]
    return "".join(cleaned).strip("-")[:40] or "callflow"


__all__ = ["TWILIO_SIGNALLING_CIDRS", "TwilioCarrier"]
