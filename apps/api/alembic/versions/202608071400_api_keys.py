"""api_keys

Org-scoped API keys for programmatic access to CallFlow's own API - not a voice
provider credential. Only a SHA-256 hash of the key is ever stored (mirrors the
`CALLFLOW_OWNER_KEY` comparison already used elsewhere: `secrets.compare_digest`
against a hash, never the plaintext). `key_prefix` is the first few characters,
kept only so a list of keys is distinguishable without ever showing the full
value again after creation.

`resolve_api_key()` is the SECURITY DEFINER counterpart to `lookup_invitation()`:
the one place a no-identity (`database.anonymous()`) connection can turn a key's
hash into a real identity, because the request has no Supabase JWT to verify at
that point. It re-checks the creating user's live membership and role on every
call rather than caching either on the key row, so removing someone from an
organisation or changing their role takes effect on their API keys immediately,
not just on their next Supabase sign-in.

Revision ID: e5f2b8d0a416
Revises: d4e1a7c9f203
Created: 2026-08-07 14:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f2b8d0a416"
down_revision: str | None = "d4e1a7c9f203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RESOLVE_API_KEY = """
create or replace function public.resolve_api_key(key_hash_in text)
returns table(
  user_id uuid, auth_user_id uuid, email text, name text, avatar_url text,
  org_id uuid, org_name text, org_slug text, org_logo_url text,
  org_onboarded_at timestamptz, org_plan_id text, role public.org_role
)
language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  key_org_id  uuid;
  key_user_id uuid;
begin
  select k.org_id, k.created_by into key_org_id, key_user_id
  from public.api_keys k
  where k.key_hash = key_hash_in;

  if not found or key_user_id is null then
    return;
  end if;

  update public.api_keys set last_used_at = now() where key_hash = key_hash_in;

  return query
    select u.id, u.auth_user_id, u.email::text, u.name, u.avatar_url,
           o.id, o.name, o.slug::text, o.logo_url, o.onboarded_at, o.plan_id::text,
           m.role
    from public.users u
    join public.memberships m on m.user_id = u.id and m.org_id = key_org_id
    join public.organisations o on o.id = m.org_id
    where u.id = key_user_id
      and o.deleted_at is null;
end;
$$;
"""

POLICIES = """
alter table public.api_keys enable row level security;
alter table public.api_keys force  row level security;

create policy api_keys_select on public.api_keys for select
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy api_keys_insert on public.api_keys for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));

create policy api_keys_delete on public.api_keys for delete
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = "grant select, insert, delete on public.api_keys to authenticated;"


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["public.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
        sa.CheckConstraint("length(key_hash) = 64", name="api_keys_hash_length"),
        schema="public",
    )
    op.create_index("api_keys_org_idx", "api_keys", ["org_id"], schema="public")

    op.execute(RESOLVE_API_KEY)
    op.execute(POLICIES)
    op.execute(GRANTS)


def downgrade() -> None:
    op.execute("drop function if exists public.resolve_api_key(text) cascade")
    op.drop_index("api_keys_org_idx", table_name="api_keys", schema="public")
    op.drop_table("api_keys", schema="public")
