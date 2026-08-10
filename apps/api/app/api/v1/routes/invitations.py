"""Resolving and accepting an invitation by its token."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import CurrentUser, current_user
from app.database import database
from app.database.repositories import invitations as invitations_repo

router = APIRouter(prefix="/api/v1/invitations", tags=["invitations"])


class InvitationPreviewOut(BaseModel):
    valid: bool
    reason: str | None
    org_name: str | None
    role: str | None
    email: str | None


class AcceptedOut(BaseModel):
    org_id: str
    org_name: str
    org_slug: str
    role: str


@router.get("/{token}", response_model=InvitationPreviewOut)
async def preview(token: str) -> InvitationPreviewOut:
    """Public - an invitee hasn't signed in yet when they open this link."""
    async with database.anonymous() as conn:
        row = await invitations_repo.lookup_public(conn, token)
    return InvitationPreviewOut(
        valid=row["valid"],
        reason=row["reason"],
        org_name=row["org_name"],
        role=row["role"],
        email=row["email"],
    )


@router.post("/{token}/accept", response_model=AcceptedOut)
async def accept(
    token: str, user: Annotated[CurrentUser, Depends(current_user)]
) -> AcceptedOut:
    async with database.as_user(user.auth_user_id) as conn:
        row = await invitations_repo.accept(conn, token)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation isn't valid - it may have expired, already been "
            "used, or been sent to a different email address.",
        )
    return AcceptedOut(
        org_id=str(row["org_id"]),
        org_name=row["org_name"],
        org_slug=row["org_slug"],
        role=row["role"],
    )
