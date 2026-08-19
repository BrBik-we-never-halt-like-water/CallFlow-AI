-- Schemas the services own, created before they start.
--
-- GoTrue and Storage each migrate their own tables on boot, but neither creates
-- the schema it migrates into, and Realtime needs `_realtime` to exist before
-- its first connection. Creating them here rather than letting each service
-- fail once and retry keeps the first `docker compose up` free of red herrings.

create schema if not exists auth authorization supabase_auth_admin;
create schema if not exists storage authorization supabase_storage_admin;
create schema if not exists _realtime authorization supabase_admin;
create schema if not exists extensions;

-- Realtime needs BOTH schemas, and they are not the same thing. `_realtime`
-- above holds its tenant metadata; `realtime` holds the per-tenant CDC tables
-- (`realtime.subscription`, the `realtime.messages` partitions) that its own
-- migrations create on a tenant's first connection. Those migrations do not
-- create the schema - they fail with "Could not create schema migrations
-- table", the tenant is left with no `subscription` table, and every
-- subscribe returns RealtimeSubscriptionError while the socket itself looks
-- healthy. Upstream Supabase creates this in its own `realtime.sql` init
-- script, which this stack does not use (`ISSUES.md` #120).
create schema if not exists realtime authorization supabase_admin;

grant usage on schema auth to anon, authenticated, service_role, postgres;
grant usage on schema storage to anon, authenticated, service_role, postgres;

alter role supabase_auth_admin set search_path = auth;
alter role supabase_storage_admin set search_path = storage;

create extension if not exists pgcrypto with schema extensions;
create extension if not exists citext;
create extension if not exists "uuid-ossp" with schema extensions;

-- `extensions` has to be on the search path, because hosted Supabase puts it
-- there and this database is supposed to behave the same.
--
-- Without this, pgcrypto lives in a schema nothing looks in: `gen_salt('bf')`
-- fails with "function gen_salt(unknown) does not exist" while
-- `extensions.gen_salt('bf')` works. That is not a theoretical difference - the
-- entire DATABASE_URL-gated test suite creates its tenants with
-- `crypt('x', gen_salt('bf'))`, unqualified, exactly as hosted Supabase accepts.
-- Against a local stack without this line every one of those tests errors in
-- setup, so `npm run local` produced a database the tests could not use.
--
-- Set on the database rather than per role: GoTrue, PostgREST, Storage, Alembic
-- and the API all connect as different roles, and any of them may call a
-- pgcrypto function. The two `alter role` lines above are narrower on purpose -
-- those roles own one schema each and should not see more than they need.
do $$
begin
  execute 'alter database ' || quote_ident(current_database())
       || ' set search_path = "$user", public, extensions';
end
$$;

-- The `supabase_realtime` publication is deliberately NOT created here.
--
-- The image's own `init-scripts/00000000000000-initial-schema.sql` creates it,
-- unguarded, and runs *after* these files - so creating it first makes that
-- script fail with "publication already exists", which aborts the rest of the
-- image's initialisation and leaves a half-built database that only shows up
-- as some later service failing for an unrelated-looking reason.
--
-- It exists by the time Alembic runs, which is all the migrations need.

-- Storage's own migrator issues `create schema if not exists storage`, and
-- Postgres checks CREATE on the *database* before it evaluates IF NOT EXISTS -
-- so owning the schema is not enough and it fails with "permission denied for
-- database postgres". GoTrue never hits this because it migrates into a schema
-- it already owns without re-creating it.
grant create on database postgres to supabase_storage_admin;
