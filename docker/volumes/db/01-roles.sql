-- `postgres`, the one role the image never creates with the attributes we need.
--
-- **Create nothing else here.** The image's own `init-scripts/` create
-- `anon`, `authenticated`, `service_role`, `authenticator`,
-- `supabase_auth_admin`, `supabase_storage_admin`, `supabase_functions_admin`,
-- `dashboard_user` and `pgbouncer` - every one of them *unguarded*, spread
-- across four files. Those scripts are run by the image's `migrate.sh`, which
-- the entrypoint executes after this file (`m` sorts after any digit; the
-- `init-scripts` directory itself is skipped). So a role created here is a role
-- that already exists when the image tries to create it, and the image's script
-- aborts on "role already exists".
--
-- That abort is expensive and its cause is nowhere near its symptom.
-- ON_ERROR_STOP means the failure stops `migrate.sh` mid-way, so every later
-- script is skipped - `auth.users` is never built, GoTrue crash-loops on a
-- schema that is half there, and `/etc/postgresql.schema.sql`
-- (`03-post-init.sql`) never runs at all.
--
-- **`postgres` is the exception, and only just.** The image runs initdb as
-- `supabase_admin`, so a bare container has no `postgres` role - while hosted
-- Supabase does, and this repo's `DATABASE_URL` and `privileged.py` both depend
-- on it. `migrate.sh` does create it, but guarded and *without* BYPASSRLS;
-- creating it first, with the attribute, is what makes a local database behave
-- like the hosted one rather than subtly differently - and because its own
-- creation is guarded, it defers to ours instead of colliding.
--
-- The guard also lets a re-run against an existing volume fall through to the
-- password reset below rather than failing.

\set pgpass `echo "$POSTGRES_PASSWORD"`

do $$ begin
  -- BYPASSRLS deliberately, matching hosted Supabase: CLAUDE.md §4b's whole
  -- account of why RLS is only real through `database.as_user()` rests on this
  -- role having it. A local database without it would pass tests the hosted one
  -- fails.
  if not exists (select 1 from pg_roles where rolname = 'postgres') then
    create role postgres superuser createdb createrole login bypassrls;
  end if;
end $$;

-- Password outside the guard so a re-run resets it to whatever the current
-- .env says, rather than leaving a stale one nobody can explain. The service
-- owners' passwords are set in `03-post-init.sql`, after the image makes them.
alter role postgres password :'pgpass';

-- `authenticator`'s password and the role grants live in `03-post-init.sql`,
-- mounted at the `/etc/postgresql.schema.sql` hook: both need `anon`,
-- `authenticated`, `service_role` and `authenticator`, which the image's own
-- scripts do not create until `migrate.sh` runs after this file.
