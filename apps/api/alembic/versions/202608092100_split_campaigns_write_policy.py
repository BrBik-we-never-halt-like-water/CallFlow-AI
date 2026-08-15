"""split_campaigns_write_policy

Role-based UI roadmap, Phase 1 follow-up: `campaigns_write` was declared
`for all` (covering select/insert/update/delete in one policy). Postgres
combines multiple permissive policies for the same command with OR, so that
`for all` policy's role-only check - true for any operator in the org - was
also being consulted for SELECT, silently re-granting every operator full
org-wide campaign visibility and defeating `campaigns_select`'s new
per-creator narrowing (migration 202608092000) for every operator, not just
the campaign's own creator.

`runs` and `call_outcomes` never had this problem because their write
policies were already split per command (`runs_insert`, `runs_update`,
`call_outcomes_insert`, `call_outcomes_update`) from their original
migration (202608070900) - `campaigns_write` was the one table using `for
all`. Caught by the new cross-member test in `test_rls_isolation.py`
(`test_operator_cannot_see_a_teammates_campaign`), which failed against the
live database until this fix.

Splitting into `campaigns_insert`/`campaigns_update`/`campaigns_delete`,
each scoped to its own command, removes the accidental SELECT grant. The
role check itself is unchanged (`owner`, `admin`, `operator` - same as
before), so this is not a new restriction on paper - but for UPDATE and
DELETE specifically, Postgres also intersects the command's own USING
clause with any applicable SELECT policy's USING clause (confirmed against
the live database before writing this migration), so an operator's
update/delete reach now automatically narrows to campaigns they created,
matching campaigns_select and, more importantly, matching the actual
product spec ("no other teammates campaign, nothing" for an operator) -
INSERT is unaffected by this intersection (there is no existing row to
combine against), so it stays role-only exactly as it always was; forging
`created_by` on insert is a pre-existing gap this migration does not widen
and is out of scope for the visibility work here.

Revision ID: 9b6e1c3a7f42
Revises: d4bcc27a2b70
Created: 2026-08-09 21:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "9b6e1c3a7f42"
down_revision: str | None = "d4bcc27a2b70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SPLIT_POLICIES = """
drop policy if exists campaigns_write on public.campaigns;

create policy campaigns_insert on public.campaigns for insert
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy campaigns_update on public.campaigns for update
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));

create policy campaigns_delete on public.campaigns for delete
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));
"""

MERGED_POLICY = """
drop policy if exists campaigns_insert on public.campaigns;
drop policy if exists campaigns_update on public.campaigns;
drop policy if exists campaigns_delete on public.campaigns;

create policy campaigns_write on public.campaigns for all
  using (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[]));
"""


def upgrade() -> None:
    op.execute(SPLIT_POLICIES)


def downgrade() -> None:
    op.execute(MERGED_POLICY)
