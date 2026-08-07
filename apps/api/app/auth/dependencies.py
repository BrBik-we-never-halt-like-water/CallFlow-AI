"""Resolving a request to an identity, an organisation, and a role."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.auth.permissions import Permission, permissions_for, role_has
from app.auth.tokens import InvalidToken, TokenClaims, token_verifier
from app.database import database
from app.database.models import OrgRole
from app.domain.api_keys import hash_api_key, looks_like_api_key

# Sent by the web client when a user belongs to more than one organisation.
ORG_HEADER = "X-Org-Id"


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, scoped to one organisation.

    `id` is `public.users.id`. `auth_user_id` is the provider's id and exists only
    so the database layer can install the JWT claims that RLS reads — application
    code should use `id`.
    """

    id: UUID
    auth_user_id: str
    email: str
    name: str | None
    avatar_url: str | None
    org_id: UUID
    org_name: str
    org_slug: str
    org_logo_url: str | None
    org_onboarded_at: datetime | None
    org_plan_id: str
    role: OrgRole

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.role)

    def can(self, permission: Permission) -> bool:
        return role_has(self.role, permission)


def _unauthorised(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise _unauthorised("Sign in to continue.")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorised("Expected an Authorization header of the form 'Bearer <token>'.")
    return token.strip()


async def current_user(
    authorization: Annotated[str | None, Header()] = None,
    x_org_id: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Resolve the bearer token to a user and one of their organisations.

    Two kinds of bearer token are accepted: a Supabase access token (the web
    client, always) or a CallFlow API key (`cfk_...`, programmatic access —
    Settings → API keys). They resolve through different queries but produce the
    same `CurrentUser`, so everything downstream — permissions, RLS, routes —
    is identical either way.
    """
    token = _bearer_token(authorization)

    if looks_like_api_key(token):
        return await _resolve_api_key(token)

    try:
        claims = token_verifier.verify(token)
    except InvalidToken as exc:
        # The specific reason is logged upstream; the client is told to sign in
        # again rather than which check failed.
        raise _unauthorised(str(exc)) from exc

    return await _resolve_supabase_session(claims, x_org_id)


async def _resolve_supabase_session(
    claims: TokenClaims, x_org_id: str | None
) -> CurrentUser:
    """The web client's path: a Supabase session, scoped to a chosen organisation.

    The lookup runs through the RLS-scoped connection rather than a privileged one:
    the policies already let a user see themselves and their own memberships, so if
    this query returns nothing the caller genuinely has no access — which is the
    answer we want rather than one we have to remember to check.
    """
    requested_org = _parse_org_header(x_org_id)

    async with database.as_user(claims.auth_user_id) as connection:
        row = await connection.fetchrow(
            """
            select u.id            as user_id,
                   u.email         as email,
                   u.name          as name,
                   u.avatar_url    as avatar_url,
                   o.id            as org_id,
                   o.name          as org_name,
                   o.slug          as org_slug,
                   o.logo_url      as org_logo_url,
                   o.onboarded_at  as org_onboarded_at,
                   o.plan_id       as org_plan_id,
                   m.role          as role
            from public.users u
            join public.memberships m on m.user_id = u.id
            join public.organisations o on o.id = m.org_id
            where u.auth_user_id = $1
              and o.deleted_at is null
              and ($2::uuid is null or o.id = $2::uuid)
            -- Deterministic default when no org is requested: the earliest joined,
            -- so a user without an org switcher always lands in the same place.
            order by m.joined_at
            limit 1
            """,
            claims.auth_user_id,
            requested_org,
        )

    if row is None:
        if requested_org is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of that organisation.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not attached to an organisation yet.",
        )

    return CurrentUser(
        id=row["user_id"],
        auth_user_id=claims.auth_user_id,
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
        org_id=row["org_id"],
        org_name=row["org_name"],
        org_slug=row["org_slug"],
        org_logo_url=row["org_logo_url"],
        org_onboarded_at=row["org_onboarded_at"],
        org_plan_id=row["org_plan_id"],
        role=OrgRole(row["role"]),
    )


async def _resolve_api_key(token: str) -> CurrentUser:
    """An API key's path: no Supabase session at all, so a no-identity connection
    is what resolves it — the same shape as the public invitation-preview lookup.

    The key is permanently bound to the organisation and user it was created
    under, but the *role* is re-checked live on every call (`resolve_api_key()`
    joins `memberships` fresh rather than caching a role on the key row), so
    removing someone or changing their role takes effect on their keys
    immediately rather than on their next sign-in.
    """
    async with database.anonymous() as connection:
        row = await connection.fetchrow(
            "select * from public.resolve_api_key($1)", hash_api_key(token)
        )

    if row is None:
        raise _unauthorised("That API key isn't valid. It may have been revoked.")

    return CurrentUser(
        id=row["user_id"],
        auth_user_id=str(row["auth_user_id"]),
        email=row["email"],
        name=row["name"],
        avatar_url=row["avatar_url"],
        org_id=row["org_id"],
        org_name=row["org_name"],
        org_slug=row["org_slug"],
        org_logo_url=row["org_logo_url"],
        org_onboarded_at=row["org_onboarded_at"],
        org_plan_id=row["org_plan_id"],
        role=OrgRole(row["role"]),
    )


def _parse_org_header(raw: str | None) -> UUID | None:
    if not raw or not raw.strip():
        return None
    try:
        return UUID(raw.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{ORG_HEADER} must be a UUID.",
        ) from exc


class RequirePermission:
    """Dependency factory guarding an endpoint with one permission.

    Usage:
        @router.post("/campaigns",
                     dependencies=[Depends(RequirePermission(Permission.CAMPAIGNS_WRITE))])

    The message names the role that would be allowed, because "not permitted" leaves
    the user with nothing to act on.
    """

    def __init__(self, permission: Permission) -> None:
        self._permission = permission

    async def __call__(
        self, user: Annotated[CurrentUser, Depends(current_user)]
    ) -> CurrentUser:
        if not user.can(self._permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Your role ({user.role.value}) cannot do this. "
                    f"It requires the {self._permission.value} permission — "
                    "ask an owner or admin in your organisation."
                ),
            )
        return user


CurrentUserDep = Annotated[CurrentUser, Depends(current_user)]
