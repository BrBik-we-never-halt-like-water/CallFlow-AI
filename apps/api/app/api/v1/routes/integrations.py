"""The third-party accounts an organisation connects, and their credentials.

Every provider a `voice_agent` can name lives here - carriers, speech vendors,
and the LLM marketplace - not just the two carriers this started as. The list
itself is `app/domain/providers.py`; this module is the HTTP surface over it.

Two ways in, because vendors differ and pretending otherwise would be a lie:

- **API key.** Most vendors issue one and offer nothing else. The operator
  pastes it and it is encrypted at rest.
- **OAuth.** OpenRouter hosts a login and hands back a key the organisation
  owns. `POST /providers/openrouter/oauth/exchange` completes that flow.

A provider that has no login flow never renders one - see `ConnectMethod` in
`domain/providers.py` for why that matters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.core.crypto import CredentialsNotConfigured, encrypt
from app.database import database
from app.database.repositories import provider_credentials as credentials_repo
from app.domain.providers import PROVIDERS, ConnectMethod, spec

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

# OpenRouter's documented PKCE exchange. The only outbound call this module
# makes - everything else is storage.
_OPENROUTER_KEY_EXCHANGE = "https://openrouter.ai/api/v1/auth/keys"


def _require_known(provider: str) -> None:
    """404 for a provider CallFlow does not support.

    A plain `Literal` would give a 422 that names every valid value, which is
    fine but says nothing about *why* one is missing. This says it.
    """
    if spec(provider) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{provider}' is not a provider CallFlow can connect.",
        )


class ProviderSpecOut(BaseModel):
    """What the settings page needs to render a provider it has never seen.

    Sent from the server rather than duplicated in the frontend: the two lists
    drifting is how a provider becomes selectable in the interface and
    unstorable by the API.
    """

    id: str
    name: str
    role: str
    connect: str
    summary: str
    identifier_label: str | None
    secret_label: str
    docs_url: str


class ProviderCredentialOut(BaseModel):
    provider: str
    label: str | None
    phone_number: str | None
    created_at: datetime
    updated_at: datetime


class ProviderCredentialIn(BaseModel):
    # Optional, because a single-secret vendor has no identifier to give. The
    # stored row still gets both halves - see `connect_provider`.
    identifier: str | None = Field(default=None, max_length=200)
    secret: str = Field(min_length=1, max_length=500)
    phone_number: str | None = Field(default=None, max_length=20)
    label: str | None = Field(default=None, max_length=120)


class OAuthExchangeIn(BaseModel):
    """The authorization code OpenRouter redirected back with."""

    code: str = Field(min_length=1, max_length=500)
    code_verifier: str | None = Field(default=None, max_length=200)


def _row_to_out(row: asyncpg.Record) -> ProviderCredentialOut:
    return ProviderCredentialOut(
        provider=row["provider"],
        label=row["label"],
        phone_number=row["phone_number"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/catalogue", response_model=list[ProviderSpecOut])
async def list_catalogue(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> list[ProviderSpecOut]:
    """Every provider CallFlow supports, and how each one connects."""
    return [
        ProviderSpecOut(
            id=p.id,
            name=p.name,
            role=p.role.value,
            connect=p.connect.value,
            summary=p.summary,
            identifier_label=p.identifier_label,
            secret_label=p.secret_label,
            docs_url=p.docs_url,
        )
        for p in PROVIDERS
    ]


@router.get("/providers", response_model=list[ProviderCredentialOut])
async def list_providers(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> list[ProviderCredentialOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await credentials_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.post("/providers/{provider}/oauth/exchange", response_model=ProviderCredentialOut)
async def exchange_oauth_code(
    provider: str,
    body: OAuthExchangeIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProviderCredentialOut:
    """Trade an authorization code for a key, and store it.

    The exchange happens server-side even though the flow starts in the
    browser: the key that comes back is a long-lived credential, and handing it
    to the frontend first would put it in a place this product otherwise takes
    care to keep it out of.
    """
    _require_known(provider)
    provider_spec = spec(provider)
    assert provider_spec is not None  # guarded above
    if provider_spec.connect is not ConnectMethod.OAUTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider_spec.name} does not offer a login flow - add an API key instead.",
        )

    payload: dict[str, str] = {"code": body.code}
    if body.code_verifier:
        payload["code_verifier"] = body.code_verifier
        payload["code_challenge_method"] = "S256"

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.post(_OPENROUTER_KEY_EXCHANGE, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not reach {provider_spec.name} to finish connecting.",
        ) from exc

    if response.status_code >= 300:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider_spec.name} rejected the authorization code. "
                "It may have already been used - start the connection again."
            ),
        )

    key = str(response.json().get("key") or "")
    if not key:
        # The code is single-use, so there is nothing to retry with. Saying so
        # beats storing an empty credential that fails at call time instead.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"{provider_spec.name} returned no key. The authorization code is "
                "single-use, so start the connection again."
            ),
        )

    return await _store(user=user, provider=provider, identifier=None, secret=key,
                        phone_number=None, label="Connected with OpenRouter")


async def _store(
    *,
    user: CurrentUser,
    provider: str,
    identifier: str | None,
    secret: str,
    phone_number: str | None,
    label: str | None,
) -> ProviderCredentialOut:
    """Encrypt and upsert. Both halves are always written.

    A single-secret vendor stores the empty string as its identifier rather
    than NULL: the column is NOT NULL, and an empty ciphertext round-trips
    cleanly, which keeps every read path free of a "does this vendor have an
    identifier" branch.
    """
    try:
        identifier_encrypted = encrypt(identifier or "")
        secret_encrypted = encrypt(secret)
    except CredentialsNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    async with database.as_user(user.auth_user_id) as conn:
        row = await credentials_repo.upsert(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            provider=provider,
            label=label,
            identifier_encrypted=identifier_encrypted,
            secret_encrypted=secret_encrypted,
            phone_number=phone_number,
        )
    return _row_to_out(row)


@router.put("/providers/{provider}", response_model=ProviderCredentialOut)
async def connect_provider(
    provider: str,
    body: ProviderCredentialIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProviderCredentialOut:
    _require_known(provider)
    provider_spec = spec(provider)
    assert provider_spec is not None  # guarded above

    # A vendor that names an identifier needs one; a vendor that does not must
    # not be asked for it. Validating against the spec rather than the request
    # keeps the rule in one place instead of in every form.
    if provider_spec.identifier_label and not (body.identifier or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider_spec.name} needs a {provider_spec.identifier_label}.",
        )

    return await _store(
        user=user,
        provider=provider,
        identifier=(body.identifier or "").strip() or None,
        secret=body.secret,
        phone_number=body.phone_number,
        label=body.label,
    )


@router.delete("/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_provider(
    provider: str,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await credentials_repo.remove(conn, user.org_id, provider)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected.")
