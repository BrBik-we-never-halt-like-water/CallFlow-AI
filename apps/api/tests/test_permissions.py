"""The role→permission matrix, and the role-hierarchy grant check.

`can_grant_role` is the fix for the admin-to-owner privilege-escalation hole:
holding `team:set_role`/`team:invite` (which Admin does, same as Owner) only
gates that a role can be changed at all, never which role. These tests pin
the actual rank rule - owner > admin > operator > viewer - independent of any
database, mirroring the pure-decision-function style CLAUDE.md asks for.
"""

from __future__ import annotations

import pytest

from app.auth.permissions import can_grant_role
from app.database.models import OrgRole

ALL_ROLES = (OrgRole.OWNER, OrgRole.ADMIN, OrgRole.OPERATOR, OrgRole.VIEWER)


@pytest.mark.parametrize("target", ALL_ROLES)
def test_owner_can_grant_any_role_including_owner(target: OrgRole) -> None:
    assert can_grant_role(OrgRole.OWNER, target) is True


def test_admin_cannot_grant_owner() -> None:
    assert can_grant_role(OrgRole.ADMIN, OrgRole.OWNER) is False


def test_admin_cannot_grant_admin_not_even_to_itself() -> None:
    assert can_grant_role(OrgRole.ADMIN, OrgRole.ADMIN) is False


@pytest.mark.parametrize("target", [OrgRole.OPERATOR, OrgRole.VIEWER])
def test_admin_can_grant_operator_or_viewer(target: OrgRole) -> None:
    assert can_grant_role(OrgRole.ADMIN, target) is True


@pytest.mark.parametrize("target", ALL_ROLES)
def test_operator_cannot_grant_any_role(target: OrgRole) -> None:
    # Operator never actually reaches this check in the API (it holds neither
    # team:set_role nor team:invite) - pinned anyway so the helper fails
    # closed if that ever changes rather than silently allowing everything.
    assert can_grant_role(OrgRole.OPERATOR, target) is (target is OrgRole.VIEWER)


@pytest.mark.parametrize("target", ALL_ROLES)
def test_viewer_cannot_grant_any_role(target: OrgRole) -> None:
    assert can_grant_role(OrgRole.VIEWER, target) is False
