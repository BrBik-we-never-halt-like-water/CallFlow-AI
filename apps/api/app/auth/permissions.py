"""What each role may do. One matrix, no scattered checks."""

from __future__ import annotations

import enum
from types import MappingProxyType

from app.database.models import OrgRole


class Permission(str, enum.Enum):
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"

    TEAM_READ = "team:read"
    TEAM_INVITE = "team:invite"
    TEAM_REMOVE = "team:remove"
    TEAM_SET_ROLE = "team:set_role"

    CAMPAIGNS_READ = "campaigns:read"
    CAMPAIGNS_WRITE = "campaigns:write"
    CAMPAIGNS_DELETE = "campaigns:delete"

    RUNS_READ = "runs:read"
    # Every run dials for real, so starting one at all is the consequential action.
    RUNS_START = "runs:start"

    CONTACTS_READ = "contacts:read"
    CONTACTS_WRITE = "contacts:write"
    # Unmasking a phone number. Deliberately not implied by contacts:read.
    CONTACTS_REVEAL = "contacts:reveal"

    SUPPRESSIONS_READ = "suppressions:read"
    SUPPRESSIONS_ADD = "suppressions:add"
    # Makes somebody who opted out callable again. Owners only.
    SUPPRESSIONS_REMOVE = "suppressions:remove"

    ESCALATIONS_READ = "escalations:read"
    ESCALATIONS_RESOLVE = "escalations:resolve"

    SAFETY_READ = "safety:read"
    SAFETY_WRITE = "safety:write"

    BILLING_READ = "billing:read"
    BILLING_WRITE = "billing:write"

    API_KEYS_READ = "api_keys:read"
    API_KEYS_WRITE = "api_keys:write"

    INTEGRATIONS_READ = "integrations:read"
    INTEGRATIONS_WRITE = "integrations:write"

    AUDIT_READ = "audit:read"


_READ_ONLY = frozenset(
    {
        Permission.ORG_READ,
        Permission.TEAM_READ,
        Permission.CAMPAIGNS_READ,
        Permission.RUNS_READ,
        Permission.CONTACTS_READ,
        Permission.SUPPRESSIONS_READ,
        Permission.ESCALATIONS_READ,
        Permission.SAFETY_READ,
    }
)

# An operator runs the product day to day: campaigns, runs, escalations. No
# billing, no team management, and no going live — that last one is an owner or
# admin decision because it spends the organisation's money.
_OPERATOR = _READ_ONLY | {
    Permission.CAMPAIGNS_WRITE,
    Permission.CAMPAIGNS_DELETE,
    Permission.RUNS_START,
    Permission.CONTACTS_WRITE,
    Permission.SUPPRESSIONS_ADD,
    Permission.ESCALATIONS_RESOLVE,
}

_ADMIN = _OPERATOR | {
    Permission.ORG_UPDATE,
    Permission.TEAM_INVITE,
    Permission.TEAM_REMOVE,
    Permission.TEAM_SET_ROLE,
    Permission.CONTACTS_REVEAL,
    Permission.SAFETY_WRITE,
    Permission.API_KEYS_READ,
    Permission.API_KEYS_WRITE,
    Permission.INTEGRATIONS_READ,
    Permission.INTEGRATIONS_WRITE,
    Permission.AUDIT_READ,
    Permission.BILLING_READ,
}

_OWNER = _ADMIN | {
    Permission.ORG_DELETE,
    Permission.BILLING_WRITE,
    Permission.SUPPRESSIONS_REMOVE,
}

ROLE_PERMISSIONS: MappingProxyType[OrgRole, frozenset[Permission]] = MappingProxyType(
    {
        OrgRole.VIEWER: _READ_ONLY,
        OrgRole.OPERATOR: frozenset(_OPERATOR),
        OrgRole.ADMIN: frozenset(_ADMIN),
        OrgRole.OWNER: frozenset(_OWNER),
    }
)


def permissions_for(role: OrgRole) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())


def role_has(role: OrgRole, permission: Permission) -> bool:
    return permission in permissions_for(role)
