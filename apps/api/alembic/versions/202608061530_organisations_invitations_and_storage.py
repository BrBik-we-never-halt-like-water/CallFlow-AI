"""organisations_invitations_and_storage

Real multi-organisation support: a logo on the organisation, an `invitations` table
so a teammate can be invited before they have an account, the RLS to make accepting
one possible, and the two Storage buckets an org logo / user avatar upload needs.

Three gaps this closes:

* `memberships_insert` only ever allowed an existing owner/admin to add a row. That
  is fine for "invite a known user_id" but nothing today can attach the *first*
  membership of a brand-new organisation (only the SECURITY DEFINER signup trigger
  could) or let an invitee insert their own membership on accept. Two more branches
  fix both.
* The signup trigger inlined its own slugify-and-dedupe loop. `unique_org_slug()`
  extracts it so the new "create organisation" endpoint gets the same collision
  handling instead of a second copy.
* No public, unauthenticated way to resolve an invite token exists - and per
  CLAUDE.md, `privileged.acquire()` must never appear in a request handler, so the
  accept-invite preview goes through `database.anonymous()` calling a SECURITY
  DEFINER function instead, matching the `is_org_member`-style helpers already here.

Revision ID: b3f8a1c4e6d2
Revises: 9c1f4b2ad7e3
Created: 2026-08-06 15:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b3f8a1c4e6d2"
down_revision: str | None = "9c1f4b2ad7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UNIQUE_ORG_SLUG = """
create or replace function public.unique_org_slug(base_name text)
returns text language plpgsql stable security definer
set search_path = public, pg_temp as $$
declare
  base_slug text := public.slugify(base_name);
  candidate text := public.slugify(base_name);
  suffix    int := 1;
begin
  while exists (
    select 1 from public.organisations
    where slug = candidate and deleted_at is null
  ) loop
    suffix := suffix + 1;
    candidate := base_slug || '-' || suffix;
  end loop;
  return candidate;
end;
$$;
"""

# Replaces the trigger wholesale (as the previous revision did) so the slug loop
# lives in one place - this function - rather than staying duplicated here.
SIGNUP_TRIGGER_USES_HELPER = """
create or replace function public.handle_new_auth_user()
returns trigger language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  new_user_id  uuid;
  new_org_id   uuid;
  display_name text;
  email_domain text;
  org_name     text;
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

  insert into public.organisations (name, slug, country, timezone)
  values (org_name, public.unique_org_slug(org_name), 'IN', 'Asia/Kolkata')
  returning id into new_org_id;

  insert into public.memberships (org_id, user_id, role)
  values (new_org_id, new_user_id, 'owner');

  return new;
end;
$$;
"""

INVITATION_HELPERS = """
create or replace function public.has_valid_invitation(target_org uuid, target_role public.org_role)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1
    from public.invitations i
    join public.users u on u.id = public.current_user_id()
    where i.org_id = target_org
      and i.role = target_role
      and lower(i.email) = lower(u.email)
      and i.accepted_at is null
      and i.expires_at > now()
  );
$$;

-- Unauthenticated accept-invite preview goes through `database.anonymous()` calling
-- this, rather than `privileged.acquire()`, which must never appear in a request
-- handler (CLAUDE.md). SECURITY DEFINER is what lets a no-identity connection still
-- resolve one row by its unguessable token.
create or replace function public.lookup_invitation(token_in text)
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

INVITATIONS_POLICIES = """
alter table public.invitations enable row level security;
alter table public.invitations force  row level security;

create policy invitations_select on public.invitations for select using (
  public.has_org_role(org_id, array['owner','admin']::public.org_role[])
  or lower(email) = (select lower(email) from public.users where id = public.current_user_id())
);

create policy invitations_insert on public.invitations for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy invitations_delete on public.invitations for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

-- Only the invitee can mark their own invite accepted.
create policy invitations_update_own on public.invitations for update
  using (lower(email) = (select lower(email) from public.users where id = public.current_user_id()))
  with check (lower(email) = (select lower(email) from public.users where id = public.current_user_id()));
"""

# A user-initiated "create another organisation" or "accept an invite" had nowhere
# to attach the first membership row before: the owner/admin branch requires a
# membership that does not exist yet.
MEMBERSHIPS_INSERT_POLICY = """
drop policy if exists memberships_insert on public.memberships;
create policy memberships_insert on public.memberships for insert
  with check (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or public.has_valid_invitation(org_id, role)
    or (
      role = 'owner'
      and not exists (select 1 from public.memberships m2 where m2.org_id = memberships.org_id)
    )
  );
"""

GRANTS = "grant select, insert, update, delete on public.invitations to authenticated;"

