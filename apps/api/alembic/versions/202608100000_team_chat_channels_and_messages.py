"""team_chat_channels_and_messages

Internal team chat (RUNBOOK_JATIN_PART_3.md): channels, channel_members, messages.
No overlap with any other tenant table - own tables, own RLS, own SECURITY DEFINER
functions, following the exact patterns already established in this repo rather
than reinventing them.

This single migration is a consolidation of what was originally five, written and
applied incrementally across three build/audit rounds while the feature and its
security boundary were still being worked out - each is described in `ISSUES.md`
(iterations 24-28, #83-#89) as the historical record of what was found and fixed
when. None of the five had shipped anywhere outside this development environment,
so folding them into one, in their final, correct form, leaves nothing to migrate
*through* - only the end state to create. What follows is that end state:

- `is_channel_member`/`channel_org_id` are `SECURITY DEFINER`, `search_path`-pinned
  helpers in the same style as `is_org_member`/`has_org_role`
  (`202608060050_initial_schema.py`) - a policy on `channel_members` that queried
  `channel_members` directly would recurse infinitely, so the check goes through a
  definer function that bypasses RLS and breaks the cycle.
- `create_channel()` is the same shape as `create_organisation()`
  (`202608072000_organisation_create_function.py`): a plain client-side insert into
  `channels` followed by a separate insert into `channel_members` would hit the same
  `RETURNING`-before-membership-exists race that migration documents - at the moment
  `channels`' own insert tries to `RETURNING` its new row, `channels_select`'s
  membership check is evaluated, and no `channel_members` row exists yet to satisfy
  it. Doing both inserts atomically inside a `SECURITY DEFINER` function is the fix.
  For a `dm`, the function is also idempotent and race-safe: `channels.dm_pair` (a
  sorted 2-element array of the two members) plus a partial unique index means
  starting a DM with the same person twice - even from two concurrent requests -
  converges on the same channel rather than creating a duplicate, and a `dm` is
  validated as exactly one other member, never the caller's own id.
- Every policy that authorises off `is_channel_member(...)` or
  `channel_created_by(...)` also requires `is_org_member(...)` (or, for the row
  being inserted/added rather than the caller, `is_user_org_member(...)`) alongside
  it. A `channel_members` row or a `created_by` value is proof someone was *once*
  seated or once created a channel - neither says anything about whether they are
  still a member of the organisation today, and only `is_org_member()`/
  `has_org_role()` (which query `memberships` live) can answer that. Without this,
  a departed organisation member's stale `channel_members` row would keep their
  read, write, and moderation access alive indefinitely through any path that
  authorises directly against Postgres - Realtime and PostgREST both do, with no
  application layer in between to catch it separately. `channel_members_delete`'s
  self-removal branch (`user_id = current_user_id()`) is the one deliberate
  exception: leaving a channel yourself grants no access and must keep working
  even for an already-stale row.
- Column-level grants, not just policies, are what keep `channels_update` and
  `messages_update` from ever becoming a way to move a channel to another
  organisation or rewrite who sent a message - `channels` only grants `UPDATE
  (name)`, `messages` only `UPDATE (body, edited_at, deleted_at)`, the same shape
  `invitations`' `accepted_at`-only grant already uses.

Revision ID: b3f7d2a891c5
Revises: f3d8a1c6e492
Created: 2026-08-10 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b3f7d2a891c5"
down_revision: str | None = "f3d8a1c6e492"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


HELPERS = """
create or replace function public.is_channel_member(target_channel uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.channel_members
    where channel_id = target_channel and user_id = public.current_user_id()
  );
$$;

create or replace function public.channel_org_id(target_channel uuid)
returns uuid language sql stable security definer
set search_path = public, pg_temp as $$
  select org_id from public.channels where id = target_channel;
$$;

-- Two-argument sibling of is_org_member(): checks an arbitrary target user, not
-- current_user_id(). Needed by channel_members_insert (below) to verify the
-- person being seated - not just the caller - actually belongs to this org.
create or replace function public.is_user_org_member(target_org uuid, target_user uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.memberships m
    where m.org_id = target_org and m.user_id = target_user
  );
$$;

-- A channel's creator, for moderation purposes - the same role created_by
-- already plays for campaigns/runs. Composed with is_org_member() at every
-- policy call site rather than folded in here, so this stays a pure lookup.
create or replace function public.channel_created_by(target_channel uuid)
returns uuid language sql stable security definer
set search_path = public, pg_temp as $$
  select created_by from public.channels where id = target_channel;
$$;
"""

# No `channels_insert` policy: channel creation never goes through a plain
# client-side `INSERT ... RETURNING` - see `create_channel()` below. No
# admin-approval gate on creating a DM/channel - chat membership is opt-in
# social structure, unlike a resource-sharing model.
#
# `channels_select`/`channel_members_select` both have an owner/admin branch
# (`has_org_role`, which queries `memberships` live) alongside the membership
# branch - an org owner/admin can see and moderate any channel in their org,
# including one they never personally joined, without that also handing them
# a back door into every DM's *contents*: `messages_select` has no matching
# branch, deliberately.
POLICIES = """
alter table public.channels        enable row level security;
alter table public.channels        force  row level security;
alter table public.channel_members  enable row level security;
alter table public.channel_members  force  row level security;
alter table public.messages        enable row level security;
alter table public.messages        force  row level security;

