"""Internal team chat: channels (and DMs) between teammates in one organisation.
Not contact-facing SMS/WhatsApp - see RUNBOOK_JATIN_PART_3.md."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser, RequirePermission
from app.auth.permissions import Permission
from app.database import database
from app.database.repositories import channels as channels_repo
from app.database.repositories import messages as messages_repo

router = APIRouter(prefix="/api/v1", tags=["chat"])


class ChannelIn(BaseModel):
    kind: Literal["channel", "dm"]
    name: str | None = None
    member_ids: list[UUID] = Field(default_factory=list)


class ChannelOut(BaseModel):
    id: UUID
    kind: Literal["channel", "dm"]
    name: str | None
    created_by: UUID | None
    member_ids: list[UUID]
    unread_count: int
    created_at: datetime


class ChannelRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AddMemberIn(BaseModel):
    user_id: UUID


class UnreadCountOut(BaseModel):
    unread_count: int


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageOut(BaseModel):
    id: UUID
    channel_id: UUID
    sender_id: UUID | None
    sender_name: str | None
    body: str
    created_at: datetime
    edited_at: datetime | None


def _channel_json(row: object) -> ChannelOut:
    return ChannelOut(
        id=row["id"],
        kind=row["kind"],
        name=row["name"],
        created_by=row["created_by"],
        member_ids=list(row["member_ids"]),
        unread_count=row["unread_count"],
        created_at=row["created_at"],
    )


def _message_json(row: object) -> MessageOut:
    return MessageOut(
        id=row["id"],
        channel_id=row["channel_id"],
        sender_id=row["sender_id"],
        sender_name=row["sender_name"],
        body=row["body"],
        created_at=row["created_at"],
        edited_at=row["edited_at"],
    )


async def _get_channel_or_404(conn: object, channel_id: UUID) -> object:
    """Shared by every `{channel_id}`-scoped route: RLS (`channels_select`)
    already hides a channel the caller isn't a member of - this just turns
    that into an explicit 404 instead of each route silently no-op-ing, which
    matters most for a channel id reached directly by URL (RUNBOOK's
    conversation-URL requirement) rather than clicked from the caller's own
    list."""
    row = await channels_repo.get_channel(conn, channel_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found.")
    return row


@router.get("/channels", response_model=list[ChannelOut])
async def list_channels(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_READ))],
) -> list[ChannelOut]:
    async with database.as_user(user.auth_user_id) as conn:
        rows = await channels_repo.list_my_channels(conn, user.org_id)
    return [_channel_json(r) for r in rows]


@router.post("/channels", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    body: ChannelIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_SEND))],
) -> ChannelOut:
    if body.kind == "channel" and not (body.name and body.name.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A channel needs a name. DMs don't - leave name blank for those.",
        )
    name = body.name.strip() if body.kind == "channel" and body.name else None

    async with database.as_user(user.auth_user_id) as conn:
        try:
            channel_id = await channels_repo.create_channel(
                conn,
                org_id=user.org_id,
                kind=body.kind,
                name=name,
                member_ids=body.member_ids,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        row = await channels_repo.get_channel(conn, channel_id)
    return _channel_json(row)


# Registered ahead of `/channels/{channel_id}` - a literal segment has to win
# over the UUID-typed path param, or `channel_id: UUID` would reject
# "unread-count" with a 422 before this route is ever considered.
@router.get("/channels/unread-count", response_model=UnreadCountOut)
async def get_unread_count(
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_READ))],
) -> UnreadCountOut:
    """The nav badge's total. Deliberately its own cheap aggregate, not `sum(c.unread_count
    for c in list_channels())` - see `channels_repo.total_unread_count()` for why that
    matters: this hits every browser tab in the organisation on every chat Realtime event."""
    async with database.as_user(user.auth_user_id) as conn:
        count = await channels_repo.total_unread_count(conn, user.org_id)
    return UnreadCountOut(unread_count=count)


@router.get("/channels/{channel_id}", response_model=ChannelOut)
async def get_channel(
    channel_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_READ))],
) -> ChannelOut:
    """Resolves a conversation reached directly by URL (`/app/chat/{id}`) - a
    channel id from another organisation, or one in this org the caller isn't
    a member of, both come back as a plain 404 via RLS, never a peek at
    whether the id exists."""
    async with database.as_user(user.auth_user_id) as conn:
        row = await _get_channel_or_404(conn, channel_id)
    return _channel_json(row)


@router.patch("/channels/{channel_id}", response_model=ChannelOut)
async def rename_channel(
    channel_id: UUID,
    body: ChannelRenameIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_SEND))],
) -> ChannelOut:
    """Who may rename: the channel's creator, or an org owner/admin - enforced
    by `channels_update`'s RLS policy, not re-checked here. This permission
    dependency only gates that the caller can use chat at all (operator+);
    the specific per-channel authorization is the database's job, the same
    division `campaigns`/`runs` already use."""
    async with database.as_user(user.auth_user_id) as conn:
        existing = await _get_channel_or_404(conn, channel_id)
        if existing["kind"] == "dm":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A direct message can't be renamed.",
            )
        updated = await channels_repo.rename_channel(
            conn, channel_id=channel_id, name=body.name.strip()
        )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only this channel's creator or an org owner/admin can rename it.",
        )
    return ChannelOut(
        id=updated["id"],
        kind=updated["kind"],
        name=updated["name"],
        created_by=updated["created_by"],
        member_ids=list(existing["member_ids"]),
        unread_count=existing["unread_count"],
        created_at=updated["created_at"],
    )


@router.post("/channels/{channel_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    channel_id: UUID,
    body: AddMemberIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_SEND))],
) -> None:
    """Who may add: any existing member of the channel, adding any other
    member of the *same organisation* - both enforced by
    `channel_members_insert`'s RLS (`is_channel_member` for the caller,
    `is_user_org_member` for the target), not re-checked here."""
    async with database.as_user(user.auth_user_id) as conn:
        ok = await channels_repo.add_member(
            conn, org_id=user.org_id, channel_id=channel_id, user_id=body.user_id
        )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Couldn't add that person - you may not be a member of this channel, "
                "or they may not be a member of your organisation."
            ),
        )


@router.delete("/channels/{channel_id}/members/{member_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    channel_id: UUID,
    member_user_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_READ))],
) -> None:
    """Gated on `MESSAGES_READ` (every role), not `MESSAGES_SEND` - leaving a
    channel you're in has to work for a viewer too. Who may remove *someone
    else*: the channel's creator, or an org owner/admin - `channel_members_delete`'s
    job, not this route's."""
    async with database.as_user(user.auth_user_id) as conn:
        removed = await channels_repo.remove_member(
            conn, channel_id=channel_id, user_id=member_user_id
        )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove yourself, or a member of a channel you created or moderate.",
        )


@router.post("/channels/{channel_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    channel_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_READ))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        await channels_repo.mark_read(conn, channel_id=channel_id, user_id=user.id)


@router.get("/channels/{channel_id}/messages", response_model=list[MessageOut])
async def list_messages(
    channel_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_READ))],
    before: Annotated[datetime | None, Query()] = None,
    before_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=messages_repo.MAX_PAGE_SIZE)] = (
        messages_repo.DEFAULT_PAGE_SIZE
    ),
) -> list[MessageOut]:
    # RLS (`messages_select`) narrows this to nothing if the caller isn't a
    # member of `channel_id` - it isn't re-checked here, the same way
    # `campaigns_select` is trusted rather than re-verified in the route.
    async with database.as_user(user.auth_user_id) as conn:
        rows = await messages_repo.list_messages(
            conn, channel_id, before=before, before_id=before_id, limit=limit
        )
    return [_message_json(r) for r in rows]


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    channel_id: UUID,
    body: MessageIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_SEND))],
) -> MessageOut:
    async with database.as_user(user.auth_user_id) as conn:
        row = await messages_repo.send_message(
            conn,
            org_id=user.org_id,
            channel_id=channel_id,
            sender_id=user.id,
            body=body.body.strip(),
        )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You aren't a member of this channel.",
        )
    return MessageOut(
        id=row["id"],
        channel_id=row["channel_id"],
        sender_id=row["sender_id"],
        sender_name=user.name,
        body=row["body"],
        created_at=row["created_at"],
        edited_at=row["edited_at"],
    )


@router.patch("/channels/{channel_id}/messages/{message_id}", response_model=MessageOut)
async def edit_message(
    channel_id: UUID,
    message_id: UUID,
    body: MessageIn,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_SEND))],
) -> MessageOut:
    """Who may edit: the sender, and only the sender - `messages_update`'s
    `USING (sender_id = current_user_id())`, not re-checked here."""
    async with database.as_user(user.auth_user_id) as conn:
        row = await messages_repo.edit_message(
            conn, message_id=message_id, sender_id=user.id, body=body.body.strip()
        )
    if row is None or row["channel_id"] != channel_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own messages.",
        )
    # edit_message()'s UPDATE ... RETURNING has no join to users, unlike
    # list_messages() - same reason send_message() builds MessageOut by hand
    # instead of calling _message_json(): the editor is always the sender, so
    # the caller's own name (already on `user`) is right here without one.
    return MessageOut(
        id=row["id"],
        channel_id=row["channel_id"],
        sender_id=row["sender_id"],
        sender_name=user.name,
        body=row["body"],
        created_at=row["created_at"],
        edited_at=row["edited_at"],
    )


@router.delete(
    "/channels/{channel_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_message(
    channel_id: UUID,
    message_id: UUID,
    user: Annotated[CurrentUser, Depends(RequirePermission(Permission.MESSAGES_SEND))],
) -> None:
    async with database.as_user(user.auth_user_id) as conn:
        deleted = await messages_repo.delete_message(
            conn, message_id=message_id, sender_id=user.id
        )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own messages.",
        )