# A storage object's key is written as "{org_id}/logo.png" / "{user_id}/avatar.png".
# A bare `::uuid` cast on an arbitrary key would raise and abort the policy check
# instead of just failing it, so this validates the shape first and returns null
# (safely false in the `=` comparisons below) rather than throwing.
PATH_PREFIX_HELPER = """
create or replace function public.path_prefix_uuid(object_name text)
returns uuid language sql immutable as $$
  select case
    when object_name ~ '^[0-9a-fA-F-]{36}/'
    then split_part(object_name, '/', 1)::uuid
    else null
  end;
$$;
"""

STORAGE_BUCKETS = """
insert into storage.buckets (id, name, public) values ('org-logos', 'org-logos', true)
  on conflict (id) do nothing;
insert into storage.buckets (id, name, public) values ('avatars', 'avatars', true)
  on conflict (id) do nothing;
"""

STORAGE_POLICIES = """
create policy org_logos_public_read on storage.objects for select
  using (bucket_id = 'org-logos');
create policy org_logos_owner_write on storage.objects for insert
  with check (
    bucket_id = 'org-logos'
    and public.has_org_role(public.path_prefix_uuid(name), array['owner','admin']::public.org_role[])
  );
create policy org_logos_owner_update on storage.objects for update
  using (
    bucket_id = 'org-logos'
    and public.has_org_role(public.path_prefix_uuid(name), array['owner','admin']::public.org_role[])
  )
  with check (
    bucket_id = 'org-logos'
    and public.has_org_role(public.path_prefix_uuid(name), array['owner','admin']::public.org_role[])
  );
create policy org_logos_owner_delete on storage.objects for delete
  using (
    bucket_id = 'org-logos'
    and public.has_org_role(public.path_prefix_uuid(name), array['owner','admin']::public.org_role[])
  );

create policy avatars_public_read on storage.objects for select
  using (bucket_id = 'avatars');
create policy avatars_owner_write on storage.objects for insert
  with check (bucket_id = 'avatars' and public.path_prefix_uuid(name) = public.current_user_id());
create policy avatars_owner_update on storage.objects for update
  using (bucket_id = 'avatars' and public.path_prefix_uuid(name) = public.current_user_id())
  with check (bucket_id = 'avatars' and public.path_prefix_uuid(name) = public.current_user_id());
create policy avatars_owner_delete on storage.objects for delete
  using (bucket_id = 'avatars' and public.path_prefix_uuid(name) = public.current_user_id());
"""


def upgrade() -> None:
    op.add_column("organisations", sa.Column("logo_url", sa.Text(), nullable=True), schema="public")

    op.create_table(
        "invitations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(name="org_role", schema="public", create_type=False),
            server_default="operator",
            nullable=False,
        ),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("invited_by", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
        schema="public",
    )
    op.create_index(
        "invitations_org_email_pending_key",
        "invitations",
        ["org_id", sa.text("lower(email)")],
        unique=True,
        schema="public",
        postgresql_where=sa.text("accepted_at IS NULL"),
    )

    op.execute(UNIQUE_ORG_SLUG)
    op.execute(SIGNUP_TRIGGER_USES_HELPER)
    op.execute(INVITATION_HELPERS)
    op.execute(INVITATIONS_POLICIES)
    op.execute(MEMBERSHIPS_INSERT_POLICY)
    op.execute(GRANTS)
    op.execute(PATH_PREFIX_HELPER)
    op.execute(STORAGE_BUCKETS)
    op.execute(STORAGE_POLICIES)


def downgrade() -> None:
    op.execute("drop policy if exists org_logos_public_read on storage.objects")
    op.execute("drop policy if exists org_logos_owner_write on storage.objects")
    op.execute("drop policy if exists org_logos_owner_update on storage.objects")
    op.execute("drop policy if exists org_logos_owner_delete on storage.objects")
    op.execute("drop policy if exists avatars_public_read on storage.objects")
    op.execute("drop policy if exists avatars_owner_write on storage.objects")
    op.execute("drop policy if exists avatars_owner_update on storage.objects")
    op.execute("drop policy if exists avatars_owner_delete on storage.objects")
    op.execute("delete from storage.buckets where id in ('org-logos', 'avatars')")
    op.execute("drop function if exists public.path_prefix_uuid(text) cascade")

    op.execute(
        "drop policy if exists memberships_insert on public.memberships"
    )
    op.execute(
        "create policy memberships_insert on public.memberships for insert "
        "with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))"
    )

    op.execute("drop function if exists public.lookup_invitation(text) cascade")
    op.execute("drop function if exists public.has_valid_invitation(uuid, public.org_role) cascade")

    op.drop_index("invitations_org_email_pending_key", table_name="invitations", schema="public")
    op.drop_table("invitations", schema="public")

    op.execute("drop function if exists public.unique_org_slug(text) cascade")

    # Restore the pre-helper signup trigger (inline slug loop) so downgrade is exact.
    op.execute(
        """
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
          while exists (
            select 1 from public.organisations
            where slug = final_slug and deleted_at is null
          ) loop
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
    )

    op.drop_column("organisations", "logo_url", schema="public")
