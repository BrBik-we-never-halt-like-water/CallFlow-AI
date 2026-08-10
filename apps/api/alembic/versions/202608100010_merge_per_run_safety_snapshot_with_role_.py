"""merge per-run safety snapshot with role-handling branch

Revision ID: 3b49e0225646
Revises: a3f7c9e2b6d8, f3d8a1c6e492
Created: 2026-08-10 00:10:32.653321
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '3b49e0225646'
down_revision: str | None = ('a3f7c9e2b6d8', 'f3d8a1c6e492')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
