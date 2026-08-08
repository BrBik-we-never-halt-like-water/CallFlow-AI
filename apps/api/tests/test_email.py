"""EmailGateway's Resend integration: request shape and error translation.

The bug this guards against: a rejected send used to surface as a raw `httpx`
exception dump (`Client error '403 Forbidden' for url '...'`), which told
whoever was troubleshooting nothing about *why* Resend refused the message.
Domain verification is the rejection worth naming specifically — it is a
one-time dashboard step, not a transient failure, and no retry or code change
works around it.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import httpx
import pytest

from app.integrations.email import resend as resend_module
from app.integrations.email.resend import (
    EmailAPIError,
    EmailGateway,
    EmailNotConfigured,
)


def _install_transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    """Routes the module's `httpx.AsyncClient()` through a `MockTransport`.

    `EmailGateway` builds its own client rather than accepting one — matching
    every other call site in this file — so the test substitutes the
    transport at the `httpx.AsyncClient` class level instead of reaching
    into an instance.
    """
    transport = httpx.MockTransport(handler)

    class _FixedTransportClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(resend_module.httpx, "AsyncClient", _FixedTransportClient)


async def test_send_invitation_posts_the_shape_resend_expects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["content_type"] = request.headers.get("content-type")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "email_123"})

    _install_transport(monkeypatch, handler)
    gateway = EmailGateway(api_key="re_test_key", from_email="CallFlow AI <noreply@verified.example>")

    await gateway.send_invitation(
        to_email="new-teammate@example.com",
        org_name="Acme",
        role="operator",
        accept_url="https://app.example.com/accept-invite/tok123",
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["auth"] == "Bearer re_test_key"
    assert captured["content_type"] == "application/json"
    body = captured["body"]
    assert body["from"] == "CallFlow AI <noreply@verified.example>"
    assert body["to"] == ["new-teammate@example.com"]
    assert body["subject"]
    assert "Acme" in body["html"]


async def test_send_invitation_without_api_key_raises_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`api_key=""` alone doesn't prove this — the constructor's `or` falls
    back to `config.resend_api_key`, so the empty case has to come from
    config itself being unset, same as a real deployment missing the env var."""
    monkeypatch.setattr(resend_module, "config", replace(resend_module.config, resend_api_key=""))
    gateway = EmailGateway(from_email="CallFlow AI <noreply@verified.example>")

    with pytest.raises(EmailNotConfigured):
        await gateway.send_invitation(
            to_email="new-teammate@example.com",
            org_name="Acme",
            role="operator",
            accept_url="https://app.example.com/accept-invite/tok123",
        )


async def test_unverified_domain_rejection_names_the_domain_and_the_fix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "statusCode": 403,
                "name": "validation_error",
                "message": (
                    "The callflow-ai.brbik.com domain is not verified. Please, "
                    "add and verify your domain on https://resend.com/domains"
                ),
            },
        )

    _install_transport(monkeypatch, handler)
    gateway = EmailGateway(
        api_key="re_test_key", from_email="CallFlow AI <noreply@callflow-ai.brbik.com>"
    )

    with pytest.raises(EmailAPIError) as exc_info:
        await gateway.send_invitation(
            to_email="new-teammate@example.com",
            org_name="Acme",
            role="operator",
            accept_url="https://app.example.com/accept-invite/tok123",
        )

    message = str(exc_info.value)
    assert "callflow-ai.brbik.com" in message
    assert "isn't a domain verified in Resend" in message
    assert "Domains" in message
    # The raw Resend sentence must not be the whole story handed back — the
    # message above it is what actually tells someone where to go fix this.
    assert "resend.com/domains" not in message


async def test_other_rejection_reasons_still_surface_resends_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 422 (bad payload) or any non-domain 403 should stay generic — the
    specific message above is reserved for the one case code can actually
    tell someone how to fix."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "statusCode": 422,
                "name": "invalid_from_address",
                "message": "Invalid `from` field.",
            },
        )

    _install_transport(monkeypatch, handler)
    gateway = EmailGateway(api_key="re_test_key", from_email="not-an-address")

    with pytest.raises(EmailAPIError) as exc_info:
        await gateway.send_invitation(
            to_email="new-teammate@example.com",
            org_name="Acme",
            role="operator",
            accept_url="https://app.example.com/accept-invite/tok123",
        )

    message = str(exc_info.value)
    assert "422" in message
    assert "Invalid `from` field." in message
    assert "verified in Resend" not in message


async def test_network_failure_message_names_resend_not_a_raw_dump(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    _install_transport(monkeypatch, handler)
    gateway = EmailGateway(api_key="re_test_key", from_email="CallFlow AI <noreply@verified.example>")

    with pytest.raises(EmailAPIError) as exc_info:
        await gateway.send_invitation(
            to_email="new-teammate@example.com",
            org_name="Acme",
            role="operator",
            accept_url="https://app.example.com/accept-invite/tok123",
        )

    assert "reach Resend" in str(exc_info.value)
