"""agent_creators_can_delete_their_own_agents

`voice_agents_delete` allowed only an owner or admin, while `voice_agents_insert`
has always allowed an operator - so an operator could build an agent and then had
no way to remove it, including the ones they had just created themselves. The
only route out was asking an admin (`ISSUES.md` #129).

The policy now matches the one `channels_delete`-style rules elsewhere in this
schema already use: an owner or admin may remove any agent in the organisation,
and everyone else may remove the ones they created. `created_by` has been on the
table since `202608151200`, so no backfill is needed - rows written before it
existed have `created_by is null` and are deletable by owners and admins only,
which is the safe side to land on.

Update is deliberately left alone. `voice_agents_update` still lets any operator
edit any agent in the organisation, which is a real asymmetry - you may edit a
colleague's agent but not delete it - and changing it would silently break teams
who share agents on purpose. Worth a decision of its own rather than being folded
into a delete fix.

Revision ID: b6d1e93af472
Revises: f4b2c9e17a35
Created: 2026-08-17 16:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b6d1e93af472"
down_revision: str | None = "f4b2c9e17a35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


NEW_POLICY = """
drop policy if exists voice_agents_delete on public.voice_agents;

create policy voice_agents_delete on public.voice_agents for delete using (
  public.has_org_role(org_id, array['owner','admin']::public.org_role[])
  or created_by = public.current_user_id()
);
"""

OLD_POLICY = """
drop policy if exists voice_agents_delete on public.voice_agents;

create policy voice_agents_delete on public.voice_agents for delete using (
  public.has_org_role(org_id, array['owner','admin']::public.org_role[])
);
"""


def upgrade() -> None:
    op.execute(NEW_POLICY)


def downgrade() -> None:
    op.execute(OLD_POLICY)
