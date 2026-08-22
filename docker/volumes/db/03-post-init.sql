-- Wiring between the image's roles and ours, after both exist.
--
-- Mounted at `/etc/postgresql.schema.sql`, NOT into
-- `/docker-entrypoint-initdb.d/`. Everything here needs `anon`,
-- `authenticated`, `service_role` and `authenticator`, which the image creates
-- in `init-scripts/00000000000000-initial-schema.sql` - and that file is run by
-- the image's `migrate.sh`, not by the entrypoint, because the entrypoint sees
-- `init-scripts` as a *directory* and ignores it.
--
-- No filename could work here. The entrypoint globs
-- `/docker-entrypoint-initdb.d/*`, which is an ASCII sort, and every digit
-- sorts before `migrate.sh`'s `m` - so a file in that directory ALWAYS runs
-- before the image's roles exist, and referencing them there fails with
-- "role does not exist", which ON_ERROR_STOP turns into an aborted init and an
-- `auth` schema with no `auth.users` in it. `migrate.sh` runs this path as its
-- very last step, which is the hook the image provides for precisely this.
--
-- `authenticator` is the role PostgREST logs in as before switching to `anon`
-- or `authenticated`. The image creates it NOINHERIT, so it holds no privilege
-- of its own and only ever acts as the role it has switched to; it needs a
-- password because it is the one that actually logs in.

\set pgpass `echo "$POSTGRES_PASSWORD"`

-- The image creates all four of these with no password at all, but every one
-- of them connects over TCP, where a passwordless role cannot authenticate.
alter role authenticator password :'pgpass';
alter role supabase_auth_admin password :'pgpass';
alter role supabase_storage_admin password :'pgpass';
alter role supabase_admin password :'pgpass';

grant anon, authenticated, service_role to authenticator;
grant anon, authenticated, service_role to postgres;

grant usage on schema storage to anon, authenticated, service_role, postgres;

-- Both services migrate into a schema they do not qualify, so the search_path
-- on the role is what decides where their tables land.
alter role supabase_auth_admin set search_path = auth;
alter role supabase_storage_admin set search_path = storage;

-- Storage's own migrator issues `create schema if not exists storage`, and
-- Postgres checks CREATE on the *database* before it evaluates IF NOT EXISTS -
-- so owning the schema is not enough and it fails with "permission denied for
-- database postgres".
grant create on database postgres to supabase_storage_admin;

-- Hand `auth` back to GoTrue, empty.
--
-- The image's `init-scripts/00000000000001-auth-schema.sql` seeds a GoTrue
-- baseline from 2017 - `users`, `refresh_tokens`, `instances`,
-- `audit_log_entries` and a `schema_migrations` already stamped with those old
-- versions - all owned by `postgres`. GoTrue v2 cannot adopt it: it creates its
-- own `schema_migrations` on boot and dies with "relation already exists"
-- (SQLSTATE 42P07), crash-looping forever while the database itself looks fine.
--
-- Dropping the schema here, after the image has finished with it and before
-- GoTrue's first connection, lets GoTrue migrate from empty the way upstream
-- Supabase's own compose does. Nothing of value is lost - it is a fresh volume
-- and these tables have never held a row.
drop schema if exists auth cascade;
create schema auth authorization supabase_auth_admin;
grant usage on schema auth to anon, authenticated, service_role, postgres;

-- Give `postgres` back the privileges the image takes away.
--
-- `init-scripts/00000000000003-post-setup.sql` deliberately demotes `postgres`
-- - `migrate.sh` calls it "postgres user demoted in post-setup" - leaving it
-- NOSUPERUSER with only USAGE on `public`. Hosted Supabase does not: there
-- `postgres` is the role you are given, it owns `public`, and it holds
-- BYPASSRLS. Alembic connects as `postgres`, so without this the very first
-- migration dies on "permission denied for schema public" before it can create
-- `alembic_version`.
--
-- BYPASSRLS matters beyond convenience: CLAUDE.md §4b's account of why RLS is
-- only real through `database.as_user()` assumes `postgres` bypasses it, and
-- `privileged.py` is written against that. A local database where `postgres`
-- did not would pass tenancy tests the hosted one fails.
alter role postgres superuser createdb createrole login bypassrls;
alter schema public owner to postgres;
grant all on schema public to postgres;
