# Running the tenant-isolation tests

`tests/test_rls_isolation.py` and the other database-backed suites skip
themselves when `DATABASE_URL` is unset - which is every CI run. They are also
the tests that matter most: a policy that looks right and permits a cross-tenant
read is the most expensive bug this product can ship.

Setup moved to the repo root, so there is one path rather than two:

    npm run dev:db

See **DEV_SETUP.md §3 and §6** for the whole flow, including how to run the
suite against it and what the Supabase shim does and does not cover.

The shim itself lives at `scripts/local-db/supabase-shim.sql`.

**Never point these at a shared Supabase project.** They create and delete
`auth.users` rows - doing that against production is part of how `ISSUES.md` #80
happened.
