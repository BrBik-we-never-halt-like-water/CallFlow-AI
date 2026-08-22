"""Join the credential-verification branch to the billing branch.

Two branches each added a revision on top of `e5c9d02a7f31` and both landed on
`dev`, which leaves two heads. `alembic upgrade head` refuses to choose between
them, and the CI guard in `ci-cd.yml` fails the build rather than letting a
half-applied schema reach the VM - so the join has to be a real revision.

- `0df78584cc38` is billing's own merge (PR #40), itself joining the
  channel-pin-and-order and credit-allocation-retirement lines.
- `d1a83c5f27e6` adds `provider_credentials.verified_at`.

Nothing to do in either direction: the two touch different tables and neither
depends on the other, so the join *is* the revision. Dropping this row splits the
history back into two heads, which is what a downgrade past a merge means.

Worth recording, because it is the thing that broke: the `dev` **database** was
already stamped at `0df78584cc38` before PR #40 merged - someone ran
`alembic upgrade head` from the billing branch against it. So `dev`'s code was
missing a revision its own database claimed to be at, and `alembic upgrade head`
failed with "Can't locate revision identified by '0df78584cc38'" for every
api-touching push. It went unnoticed because the pushes before it were web-only,
and the `migrate` job is gated on `changes.outputs.api`, so it had been skipped
rather than failing. Applying an unmerged branch's migrations to a shared
database is what set that up; merging the branch is what clears it.

Revision ID: ce1d5fc1faef
Revises: 0df78584cc38, d1a83c5f27e6
Created: 2026-08-22 19:34:03.398796
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "ce1d5fc1faef"
down_revision: str | None = ("0df78584cc38", "d1a83c5f27e6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Nothing to do. The join is the revision."""


def downgrade() -> None:
    """Splitting back into two heads is what dropping this row does."""
