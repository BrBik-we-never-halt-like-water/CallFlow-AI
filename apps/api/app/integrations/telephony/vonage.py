"""The only file that calls Vonage's REST API.

Mirrors the other three adapters - same constructor shape, same
`configure_number()` entry point, same `CarrierTrunk` back.

What is Vonage's own, not ours:

- **SIP trunking is configured per *domain*, not per number.** Vonage's
  Programmable SIP registers an inbound domain and a set of authenticated
  outbound credentials; a number is then linked to it. So this creates the
  domain first and links last, the same ordering as the other adapters and for
  the same reason.
- **Authentication is an api_key/api_secret pair over HTTP Basic**, and the key
  is not itself a secret - Vonage prints it in the dashboard header. It is
  declared `secret=False` in `domain/providers.py` for that reason, so the
  settings page does not mask something the operator has to read back.
- **The termination domain is `<name>.sip.vonage.com`**, derived from the domain
  name Vonage is given, which has to be globally unique - hence `_slug()`.

⚠️ The endpoint paths below follow Vonage's published Programmable SIP API but
have not been exercised against a live account - no Vonage credentials exist for
this project. The request shaping is tested against a stub; the paths are the
thing to verify first when an account arrives.
"""

from __future__ import annotations

import logging
from typing import Any, Self

import httpx

from app.integrations.telephony import CarrierError, CarrierTrunk, sip_uri

log = logging.getLogger("app.integrations.telephony.vonage")

_BASE = "https://api.nexmo.com/v1"
_ACCOUNT = "https://rest.nexmo.com"

DEFAULT_TRANSPORT = "tls"


class VonageCarrier:
    """Configures an organisation's own Vonage account to talk to LiveKit."""

    outbound_transport: str | None = DEFAULT_TRANSPORT

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not (api_key and api_secret):
            raise CarrierError(
                "Vonage", "authenticate", "no API key and secret are stored for this org."
            )
        self._api_key = api_key
        self._auth = (api_key, api_secret)
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

    async def _request(
        self, method: str, url: str, payload: dict[str, Any], *, action: str
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("VonageCarrier is not open. Use `async with VonageCarrier(...)`.")
        try:
            response = await self._client.request(method, url, json=payload, auth=self._auth)
        except httpx.HTTPError as exc:
            raise CarrierError(
                "Vonage", action, f"could not be reached ({type(exc).__name__})."
            ) from exc

        if response.status_code >= 300:
            raise CarrierError("Vonage", action, _detail(response))
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

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
        """Point a Vonage number at LiveKit, both directions.

        `number_ref` is the E.164 number - Vonage addresses numbers directly, the
        same as Plivo. Named uniformly across the adapters so the provisioning
        workflow does not branch on the provider.
        """
        name = _slug(label)

        domain = await self._request(
            "POST",
            f"{_BASE}/networks/sip/domains",
            {
                "name": name,
                # Inbound: where Vonage delivers calls it receives for the number.
                "inbound_uri": sip_uri(livekit_sip_host, transport),
                # Outbound: what LiveKit authenticates to Vonage with.
                "credentials": {"username": auth_username, "password": auth_password},
            },
            action="create the SIP domain",
        )
        domain_id = str(domain.get("id") or domain.get("domain_id") or "")
        if not domain_id:
            raise CarrierError("Vonage", "create the SIP domain", "no domain id came back.")

        await self._request(
            "POST",
            f"{_ACCOUNT}/number/update",
            {
                "country": _country_of(number_ref),
                "msisdn": number_ref.lstrip("+"),
                "voiceCallbackType": "sip",
                "voiceCallbackValue": f"{name}.sip.vonage.com",
            },
            action="attach the phone number to the SIP domain",
        )

        log.info("configured Vonage SIP domain %s", domain_id)
        return CarrierTrunk(
            provider="vonage",
            trunk_id=domain_id,
            termination_domain=f"{name}.sip.vonage.com",
            auth_username=auth_username,
            auth_password=auth_password,
            details={"domain_id": domain_id, "transport": transport},
        )

    @staticmethod
    def allowed_addresses() -> list[str]:
        """Empty on purpose - Vonage authenticates outbound with a credential,
        so LiveKit's inbound trunk needs no IP allowlist. See `PlivoCarrier`."""
        return []


def _country_of(number: str) -> str:
    """Vonage's number-update call wants the ISO country alongside the number.

    Derived from the dialling code rather than asked for, because an operator
    connecting their own number should not have to restate where it is. Only the
    codes CallFlow actually sells into are mapped; anything else falls back to
    the number's own country being rejected by Vonage with a message that says
    so, which is better than guessing wrong.
    """
    digits = number.lstrip("+")
    for prefix, country in (("91", "IN"), ("1", "US"), ("44", "GB"), ("61", "AU"), ("971", "AE")):
        if digits.startswith(prefix):
            return country
    return ""


def _detail(response: httpx.Response) -> str:
    """Vonage's own message, which is the only part that says why."""
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}."
    if not isinstance(body, dict):
        return f"HTTP {response.status_code}."
    message = (
        body.get("detail")
        or body.get("title")
        or body.get("error_text")
        or body.get("error-code-label")
        or ""
    )
    return str(message) if message else f"HTTP {response.status_code}."


def _slug(label: str) -> str:
    """A SIP domain name Vonage will accept, globally unique per the caller's
    org-scoped label."""
    cleaned = "".join(c.lower() if c.isalnum() else "-" for c in label).strip("-")
    return cleaned[:40] or "callflow"


__all__ = ["DEFAULT_TRANSPORT", "VonageCarrier"]