create policy channels_select on public.channels for select
  using (
    (public.is_channel_member(id) and public.is_org_member(org_id))
    or public.has_org_role(org_id, array['owner','admin']::public.org_role[])
  );

-- Rename: the creator, or an org owner/admin moderating any channel in their
-- org - both require the actor to still be a current member of it. Column-level
-- grant (name only, below) is the actual immutability guard for
-- org_id/kind/created_by/dm_pair - a policy bug here can't leak into moving a
-- channel to a different organisation.
create policy channels_update on public.channels for update
  using (
    (public.channel_created_by(id) = public.current_user_id() and public.is_org_member(org_id))
    or public.has_org_role(org_id, array['owner','admin']::public.org_role[])
  )
  with check (
    (public.channel_created_by(id) = public.current_user_id() and public.is_org_member(org_id))
    or public.has_org_role(org_id, array['owner','admin']::public.org_role[])
  );

create policy channel_members_select on public.channel_members for select
  using (
    (public.is_channel_member(channel_id) and public.is_org_member(public.channel_org_id(channel_id)))
    or public.has_org_role(public.channel_org_id(channel_id), array['owner','admin']::public.org_role[])
  );

-- Adding a teammate to an EXISTING channel - not the creation path, see
-- create_channel() below. Checks the INSERTER (already seated, still an org
-- member) and the TARGET row's own user_id (must be an org member too, and
-- its org_id must actually match the channel's) - without the second half, any
-- existing channel member could seat a user id from *any other organisation*
-- into their channel, handing that outsider channels_select/messages_select
-- access to this org's channel and its messages.
create policy channel_members_insert on public.channel_members for insert
  with check (
    public.is_channel_member(channel_id)
    and public.is_org_member(public.channel_org_id(channel_id))
    and public.is_user_org_member(public.channel_org_id(channel_id), user_id)
    and org_id = public.channel_org_id(channel_id)
  );

-- A member's own last-read marker, for unread counts. Column-level grant
-- (last_read_at only, below) keeps this from ever becoming a way to rewrite
-- channel_id/user_id/org_id on someone else's - or your own - row.
create policy channel_members_update on public.channel_members for update
  using (user_id = public.current_user_id())
  with check (user_id = public.current_user_id());

-- Remove a member: leaving voluntarily (always allowed, regardless of org
-- standing - self-removal grants no access), the channel's creator removing
-- someone (only while still a current org member), or an org owner/admin
-- moderating any channel in their org. Grants decide reachability, RLS decides
-- visibility - a policy with no matching GRANT (below) is unreachable, not
-- "extra safe".
create policy channel_members_delete on public.channel_members for delete
  using (
    user_id = public.current_user_id()
    or (
      public.channel_created_by(channel_id) = public.current_user_id()
      and public.is_org_member(public.channel_org_id(channel_id))
    )
    or public.has_org_role(public.channel_org_id(channel_id), array['owner','admin']::public.org_role[])
  );

create policy messages_select on public.messages for select
  using (
    public.is_channel_member(channel_id)
    and public.is_org_member(public.channel_org_id(channel_id))
  );

create policy messages_insert on public.messages for insert
  with check (
    sender_id = public.current_user_id()
    and public.is_channel_member(channel_id)
    and public.is_org_member(public.channel_org_id(channel_id))
  );

-- Edit or soft-delete: the sender only, on their own message, never anyone
-- else's - the column grant (below) is what actually confines a write to
-- body/edited_at (editing) or deleted_at (soft delete), not the full row.
create policy messages_update on public.messages for update
  using (sender_id = public.current_user_id())
  with check (sender_id = public.current_user_id());

grant select, insert on public.channels, public.channel_members, public.messages to authenticated;
grant update (name) on public.channels to authenticated;
grant update (last_read_at) on public.channel_members to authenticated;
grant delete on public.channel_members to authenticated;
grant update (body, edited_at, deleted_at) on public.messages to authenticated;
"""


CREATE_CHANNEL_FUNCTION = """
create or replace function public.create_channel(
  target_org uuid, target_kind text, target_name text, member_ids uuid[]
)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  new_channel_id uuid;
  v_dm_pair uuid[];
