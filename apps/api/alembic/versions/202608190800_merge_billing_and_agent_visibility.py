"""Join the billing branch to the agent-visibility branch.

Empty on purpose. Two lines of work were authored in parallel from
`b6d1e93af472` and both reached a head:

  - `a4d1f8c93e26` - plans, subscriptions, the seat trigger, platform admin
  - `c9f47a1e6b28` - invitation preview, agent delete, the per-creator agent silo

Alembic refuses `upgrade head` with two heads present, so they need an explicit
join. This is that join and nothing else: a merge revision that also did work
would make `alembic history` claim the branches met inside a feature, and the
next person bisecting a schema problem would have to read the file to find out
otherwise.

**Checked for real conflict before merging, since the two branches do touch one
table.** `c9f47a1e6b28` drops and recreates `voice_agents_select`; the billing
branch added a *separate* `voice_agents_platform_read` policy rather than editing
the existing qual, precisely so the two could not collide. Postgres ORs permissive
policies, so both survive and neither side's intent is lost - which is the payoff
for not having rewritten 17 quals by hand.

Revision ID: d7c3b8e21a94
Revises: a4d1f8c93e26, c9f47a1e6b28
"""

from __future__ import annotations

revision = "d7c3b8e21a94"
down_revision = ("a4d1f8c93e26", "c9f47a1e6b28")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Nothing to do. The join is the revision."""


def downgrade() -> None:
    """Splitting back into two heads is what dropping this row does."""
