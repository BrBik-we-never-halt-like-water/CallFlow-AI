"""Thin wrapper over the Resend HTTP API.

This module is the only place in the codebase that speaks to Resend. Everything
above it calls `EmailGateway.send_invitation` - no vendor endpoint or payload shape
leaks past this file.
"""

from __future__ import annotations

import logging
import re

import httpx

from app.core.config import config
from app.integrations.email.templates import invitation_email

log = logging.getLogger("callflow.email")

_RESEND_ENDPOINT = "https://api.resend.com/emails"

# Resend's exact shape for an unverified `from` domain:
#   {"statusCode": 403, "name": "validation_error",
#    "message": "The example.com domain is not verified. Please, add and
#    verify your domain on https://resend.com/domains"}
# Matched on `name` + a substring of `message` rather than the whole sentence,
# since Resend interpolates the offending domain into it.
_DOMAIN_NOT_VERIFIED_NAME = "validation_error"
_DOMAIN_NOT_VERIFIED_HINT = "domain is not verified"


class EmailAPIError(RuntimeError):
    """Resend rejected or failed to send the message."""


class EmailNotConfigured(RuntimeError):
    """No RESEND_API_KEY is set - sending would silently do nothing without this."""


class EmailGateway:
    """Sends the transactional emails CallFlow needs. Currently: invitations."""

    def __init__(self, api_key: str | None = None, from_email: str | None = None) -> None:
        self._api_key = api_key or config.resend_api_key
        self._from = from_email or config.resend_from_email

    async def send_invitation(
        self, *, to_email: str, org_name: str, role: str, accept_url: str
    ) -> None:
        if not self._api_key:
            raise EmailNotConfigured(
                "No Resend API key is set - RESEND_API_KEY must be configured before "
                "invitations can be sent."
            )

        subject, body = invitation_email(org_name=org_name, role=role, accept_url=accept_url)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    _RESEND_ENDPOINT,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={
                        "from": self._from,
                        "to": [to_email],
                        "subject": subject,
                        "html": body,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EmailAPIError(self._describe_rejection(exc.response)) from exc
        except httpx.HTTPError as exc:
            log.exception("resend invitation send failed")
            raise EmailAPIError(
                f"Could not reach Resend to send the invitation email: {exc}"
            ) from exc

    def _describe_rejection(self, response: httpx.Response) -> str:
        """Turns a rejected-send response into a message that says what's
        wrong and where to fix it, instead of dumping Resend's raw text.

        Domain verification is the rejection worth naming specifically: it is
        a one-time dashboard setup step, not a transient failure, and nothing
        in application code can work around it (Resend requires DNS records
        proving domain ownership before it will relay mail from that domain).
        """
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        name = payload.get("name") if isinstance(payload, dict) else None
        message = payload.get("message") if isinstance(payload, dict) else None

        if (
            response.status_code == 403
            and name == _DOMAIN_NOT_VERIFIED_NAME
            and isinstance(message, str)
            and _DOMAIN_NOT_VERIFIED_HINT in message
        ):
            log.error(
                "resend invitation send failed: sending domain not verified (from=%s)",
                self._from,
            )
            return (
                f"Invitations can't be sent yet - the sender address ({self._from_domain()}) "
                "isn't a domain verified in Resend. In the Resend dashboard, go to Domains, "
                "add and verify this domain (or point RESEND_FROM_EMAIL at one that's already "
                "verified), then try again."
            )

        log.exception("resend invitation send failed")
        detail = message if isinstance(message, str) and message else response.text
        return (
            f"Could not send the invitation email: Resend rejected the request "
            f"({response.status_code}) - {detail}"
        )

    def _from_domain(self) -> str:
        match = re.search(r"@([^\s>]+)", self._from)
        return match.group(1) if match else self._from


__all__ = ["EmailAPIError", "EmailGateway", "EmailNotConfigured"]
