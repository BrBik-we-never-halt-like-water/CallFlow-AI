"""Enforce the seat limit where a seat is actually taken.

`POST /organisations/me/invitations` counts seats before sending, which stops an
admin over-inviting and disappointing people one accept at a time. It is not the
guard: a plan can be downgraded between the invitation and the click, and the
accept path never re-checked - so an invite sent on Growth could be accepted on
Starter and put the organisation over its own limit. The send-side comment even
claimed accept re-checked. It did not.

A trigger rather than a Python check, for the reason `enforce_voice_agent_limit`
gives and one more specific to this path: at accept time the caller is not yet a
member of the target organisation, so an RLS-scoped connection cannot read that
organisation's memberships to count them. Only a definer function can see the true
count, and putting it in the trigger covers every insert rather than the one route.

**Pending invitations count towards the total**, matching `check_seat_available` in
`domain/entitlements.py`. Two invitations sent into the last free seat must not
both be acceptable.

Revision ID: d1a7b3e58f42
Revises: c8f4a1e97b23
"""

from __future__ import annotations

from alembic import op

revision = "d1a7b3e58f42"
down_revision = "c8f4a1e97b23"
branch_labels = None
depends_on = None


# The invitation being accepted is itself pending and would otherwise be counted
# against the seat it is claiming - an off-by-one that makes the last seat of every
# plan unusable. `pending` therefore excludes any invitation addressed to the
# email of the user being inserted.
ENFORCE_SEAT_LIMIT = """
create or replace function public.enforce_seat_limit()
returns trigger
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  allowed integer := public.effective_limit(new.org_id, 'max_seats');
  members integer;
  pending integer;
  joiner  text;
begin
  if allowed is null then
    return new;
  end if;

  select count(*) into members
    from public.memberships where org_id = new.org_id;

  -- The very first membership of a new organisation. `create_organisation()` and
  -- the signup trigger `handle_new_auth_user()` both land here, and neither may
  -- ever fail: a plan limit that can block signup is an outage, not a limit.
  if members = 0 then
    return new;
  end if;

  select u.email into joiner from public.users u where u.id = new.user_id;

  select count(*) into pending
    from public.invitations i
   where i.org_id = new.org_id
     and i.accepted_at is null
     and i.expires_at > now()
     and (joiner is null or lower(i.email) <> lower(joiner));

  if members + pending >= allowed then
    raise exception
      'This plan includes % seat(s) and % are taken. Upgrade in Billing to add another.',
      allowed, members + pending
      using errcode = '23514';
  end if;

  return new;
end;
$$;

create trigger memberships_enforce_seat_limit before insert on public.memberships
  for each row execute function public.enforce_seat_limit();
"""


def upgrade() -> None:
    op.execute(ENFORCE_SEAT_LIMIT)


def downgrade() -> None:
    op.execute(
        "drop trigger if exists memberships_enforce_seat_limit on public.memberships"
    )
    op.execute("drop function if exists public.enforce_seat_limit()")
