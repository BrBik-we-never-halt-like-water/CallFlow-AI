"""Platform-admin identity: orthogonal to `OrgRole`, and never inlined.

`docs/PLATFORM_ADMIN.md` §2. This is deliberately **not** in `permissions.py`: that
file maps `OrgRole -> Permission`, and an org role is scoped to one organisation by
definition, so a fifth value would be the wrong shape for an identity that spans
every organisation. `permissions.py` carries a comment saying so, because the next
reader's instinct is to "fix" the omission.

**The dependency is not the boundary.** Postgres grants function EXECUTE to PUBLIC
unless revoked, so any authenticated user can call `platform_set_org_entitlements`
directly over SQL. Every one of those functions re-checks the capability itself.
What this file adds is a 404 for anyone else, so a prober cannot learn the surface
exists - not the authorisation.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.auth.dependencies import CurrentUser, current_user
from app.database import database

log = logging.getLogger("callflow.platform")


class PlatformCapability(str, Enum):
    """Tiers for free, rather than a `platform_admins`/`super_admins` pair.

    `PII_REVEAL` is separate from `DATA_READ` on purpose: CLAUDE.md §4 #4 already
    makes revealing a full number a separate permissioned, audit-logged action, and
    the support surface does not get an exemption from a rule the product holds
    everywhere else. Most support work reads dispositions, errors and timings.
    """

    ORGS_READ = "orgs:read"
    DATA_READ = "data:read"
    PII_REVEAL = "pii:reveal"
    ENTITLEMENTS_WRITE = "entitlements:write"
    DATA_WRITE = "data:write"


class PlatformAdmin:
    """A resolved platform admin. Carries the org-scoped identity too, because the
    audit trail records a real person, not a capability set."""

    def __init__(self, user: CurrentUser, capabilities: frozenset[str]) -> None:
        self.user = user
        self.capabilities = capabilities

    @property
    def auth_user_id(self) -> UUID | str:
        return self.user.auth_user_id

    def can(self, capability: PlatformCapability) -> bool:
        return capability.value in self.capabilities


async def _capabilities_for(user: CurrentUser) -> frozenset[str]:
    """What this person holds right now, read fresh on every request.

    Never cached on the session: revoking a grant has to take effect immediately,
    the same reasoning `api_keys` re-reads its role from `memberships` rather than
    trusting the key row.

    Read through `as_user`, so an ordinary RLS-scoped connection is all this needs -
    `platform_admins` has no policies and no grant to `authenticated`, so the table
    is invisible from here. The capability is therefore asked for by name through
    the definer function rather than selected.
    """
    async with database.as_user(user.auth_user_id) as conn:
        rows = await conn.fetch(
            "select c from unnest($1::text[]) as c where public.platform_has_capability(c)",
            [c.value for c in PlatformCapability],
        )
    return frozenset(row["c"] for row in rows)


async def platform_admin(
    user: Annotated[CurrentUser, Depends(current_user)],
) -> PlatformAdmin:
    """Any platform admin, whatever their capabilities.

    404 rather than 403 for everyone else. A 403 confirms the route exists and that
    a privileged tier is behind it; a 404 tells a prober nothing at all. The same
    choice `internal.py` already makes for its unsigned callers.
    """
    capabilities = await _capabilities_for(user)
    if not capabilities:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")
    return PlatformAdmin(user, capabilities)


class RequirePlatformCapability:
    """Declared per route, never a role comparison inline in a handler.

    Mirrors `RequirePermission`'s shape so the two read the same way at a route
    definition, even though the identities behind them are unrelated.
    """

    def __init__(self, capability: PlatformCapability) -> None:
        self.capability = capability

    async def __call__(
        self, admin: Annotated[PlatformAdmin, Depends(platform_admin)]
    ) -> PlatformAdmin:
        if not admin.can(self.capability):
            # Also a 404. A platform admin holding `orgs:read` who probes the
            # entitlements endpoint should not learn that a higher tier exists
            # either - the capability set is issued out of band and is not
            # something the API enumerates.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Not found."
            )
        return admin


async def is_platform_admin(user: CurrentUser) -> bool:
    """For `GET /api/v1/me`, so the interface can render a Platform entry.

    Display only. It grants nothing: every platform route resolves the capability
    again, and the definer functions re-check it a third time in the database.
    """
    return bool(await _capabilities_for(user))
