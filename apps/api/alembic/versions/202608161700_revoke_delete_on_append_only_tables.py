"""revoke the delete grant Supabase's default ACL hands back

`telephony_provisioning` is append-only by design: an attempt is re-statused,
never removed, so the record of what was tried survives a retry. Its migration
grants only `select, insert, update` and defines no delete policy.

That is not enough on a Supabase project. `public` carries a default ACL
(`arwdDxtm` to `anon`, `authenticated`, `service_role`) that applies to every
newly created table, so the table ends up with a DELETE grant nobody wrote and
the "no delete grant" half of the guarantee is silently gone. RLS still refuses
the delete - there is no delete policy, so it filters to zero rows - but the
second layer is missing, and a future policy edit would remove the only one
left without anything failing.

Revoking it restores defence in depth: a delete is refused by the grant *and*
by the absence of a policy.

Revision ID: d4a8b3c15e29
Revises: c7d3e91a4f28
Created: 2026-08-16 17:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d4a8b3c15e29"
down_revision: str | None = "c7d3e91a4f28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "revoke delete on public.telephony_provisioning from authenticated, anon"
    )


def downgrade() -> None:
    op.execute("grant delete on public.telephony_provisioning to authenticated")
