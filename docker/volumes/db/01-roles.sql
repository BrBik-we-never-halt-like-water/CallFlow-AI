-- The login roles each Supabase service connects as.
--
-- The `supabase/postgres` image ships `anon`, `authenticated`, `service_role`
-- and `supabase_admin`, but not the per-service owners GoTrue, PostgREST and
-- Storage expect - those are created by Supabase's own provisioning, which a
-- plain image start never runs. Without them each service dies on connect with
-- "role does not exist".
--
-- **`postgres` is one of the missing ones.** The image runs initdb as
-- `supabase_admin`, so a bare container has no `postgres` role at all - while
-- hosted Supabase does, and this repo's `DATABASE_URL` and `privileged.py` both
-- depend on it. Creating it here is what makes a local database behave like the
-- hosted one rather than subtly differently.
--
-- Every statement is guarded. The entrypoint runs these with ON_ERROR_STOP, so
-- one failure silently skips every later file - which is exactly how a missing
-- `postgres` role turned into GoTrue crash-looping on an absent `auth` schema,
-- two files and one service away from the actual cause.
--
-- `authenticator` is the one PostgREST logs in as before switching to `anon` or
-- `authenticated`; it is deliberately NOINHERIT so it holds no privileges of its
-- own and only ever acts as the role it has switched to.

\set pgpass `echo "$POSTGRES_PASSWORD"`

do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticator') then
    create role authenticator noinherit login;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'supabase_auth_admin') then
    create role supabase_auth_admin noinherit createrole login;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'supabase_storage_admin') then
    create role supabase_storage_admin noinherit createrole login;
  end if;
  -- BYPASSRLS deliberately, matching hosted Supabase: CLAUDE.md §4b's whole
  -- account of why RLS is only real through `database.as_user()` rests on this
  -- role having it. A local database without it would pass tests the hosted one
  -- fails.
  if not exists (select 1 from pg_roles where rolname = 'postgres') then
    create role postgres superuser createdb createrole login bypassrls;
  end if;
end $$;

-- Passwords outside the guard so a re-run resets them to whatever the current
-- .env says, rather than leaving a stale one nobody can explain.
alter role authenticator password :'pgpass';
alter role supabase_auth_admin password :'pgpass';
alter role supabase_storage_admin password :'pgpass';
alter role postgres password :'pgpass';

grant anon, authenticated, service_role to authenticator;
grant anon, authenticated, service_role to postgres;
