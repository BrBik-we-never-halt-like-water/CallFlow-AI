"""reuse_freed_slugs_on_signup

Completes the ISSUES.md #17 fix. The previous revision made slug uniqueness partial
on `deleted_at IS NULL` and retired member-less organisations, but the signup
trigger's collision loop still counted every row:

    while exists (select 1 from public.organisations where slug = final_slug)

so it kept stepping past slugs that retired organisations no longer held. A domain
that had signed up and deleted once still got `acme-2`, which is the symptom the fix
existed to remove. The loop now ignores soft-deleted rows, matching the index that
actually enforces uniqueness.

Revision ID: 9c1f4b2ad7e3
Revises: 4337590dce16
Created: 2026-08-06 01:21:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "9c1f4b2ad7e3"
down_revision: str | None = "4337590dce16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SLUG_LOOP_ACTIVE_ONLY = """  -- Only live organisations reserve a slug; retired ones have released theirs.
  while exists (
    select 1 from public.organisations
    where slug = final_slug and deleted_at is null
  ) loop"""

SLUG_LOOP_ALL_ROWS = (
    "  while exists (select 1 from public.organisations where slug = final_slug) loop"
)

# Replaced wholesale rather than patched, so the function body is readable in one
# place at this point in the history.
SIGNUP_TRIGGER_FUNCTION = """
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  new_user_id  uuid;
  new_org_id   uuid;
  display_name text;
  email_domain text;
  org_name     text;
  base_slug    text;
  final_slug   text;
  suffix       int := 1;
begin
  display_name := nullif(trim(coalesce(
    new.raw_user_meta_data ->> 'full_name',
    new.raw_user_meta_data ->> 'name', '')), '');

  insert into public.users (auth_user_id, email, name, avatar_url)
  values (new.id, new.email, display_name,
          nullif(new.raw_user_meta_data ->> 'avatar_url', ''))
  on conflict (auth_user_id) do update set email = excluded.email
  returning id into new_user_id;

  if exists (select 1 from public.memberships where user_id = new_user_id) then
    return new;
  end if;

  email_domain := split_part(new.email, '@', 2);

  if email_domain is null or email_domain = ''
     or public.is_free_email_domain(email_domain) then
    org_name := coalesce(display_name, split_part(new.email, '@', 1)) || '''s workspace';
  else
    org_name := initcap(replace(split_part(email_domain, '.', 1), '-', ' '));
  end if;

  base_slug := public.slugify(org_name);
  final_slug := base_slug;

__SLUG_LOOP__
    suffix := suffix + 1;
    final_slug := base_slug || '-' || suffix;
  end loop;

  insert into public.organisations (name, slug, country, timezone)
  values (org_name, final_slug, 'IN', 'Asia/Kolkata')
  returning id into new_org_id;

  insert into public.memberships (org_id, user_id, role)
  values (new_org_id, new_user_id, 'owner');

  return new;
end;
$$;
"""


def upgrade() -> None:
    op.execute(SIGNUP_TRIGGER_FUNCTION.replace("__SLUG_LOOP__", SLUG_LOOP_ACTIVE_ONLY))


def downgrade() -> None:
    op.execute(SIGNUP_TRIGGER_FUNCTION.replace("__SLUG_LOOP__", SLUG_LOOP_ALL_ROWS))
