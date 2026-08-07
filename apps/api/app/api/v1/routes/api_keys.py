"""Org-scoped API keys for programmatic access to CallFlow's own API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.database import database
from app.database.repositories import api_keys as api_keys_repo
from app.domain.api_keys import generate_api_key

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


class ApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreatedOut(ApiKeyOut):
    """Only the create response ever carries the full key."""

    key: str


class ApiKeyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


def _row_to_out(row: asyncpg.Record) -> ApiKeyOut:
    return ApiKeyOut(
        id=str(row["id"]),
        name=row["name"],
        key_prefix=row["key_prefix"],
        last_used_at=row["last_used_at"],
        created_at=row["created_at"],
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.API_KEYS_READ))],
) -> list[ApiKeyOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await api_keys_repo.list_for_org(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: ApiKeyCreateIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.API_KEYS_WRITE))],
) -> ApiKeyCreatedOut:
    generated = generate_api_key()
    async with database.as_user(user.auth_user_id) as conn:
        row = await api_keys_repo.create(
            conn,
            org_id=user.org_id,
            created_by=user.id,
            name=body.name,
            key_prefix=generated.key_prefix,
            key_hash=generated.key_hash,
        )
    return ApiKeyCreatedOut(**_row_to_out(row).model_dump(), key=generated.full_key)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.API_KEYS_WRITE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await api_keys_repo.revoke(conn, user.org_id, key_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")
