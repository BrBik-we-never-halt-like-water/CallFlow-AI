"""give every pre-trigger auth user a public.users row and an organisation

`on_auth_user_created` fires on INSERT into `auth.users`, so any account that
signed up before the trigger existed on this database has no `public.users`
row, no organisation, and no membership. Signing in works - GoTrue issues a
valid token - but every authenticated endpoint then 403s with "has no
organisation", which reads as a broken product rather than a missing row.

`backfill_orphaned_auth_users()` replays exactly what the trigger does, by
calling the same helpers it calls (`is_free_email_domain`, `unique_org_slug`)
rather than restating the rules. The two must not drift: a second copy of
"which domains are personal" is how they silently disagree.

Idempotent - it selects only accounts with no `public.users` row and skips
anyone who already has a membership, so re-running it does nothing.

Revision ID: e5b9c4d26f31
Revises: d4a8b3c15e29
Created: 2026-08-16 18:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "e5b9c4d26f31"
down_revision: str | None = "d4a8b3c15e29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BACKFILL = """
create or replace function public.backfill_orphaned_auth_users()
returns integer
language plpgsql
security definer
set search_path = public, auth, pg_temp
as $$
declare
  account      record;
  new_user_id  uuid;
  new_org_id   uuid;
  display_name text;
  email_domain text;
  org_name     text;
  repaired     integer := 0;
begin
  for account in
    select a.id, a.email, a.raw_user_meta_data
    from auth.users a
    left join public.users u on u.auth_user_id = a.id
    where u.id is null
      -- Test fixtures create auth users directly and delete the public rows
      -- behind them; giving each one an organisation would bury the real
      -- accounts in hundreds of empty workspaces. These prefixes are the ones
      -- `tests/` uses (see `_create_tenant`, the telephony and provisioning
      -- suites) - all on @brbik.com, which is ours, so no real signup matches.
      and not (a.email like 'rls-%@brbik.com'
            or a.email like 'tel-%@brbik.com'
            or a.email like 'prov-%@brbik.com'
            or a.email like 'outsider-%@brbik.com'
            or a.email like 'probe-%@brbik.com'
            or a.email like 'trigcheck-%@brbik.com')
    order by a.created_at
  loop
    display_name := nullif(trim(coalesce(
      account.raw_user_meta_data ->> 'full_name',
      account.raw_user_meta_data ->> 'name', '')), '');

    insert into public.users (auth_user_id, email, name, avatar_url)
    values (account.id, account.email, display_name,
            nullif(account.raw_user_meta_data ->> 'avatar_url', ''))
    on conflict (auth_user_id) do update set email = excluded.email
    returning id into new_user_id;

    if exists (select 1 from public.memberships where user_id = new_user_id) then
      continue;
    end if;

    email_domain := split_part(account.email, '@', 2);

    if email_domain is null or email_domain = ''
       or public.is_free_email_domain(email_domain) then
      org_name := coalesce(display_name, split_part(account.email, '@', 1))
                  || '''s workspace';
    else
      org_name := initcap(replace(split_part(email_domain, '.', 1), '-', ' '));
    end if;

    insert into public.organisations (name, slug, country, timezone)
    values (org_name, public.unique_org_slug(org_name), 'IN', 'Asia/Kolkata')
    returning id into new_org_id;

    insert into public.memberships (org_id, user_id, role)
    values (new_org_id, new_user_id, 'owner');

    repaired := repaired + 1;
  end loop;

  return repaired;
end;
$$;
"""


def upgrade() -> None:
    op.execute(BACKFILL)
    op.execute("select public.backfill_orphaned_auth_users()")


def downgrade() -> None:
    # The repaired rows are left alone: they are indistinguishable from a normal
    # signup by design, and deleting them would take real organisations with them.
    op.execute("drop function if exists public.backfill_orphaned_auth_users()")
