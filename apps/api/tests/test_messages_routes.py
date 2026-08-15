"""`edit_message`'s route, exercised directly - not through the RLS suite,
because the bug this pins lived entirely in the route layer.

`messages_repo.edit_message()`'s `UPDATE ... RETURNING` has no join to
`users` (unlike `list_messages()`), so its Record never carries `sender_name`
- the route building its response with `_message_json()` (written for
`list_messages()`'s rows) raised `KeyError: 'sender_name'` on every real edit,
a 500 caught only by driving the live API end to end, not by any of the
repo-level or RLS tests already covering `edit_message()`. `send_message()`'s
route already avoided this by building `MessageOut` from `user.name` instead
of calling `_message_json()`; `edit_message()` now does the same.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.v1.routes import messages
from app.auth.dependencies import CurrentUser
from app.database.models import OrgRole


def _current_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        auth_user_id=str(uuid.uuid4()),
        email="sender@example.com",
        name="Real Sender",
        avatar_url=None,
        org_id=uuid.uuid4(),
        org_name="Acme",
        org_slug="acme",
        org_logo_url=None,
        org_onboarded_at=datetime.now(UTC),
        org_plan_id="free",
        role=OrgRole.OPERATOR,
    )


@asynccontextmanager
async def _fake_as_user(auth_user_id: str) -> Any:
    yield object()


async def test_edit_message_route_does_not_need_sender_name_from_the_repo(
    monkeypatch,
) -> None:
    user = _current_user()
    channel_id = uuid.uuid4()
    message_id = uuid.uuid4()

    monkeypatch.setattr(messages.database, "as_user", _fake_as_user)
    monkeypatch.setattr(
        messages.messages_repo,
        "edit_message",
        AsyncMock(
            return_value={
                "id": message_id,
                "channel_id": channel_id,
                "sender_id": user.id,
                "body": "edited for real",
                "created_at": datetime.now(UTC),
                "edited_at": datetime.now(UTC),
                # Deliberately no "sender_name" key - the real repo Record
                # never has one either.
            }
        ),
    )

    result = await messages.edit_message(
        channel_id, message_id, messages.MessageIn(body="edited for real"), user
    )

    assert result.body == "edited for real"
    assert result.sender_name == user.name


async def test_create_channel_route_turns_a_repo_value_error_into_a_clean_400(
    monkeypatch,
) -> None:
    """Regression for the audit's finding: `create_channel()`'s own validation
    (a member id from another organisation, a malformed dm) used to reach the
    route as a raw, uncaught `asyncpg` error and 500. The repository now
    converts that into `ValueError` (`channels_repo.create_channel()`); this
    pins that the route in turn converts it into a 400, not a 500."""
    user = _current_user()

    monkeypatch.setattr(messages.database, "as_user", _fake_as_user)
    monkeypatch.setattr(
        messages.channels_repo,
        "create_channel",
        AsyncMock(side_effect=ValueError("one or more member_ids are not members of this organisation")),
    )

    with pytest.raises(HTTPException) as exc_info:
        await messages.create_channel(
            messages.ChannelIn(kind="channel", name="cross-org", member_ids=[uuid.uuid4()]), user
        )

    assert exc_info.value.status_code == 400
    assert "not members of this organisation" in exc_info.value.detail


async def test_get_unread_count_route_returns_the_repositorys_value(monkeypatch) -> None:
    """A dedicated, cheap endpoint - not derived from `list_channels()` - so
    this just has to prove the route hands back whatever the repository
    computed, unmodified."""
    user = _current_user()

    monkeypatch.setattr(messages.database, "as_user", _fake_as_user)
    monkeypatch.setattr(
        messages.channels_repo, "total_unread_count", AsyncMock(return_value=7)
    )

    result = await messages.get_unread_count(user)

    assert result.unread_count == 7
