# Running the RLS tests against a throwaway Postgres

`tests/test_rls_isolation.py` skips itself when `DATABASE_URL` is unset, which is
every CI run and most local ones. That means the checks `CLAUDE.md` §7 calls the
most expensive bug class available here - a policy that looks right and permits a
cross-tenant read - normally never execute.

This directory makes them runnable in about a minute, against a disposable local
cluster. **Never point them at the shared Supabase instance**: they create and
delete `auth.users` rows.

`supabase_shim.sql` is the minimum Supabase surface the migrations reference -
`auth.users`, `auth.uid()`, `storage.buckets`/`storage.objects`, and the
`anon`/`authenticated`/`service_role` roles. It is not a Supabase replica, only
enough for the schema to apply and the policies to evaluate.

## Setup

```bash
export PGDATA=/tmp/callflow-pg          # anywhere disposable
initdb -D "$PGDATA" -U postgres --auth=trust -E UTF8
pg_ctl -D "$PGDATA" -o "-p 55432 -c listen_addresses=127.0.0.1" -l /tmp/pg.log start

export PGPASSWORD=postgres
psql -h 127.0.0.1 -p 55432 -U postgres -d postgres -c "create database callflow_test"
psql -h 127.0.0.1 -p 55432 -U postgres -d callflow_test -v ON_ERROR_STOP=1 \
  -f apps/api/tests/local_postgres/supabase_shim.sql

export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:55432/callflow_test"
export DIRECT_URL="$DATABASE_URL"
(cd apps/api && alembic upgrade head)

# Supabase's own bootstrap grants anon table-level SELECT and relies on RLS to
# return zero rows. Replicate that, or `test_anonymous_sees_nothing` fails with a
# permission error instead of the empty result it asserts.
psql -h 127.0.0.1 -p 55432 -U postgres -d callflow_test \
  -c "grant select on all tables in schema public to anon;"
```

## Run

```bash
cd apps/api && pytest -q            # 212 passed, 0 skipped
```

Without `DATABASE_URL` the same command gives `163 passed, 49 skipped`.

## Tear down

```bash
pg_ctl -D "$PGDATA" stop && rm -rf "$PGDATA"
```

## Known fidelity gaps

The shim is deliberately thin. It does **not** reproduce Supabase's default
privileges, its GoTrue triggers beyond the one this schema installs, or
`storage`'s real column set. If a test depends on Supabase behaviour not modelled
here, it belongs against a real Supabase branch instead - add the gap to this list
rather than widening the shim until it pretends to be something it isn't.
