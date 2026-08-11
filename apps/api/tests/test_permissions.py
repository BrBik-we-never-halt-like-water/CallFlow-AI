"""The role→permission matrix, and the role-hierarchy grant check.

`can_grant_role` is the fix for the admin-to-owner privilege-escalation hole:
holding `team:set_role`/`team:invite` (which Admin does, same as Owner) only
gates that a role can be changed at all, never which role. These tests pin
the actual rank rule - owner > admin > operator > viewer - independent of any
database, mirroring the pure-decision-function style CLAUDE.md asks for.
"""

from __future__ import annotations

import pytest

from app.auth.permissions import Permission, can_grant_role, role_has
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


@pytest.mark.parametrize("role", [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.VIEWER])
def test_owner_admin_and_viewer_can_read_the_team_breakdown(role: OrgRole) -> None:
    assert role_has(role, Permission.RUNS_READ_TEAM) is True


def test_operator_cannot_read_the_team_breakdown() -> None:
    """Their own runs are already covered by runs:read - `runs:read_team` is
    the org-wide chart RLS (`runs_select`, migration 202608092000) would
    otherwise silently return nothing for anyway."""
    assert role_has(OrgRole.OPERATOR, Permission.RUNS_READ_TEAM) is False


@pytest.mark.parametrize("role", [OrgRole.OWNER, OrgRole.ADMIN])
def test_owner_and_admin_can_assign_escalations(role: OrgRole) -> None:
    assert role_has(role, Permission.ESCALATIONS_ASSIGN) is True


@pytest.mark.parametrize("role", [OrgRole.OPERATOR, OrgRole.VIEWER])
def test_operator_and_viewer_cannot_assign_escalations(role: OrgRole) -> None:
    """Assigning who's responsible for something is heavier than resolving
    your own - operator keeps escalations:resolve (its own runs) without
    gaining the power to hand escalations to other teammates."""
    assert role_has(role, Permission.ESCALATIONS_ASSIGN) is False


@pytest.mark.parametrize("role", [OrgRole.OWNER, OrgRole.ADMIN])
def test_owner_and_admin_can_write_teammate_credits(role: OrgRole) -> None:
    assert role_has(role, Permission.CREDITS_WRITE) is True


@pytest.mark.parametrize("role", [OrgRole.OPERATOR, OrgRole.VIEWER])
def test_operator_and_viewer_cannot_write_teammate_credits(role: OrgRole) -> None:
    assert role_has(role, Permission.CREDITS_WRITE) is False


@pytest.mark.parametrize("role", [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.OPERATOR])
def test_owner_admin_and_operator_can_request_sharing(role: OrgRole) -> None:
    assert role_has(role, Permission.SHARING_REQUEST) is True


def test_viewer_cannot_request_sharing() -> None:
    """A read-only role has nothing to do with asking for someone else's
    resource - the same reasoning as every other viewer restriction."""
    assert role_has(OrgRole.VIEWER, Permission.SHARING_REQUEST) is False
