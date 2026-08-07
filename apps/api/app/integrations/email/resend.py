"""Thin wrapper over the Resend HTTP API.

This module is the only place in the codebase that speaks to Resend. Everything
above it calls `EmailGateway.send_invitation` — no vendor endpoint or payload shape
leaks past this file.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import config

log = logging.getLogger("callflow.email")

_RESEND_ENDPOINT = "https://api.resend.com/emails"


class EmailAPIError(RuntimeError):
    """Resend rejected or failed to send the message."""


class EmailNotConfigured(RuntimeError):
    """No RESEND_API_KEY is set — sending would silently do nothing without this."""


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
                "No Resend API key is set — RESEND_API_KEY must be configured before "
                "invitations can be sent."
            )

        subject = f"You've been invited to {org_name} on CallFlow AI"
        body = (
            f"<p>You've been invited to join <strong>{org_name}</strong> on CallFlow AI "
            f"as a{'n' if role[:1].lower() in 'aeiou' else ''} <strong>{role}</strong>.</p>"
            f'<p><a href="{accept_url}">Accept the invitation</a></p>'
            f"<p>If you weren't expecting this, you can ignore this email.</p>"
        )

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
        except httpx.HTTPError as exc:
            log.exception("resend invitation send failed")
            raise EmailAPIError(f"Could not send the invitation email: {exc}") from exc


__all__ = ["EmailAPIError", "EmailGateway", "EmailNotConfigured"]
