"""invitation_preview_reports_existing_account

`public.lookup_invitation()` gains `account_exists`, so the accept-invite page
can tell an invitee who already has a CallFlow account to sign in rather than
handing them a signup form that is guaranteed to fail. Before this, someone
invited at an address they had already registered with was shown "set a
password", submitted it, and got back "a user with this email already exists" -
the flow only worked if they left, signed in through the normal route, and
opened the link a second time (`ISSUES.md` #126).

Not new information to whoever holds the link: the token is a secret delivered
to that mailbox, and this same response already returns the invited address.
The check is reachable only through a valid token and cannot be pointed at an
arbitrary email, so it is not an account-enumeration surface.

`drop`, not `create or replace`: adding a column to a `returns table (...)`
changes the function's result type, which Postgres refuses to replace in place.
The function has no explicit grant - it relies on Postgres's default `execute`
for `PUBLIC`, the same as before this change (noted in migration
`202608091200`) - so nothing needs re-granting after the drop.

Revision ID: f4b2c9e17a35
Revises: e5b9c4d26f31
Created: 2026-08-17 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f4b2c9e17a35"
down_revision: str | None = "e5b9c4d26f31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_FUNCTION = """
drop function if exists public.lookup_invitation(text);

create function public.lookup_invitation(token_in text)
returns table(
  org_name text,
  role public.org_role,
  email text,
  valid boolean,
  reason text,
  account_exists boolean
)
language plpgsql stable security definer
set search_path = public, pg_temp as $$
declare
  inv record;
  has_account boolean := false;
begin
  select i.role, i.email, i.accepted_at, i.expires_at, o.name as org_name
    into inv
  from public.invitations i
  join public.organisations o on o.id = i.org_id
  where i.token = token_in;

  if not found then
    return query
      select null::text, null::public.org_role, null::text, false, 'not_found', false;
    return;
  end if;

  -- Cast both sides and lower them rather than leaning on citext's own
  -- case-insensitive comparison: `invitations.email` and `users.email` have
  -- differed in type before now (migration 202608092500 was that bug), and a
  -- silent false here would send someone who has an account to a signup form
  -- that cannot succeed.
  select exists (
    select 1 from public.users u
    where lower(u.email::text) = lower(inv.email::text)
  ) into has_account;

  if inv.accepted_at is not null then
    return query
      select inv.org_name, inv.role, inv.email::text, false, 'used', has_account;
    return;
  end if;

  if inv.expires_at <= now() then
    return query
      select inv.org_name, inv.role, inv.email::text, false, 'expired', has_account;
    return;
  end if;

  return query
    select inv.org_name, inv.role, inv.email::text, true, null::text, has_account;
end;
$$;
"""

OLD_FUNCTION = """
drop function if exists public.lookup_invitation(text);

create function public.lookup_invitation(token_in text)
returns table(org_name text, role public.org_role, email text, valid boolean, reason text)
language plpgsql stable security definer
set search_path = public, pg_temp as $$
declare
  inv record;
begin
  select i.role, i.email, i.accepted_at, i.expires_at, o.name as org_name
    into inv
  from public.invitations i
  join public.organisations o on o.id = i.org_id
  where i.token = token_in;

  if not found then
    return query select null::text, null::public.org_role, null::text, false, 'not_found';
    return;
  end if;

  if inv.accepted_at is not null then
    return query select inv.org_name, inv.role, inv.email::text, false, 'used';
    return;
  end if;

  if inv.expires_at <= now() then
    return query select inv.org_name, inv.role, inv.email::text, false, 'expired';
    return;
  end if;

  return query select inv.org_name, inv.role, inv.email::text, true, null::text;
end;
$$;
"""


def upgrade() -> None:
    op.execute(NEW_FUNCTION)


def downgrade() -> None:
    op.execute(OLD_FUNCTION)
