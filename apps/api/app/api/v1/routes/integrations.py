"""Org-owned Twilio/Plivo credentials, so a run can dial from the org's own number.

Twilio and Plivo both authenticate with an identifier + secret pair rather than
OAuth (Account SID + Auth Token; Auth ID + Auth Token), so this is credential
storage, not a connection flow. Actually placing a call over one of these
providers is separate, not-yet-built work — this endpoint only stores and
reports whether credentials are on file.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.core.crypto import CredentialsNotConfigured, encrypt
from app.database import database
from app.database.repositories import provider_credentials as credentials_repo

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

Provider = Literal["twilio", "plivo"]


class ProviderCredentialOut(BaseModel):
    provider: Provider
    label: str | None
    phone_number: str | None
    created_at: datetime
    updated_at: datetime


class ProviderCredentialIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=200)
    secret: str = Field(min_length=1, max_length=500)
    phone_number: str | None = Field(default=None, max_length=20)
    label: str | None = Field(default=None, max_length=120)


def _row_to_out(row: asyncpg.Record) -> ProviderCredentialOut:
    return ProviderCredentialOut(
        provider=row["provider"],
        label=row["label"],
        phone_number=row["phone_number"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/providers", response_model=list[ProviderCredentialOut])
async def list_providers(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> list[ProviderCredentialOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await credentials_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.put("/providers/{provider}", response_model=ProviderCredentialOut)
async def connect_provider(
    provider: Provider,
    body: ProviderCredentialIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> ProviderCredentialOut:
    try:
        identifier_encrypted = encrypt(body.identifier)
        secret_encrypted = encrypt(body.secret)
    except CredentialsNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    async with database.as_user(user.auth_user_id) as conn:
        row = await credentials_repo.upsert(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            provider=provider,
            label=body.label,
            identifier_encrypted=identifier_encrypted,
            secret_encrypted=secret_encrypted,
            phone_number=body.phone_number,
        )
    return _row_to_out(row)


@router.delete("/providers/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_provider(
    provider: Provider,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await credentials_repo.remove(conn, user.org_id, provider)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected.")
