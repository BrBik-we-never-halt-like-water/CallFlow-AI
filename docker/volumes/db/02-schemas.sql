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

grant usage on schema auth to anon, authenticated, service_role, postgres;
grant usage on schema storage to anon, authenticated, service_role, postgres;

alter role supabase_auth_admin set search_path = auth;
alter role supabase_storage_admin set search_path = storage;

create extension if not exists pgcrypto with schema extensions;
create extension if not exists citext;
create extension if not exists "uuid-ossp" with schema extensions;

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
