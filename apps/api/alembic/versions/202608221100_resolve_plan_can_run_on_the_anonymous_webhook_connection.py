"""Let the anonymous webhook connection read the two tables `resolve_plan` needs.

**What broke, and why only now.** `services/billing.py::_grant_period_credit` -
reached from `handle_event`'s `ACTIVE` transition and renewal branches, which run
on `database.anonymous()` for both the real Dodo webhook and the "Sync with
provider" button - calls `resolve_plan()`, which does two plain (non-`SECURITY
DEFINER`) reads: `org_subscriptions` (`get_latest_for_org`) and
`org_entitlement_overrides` (`get_override_for_org`). Both tables grant `select`
to `authenticated` only (`202608172000`, `202608181100`) - nobody granted `anon`,
because nothing exercised this path against a real gateway with a real, already-
active subscription until now. The result was `InsufficientPrivilegeError:
permission denied for table org_subscriptions`, which - being an uncaught error
inside the same transaction `handle_event` and `mark_event_processed` share -
poisoned the whole request: `mark_event_processed` then failed a second time
with `InFailedSQLTransactionError`, the entire transaction rolled back
(including the subscription's own already-applied status change), and the
request 500'd. A real subscription activation was completely unable to
complete - not just its credit grant - and a webhook redelivery would have
failed identically for the full ten-hour retry window.

**Why granting `select` to `anon` here is safe.** Neither table's `select`
policy special-cases `anon`: `org_subscriptions_select` requires
`has_org_role(org_id, ['owner','admin'])` and
`org_entitlement_overrides_select` requires `is_org_member(org_id) or
platform_can_read(org_id)`, both of which resolve through `auth.uid()` -
`null` for an anonymous session, so both policies still return zero rows for
`anon` exactly as they did before this migration. This closes the "permission
denied" crash, not a data-visibility gap: `anon` still sees nothing, RLS still
does the real work, and the caller (`resolve_plan`) already falls back
correctly on an empty result - the plan id it was handed is the one
`apply_event`/`extend_period` just wrote in the same transaction, so this is
the one call site where "no subscription" is already the right fallback.

Matches the same reasoning `usage_rates`/`provider_tiers` (`202608190900`)
already grant `select` to `authenticated, anon` for - a public rate card is
read on the anonymous pricing route the same way this is read on the anonymous
webhook route; the table's own RLS or absence of tenant scope is what actually
protects it.

Revision ID: d2f8a6c93b17
Revises: c9a3f7e15d84
"""

from __future__ import annotations

from alembic import op

revision = "d2f8a6c93b17"
down_revision = "c9a3f7e15d84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("grant select on public.org_subscriptions to anon")
    op.execute("grant select on public.org_entitlement_overrides to anon")


def downgrade() -> None:
    op.execute("revoke select on public.org_entitlement_overrides from anon")
    op.execute("revoke select on public.org_subscriptions from anon")
