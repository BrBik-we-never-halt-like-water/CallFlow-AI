"""agents_per_creator_visibility_silo

Extends the per-creator visibility silo of `202608092000` to voice agents. That
migration narrowed campaigns, runs and call_outcomes so an operator sees only
what they created, while owner, admin and viewer keep seeing everything in the
organisation. Voice agents were built afterwards and kept the older, flat
`is_org_member(org_id)` - so every operator could see every colleague's agent.

Product decision, confirmed with the user: an operator has access to their own
agents and no one else's; an admin (and owner) sees everyone's. Viewer follows
`202608092000` and keeps seeing everything, which is what makes it the read-only
oversight role rather than a weaker operator.

Three policies move together, because visibility alone would have been a
half-measure:

* `select` - the reported requirement.
* `update` - previously ANY operator could edit ANY agent in the organisation.
  Left alone, an operator would have been unable to *see* a colleague's agent
  while still being permitted to overwrite one whose id they had. `202608092000`
  could leave its write policies untouched because they were already
  creator-scoped; this one cannot.
* `delete` - already creator-scoped by `b6d1e93af472`, restated here only to add
  the operator role check described below.

Each non-owner branch now also requires the `operator` role rather than just
matching `created_by`. Without it, someone demoted from operator to viewer would
keep write access to the agents they had created, since `created_by` does not
change when a role does. The API blocks that anyway - viewer holds neither
`AGENTS_WRITE` nor `AGENTS_DELETE` - but RLS is the boundary that has to be right
on its own (CLAUDE.md §4b).

`insert` is unchanged: who may create an agent is a role question, and it already
answers it correctly.

Revision ID: c9f47a1e6b28
Revises: b6d1e93af472
Created: 2026-08-17 19:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c9f47a1e6b28"
down_revision: str | None = "b6d1e93af472"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_POLICIES = """
drop policy if exists voice_agents_select on public.voice_agents;
create policy voice_agents_select on public.voice_agents for select
  using (
    public.has_org_role(org_id, array['owner','admin','viewer']::public.org_role[])
    or created_by = public.current_user_id()
  );

drop policy if exists voice_agents_update on public.voice_agents;
create policy voice_agents_update on public.voice_agents for update
  using (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or (
      created_by = public.current_user_id()
      and public.has_org_role(org_id, array['operator']::public.org_role[])
    )
  )
  with check (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or (
      created_by = public.current_user_id()
      and public.has_org_role(org_id, array['operator']::public.org_role[])
    )
  );

drop policy if exists voice_agents_delete on public.voice_agents;
create policy voice_agents_delete on public.voice_agents for delete
  using (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or (
      created_by = public.current_user_id()
      and public.has_org_role(org_id, array['operator']::public.org_role[])
    )
  );
"""

OLD_POLICIES = """
drop policy if exists voice_agents_select on public.voice_agents;
create policy voice_agents_select on public.voice_agents for select
  using (public.is_org_member(org_id));

drop policy if exists voice_agents_update on public.voice_agents;
create policy voice_agents_update on public.voice_agents for update
  using (
    public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[])
  )
  with check (
    public.has_org_role(org_id, array['owner','admin','operator']::public.org_role[])
  );

drop policy if exists voice_agents_delete on public.voice_agents;
create policy voice_agents_delete on public.voice_agents for delete
  using (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    or created_by = public.current_user_id()
  );
"""


def upgrade() -> None:
    op.execute(NEW_POLICIES)


def downgrade() -> None:
    op.execute(OLD_POLICIES)
