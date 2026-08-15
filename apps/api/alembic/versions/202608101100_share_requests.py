"""share_requests

Role-based UI roadmap, Phase 4: peer-to-peer campaign/escalation sharing.
An operator can request access to a teammate's campaign or ask to take over
their escalation; the resource's actual owner (whoever created the campaign,
or is assigned to / started the run behind the escalation) decides.

Three new pieces, deliberately kept separate rather than folded into
`campaigns_select`/`escalations_select` again - the RLS-recursion bug from
the previous migration (`3ea00413701c`) is exactly the failure mode this
avoids by construction:

1. `share_requests` - the request/decision record itself, RLS-scoped to
   requester/owner/admin-or-owner, same shape as `escalations`.
2. `resolve_resource_owner()` - `SECURITY DEFINER`, resolves who actually
   owns a campaign or escalation *without* going through the requester's own
   RLS scope (which, by Phase 1's own design, hides exactly the resource
   they're trying to request). Never trusts a client-supplied owner id -
   the route always calls this itself before inserting a request, and again
   before approving one.
3. `list_campaign_directory()` / `list_escalation_directory()` -
   `SECURITY DEFINER`, name-only/contact-only directories so an operator can
   see *what exists* to request without the full content their own RLS
   scope would otherwise hide. Each checks `is_org_member()` internally
   before returning anything, the same defense-in-depth every other
   `SECURITY DEFINER` function in this codebase already has - a caller who
   isn't in the target org gets nothing back, not a permissions error.

RLS/index style follows `security-rls-basics`/`security-rls-performance`/
`query-partial-indexes`/`schema-foreign-key-indexes` from the Supabase
Postgres best-practices skill, checked deliberately before writing this
migration: per-command policies (never `for all` - iteration 21's `#64` is
the exact reason), an index on every FK column, and a partial unique index
for "one pending request per resource per requester" rather than a always-on
unique constraint that would block a second, later request once a first one
is resolved. `(select auth.uid())`-style wrapping for RLS function calls is
NOT applied here, matching every existing policy in this codebase (none of
them wrap `current_user_id()`/`has_org_role()` this way) - flagged as a
deliberate consistency choice, not an oversight; a codebase-wide pass to add
it everywhere at once would be a separate, deliberate change, not something
to introduce inconsistently in one new table's policies.

Revision ID: 4cbc5103657f
Revises: aebc05c817cf
Created: 2026-08-10 11:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4cbc5103657f"
down_revision: str | None = "aebc05c817cf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTIONS = """
create or replace function public.resolve_resource_owner(
  target_org uuid, target_type text, target_id text
)
returns uuid language plpgsql stable security definer
set search_path = public, pg_temp as $$
declare
  result uuid;
begin
  if not public.is_org_member(target_org) then
    return null;
  end if;

  if target_type = 'campaign' then
    select created_by into result
    from public.campaigns
    where org_id = target_org and id = target_id;
  elsif target_type = 'escalation' then
    select coalesce(e.assigned_to, r.started_by) into result
    from public.escalations e
    join public.runs r on r.id = e.run_id
    where e.org_id = target_org and e.id = target_id::uuid;
  end if;

  return result;
end;
$$;

create or replace function public.list_campaign_directory(target_org uuid)
returns table(id text, name text, owner_user_id uuid, owner_name text)
language sql stable security definer
set search_path = public, pg_temp as $$
  select c.id, c.name, c.created_by, u.name
  from public.campaigns c
  left join public.users u on u.id = c.created_by
  where c.org_id = target_org and public.is_org_member(target_org);
$$;

create or replace function public.list_escalation_directory(target_org uuid)
returns table(
  id uuid, contact_name text, campaign_name text,
  owner_user_id uuid, owner_name text
)
language sql stable security definer
set search_path = public, pg_temp as $$
  select e.id, c.contact_name, coalesce(camp.name, r.campaign_id),
         coalesce(e.assigned_to, r.started_by), u.name
  from public.escalations e
  join public.call_outcomes c on c.id = e.call_outcome_id
  join public.runs r on r.id = e.run_id
  left join public.campaigns camp on camp.id = r.campaign_id
  left join public.users u on u.id = coalesce(e.assigned_to, r.started_by)
  where e.org_id = target_org and e.status = 'open'
    and public.is_org_member(target_org);
$$;
"""

POLICIES = """
alter table public.share_requests enable row level security;
alter table public.share_requests force  row level security;

create policy share_requests_select on public.share_requests for select
  using (
    requested_by = public.current_user_id()
    or owner_user_id = public.current_user_id()
    or public.has_org_role(org_id, array['owner','admin']::public.org_role[])
  );

create policy share_requests_insert on public.share_requests for insert
  with check (
    requested_by = public.current_user_id()
    and public.is_org_member(org_id)
  );

-- Deciding (approve/reject) is the resource owner's call alone - not
-- broadened to admin/owner, matching the roadmap's own scoping: an admin
-- can already see everything, so there is nothing for them to "decide" on
-- someone else's behalf here.
create policy share_requests_update on public.share_requests for update
  using (owner_user_id = public.current_user_id())
  with check (owner_user_id = public.current_user_id());
"""

GRANTS = """
grant select, insert, update on public.share_requests to authenticated;
"""


def upgrade() -> None:
    op.create_table(
        "share_requests",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "resource_type in ('campaign', 'escalation')", name="share_requests_resource_type_valid"
        ),
        sa.CheckConstraint(
            "status in ('pending', 'approved', 'rejected')", name="share_requests_status_valid"
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["public.users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["public.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        schema="public",
    )
    op.create_index("share_requests_org_idx", "share_requests", ["org_id"], schema="public")
    op.create_index(
        "share_requests_requested_by_idx", "share_requests", ["requested_by"], schema="public"
    )
    op.create_index(
        "share_requests_owner_idx", "share_requests", ["owner_user_id"], schema="public"
    )
    # One pending request per resource per requester - a partial index, not
    # an always-on unique constraint, so a second request is still possible
    # once the first is approved or rejected.
    op.execute(
        """
        create unique index share_requests_one_pending_idx
          on public.share_requests (resource_type, resource_id, requested_by)
          where status = 'pending'
        """
    )

    op.execute(FUNCTIONS)
    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("drop policy if exists share_requests_select on public.share_requests")
    op.execute("drop policy if exists share_requests_insert on public.share_requests")
    op.execute("drop policy if exists share_requests_update on public.share_requests")
    op.execute("drop function if exists public.resolve_resource_owner(uuid, text, text)")
    op.execute("drop function if exists public.list_campaign_directory(uuid)")
    op.execute("drop function if exists public.list_escalation_directory(uuid)")
    op.drop_table("share_requests", schema="public")
