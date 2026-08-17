"""The only file that calls Telnyx's REST API.

Mirrors `twilio.py` and `plivo.py` deliberately - same constructor shape, same
`configure_number()` entry point, same `CarrierTrunk` back. That symmetry is the
point: the provisioning workflow picks an adapter and calls it, and a fourth
carrier means writing one more of these and nothing else.

What is Telnyx's own, not ours:

- **One object does both directions.** Twilio has a Trunk plus Origination URLs;
  Plivo has separate inbound and outbound trunks. Telnyx has a single *Credential
  Connection* carrying both the outbound username/password and the inbound
  destination, so `configure_number()` creates one thing rather than three.
- **Authentication is a bearer token**, not HTTP Basic - the only adapter here
  that differs, which is why `_headers()` exists rather than reusing `auth=`.
- **The termination domain is `<subdomain>.sip.telnyx.com`.** Telnyx derives it
  from the subdomain the connection is created with, so the subdomain has to be
  globally unique the same way Twilio's trunk domain does - hence `_slug()`,
  which the caller feeds an org-scoped label.

⚠️ The endpoint paths below follow Telnyx's published v2 API but have not been
exercised against a live account - no Telnyx credentials exist for this project.
The request shaping is tested against a stub; the paths are the thing to verify
first when an account arrives.
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

log = logging.getLogger("app.integrations.telephony.telnyx")

_BASE = "https://api.telnyx.com/v2"

# Telnyx supports TLS on SIP signalling and inbound signalling carries the
# dialled number - the same reasoning `plivo.py` documents for defaulting to it.
DEFAULT_TRANSPORT = "tls"

# Pagination. `_MAX_NUMBER_PAGES` is a ceiling, not an expected count: a vendor
# that kept returning a next page would otherwise hold the request open, and a
# picker that silently stopped at page one would hide an org's own numbers.
_MAX_NUMBER_PAGES = 100
_PAGE_SIZE = 100



class TelnyxCarrier:
    """Configures an organisation's own Telnyx account to talk to LiveKit."""

    #: Telnyx accepts an explicit transport on the URI it dials, and naming it
    #: avoids relying on LiveKit's `auto`. Same field as `PlivoCarrier`.
    outbound_transport: str | None = DEFAULT_TRANSPORT

    def __init__(
        self,
        *,
        api_key: str,
        connection_id: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise CarrierError(
                "Telnyx", "authenticate", "no API key is stored for this org."
            )
        self._api_key = api_key
        # An operator who already runs a Telnyx connection can name it rather
        # than have CallFlow create a second one beside it.
        self._connection_id = connection_id or None
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

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def _request(
        self, method: str, path: str, payload: dict[str, Any], *, action: str
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("TelnyxCarrier is not open. Use `async with TelnyxCarrier(...)`.")
        try:
            response = await self._client.request(
                method, f"{_BASE}/{path}", json=payload, headers=self._headers()
            )
        except httpx.HTTPError as exc:
            raise CarrierError(
                "Telnyx", action, f"could not be reached ({type(exc).__name__})."
            ) from exc

        if response.status_code >= 300:
            raise CarrierError("Telnyx", action, _detail(response))
        try:
            body = response.json()
        except ValueError:
            return {}
        # Telnyx wraps every v2 payload in `data`.
        data = body.get("data") if isinstance(body, dict) else None
        return data if isinstance(data, dict) else {}

    async def configure_number(
        self,
        *,
        number_ref: str,
        livekit_sip_host: str,
        label: str,
        auth_username: str,
        auth_password: str,
        transport: str = DEFAULT_TRANSPORT,
    ) -> CarrierTrunk:
        """Point a Telnyx number at LiveKit, both directions.

        `number_ref` is the Telnyx **Phone Number ID**, or the E.164 number - the
        adapter looks the id up when given a number, because Telnyx addresses
        numbers by id on the update call but operators know them as numbers.

        The number is attached last, for the same reason as the other two
        adapters: until then nothing about live traffic has changed, so a failure
        part-way leaves an unused connection rather than a number ringing into
        nowhere.
        """
        subdomain = _slug(label)
        connection_id = self._connection_id
        if not connection_id:
            connection = await self._request(
                "POST",
                "credential_connections",
                {
                    "connection_name": f"CallFlow {label}",
                    # Outbound: what LiveKit authenticates to Telnyx with.
                    "user_name": auth_username,
                    "password": auth_password,
                    # Inbound: where Telnyx delivers calls for this number.
                    "sip_uri_calling_preference": "unrestricted",
                    "inbound": {"sip_subdomain": subdomain},
                    "outbound": {"outbound_voice_profile_id": None},
                    "webhook_event_url": sip_uri(livekit_sip_host, transport),
                },
                action="create the SIP connection",
            )
            connection_id = str(connection.get("id") or "")
            subdomain = str(
                (connection.get("inbound") or {}).get("sip_subdomain") or subdomain
            )

        if not connection_id:
            raise CarrierError(
                "Telnyx", "create the SIP connection", "no connection id came back."
            )

        number_id = await self._resolve_number_id(number_ref)
        await self._request(
            "PATCH",
            f"phone_numbers/{number_id}",
            {"connection_id": connection_id},
            action="attach the phone number to the connection",
        )

        log.info("configured Telnyx connection %s", connection_id)
        return CarrierTrunk(
            provider="telnyx",
            trunk_id=connection_id,
            termination_domain=f"{subdomain}.sip.telnyx.com",
            auth_username=auth_username,
            auth_password=auth_password,
            details={"connection_id": connection_id, "transport": transport},
        )

    async def _get(self, path: str, *, action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("TelnyxCarrier is not open. Use `async with TelnyxCarrier(...)`.")
        try:
            response = await self._client.get(
                f"{_BASE}{path}", params=params, headers=self._headers()
            )
        except httpx.HTTPError as exc:
            raise CarrierError("Telnyx", action, f"could not be reached ({type(exc).__name__}).") from exc
        if response.status_code >= 300:
            raise CarrierError("Telnyx", action, _detail(response))
        try:
            return response.json()
        except ValueError:
            return {}

    async def list_numbers(self) -> list[CarrierNumber]:
        """The voice-capable numbers already on this Telnyx account.

        Telnyx pages with `page[number]`/`page[size]` and reports
        `meta.total_pages`, so the loop counts pages rather than offsets.
        """
        numbers: list[CarrierNumber] = []
        page = 1

        for _ in range(_MAX_NUMBER_PAGES):
            body = await self._get(
                "/phone_numbers",
                action="list the numbers on this account",
                params={"page[number]": page, "page[size]": _PAGE_SIZE},
            )
            items = body.get("data") or []
            for item in items:
                e164 = (item.get("phone_number") or "").strip()
                number_id = str(item.get("id") or "").strip()
                if not (e164 and number_id):
                    continue
                # Telnyx nests these under the number's connection settings; an
                # absent list means the vendor did not say, not "no voice".
                features = item.get("features") or []
                capabilities = {
                    f for f in features if isinstance(f, str)
                } or {"voice"}
                numbers.append(
                    CarrierNumber(
                        provider="telnyx",
                        e164=e164 if e164.startswith("+") else f"+{e164}",
                        # The id, not the E.164: `configure_number` PATCHes by id
                        # and would otherwise pay for a lookup it can skip.
                        number_ref=number_id,
                        label=(item.get("customer_reference") or "").strip() or None,
                        capabilities=frozenset(capabilities),
                    )
                )

            total_pages = (body.get("meta") or {}).get("total_pages")
            if not items or total_pages is None or page >= int(total_pages):
                break
            page += 1

        return numbers

    async def _resolve_number_id(self, number_ref: str) -> str:
        """Telnyx updates numbers by id; operators hold E.164.

        Passed through untouched when it is already an id, so an integration
        that has the id does not pay for a lookup.
        """
        if not number_ref.startswith("+"):
            return number_ref
        if self._client is None:  # pragma: no cover - guarded by the caller
            raise RuntimeError("TelnyxCarrier is not open.")
        try:
            response = await self._client.get(
                f"{_BASE}/phone_numbers",
                params={"filter[phone_number]": number_ref},
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise CarrierError(
                "Telnyx", "look up the phone number", f"could not be reached ({type(exc).__name__})."
            ) from exc
        if response.status_code >= 300:
            raise CarrierError("Telnyx", "look up the phone number", _detail(response))

        try:
            items = response.json().get("data") or []
        except ValueError:
            items = []
        if not items:
            raise CarrierError(
                "Telnyx",
                "look up the phone number",
                "that number is not on this Telnyx account.",
            )
        return str(items[0].get("id") or "")

    @staticmethod
    def allowed_addresses() -> list[str]:
        """Empty on purpose, and not an oversight.

        A Telnyx credential connection authenticates with a username and
        password, so LiveKit's inbound trunk does not have to fall back to an IP
        allowlist the way Twilio's does. Returned as an empty list rather than
        omitted so the provisioning workflow can call this on any adapter
        without knowing which it holds.
        """
        return []


def _detail(response: httpx.Response) -> str:
    """Telnyx's own message, which is the only part that says why."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}."
    errors = body.get("errors") if isinstance(body, dict) else None
    if isinstance(errors, list) and errors:
        first = errors[0]
        detail = first.get("detail") or first.get("title") or ""
        if detail:
            return str(detail)
    return f"HTTP {response.status_code}."


def _slug(label: str) -> str:
    """A SIP subdomain Telnyx will accept.

    Telnyx requires it globally unique and alphanumeric, so a collision is a real
    failure mode - the caller passes a label already scoped to the organisation.
    """
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in label).strip("-")
    return cleaned[:40] or "callflow"


__all__ = ["DEFAULT_TRANSPORT", "TelnyxCarrier"]
