"""The only file that calls Plivo's REST API.

Mirrors `twilio.py` deliberately - same constructor shape, same
`configure_number()` entry point, same `CarrierTrunk` back. That symmetry is
the point: the provisioning workflow picks an adapter and calls it, and adding
a third carrier means writing one more of these and nothing else.

Two differences from Twilio that are Plivo's, not ours:

- **The transport parameter is mandatory.** Plivo rejects an origination URI
  that does not name one; Twilio infers it. `sip_uri()` always emits it, so
  neither adapter can drift on the detail most likely to silently break
  inbound audio.
- **Outbound produces a termination domain** (`<trunk_id>.zt.plivo.com`) with
  its own username and password, which is what LiveKit's outbound trunk dials.
  Twilio has no analog, which is why `CarrierTrunk.termination_domain` is
  optional rather than every caller branching on the provider name.

⚠️ The endpoint paths below follow Plivo's published Zentrunk API but have not
been exercised against a live account - no Plivo credentials exist for this
project (RUNBOOK_HET_PART_1.md §2). The request shaping is tested against a
stub; the paths are the thing to verify first when an account arrives.
"""

from __future__ import annotations

import logging
from typing import Any, Self

import httpx

from app.integrations.telephony import CarrierError, CarrierTrunk, sip_uri

log = logging.getLogger("app.integrations.telephony.plivo")

_BASE = "https://api.plivo.com/v1/Account"

# TLS where the carrier supports it. Plivo does, and inbound SIP signalling
# carries the dialled number - which is exactly the kind of thing CLAUDE.md's
# no-PII-in-transit instinct says not to send in the clear when a flag avoids it.
DEFAULT_TRANSPORT = "tls"


class PlivoCarrier:
    """Configures an organisation's own Plivo account to talk to LiveKit."""

    def __init__(
        self,
        *,
        auth_id: str,
        auth_token: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not (auth_id and auth_token):
            raise CarrierError(
                "Plivo", "authenticate", "no Auth ID and Auth Token are stored for this org."
            )
        self._auth_id = auth_id
        self._auth = (auth_id, auth_token)
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

    async def _post(self, path: str, payload: dict[str, Any], *, action: str) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("PlivoCarrier is not open. Use `async with PlivoCarrier(...)`.")
        url = f"{_BASE}/{self._auth_id}/{path}"
        try:
            # JSON, not form-encoded - the one shape difference from Twilio.
            response = await self._client.post(url, json=payload, auth=self._auth)
        except httpx.HTTPError as exc:
            raise CarrierError("Plivo", action, f"could not be reached ({type(exc).__name__}).") from exc

        if response.status_code >= 300:
            raise CarrierError("Plivo", action, _detail(response))
        try:
            return response.json()
        except ValueError:
            # Plivo answers some creates with an empty body; an empty mapping is
            # honest here, and the caller checks for the id it actually needs.
            return {}

    async def configure_number(
        self,
        *,
        phone_number: str,
        livekit_sip_host: str,
        label: str,
        auth_username: str,
        auth_password: str,
        transport: str = DEFAULT_TRANSPORT,
    ) -> CarrierTrunk:
        """Point a Plivo number at LiveKit, both directions.

        The number is associated last, for the same reason as Twilio: until
        then nothing about live traffic has changed, so a failure part-way
        leaves unused objects rather than a number ringing into nowhere.
        """
        uri = await self._post(
            "Zentrunk/Uri/",
            {"name": f"CallFlow {label}", "uri": sip_uri(livekit_sip_host, transport)},
            action="register the LiveKit SIP address",
        )
        uri_id = str(uri.get("uri_id") or uri.get("id") or "")

        inbound = await self._post(
            "Zentrunk/Trunk/",
            {"name": f"CallFlow {label} inbound", "primary_uri_id": uri_id, "trunk_type": "inbound"},
            action="create the inbound trunk",
        )
        inbound_id = str(inbound.get("trunk_id") or inbound.get("id") or "")

        # Outbound authenticates with a credential, unlike Twilio's inbound.
        credential = await self._post(
            "Zentrunk/Credential/",
            {"username": auth_username, "password": auth_password},
            action="store outbound credentials",
        )
        credential_id = str(credential.get("credential_id") or credential.get("id") or "")

        outbound = await self._post(
            "Zentrunk/Trunk/",
            {
                "name": f"CallFlow {label} outbound",
                "trunk_type": "outbound",
                "credential_id": credential_id,
            },
            action="create the outbound trunk",
        )
        outbound_id = str(outbound.get("trunk_id") or outbound.get("id") or "")
        termination_domain = str(
            outbound.get("termination_sip_domain") or f"{outbound_id}.zt.plivo.com"
        )

        await self._post(
            f"Number/{phone_number.lstrip('+')}/",
            {"app_type": "trunk", "trunk_id": inbound_id},
            action="attach the phone number to the trunk",
        )

        log.info("configured Plivo trunks in=%s out=%s", inbound_id, outbound_id)
        return CarrierTrunk(
            provider="plivo",
            trunk_id=inbound_id,
            termination_domain=termination_domain,
            auth_username=auth_username,
            auth_password=auth_password,
            details={
                "outbound_trunk_id": outbound_id,
                "uri_id": uri_id,
                "credential_id": credential_id,
                "transport": transport,
            },
        )

    @staticmethod
    def allowed_addresses() -> list[str]:
        """Empty on purpose, and not an oversight.

        Plivo's outbound trunk authenticates with a username and password, so
        LiveKit's inbound trunk does not have to fall back to an IP allowlist
        the way Twilio's does. Returned as an empty list rather than omitted so
        the provisioning workflow can call this on either adapter without
        knowing which it holds.
        """
        return []


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}."
    message = body.get("error") or body.get("message") or ""
    return str(message) if message else f"HTTP {response.status_code}."


__all__ = ["DEFAULT_TRANSPORT", "PlivoCarrier"]
