"""The do-not-call list - CRUD for `public.suppressions`, the table
`check_dial_allowed()` actually consults (see ISSUES.md #3). Before this route
existed, the table had no writer anywhere in the app: a run resolved a real
verdict against it, but nothing had ever put a row there.
"""

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
from app.database.repositories import suppressions as suppressions_repo
from app.domain.safety import assert_e164, mask, phone_hash

router = APIRouter(prefix="/api/v1/suppressions", tags=["suppressions"])


class SuppressionOut(BaseModel):
    id: str
    phone_masked: str
    source: str
    reason: str | None
    suppressed_at: datetime


class SuppressionCreateIn(BaseModel):
    phone: str
    reason: str | None = Field(default=None, max_length=500)


def _row_to_out(row: asyncpg.Record) -> SuppressionOut:
    return SuppressionOut(
        id=str(row["id"]),
        phone_masked=mask(row["phone_e164"]) if row["phone_e164"] else "***",
        source=row["source"],
        reason=row["reason"],
        suppressed_at=row["suppressed_at"],
    )


@router.get("", response_model=list[SuppressionOut])
async def list_suppressions(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SUPPRESSIONS_READ))],
) -> list[SuppressionOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await suppressions_repo.list_suppressions(conn, user.org_id)
    return [_row_to_out(r) for r in rows]


@router.post("", response_model=SuppressionOut, status_code=status.HTTP_201_CREATED)
async def add_suppression(
    body: SuppressionCreateIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SUPPRESSIONS_ADD))],
) -> SuppressionOut:
    try:
        phone = assert_e164(body.phone)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    async with database.as_user(user.auth_user_id) as conn:
        row = await suppressions_repo.add_suppression(
            conn,
            org_id=user.org_id,
            phone_hash=phone_hash(phone),
            phone_e164=phone,
            reason=body.reason,
            suppressed_by=user.id,
        )
    return _row_to_out(row)


@router.delete("/{suppression_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_suppression(
    suppression_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.SUPPRESSIONS_REMOVE))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await suppressions_repo.remove_suppression(conn, user.org_id, suppression_id)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suppression not found.")
