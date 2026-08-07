"""Who the signed-in user is, and letting them edit it."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, current_user
from app.database import database
from app.database.repositories import users as users_repo

router = APIRouter(prefix="/api/v1", tags=["profile"])


class MembershipOut(BaseModel):
    org_id: str
    org_name: str
    org_slug: str
    org_logo_url: str | None
    # Null means the org still has its auto-generated placeholder name — the
    # dashboard gates on this to force the first-run org setup screen.
    onboarded_at: datetime | None
    plan_id: str
    role: str


class MeOut(BaseModel):
    """The signed-in user, their active organisation, and what they may do."""

    user_id: str
    email: str
    name: str | None
    avatar_url: str | None
    active: MembershipOut
    permissions: list[str]


class ProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = None


class ProfileOut(BaseModel):
    user_id: str
    email: str
    name: str | None
    avatar_url: str | None


@router.get("/me", response_model=MeOut)
async def me(user: Annotated[CurrentUser, Depends(current_user)]) -> MeOut:
    """The web client calls this after sign-in to hydrate its session."""
    return MeOut(
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        active=MembershipOut(
            org_id=str(user.org_id),
            org_name=user.org_name,
            org_slug=user.org_slug,
            org_logo_url=user.org_logo_url,
            onboarded_at=user.org_onboarded_at,
            plan_id=user.org_plan_id,
            role=user.role.value,
        ),
        # Sent so the client can disable actions the role cannot perform, rather
        # than letting someone click through to a 403.
        permissions=sorted(p.value for p in user.permissions),
    )


@router.patch("/me", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdateIn, user: Annotated[CurrentUser, Depends(current_user)]
) -> ProfileOut:
    async with database.as_user(user.auth_user_id) as conn:
        row = await users_repo.update_profile(
            conn, name=body.name, avatar_url=body.avatar_url
        )
    return ProfileOut(
        user_id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
    )
