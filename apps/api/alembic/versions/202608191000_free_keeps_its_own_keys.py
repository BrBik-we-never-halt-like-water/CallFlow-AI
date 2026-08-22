"""Free keeps its own vendor keys, because CallFlow has none to lend.

The previous revision seeded Free with `max_ai_integrations = 0` and
`may_bring_own_keys = false`, implementing a decision to make Free managed-only.
**That decision is not implementable yet and this reverts the data half of it.**

Every STT/TTS/LLM key a call uses is read from `ai_provider_credentials` - the
organisation's own table. There is no platform-owned credential in `config`, no
fallback in the voice worker's `AgentSpec`, and no code path that could supply
one. So zero own-keys on Free does not make Free *managed*; it makes Free
**undialable**, which `test_free_can_connect_at_least_one_model_provider` has
asserted since long before any of this billing work.

Written as a forward revision rather than by editing the previous one, because
that revision is already applied to a database. Editing an applied migration
leaves every environment that ran it in a state the file no longer describes.

`max_managed_tier = 'economy'` stays as it is. It caps what Free may run **on
CallFlow's keys**, nothing runs on CallFlow's keys, so it is dormant and correct -
and it becomes live on the same day `may_bring_own_keys = false` becomes possible.

Revision ID: e8a4d1c72b56
Revises: b5e2c7a94f31
"""

from __future__ import annotations

from alembic import op

revision = "e8a4d1c72b56"
down_revision = "b5e2c7a94f31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        update public.plan_entitlements
           set max_ai_integrations = 2,
               may_bring_own_keys = true
         where plan_id = 'free'
        """
    )


def downgrade() -> None:
    """Deliberately not restoring the undialable state. A downgrade that
    reinstates a known-broken plan is a downgrade nobody should be able to run by
    accident; the previous revision's own downgrade drops these columns entirely,
    which is the honest way back."""
