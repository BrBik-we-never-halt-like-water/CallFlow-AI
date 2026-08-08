"""The admin-to-owner privilege-escalation fix, exercised through the real
route handlers rather than through the permission matrix.

`Permission.TEAM_SET_ROLE`/`TEAM_INVITE`/`TEAM_REMOVE` alone would say an
Admin may call any of these endpoints — Admin holds all three, same as Owner.
That was never the bug: the bug is that none of them checked *which* role was
being granted (`_ensure_can_grant`) or *whose* row was being touched
(`_ensure_can_act_on`), so an Admin could set their own role to `owner`,
invite a new email straight into `owner`, or demote/remove an existing Owner
in a multi-owner org. These tests call `organisations.set_member_role`,
`organisations.invite`, and `organisations.remove_member` directly — the
actual FastAPI path functions FastAPI would dispatch to, not a
re-implementation of either check — and assert the 403, per the brief's
requirement to hit the real behaviour rather than just ask
`role_has()`/`permissions_for()` whether Admin holds the permission (it does;
that was never in question).

Every denial below fires before the DB write itself runs (`_ensure_can_grant`
and `_ensure_can_act_on` both run ahead of the mutating call in the route),
which is why these tests need no live database — see
`tests/test_rls_isolation.py` for the matching defense-in-depth proof at the
RLS layer, which does need one. The non-regression cases prove Admin's
existing, legitimate actions (grants to/removal of operator/viewer, and
self-service) and Owner's full range still work — these are hierarchy fixes,
not permission removals — by stubbing only the DB/email I/O, never either
hierarchy check itself.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.routes import organisations
from app.auth.dependencies import CurrentUser
from app.database.models import OrgRole


def _current_user(role: OrgRole) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        auth_user_id=str(uuid.uuid4()),
        email="caller@example.com",
        name="Caller",
        avatar_url=None,
        org_id=uuid.uuid4(),
        org_name="Acme",
        org_slug="acme",
        org_logo_url=None,
        org_onboarded_at=datetime.now(UTC),
        org_plan_id="free",
        role=role,
    )


@asynccontextmanager
async def _fake_as_user(auth_user_id: str) -> Any:
    yield object()


def _forbid_db_access(monkeypatch: pytest.MonkeyPatch, *, what: str) -> None:
    """Fails loudly if the route reaches the database — proof the 403 is the
    *reason* nothing was written, not a coincidence of a missing connection."""

    @asynccontextmanager
    async def _fail(_auth_user_id: str) -> Any:
        raise AssertionError(f"reached the database — the hierarchy check did not block {what}")
        yield  # pragma: no cover - unreachable, keeps this an async generator

    monkeypatch.setattr(organisations.database, "as_user", _fail)


def _stub_db(monkeypatch: pytest.MonkeyPatch, *, current_role: str | None) -> AsyncMock:
    """Wires a fake connection plus a `get_member_role` stub returning
    `current_role` (the value `_ensure_can_act_on` is checked against), and
    returns the `set_member_role`/`remove_member` mock so the caller can
    assert on it. `current_role=None` mirrors "not a member" — the same as a
    self-targeted call, which never even reaches `get_member_role`."""
    monkeypatch.setattr(organisations.database, "as_user", _fake_as_user)
    monkeypatch.setattr(
        organisations.org_repo, "get_member_role", AsyncMock(return_value=current_role)
    )
    mutate = AsyncMock()
    return mutate


class _FakeEmailGateway:
    async def send_invitation(self, **_kwargs: Any) -> None:
        return None


# --- Denials: the granted-role escalation path from the audit --------------


@pytest.mark.parametrize("target_role", ["owner", "admin"])
async def test_admin_cannot_set_a_members_role_to_owner_or_admin(
    target_role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_db_access(monkeypatch, what="this role change")
    admin = _current_user(OrgRole.ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await organisations.set_member_role(
            member_user_id=uuid.uuid4(),
            body=organisations.RoleUpdateIn(role=target_role),
            user=admin,
        )
    assert exc_info.value.status_code == 403


async def test_admin_cannot_self_promote_to_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact takeover path from the audit: Admin targets *their own* row."""
    _forbid_db_access(monkeypatch, what="self-promotion")
    admin = _current_user(OrgRole.ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await organisations.set_member_role(
            member_user_id=admin.id,
            body=organisations.RoleUpdateIn(role="owner"),
            user=admin,
        )
    assert exc_info.value.status_code == 403


@pytest.mark.parametrize("target_role", ["owner", "admin"])
async def test_admin_cannot_invite_someone_as_owner_or_admin(
    target_role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    _forbid_db_access(monkeypatch, what="this invite")
    admin = _current_user(OrgRole.ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await organisations.invite(
            body=organisations.InviteIn(email="new-hire@example.com", role=target_role),
            user=admin,
        )
    assert exc_info.value.status_code == 403


# --- Denials: the target-role escalation path (Admin acting on an existing
# Owner or peer Admin's row) -------------------------------------------------


@pytest.mark.parametrize("current_role", ["owner", "admin"])
async def test_admin_cannot_change_the_role_of_an_owner_or_admin_member(
    current_role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        organisations.org_repo, "get_member_role", AsyncMock(return_value=current_role)
    )
    set_role = AsyncMock()
    monkeypatch.setattr(organisations.org_repo, "set_member_role", set_role)
    monkeypatch.setattr(organisations.database, "as_user", _fake_as_user)
    admin = _current_user(OrgRole.ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await organisations.set_member_role(
            member_user_id=uuid.uuid4(),
            body=organisations.RoleUpdateIn(role="viewer"),
            user=admin,
        )
    assert exc_info.value.status_code == 403
    set_role.assert_not_awaited()


@pytest.mark.parametrize("current_role", ["owner", "admin"])
async def test_admin_cannot_remove_an_owner_or_admin_member(
    current_role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        organisations.org_repo, "get_member_role", AsyncMock(return_value=current_role)
    )
    remove = AsyncMock()
    monkeypatch.setattr(organisations.org_repo, "remove_member", remove)
    monkeypatch.setattr(organisations.database, "as_user", _fake_as_user)
    admin = _current_user(OrgRole.ADMIN)

    with pytest.raises(HTTPException) as exc_info:
        await organisations.remove_member(member_user_id=uuid.uuid4(), user=admin)
    assert exc_info.value.status_code == 403
    remove.assert_not_awaited()


# --- Non-regression: Admin's real grants/actions, and Owner's full range,
# still work ------------------------------------------------------------------


@pytest.mark.parametrize("target_role", ["operator", "viewer"])
async def test_admin_can_still_set_a_members_role_to_operator_or_viewer(
    target_role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_role = _stub_db(monkeypatch, current_role="viewer")
    monkeypatch.setattr(organisations.org_repo, "set_member_role", set_role)
    admin = _current_user(OrgRole.ADMIN)

    await organisations.set_member_role(
        member_user_id=uuid.uuid4(),
        body=organisations.RoleUpdateIn(role=target_role),
        user=admin,
    )

    set_role.assert_awaited_once()
    assert set_role.await_args.args[-1] == target_role


async def test_admin_can_still_remove_an_operator_or_viewer(monkeypatch: pytest.MonkeyPatch) -> None:
    remove = _stub_db(monkeypatch, current_role="operator")
    monkeypatch.setattr(organisations.org_repo, "remove_member", remove)
    admin = _current_user(OrgRole.ADMIN)

    await organisations.remove_member(member_user_id=uuid.uuid4(), user=admin)

    remove.assert_awaited_once()


async def test_admin_can_still_step_themselves_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Self-targeting skips `_ensure_can_act_on` entirely — confirmed here by
    never stubbing `get_member_role` at all; a call would be an AttributeError
    on the fake connection, so this also proves the route never reaches it."""
    monkeypatch.setattr(organisations.database, "as_user", _fake_as_user)
    set_role = AsyncMock()
    monkeypatch.setattr(organisations.org_repo, "set_member_role", set_role)
    admin = _current_user(OrgRole.ADMIN)

    await organisations.set_member_role(
        member_user_id=admin.id,
        body=organisations.RoleUpdateIn(role="viewer"),
        user=admin,
    )

    set_role.assert_awaited_once()
    assert set_role.await_args.args[-1] == "viewer"


async def test_removing_yourself_needs_no_permission_and_skips_the_act_on_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(organisations.database, "as_user", _fake_as_user)
    remove = AsyncMock()
    monkeypatch.setattr(organisations.org_repo, "remove_member", remove)
    # A viewer holds neither team:remove nor team:set_role — leaving is still allowed.
    viewer = _current_user(OrgRole.VIEWER)

    await organisations.remove_member(member_user_id=viewer.id, user=viewer)

    remove.assert_awaited_once()


@pytest.mark.parametrize("target_role", ["operator", "viewer"])
async def test_admin_can_still_invite_as_operator_or_viewer(
    target_role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(organisations.database, "as_user", _fake_as_user)
    create_invitation = AsyncMock(
        return_value={
            "id": uuid.uuid4(),
            "email": "new-hire@example.com",
            "role": target_role,
            "expires_at": datetime.now(UTC),
            "created_at": datetime.now(UTC),
        }
    )
    monkeypatch.setattr(organisations.org_repo, "create_invitation", create_invitation)
    monkeypatch.setattr(organisations, "EmailGateway", _FakeEmailGateway)
    admin = _current_user(OrgRole.ADMIN)

    result = await organisations.invite(
        body=organisations.InviteIn(email="new-hire@example.com", role=target_role),
        user=admin,
    )

    assert result.role == target_role
    assert create_invitation.await_args.kwargs["role"] == target_role


async def test_owner_can_grant_owner_or_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    """Owner's own existing ability to promote is untouched by this fix."""
    set_role = _stub_db(monkeypatch, current_role="admin")
    monkeypatch.setattr(organisations.org_repo, "set_member_role", set_role)
    owner = _current_user(OrgRole.OWNER)

    await organisations.set_member_role(
        member_user_id=uuid.uuid4(),
        body=organisations.RoleUpdateIn(role="owner"),
        user=owner,
    )

    set_role.assert_awaited_once()
    assert set_role.await_args.args[-1] == "owner"


async def test_owner_can_still_remove_another_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    remove = _stub_db(monkeypatch, current_role="owner")
    monkeypatch.setattr(organisations.org_repo, "remove_member", remove)
    owner = _current_user(OrgRole.OWNER)

    await organisations.remove_member(member_user_id=uuid.uuid4(), user=owner)

    remove.assert_awaited_once()
