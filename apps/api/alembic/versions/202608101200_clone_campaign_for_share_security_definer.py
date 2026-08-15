"""clone_campaign_for_share_security_definer

Found by manually walking through the approve-a-campaign-share-request flow
end to end (not by static review): `campaigns_repo.create_campaign()`'s
`INSERT ... RETURNING` failed with `InsufficientPrivilegeError: new row
violates row-level security policy for table "campaigns"` whenever the
approver (the original campaign's owner) isn't owner/admin/viewer -
i.e. exactly the common case, an operator approving another operator's
request for their own campaign.

Root cause: `campaigns_insert`'s `WITH CHECK` is role-only
(`has_org_role(org_id, [owner,admin,operator])`) and correctly lets an
operator insert the cloned row - but Postgres also evaluates the `SELECT`
policy (`campaigns_select`) against any row returned via `RETURNING`, and
raises the same "violates row-level security policy" error if that check
fails. `campaigns_select` for an operator is `created_by = self` (no
broader role branch) - and the clone's `created_by` is the *requester*
(the other operator), not the approver running the INSERT. An operator can
therefore insert the row (the write policy allows it) but can never legally
see it back (the read policy doesn't), and `RETURNING` demands both.

Same shape as `create_organisation()`/`remove_member_and_reassign_data()`
(migrations `a7c2e5f9b184`, `202608092600`): a narrowly-scoped `SECURITY
DEFINER` function is the established fix in this codebase whenever an
action needs to write a row on someone else's behalf. The unique-slug
dedup logic stays in Python (`sharing.py::_clone_campaign`, unchanged) -
only the actual privileged INSERT moves into the function, taking an
already-deduplicated id as an argument rather than recomputing one itself.

Revision ID: b938fa82e54d
Revises: bf7c636e014d
Created: 2026-08-10 12:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b938fa82e54d"
down_revision: str | None = "bf7c636e014d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FUNCTION = """
create or replace function public.clone_campaign_for_share(
  source_org uuid, source_campaign_id text, new_campaign_id text, new_owner uuid
)
returns void language plpgsql security definer
set search_path = public, pg_temp as $$
declare
  src record;
begin
  if not public.is_org_member(source_org) then
    raise exception 'not a member of this organisation';
  end if;

  select * into src from public.campaigns
    where org_id = source_org and id = source_campaign_id;
  if src is null then
    raise exception 'source campaign not found';
  end if;

  insert into public.campaigns
    (id, org_id, name, goal_template, outcome_fields, result_schema,
     region, language, escalate_on_negative, created_by)
  values
    (new_campaign_id, source_org, src.name || ' (shared)', src.goal_template,
     src.outcome_fields, src.result_schema, src.region, src.language,
     src.escalate_on_negative, new_owner);
end;
$$;
"""


def upgrade() -> None:
    op.execute(FUNCTION)


def downgrade() -> None:
    op.execute("drop function if exists public.clone_campaign_for_share(uuid, text, text, uuid)")
