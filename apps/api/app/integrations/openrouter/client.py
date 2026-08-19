"""The only file that calls OpenRouter.

Two jobs that happen to share a vendor, and are otherwise unrelated:

1. **Provisioning** (`OpenRouterProvisioning`) - CallFlow issues one API key per
   organisation from its own management key, with a spend limit. This is not an
   organisation's own credential the way Twilio is; it is one CallFlow hands
   *to* them, which is why the management key is a platform-level setting and
   never a `provider_credentials` row.
2. **Conversation** (`get_conversational_llm`) - resolving an organisation's
   provisioned key plus a voice agent's model into something that can hold a
   turn. This is what the extraction/completion-judgment call site needs
   (`RUNBOOK_ARBAAZ_PART_2.md` P2-T2) without importing an LLM SDK of its own.

**Where the issued key is stored, and why there is no new table for it.**
`provider_credentials` already has exactly the right shape - one row per
organisation per provider, both halves encrypted at rest, RLS, and a `provider`
check that was widened for precisely this in the ADR-4 migration. A second
table would duplicate the encryption and tenancy work to hold one row per org.
The distinction that it is CallFlow-issued rather than org-owned is real but it
is a *semantic* one, and it lives in this comment and the `label`, not in a
separate schema.

⚠️ Endpoint shapes follow OpenRouter's published API but no account exists for
this project yet (RUNBOOK_HET_PART_1.md §2). Request shaping and error handling
are tested against stubs; the paths are the first thing to verify live.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, Self

import httpx

from app.core.config import config

log = logging.getLogger("app.integrations.openrouter")

_BASE = "https://openrouter.ai/api/v1"


class OpenRouterError(Exception):
    """OpenRouter refused or could not be reached.

    Surfaced to an operator, so it carries OpenRouter's own message - a spend
    limit that has been hit reads very differently from a revoked key, and
    "something went wrong" tells them neither (CLAUDE.md §5).
    """

    def __init__(self, action: str, detail: str) -> None:
        self.action = action
        self.detail = detail
        super().__init__(f"OpenRouter could not {action}: {detail}")


@dataclass(frozen=True)
class ProvisionedKey:
    """A key CallFlow issued to one organisation.

    `key` is present only on creation - OpenRouter returns the secret once and
    never again, which is why it has to be encrypted and stored at that moment
    rather than re-fetched when needed.
    """

    key_hash: str
    name: str
    limit_usd: float | None = None
    usage_usd: float = 0.0
    disabled: bool = False
    key: str | None = None

    @property
    def remaining_usd(self) -> float | None:
        if self.limit_usd is None:
            return None
        return max(0.0, self.limit_usd - self.usage_usd)


class OpenRouterProvisioning:
    """Issues and meters per-organisation keys with CallFlow's management key."""

    def __init__(
        self, *, management_key: str | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self._management_key = (
            management_key if management_key is not None else config.openrouter_management_key
        )
        if not self._management_key:
            raise OpenRouterError(
                "authenticate",
                "OPENROUTER_MANAGEMENT_KEY is not set, so no organisation key can be issued.",
            )
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
        self, method: str, path: str, *, action: str, json_body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("Use `async with OpenRouterProvisioning(...)`.")
        try:
            response = await self._client.request(
                method,
                f"{_BASE}{path}",
                json=json_body,
                headers={"Authorization": f"Bearer {self._management_key}"},
            )
        except httpx.HTTPError as exc:
            raise OpenRouterError(action, f"could not be reached ({type(exc).__name__}).") from exc

        if response.status_code >= 300:
            raise OpenRouterError(action, _detail(response))
        try:
            return response.json()
        except ValueError:
            return {}

    async def create_key(self, *, org_id: str, limit_usd: float | None = None) -> ProvisionedKey:
        """Issue this organisation's key. The secret comes back exactly once.

        `limit_usd` is the org's plan ceiling. Passing `None` means unlimited,
        which is a real choice and not a default - an unmetered key on a
        marketplace that bills per token is how one organisation's runaway
        run becomes CallFlow's bill.
        """
        body: dict[str, Any] = {"name": f"callflow-org-{org_id}"}
        if limit_usd is not None:
            body["limit"] = limit_usd

        payload = await self._request("POST", "/keys", action="issue a key", json_body=body)
        secret = payload.get("key")
        if not secret:
            raise OpenRouterError(
                "issue a key",
                "the response carried no key. It is returned once and cannot be fetched later, "
                "so this attempt has to be treated as failed.",
            )
        base = _parse_key(payload)
        log.info("issued OpenRouter key for org %s", org_id)
        return ProvisionedKey(
            key_hash=base.key_hash,
            name=base.name,
            limit_usd=base.limit_usd,
            usage_usd=base.usage_usd,
            disabled=base.disabled,
            key=str(secret),
        )

    async def get_key(self, key_hash: str) -> ProvisionedKey:
        """Current usage and limit, read from the provisioning API.

        Read here rather than accumulated from streaming responses: OpenRouter
        documents no guarantee that a final usage chunk always arrives, and a
        meter that silently misses spend is worse than one that costs a request.
        """
        payload = await self._request("GET", f"/keys/{key_hash}", action="read key usage")
        return _parse_key(payload)

    async def set_limit(self, key_hash: str, *, limit_usd: float | None) -> ProvisionedKey:
        """Move an organisation's ceiling when their plan changes."""
        payload = await self._request(
            "PATCH", f"/keys/{key_hash}", action="update the spend limit",
            json_body={"limit": limit_usd},
        )
        return _parse_key(payload)

    async def disable_key(self, key_hash: str) -> ProvisionedKey:
        """Stop an organisation spending without destroying the usage history.

        Disable rather than delete, deliberately: a deleted key takes its usage
        record with it, and that record is what a billing dispute is settled by.
        """
        payload = await self._request(
            "PATCH", f"/keys/{key_hash}", action="disable the key",
            json_body={"disabled": True},
        )
        return _parse_key(payload)


class ConversationalLLM(Protocol):
    """What a caller needs to hold a turn, and nothing more.

    Deliberately one method. `RUNBOOK_ARBAAZ_PART_2.md`'s extraction and
    completion-judgment step needs to ask a model a question without importing
    an LLM SDK - that is the whole point of the vendor boundary, and a wider
    interface would start leaking one vendor's concepts into their code.
    """

    async def respond(
        self, history: list[dict[str, str]], *, system_prompt: str
    ) -> AsyncIterator[str]: ...


class OpenRouterLLM:
    """`ConversationalLLM` over OpenRouter's OpenAI-compatible chat endpoint."""

    def __init__(
        self, *, api_key: str, model: str, client: httpx.AsyncClient | None = None
    ) -> None:
        if not api_key:
            raise OpenRouterError("start a conversation", "this organisation has no issued key.")
        if not model:
            raise OpenRouterError(
                "start a conversation",
                "this voice agent has no model set. One key proxies many models, "
                "so the key alone does not say which to run.",
            )
        self._api_key = api_key
        self._model = model
        self._client = client

    async def respond(
        self, history: list[dict[str, str]], *, system_prompt: str
    ) -> AsyncIterator[str]:
        """Stream the reply as it arrives.

        Streamed rather than awaited whole because this sits in a live phone
        call: waiting for a complete response before speaking is a silence the
        contact hears.
        """
        messages = [{"role": "system", "content": system_prompt}, *history]
        owns = self._client is None
        http = self._client or httpx.AsyncClient(timeout=60.0)
        try:
            async with http.stream(
                "POST",
                f"{_BASE}/chat/completions",
                json={"model": self._model, "messages": messages, "stream": True},
                headers={"Authorization": f"Bearer {self._api_key}"},
            ) as response:
                if response.status_code >= 300:
                    await response.aread()
                    raise OpenRouterError("generate a reply", _detail(response))
                async for line in response.aiter_lines():
                    chunk = _content_of(line)
                    if chunk:
                        yield chunk
        except httpx.HTTPError as exc:
            raise OpenRouterError(
                "generate a reply", f"could not be reached ({type(exc).__name__})."
            ) from exc
        finally:
            if owns:
                await http.aclose()


def get_conversational_llm(
    *, api_key: str, model: str, client: httpx.AsyncClient | None = None
) -> ConversationalLLM:
    """Resolve an organisation's key and a voice agent's model into an LLM.

    The function `RUNBOOK_HET_PART_1.md` §5 owes Part 2. Kept deliberately thin
    and keyword-only so their call site never has to name a vendor: they pass
    what the `voice_agent` row already holds and get something satisfying
    `ConversationalLLM` back.
    """
    return OpenRouterLLM(api_key=api_key, model=model, client=client)


def _parse_key(payload: dict[str, Any]) -> ProvisionedKey:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    limit = data.get("limit")
    return ProvisionedKey(
        key_hash=str(data.get("hash") or ""),
        name=str(data.get("name") or ""),
        limit_usd=float(limit) if isinstance(limit, int | float) else None,
        usage_usd=float(data.get("usage") or 0.0),
        disabled=bool(data.get("disabled")),
    )


def _content_of(line: str) -> str:
    """One token out of an SSE line, or "" for the many lines that carry none.

    Never raises: a malformed chunk mid-call must not end the conversation, and
    the alternative to skipping it is the contact hearing the line go dead.
    """
    if not line.startswith("data:"):
        return ""
    body = line[len("data:") :].strip()
    if not body or body == "[DONE]":
        return ""
    try:
        parsed = json.loads(body)
        return str(parsed["choices"][0]["delta"].get("content") or "")
    except (ValueError, KeyError, IndexError, TypeError):
        return ""


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"HTTP {response.status_code}."
    error = body.get("error")
    message = error.get("message") if isinstance(error, dict) else body.get("message")
    return str(message) if message else f"HTTP {response.status_code}."


__all__ = [
    "ConversationalLLM",
    "OpenRouterError",
    "OpenRouterLLM",
    "OpenRouterProvisioning",
    "ProvisionedKey",
    "get_conversational_llm",
]
