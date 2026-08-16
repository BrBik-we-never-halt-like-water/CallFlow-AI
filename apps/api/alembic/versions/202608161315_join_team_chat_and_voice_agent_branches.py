"""join team chat and voice agent branches

Two feature branches added a migration on top of `b938fa82e54d` in parallel -
`b3f7d2a891c5` (team chat: channels, channel_members, messages) and
`a1c48e7f2b93` (the Agentic tab: ai_provider_credentials, voice_agents). Both
were correct in isolation, which left Alembic with two heads and no way to
resolve a bare `upgrade head`.

This revision only joins the two lineages. It creates nothing and drops nothing:
the two branches touch disjoint tables, so neither ordering changes the result,
and there is no schema work left for a merge point to do.

Revision ID: 6b4221f5c333
Revises: b3f7d2a891c5, a1c48e7f2b93
Created: 2026-08-16 13:15:10.075748
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "6b4221f5c333"
down_revision: tuple[str, ...] | None = ("b3f7d2a891c5", "a1c48e7f2b93")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
