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

-- The publication Realtime subscribes to. Migrations add tables to it, and a
-- missing publication makes each of those `alter publication` calls fail.
do $$ begin
  if not exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    create publication supabase_realtime;
  end if;
end $$;
