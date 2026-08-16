-- The login roles each Supabase service connects as.
--
-- The `supabase/postgres` image ships `anon`, `authenticated`, `service_role`
-- and `supabase_admin`, but not the per-service owners GoTrue, PostgREST and
-- Storage expect - those are created by Supabase's own provisioning, which a
-- plain image start never runs. Without them each service dies on connect with
-- "role does not exist".
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
end $$;

create role authenticator noinherit login password :'pgpass';
grant anon, authenticated, service_role to authenticator;

create role supabase_auth_admin noinherit createrole login password :'pgpass';
create role supabase_storage_admin noinherit createrole login password :'pgpass';

grant anon, authenticated, service_role to postgres;
