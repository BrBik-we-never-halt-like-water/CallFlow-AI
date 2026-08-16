"""Voice agents: an org's reusable STT/TTS/LLM/telephony configurations for
the Agentic tab, plus the provider catalog and preview endpoints the builder
UI needs to populate itself.

Read access to an agent is org-wide, not per-creator (`voice_agents.py`'s own
docstring) - an agent is shared infrastructure, not personal work product
like a campaign.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.database import database
from app.database.repositories import (
    ai_provider_credentials as ai_provider_credentials_repo,
)
from app.database.repositories import provider_credentials as provider_credentials_repo
from app.database.repositories import voice_agents as voice_agents_repo
from app.domain.campaigns import FIELD_TYPES
from app.domain.safety import mask
from app.integrations.ai_providers import catalog
from app.services import voice_preview

router = APIRouter(prefix="/api/v1/voice-agents", tags=["voice-agents"])

TelephonyProvider = Literal["twilio", "plivo"]

_TELEPHONY_DISPLAY_NAMES: dict[str, str] = {"twilio": "Twilio", "plivo": "Plivo"}


class CollectFieldIn(BaseModel):
    """One thing the agent has to come back with.

    Deliberately the same shape as a campaign's `extra_fields` entry
    (`campaigns.py`'s `FieldIn`): both end up as structured call results, and a
    second field format would mean a second validator to keep in step.
    """

    key: str = Field(min_length=1, max_length=40)
    type: str = "string"
    description: str = ""
    required: bool = False


class VoiceAgentIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    kind: Literal["custom", "prebuilt"] = "custom"
    stt_provider: str | None = None
    tts_provider: str | None = None
    llm_provider: str | None = "openrouter"
    llm_model: str | None = None
    voice_id: str | None = None
    system_prompt: str | None = None
    prebuilt_persona: str | None = None
    telephony_provider: TelephonyProvider | None = None
    collect_fields: list[CollectFieldIn] = Field(default_factory=list)


class VoiceAgentOut(VoiceAgentIn):
    id: str
    org_id: str
    created_at: datetime
    created_by: str | None = None
    created_by_name: str | None = None
    created_by_avatar_url: str | None = None


class TelephonyOptionOut(BaseModel):
    provider: TelephonyProvider
    connected: bool
    phone_number_masked: str | None


class ProviderCatalogOut(BaseModel):
    stt: list[dict[str, Any]]
    tts: list[dict[str, Any]]
    llm: list[dict[str, Any]]
    telephony: list[TelephonyOptionOut]


class PreviewIn(BaseModel):
    provider: str
    kind: Literal["stt", "tts"]
    text: str | None = None
    voice_id: str | None = None
    audio_base64: str | None = None
    language: str | None = None


class PreviewOut(BaseModel):
    available: bool
    reason: str | None = None
    audio_base64: str | None = None
    transcript: str | None = None


def _decode_collect_fields(raw: object) -> list[CollectFieldIn]:
    """`session.py` registers a `jsonb` codec, so this arrives as a real list -
    the guard is for rows written before the column existed, which read back as
    the `[]` server default, and for anything hand-edited into a non-list."""
    if not isinstance(raw, list):
        return []
    return [CollectFieldIn.model_validate(item) for item in raw]


def _row_json(row: asyncpg.Record) -> VoiceAgentOut:
    created_by = row["created_by"]
    return VoiceAgentOut(
        id=str(row["id"]),
        org_id=str(row["org_id"]),
        name=row["name"],
        kind=row["kind"],
        stt_provider=row["stt_provider"],
        tts_provider=row["tts_provider"],
        llm_provider=row["llm_provider"],
        llm_model=row["llm_model"],
        voice_id=row["voice_id"],
        system_prompt=row["system_prompt"],
        prebuilt_persona=row["prebuilt_persona"],
        telephony_provider=row["telephony_provider"],
        collect_fields=_decode_collect_fields(row["collect_fields"]),
        created_at=row["created_at"],
        created_by=str(created_by) if created_by else None,
        created_by_name=row.get("created_by_name"),
        created_by_avatar_url=row.get("created_by_avatar_url"),
    )


@router.get("", response_model=list[VoiceAgentOut])
async def list_voice_agents(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.AGENTS_READ))],
) -> list[VoiceAgentOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await voice_agents_repo.list_org_agents(conn, user.org_id)
    return [_row_json(r) for r in rows]


def _serialize_catalog(
    entries: tuple[catalog.ProviderCatalogEntry, ...],
    connected_providers: set[str],
    connected_key: Callable[[catalog.ProviderCatalogEntry], str],
) -> list[dict[str, Any]]:
    serialized = []
    for entry in entries:
        data = asdict(entry)
        data["connected"] = connected_key(entry) in connected_providers
        serialized.append(data)
    return serialized


@router.get("/providers", response_model=ProviderCatalogOut)
async def provider_catalog(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.AGENTS_READ))],
) -> ProviderCatalogOut:
    """Every role sees this, unlike `ai_providers.py`'s own admin-gated
    credential management: whether Sarvam is connected, and a masked phone
    number, is not the same sensitivity as reading or changing the secret
    itself - just what a viewer needs while building or reviewing an agent.
    """
    async with database.as_user(user.auth_user_id) as conn:
        ai_rows = await ai_provider_credentials_repo.list_for_org(conn, user.org_id)
        telephony_rows = await provider_credentials_repo.list_for_org(conn, user.org_id)

    connected_ai_providers = {r["provider"] for r in ai_rows}
    telephony_by_provider = {r["provider"]: r for r in telephony_rows}

    stt = _serialize_catalog(catalog.STT_PROVIDERS, connected_ai_providers, lambda e: e.id)
    tts = _serialize_catalog(catalog.TTS_PROVIDERS, connected_ai_providers, lambda e: e.id)
    # LLM_MODELS entries route through OpenRouter and are per-model ids
    # (e.g. "openai/gpt-4o"), not vendor names - "connected" checks the
    # vendor credential, not the model id.
    llm = _serialize_catalog(
        catalog.LLM_MODELS, connected_ai_providers, lambda _e: "openrouter"
    )

    telephony = []
    for provider in ("twilio", "plivo"):
        row = telephony_by_provider.get(provider)
        phone = row["phone_number"] if row else None
        connected = row is not None and bool(phone)
        telephony.append(
            TelephonyOptionOut(
                provider=provider,
                connected=connected,
                phone_number_masked=mask(phone) if connected and phone else None,
            )
        )

    return ProviderCatalogOut(stt=stt, tts=tts, llm=llm, telephony=telephony)


def _encode_collect_fields(body: VoiceAgentIn) -> list[dict[str, Any]]:
    """Plain dicts, not a JSON string: the `jsonb` codec does the encoding."""
    return [f.model_dump() for f in body.collect_fields]


async def _validate_agent_fields(
    conn: asyncpg.Connection, org_id: UUID, body: VoiceAgentIn
) -> None:
    if body.llm_provider == "openrouter" and not body.llm_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="llm_model is required when llm_provider is 'openrouter' - pick a model.",
        )

    bad = [f.type for f in body.collect_fields if f.type not in FIELD_TYPES]
    if bad:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported field type(s): {', '.join(bad)}. "
                f"Use: {', '.join(sorted(FIELD_TYPES))}"
            ),
        )

    keys = [f.key for f in body.collect_fields]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Two fields share the key {', '.join(duplicates)}. "
                "Give each field its own key."
            ),
        )

    if body.telephony_provider is not None:
        telephony_rows = await provider_credentials_repo.list_for_org(conn, org_id)
        # A credential row with no phone_number set isn't a usable connection -
        # same "connected" definition provider_catalog() uses for its picker,
        # so an agent can never be assigned a number-less telephony provider.
        connected = {r["provider"] for r in telephony_rows if r["phone_number"]}
        if body.telephony_provider not in connected:
            display = _TELEPHONY_DISPLAY_NAMES[body.telephony_provider]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Connect a {display} number in Settings → Integrations "
                    "before assigning it to an agent."
                ),
            )


@router.post("", response_model=VoiceAgentOut, status_code=status.HTTP_201_CREATED)
async def create_voice_agent(
    body: VoiceAgentIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.AGENTS_WRITE))],
) -> VoiceAgentOut:
    async with database.as_user(user.auth_user_id) as conn:
        await _validate_agent_fields(conn, user.org_id, body)
        row = await voice_agents_repo.create_agent(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            name=body.name.strip(),
            kind=body.kind,
            stt_provider=body.stt_provider,
            tts_provider=body.tts_provider,
            llm_provider=body.llm_provider,
            llm_model=body.llm_model,
            voice_id=body.voice_id,
            system_prompt=body.system_prompt,
            prebuilt_persona=body.prebuilt_persona,
            telephony_provider=body.telephony_provider,
            collect_fields=_encode_collect_fields(body),
        )
    return _row_json(row)


@router.patch("/{agent_id}", response_model=VoiceAgentOut)
async def update_voice_agent(
    agent_id: UUID,
    body: VoiceAgentIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.AGENTS_WRITE))],
) -> VoiceAgentOut:
    async with database.as_user(user.auth_user_id) as conn:
        await _validate_agent_fields(conn, user.org_id, body)
        row = await voice_agents_repo.update_agent(
            conn,
            org_id=user.org_id,
            agent_id=agent_id,
            name=body.name.strip(),
            kind=body.kind,
            stt_provider=body.stt_provider,
            tts_provider=body.tts_provider,
            llm_provider=body.llm_provider,
            llm_model=body.llm_model,
            voice_id=body.voice_id,
            system_prompt=body.system_prompt,
            prebuilt_persona=body.prebuilt_persona,
            telephony_provider=body.telephony_provider,
            collect_fields=_encode_collect_fields(body),
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown voice agent: {agent_id}"
        )
    return _row_json(row)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voice_agent(
    agent_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.AGENTS_DELETE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await voice_agents_repo.delete_agent(conn, user.org_id, agent_id)
    if deleted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown voice agent: {agent_id}"
        )


@router.post("/preview", response_model=PreviewOut)
async def preview_voice_agent(
    body: PreviewIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.AGENTS_WRITE))],
) -> PreviewOut:
    """A real, possibly-billed vendor call on the org's own key - same trust
    tier as building/editing an agent, not read-only.

    An unavailable preview is never an HTTPException: `available=False` with
    a `reason` is the correct, successful response shape (CLAUDE.md
    non-negotiable #9) - the frontend renders the reason inline.
    """
    if body.kind == "tts" and not body.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="text is required to preview a voice.",
        )
    if body.kind == "stt" and not body.audio_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="audio_base64 is required to preview transcription.",
        )

    async with database.as_user(user.auth_user_id) as conn:
        credential = await ai_provider_credentials_repo.get_credential(
            conn, user.org_id, body.provider
        )
    encrypted_api_key = credential["api_key_encrypted"] if credential else None

    if body.kind == "tts":
        result = await voice_preview.preview_tts(
            provider=body.provider,
            encrypted_api_key=encrypted_api_key,
            text=body.text,  # type: ignore[arg-type]  # validated non-empty above
            voice_id=body.voice_id,
        )
    else:
        result = await voice_preview.preview_stt(
            provider=body.provider,
            encrypted_api_key=encrypted_api_key,
            audio_base64=body.audio_base64,  # type: ignore[arg-type]  # validated non-empty above
            language=body.language,
        )

    return PreviewOut(
        available=result.available,
        reason=result.reason,
        audio_base64=result.audio_base64,
        transcript=result.transcript,
    )