begin
  if not public.is_org_member(target_org) then
    raise exception 'not a member of this organisation';
  end if;
  -- This function is SECURITY DEFINER: it bypasses channel_members_insert's
  -- RLS check entirely, including the is_user_org_member() half of it, so an
  -- outsider's id in member_ids has to be rejected explicitly here, before
  -- either insert runs.
  if exists (
    select 1 from unnest(member_ids) as t(member_id)
    where not public.is_user_org_member(target_org, t.member_id)
  ) then
    raise exception 'one or more member_ids are not members of this organisation';
  end if;

  if target_kind = 'dm' then
    if array_length(member_ids, 1) is distinct from 1 then
      raise exception 'a direct message needs exactly one other member';
    end if;
    if member_ids[1] = public.current_user_id() then
      raise exception 'cannot start a direct message with yourself';
    end if;
    v_dm_pair := array[
      least(member_ids[1], public.current_user_id()),
      greatest(member_ids[1], public.current_user_id())
    ];

    -- Common case: the pair already has a channel - no insert, no contention.
    select id into new_channel_id from public.channels
      where org_id = target_org and kind = 'dm' and dm_pair = v_dm_pair;
    if found then
      return new_channel_id;
    end if;
  end if;

  begin
    insert into public.channels (org_id, kind, name, created_by, dm_pair)
      values (target_org, target_kind, target_name, public.current_user_id(), v_dm_pair)
      returning id into new_channel_id;
  exception when unique_violation then
    -- Lost a race with a concurrent create_channel() for the same pair - the
    -- implicit savepoint this exception block gives us means the outer call
    -- is still healthy; hand back the winner's id instead of erroring.
    select id into new_channel_id from public.channels
      where org_id = target_org and kind = 'dm' and dm_pair = v_dm_pair;
    return new_channel_id;
  end;

  -- `distinct` absorbs a duplicate or self id in member_ids (harmless for a
  -- channel; for a dm it can't happen, the checks above already reject it) -
  -- without it, such an array makes this select emit the same
  -- (new_channel_id, user_id) pair twice and the insert hits the primary key.
  insert into public.channel_members (channel_id, user_id, org_id)
    select distinct new_channel_id, x, target_org
    from unnest(member_ids || array[public.current_user_id()]) as t(x);
  return new_channel_id;
end;
$$;
"""

DROP_CREATE_CHANNEL_FUNCTION = "drop function if exists public.create_channel(uuid, text, text, uuid[])"

# `postgres` owns `supabase_realtime` (confirmed against this project before
# writing this migration - CLAUDE.md's document map calls SUPABASE_SETUP.md the
# place for a step that needs a human's dashboard click instead; this one
# doesn't, since the migration role already owns the publication it's adding to).
REALTIME_PUBLICATION = (
    "alter publication supabase_realtime add table "
    "public.channels, public.channel_members, public.messages"
)
REALTIME_PUBLICATION_DROP = (
    "alter publication supabase_realtime drop table "
    "public.channels, public.channel_members, public.messages"
)


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Sorted 2-element pair of member ids, set only for kind='dm' - see
        # the partial unique index below and create_channel()'s own use of it.
        sa.Column("dm_pair", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.CheckConstraint("kind in ('channel', 'dm')", name="channels_kind_check"),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index("channels_org_idx", "channels", ["org_id"], unique=False, schema="public")
    op.create_index(
        "channels_dm_pair_unique_idx",
        "channels",
        ["org_id", "dm_pair"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("kind = 'dm' and dm_pair is not null"),
    )

    op.create_table(
        "channel_members",
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Denormalised from channels.org_id, deliberately - direct RLS/index
        # target without a join back to channels, the same reasoning
        # messages.org_id already uses.
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column(
            "last_read_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["public.channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("channel_id", "user_id"),
        schema="public",
    )
    op.create_index(
        "channel_members_user_idx", "channel_members", ["user_id"], unique=False, schema="public"
    )
    op.create_index(
        "channel_members_org_idx", "channel_members", ["org_id"], unique=False, schema="public"
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # Denormalised from channel_id, deliberately - direct RLS/index without a
        # join, the same reasoning `call_outcomes.org_id` already uses.
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("sender_id", sa.UUID(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        # Soft delete - a hard-deleted row re-checked by RLS on a lagging Realtime
        # event is a real edge case; a client-side `deleted_at is null` filter is
        # cheap insurance against it.
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["public.channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index(
        "messages_channel_created_idx",
        "messages",
        ["channel_id", "created_at"],
        unique=False,
        schema="public",
    )

    op.execute(HELPERS)
    op.execute(POLICIES)
    op.execute(CREATE_CHANNEL_FUNCTION)
    op.execute(REALTIME_PUBLICATION)


def downgrade() -> None:
    op.execute(REALTIME_PUBLICATION_DROP)
    op.execute(DROP_CREATE_CHANNEL_FUNCTION)
    op.execute("drop function if exists public.channel_created_by(uuid) cascade")
    op.execute("drop function if exists public.is_user_org_member(uuid, uuid) cascade")
    op.execute("drop function if exists public.channel_org_id(uuid) cascade")
    op.execute("drop function if exists public.is_channel_member(uuid) cascade")

    op.drop_index("messages_channel_created_idx", table_name="messages", schema="public")
    op.drop_table("messages", schema="public")
    op.drop_index("channel_members_org_idx", table_name="channel_members", schema="public")
    op.drop_index("channel_members_user_idx", table_name="channel_members", schema="public")
    op.drop_table("channel_members", schema="public")
    op.drop_index("channels_dm_pair_unique_idx", table_name="channels", schema="public")
    op.drop_index("channels_org_idx", table_name="channels", schema="public")
    op.drop_table("channels", schema="public")
