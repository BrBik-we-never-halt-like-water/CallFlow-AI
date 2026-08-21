"""channel_pin_and_order

Per-user pinning and manual ordering for chat conversations, plus a soft
delete for a channel itself.

**Why `channel_members` and not `channels`.** Pinning and ordering are one
person's view of their own list - pinning a channel must not move it for
every other member. `channel_members` is already the per-(channel, user)
row, already carries `org_id` for RLS, and is already the table a member's
own list is built from, so both columns belong there and neither needs a new
table.

**The max-3 pin rule is enforced here, not only in the client.** A partial
unique index would cap "one pin" but cannot express "at most three", so the
count is checked in a trigger. A UI-only cap is not a cap: any caller with a
token could pin twenty, and every client would then have to cope with a state
the product says is impossible.

**`sort_order` is a float, not an integer.** Dragging a row between two
neighbours then needs one UPDATE (the midpoint of the two) rather than
renumbering every row after it. `null` means "never manually placed" and
sorts by recency, so an untouched list behaves exactly as it does today.

**`channels.deleted_at`** is a soft delete: a channel's messages are a
record of what people said to each other, and a hard delete would take them
with it. The list filters on it, so a deleted channel disappears from every
member's list without the history being destroyed.

Revision ID: e5c9d02a7f31
Revises: c8a1f5d3b704
Created: 2026-08-20 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5c9d02a7f31"
down_revision: str | None = "c8a1f5d3b704"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_PINS = 3

# `SECURITY DEFINER` with a pinned `search_path`, the same shape every other
# RLS helper in this schema uses.
PIN_LIMIT_TRIGGER = f"""
create or replace function public.enforce_channel_pin_limit()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  pinned_count integer;
begin
  if new.pinned_at is null then
    return new;
  end if;

  select count(*) into pinned_count
  from public.channel_members
  where user_id = new.user_id
    and org_id = new.org_id
    and pinned_at is not null
    and channel_id <> new.channel_id;

  if pinned_count >= {MAX_PINS} then
    raise exception
      'You can pin up to {MAX_PINS} conversations. Unpin one first.'
      using errcode = 'check_violation';
  end if;

  return new;
end;
$$;
"""

CREATE_TRIGGER = """
create trigger channel_members_pin_limit
before insert or update of pinned_at on public.channel_members
for each row
execute function public.enforce_channel_pin_limit();
"""


def upgrade() -> None:
    op.add_column(
        "channel_members",
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "channel_members",
        sa.Column("sort_order", sa.Float(), nullable=True),
    )
    op.add_column(
        "channels",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # The list query orders by (pinned_at, sort_order, last activity) scoped to
    # one member, so that is the index.
    op.execute(
        "create index ix_channel_members_user_order "
        "on public.channel_members (user_id, org_id, pinned_at, sort_order)"
    )
    # Every list read filters deleted channels out.
    op.execute(
        "create index ix_channels_live on public.channels (org_id) "
        "where deleted_at is null"
    )

    op.execute(PIN_LIMIT_TRIGGER)
    op.execute(CREATE_TRIGGER)


def downgrade() -> None:
    op.execute("drop trigger if exists channel_members_pin_limit on public.channel_members")
    op.execute("drop function if exists public.enforce_channel_pin_limit()")
    op.execute("drop index if exists public.ix_channels_live")
    op.execute("drop index if exists public.ix_channel_members_user_order")
    op.drop_column("channels", "deleted_at")
    op.drop_column("channel_members", "sort_order")
    op.drop_column("channel_members", "pinned_at")
