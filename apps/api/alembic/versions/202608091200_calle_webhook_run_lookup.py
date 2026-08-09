"""calle_webhook_run_lookup

The CALL-E webhook receiver (module 5 of the CALL-E integration rebuild) has no
signed-in user behind it - CALL-E's server calls this endpoint, not a person
with a session. CLAUDE.md is explicit that `privileged.acquire()` must never
appear in a request handler, so this follows the exact precedent
`lookup_invitation` (202608061530_organisations_invitations_and_storage.py)
already set: `database.anonymous()` calling one narrow SECURITY DEFINER
function that resolves identity, then handing off to the *existing*,
already-RLS-correct `database.as_user()` path for the actual write - no new
RLS-bypassing write path, and no new grant needed (function EXECUTE defaults
to PUBLIC in Postgres unless revoked, and nothing in this project revokes it -
confirmed by `lookup_invitation` having no explicit grant either).

Resolves the run's *starter* deliberately, not just any org member: whoever
started the run already held sufficient permission to (`RUNS_START` requires
operator+, the same floor `call_outcomes_insert`/`_update`'s RLS policies
require). If that person's role was downgraded since, the subsequent
`as_user()` write correctly fails closed via RLS - the safe behaviour, not a
bug this migration needs to work around.

Revision ID: d16508451884
Revises: e15f3d9a2c78
Created: 2026-08-09 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d16508451884"
down_revision: str | None = "e15f3d9a2c78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION = """
create or replace function public.lookup_run_owner_for_webhook(run_id_in text)
returns table(org_id uuid, campaign_id text, auth_user_id uuid)
language plpgsql stable security definer
set search_path = public, pg_temp as $$
begin
  -- The inner join is deliberate: a run with no `started_by` (the column is
  -- nullable) or whose starter's user row is gone has no identity left to
  -- act as - correctly resolves to zero rows, which the caller treats the
  -- same as "unknown run": ack the webhook, don't write anything.
  return query
    select r.org_id, r.campaign_id, u.auth_user_id
    from public.runs r
    join public.users u on u.id = r.started_by
    where r.id = run_id_in;
end;
$$;
"""


def upgrade() -> None:
    op.execute(FUNCTION)


def downgrade() -> None:
    op.execute("drop function if exists public.lookup_run_owner_for_webhook(text) cascade")
