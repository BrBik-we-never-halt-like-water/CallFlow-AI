"""Let an organisation choose which agents stay active when it is over its limit.

Until now `check_agent_create_allowed` guarded only *creating* an agent, so the
limit was a one-time toll rather than an entitlement: subscribe for a month,
create ten agents, downgrade to Free, keep using all ten forever.

The excess is now **locked, never deleted**. An agent is a configuration row -
making it unusable destroys nothing and it returns the moment the plan does. That
is deliberately different from a vendor credential, which holds a secret this
product could not recreate, and which `docs/BILLING.md` §3 therefore leaves alone
on a downgrade. That rule was about credentials and had been over-generalised.

`kept_at` records which agents the customer explicitly chose to keep active. It is
a *preference*, not a state:

  - null on every existing row, so nothing changes for anyone until they choose
  - the default without it is oldest-first (`domain/entitlements.usable_agent_ids`),
    because the agent built first is the likeliest to be doing the work
  - it survives an upgrade, so downgrading twice does not ask the same question
    twice

No trigger and no SQL-side guard here, unlike the create limit. This gate refuses
a *run*, and a run only ever starts through `POST /api/v1/runs` - there is no
second write path to bypass it, so a database trigger would have nothing to catch.

Revision ID: c4e7f2b81d63
Revises: f1b6a3d94c72
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c4e7f2b81d63"
down_revision = "f1b6a3d94c72"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "voice_agents",
        sa.Column("kept_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("voice_agents", "kept_at")
