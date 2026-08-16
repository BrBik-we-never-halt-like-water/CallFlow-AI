"""OpenRouter provisioning and the conversational LLM, against stubbed HTTP.

No account needed. What is asserted is the shaping and the failure handling -
in particular the one-shot nature of the issued key, which is the detail that
turns a small bug into an organisation that can never make a call.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.integrations.openrouter.client import (
    OpenRouterError,
    OpenRouterProvisioning,
    get_conversational_llm,
)

KEY_BODY = {
    "data": {"hash": "kh_123", "name": "callflow-org-abc", "limit": 25.0, "usage": 4.5},
    "key": "sk-or-v1-secret",
}


class Recorder:
    def __init__(self, *responses: Any) -> None:
        self._responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responses.pop(0) if self._responses else httpx.Response(200, json=KEY_BODY)

    def body_of(self, index: int) -> dict[str, Any]:
        import json

        return json.loads(self.requests[index].content.decode() or "{}")


def _client(recorder: Recorder) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(recorder.handler))


# --- provisioning -------------------------------------------------------------


def test_provisioning_refuses_without_a_management_key() -> None:
    """The management key mints every organisation's key, so an unset one is a
    misconfiguration to report, not a condition to work around."""
    with pytest.raises(OpenRouterError) as caught:
        OpenRouterProvisioning(management_key="")
    assert "OPENROUTER_MANAGEMENT_KEY" in str(caught.value)


async def test_a_key_is_issued_per_organisation_with_a_limit() -> None:
    recorder = Recorder()
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        issued = await api.create_key(org_id="abc", limit_usd=25.0)

    assert recorder.requests[0].url.path.endswith("/keys")
    body = recorder.body_of(0)
    assert body["name"] == "callflow-org-abc"
    assert body["limit"] == 25.0
    assert issued.key == "sk-or-v1-secret"
    assert issued.key_hash == "kh_123"


async def test_the_management_key_authenticates_the_request() -> None:
    recorder = Recorder()
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        await api.create_key(org_id="abc")

    assert recorder.requests[0].headers["authorization"] == "Bearer mk"


async def test_no_limit_sends_no_limit_rather_than_zero() -> None:
    """Zero would be a ceiling of nothing, not the absence of one - the two
    mean opposite things to OpenRouter."""
    recorder = Recorder()
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        await api.create_key(org_id="abc", limit_usd=None)

    assert "limit" not in recorder.body_of(0)


async def test_a_response_without_the_secret_is_treated_as_a_failed_issue() -> None:
    """OpenRouter returns the key exactly once. Accepting a response that has
    no key would leave the organisation with a key hash it can meter but never
    authenticate with, and no way to recover it."""
    recorder = Recorder(httpx.Response(200, json={"data": {"hash": "kh_1"}}))
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        with pytest.raises(OpenRouterError) as caught:
            await api.create_key(org_id="abc")

    assert "returned once" in str(caught.value)


async def test_usage_is_read_from_the_provisioning_api() -> None:
    """Not accumulated from streaming responses: OpenRouter documents no
    guarantee a final usage chunk always arrives, and a meter that silently
    misses spend is worse than one that costs a request."""
    recorder = Recorder(httpx.Response(200, json=KEY_BODY))
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        state = await api.get_key("kh_123")

    assert recorder.requests[0].method == "GET"
    assert state.usage_usd == 4.5
    assert state.limit_usd == 25.0
    assert state.remaining_usd == 20.5


def test_remaining_is_unknown_rather_than_zero_without_a_limit() -> None:
    from app.integrations.openrouter.client import ProvisionedKey

    assert ProvisionedKey(key_hash="k", name="n", limit_usd=None, usage_usd=9).remaining_usd is None


async def test_an_exhausted_key_reports_no_remaining_budget_not_a_negative_one() -> None:
    recorder = Recorder(
        httpx.Response(200, json={"data": {"hash": "kh_1", "limit": 10.0, "usage": 12.0}})
    )
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        state = await api.get_key("kh_1")

    assert state.remaining_usd == 0.0


async def test_a_key_is_disabled_rather_than_deleted() -> None:
    """A deleted key takes its usage record with it, and that record is what a
    billing dispute is settled by."""
    recorder = Recorder(httpx.Response(200, json={"data": {"hash": "kh_1", "disabled": True}}))
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        state = await api.disable_key("kh_1")

    assert recorder.requests[0].method == "PATCH"
    assert recorder.body_of(0)["disabled"] is True
    assert state.disabled is True


async def test_an_openrouter_error_surfaces_its_own_message() -> None:
    recorder = Recorder(httpx.Response(402, json={"error": {"message": "Insufficient credits."}}))
    async with OpenRouterProvisioning(management_key="mk", client=_client(recorder)) as api:
        with pytest.raises(OpenRouterError) as caught:
            await api.create_key(org_id="abc")

    assert "Insufficient credits." in str(caught.value)
    assert "OpenRouter could not issue a key" in str(caught.value)


# --- the conversational LLM Part 2 consumes -----------------------------------


def test_the_llm_refuses_without_a_key_or_a_model() -> None:
    """One key proxies many models, so the key alone does not say which to run -
    a default here would silently talk to the wrong model."""
    with pytest.raises(OpenRouterError):
        get_conversational_llm(api_key="", model="anthropic/claude-sonnet-4")
    with pytest.raises(OpenRouterError) as caught:
        get_conversational_llm(api_key="sk-or-v1-x", model="")
    assert "no model set" in str(caught.value)


async def test_the_reply_streams_token_by_token() -> None:
    """Awaiting a whole response before speaking is a silence the contact
    hears, so the interface streams."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":", Aditi"}}]}\n\n'
                "data: [DONE]\n\n"
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        llm = get_conversational_llm(api_key="sk-or-v1-x", model="m", client=http)
        chunks = [chunk async for chunk in llm.respond([], system_prompt="Be brief.")]

    assert "".join(chunks) == "Hello, Aditi"


async def test_the_system_prompt_leads_the_history() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.update(json.loads(request.content.decode()))
        return httpx.Response(200, text="data: [DONE]\n\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        llm = get_conversational_llm(api_key="sk-or-v1-x", model="m", client=http)
        async for _ in llm.respond(
            [{"role": "user", "content": "Hi"}], system_prompt="Ask about Bali."
        ):
            pass

    assert seen["messages"][0] == {"role": "system", "content": "Ask about Bali."}
    assert seen["messages"][1] == {"role": "user", "content": "Hi"}
    assert seen["stream"] is True


async def test_a_malformed_chunk_is_skipped_rather_than_ending_the_call() -> None:
    """The alternative to skipping is the contact hearing the line go dead."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
                "data: {not json at all\n\n"
                "data: {}\n\n"
                ': a comment line\n\n'
                'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        llm = get_conversational_llm(api_key="sk-or-v1-x", model="m", client=http)
        chunks = [chunk async for chunk in llm.respond([], system_prompt="x")]

    assert "".join(chunks) == "Hello there"


async def test_a_rejected_conversation_reports_openrouters_reason() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "Rate limit exceeded."}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        llm = get_conversational_llm(api_key="sk-or-v1-x", model="m", client=http)
        with pytest.raises(OpenRouterError) as caught:
            async for _ in llm.respond([], system_prompt="x"):
                pass

    assert "Rate limit exceeded." in str(caught.value)
