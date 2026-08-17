"""Org-owned AI vendor credentials (Sarvam, Deepgram, ElevenLabs, OpenAI,
OpenRouter) that a voice agent's STT/TTS/LLM selection draws on.

Mirrors `routes/integrations.py`'s shape closely - same connect/disconnect
credential pattern, same permission tier: connecting a costed AI-vendor key
is the same sensitivity as connecting Twilio/Plivo, so this reuses
INTEGRATIONS_READ/WRITE rather than adding a narrower permission.
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
from app.database.repositories import (
    ai_provider_credentials as ai_provider_credentials_repo,
)

router = APIRouter(prefix="/api/v1/ai-providers", tags=["ai-providers"])

# The `ai_provider_credentials.provider` check constraint's exact five values -
# not the provider catalog's ids, which for LLM_MODELS are per-model
# (e.g. "openai/gpt-4o"), not vendor names.
AiProvider = Literal["sarvam", "deepgram", "elevenlabs", "openai", "openrouter"]


class AiProviderCredentialOut(BaseModel):
    provider: AiProvider
    label: str | None
    created_at: datetime
    updated_at: datetime


class AiProviderCredentialIn(BaseModel):
    api_key: str = Field(min_length=1, max_length=500)
    label: str | None = Field(default=None, max_length=120)


def _row_to_out(row: asyncpg.Record) -> AiProviderCredentialOut:
    return AiProviderCredentialOut(
        provider=row["provider"],
        label=row["label"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=list[AiProviderCredentialOut])
async def list_ai_providers(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_READ))],
) -> list[AiProviderCredentialOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await ai_provider_credentials_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.put("/{provider}", response_model=AiProviderCredentialOut)
async def connect_ai_provider(
    provider: AiProvider,
    body: AiProviderCredentialIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> AiProviderCredentialOut:
    try:
        api_key_encrypted = encrypt(body.api_key)
    except CredentialsNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    async with database.as_user(user.auth_user_id) as conn:
        row = await ai_provider_credentials_repo.upsert(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            provider=provider,
            label=body.label,
            api_key_encrypted=api_key_encrypted,
        )
    return _row_to_out(row)


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_ai_provider(
    provider: AiProvider,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.INTEGRATIONS_WRITE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await ai_provider_credentials_repo.remove(conn, user.org_id, provider)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not connected.")
