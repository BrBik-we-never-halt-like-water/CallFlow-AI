"""voice agents: the fields an agent collects during a call

An agent's job is not only to talk - it is to come back with data. This adds
`collect_fields`, the list of things the agent should establish while the call
is happening, in the same shape campaigns already use for `extra_fields`
(`app/domain/result_schemas.py`): a key, a type, a description the model reads,
and whether the call is incomplete without it.

Reusing that shape rather than inventing a second one matters because both
eventually feed the same triage step - a result is a result whether the call
came from a campaign or from an agent, and two field formats would mean two
validators.

No RLS work here: `voice_agents` already has `org_id`, its policies, and its
grants from `a1c48e7f2b93`. Adding a column to an existing table inherits all
of it.

Revision ID: c7d3e91a4f28
Revises: a1c48e7f2b93
Created: 2026-08-16 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d3e91a4f28"
down_revision: str | None = "a1c48e7f2b93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "voice_agents",
        sa.Column(
            "collect_fields",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        schema="public",
    )
    # An agent collects a list of fields or it collects nothing; a bare object
    # or a string here would reach the model as malformed instructions.
    op.create_check_constraint(
        "voice_agents_collect_fields_is_array",
        "voice_agents",
        "jsonb_typeof(collect_fields) = 'array'",
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "voice_agents_collect_fields_is_array",
        "voice_agents",
        schema="public",
        type_="check",
    )
    op.drop_column("voice_agents", "collect_fields", schema="public")
