"""lead_grading_columns_and_taxonomy_config

The schema half of the graded-lead model - `docs/GRADING.md` §8, task H7.

Additive on purpose. `disposition` stays exactly where it is and keeps being
written; these columns land beside it, get backfilled with what can honestly be
inferred, and `disposition` is dropped only in a later revision once
`grep -rn "disposition" apps/` comes back clean (§8 steps 1-5). Nothing here
reads or breaks on the old column.

**The backfill does not invent grades.** `result` is inferred from the provider
`status` the row already carries, which is the same fact `CallResult` describes;
`grade` is set to `ungraded` for rows we actually spoke to and left null
everywhere else. A historical row was produced by a rule answering a different
question ("does this need a human?"), so any grade derived from it would be
fiction - and a fabricated `cold` poisons the first decline report, which is the
half of the product a floor cannot produce for itself (`docs/GRADING.md` §8
step 2, §2.2).

`org_grading_config` is tenant-scoped, so it ships with all four parts in this
one revision per CLAUDE.md §4b: `org_id NOT NULL` + FK + index · enable *and*
force RLS · a policy per operation · a grant for `authenticated`. The RLS is
hand-written because autogenerate cannot see it.

Revision ID: a1c4e8b73f29
Revises: f3c7b21a9d04
Created: 2026-09-17 11:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1c4e8b73f29"
down_revision: str | None = "f3c7b21a9d04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Text plus a CHECK rather than a Postgres enum type, matching how
# `runs.status` and `call_outcomes.disposition` already work here. The
# taxonomy is expected to be wrong in places come January (`docs/GRADING.md`
# §9), and altering a check is a migration; altering a pg enum in use is a
# migration plus a rewrite.
_RESULTS = "'in_flight','spoke','no_answer','busy','voicemail','invalid_number','failed','suppressed'"
_GRADES = "'hot','warm','cold','refused','wrong_person','ungraded'"
_NEXT_ACTIONS = "'call_now','call_at','nurture','drop','suppress','fix_data'"
_DECLINE_REASONS = (
    "'already_enrolled_elsewhere','price_or_emi','degree_validity_doubt',"
    "'wrong_programme','no_time','employer_wont_sponsor','still_deciding',"
    "'language_barrier','do_not_contact','other'"
)

CHECKS = f"""
alter table public.call_outcomes
  add constraint call_outcomes_result_check
  check (result is null or result in ({_RESULTS}));
alter table public.call_outcomes
  add constraint call_outcomes_grade_check
  check (grade is null or grade in ({_GRADES}));
alter table public.call_outcomes
  add constraint call_outcomes_next_action_check
  check (next_action is null or next_action in ({_NEXT_ACTIONS}));
alter table public.call_outcomes
  add constraint call_outcomes_decline_reason_check
  check (decline_reason is null or decline_reason in ({_DECLINE_REASONS}));

-- §1: only a call we actually spoke on carries a grade. Without this the
-- promise is a convention, and a convention is what produced a model where
-- "unreachable" and "not interested" shared an enum.
alter table public.call_outcomes
  add constraint call_outcomes_grade_requires_spoke
  check (grade is null or result = 'spoke');
"""


# Inferred from the provider status the row already carries, not from
# `disposition` - `status` is the same fact `CallResult` describes, while
# `disposition` is a decision about it.
BACKFILL = """
update public.call_outcomes set result = case
    when disposition = 'in_flight'      then 'in_flight'
    -- `skipped` only ever meant the suppression gate, which is the one guard
    -- `check_dial_allowed()` still has (CLAUDE.md §4.8).
    when disposition = 'skipped'        then 'suppressed'
    when upper(status) = 'COMPLETED'    then 'spoke'
    when upper(status) = 'BUSY'         then 'busy'
    when upper(status) = 'NO_ANSWER'    then 'no_answer'
    when upper(status) = 'VOICEMAIL'    then 'voicemail'
    when upper(status) in ('FAILED','CANCELED','CANCELLED','EXPIRED','DECLINED') then 'failed'
    else 'failed'
  end
  where result is null;

-- Spoke to them, but under a rule asking a different question. `ungraded` is
-- the honest answer and the one §2.2 reserves for exactly this.
update public.call_outcomes set grade = 'ungraded'
  where grade is null and result = 'spoke';

-- §4.1a, plus rule 4's FIX_DATA for the ungraded rows above.
update public.call_outcomes set next_action = case
    when result in ('no_answer','busy')        then 'call_now'
    when result = 'voicemail'                  then 'nurture'
    when result = 'suppressed'                 then 'suppress'
    when result in ('invalid_number','failed') then 'fix_data'
    when result = 'spoke'                      then 'fix_data'
  end
  where next_action is null and result <> 'in_flight';
"""


POLICIES = """
alter table public.org_grading_config enable row level security;
alter table public.org_grading_config force  row level security;

create policy org_grading_config_select on public.org_grading_config for select
  using (public.is_org_member(org_id));

-- Thresholds decide what a customer is billed for as a qualified lead, so
-- writing them is an owner/admin act, not an operator one
-- (`docs/GRADING.md` §7, constraint 2).
create policy org_grading_config_insert on public.org_grading_config for insert
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
create policy org_grading_config_update on public.org_grading_config for update
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))
  with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]));
"""

GRANTS = "grant select, insert, update on public.org_grading_config to authenticated;"

TOUCH_TRIGGER = """
create trigger org_grading_config_touch_updated_at before update on public.org_grading_config
  for each row execute function public.touch_updated_at();
"""


def upgrade() -> None:
    for column in (
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("grade", sa.Text(), nullable=True),
        sa.Column("grade_reason", sa.Text(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("callback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("decline_note", sa.Text(), nullable=True),
        sa.Column("handoff_brief", sa.Text(), nullable=True),
        sa.Column("human_verdict", sa.Boolean(), nullable=True),
    ):
        op.add_column("call_outcomes", column, schema="public")

    op.execute(BACKFILL)
    op.execute(CHECKS)

    # org_id leads every index: RLS scopes every read to one organisation, so
    # an index that does not start there makes the planner filter what it
    # could have skipped. Y9 tunes these against EXPLAIN at 5,000 rows.
    op.create_index(
        "call_outcomes_org_grade_idx", "call_outcomes", ["org_id", "grade"], schema="public"
    )
    op.create_index(
        "call_outcomes_org_decline_reason_idx",
        "call_outcomes",
        ["org_id", "decline_reason"],
        schema="public",
    )
    op.create_index(
        "call_outcomes_org_result_idx", "call_outcomes", ["org_id", "result"], schema="public"
    )

    op.create_table(
        "org_grading_config",
        sa.Column("org_id", sa.UUID(), nullable=False),
        # Null means "any stated budget qualifies" - a ₹12L programme and a
        # ₹40k certificate do not share a floor (`docs/GRADING.md` §7).
        # Paise, BIGINT, never a float (CLAUDE.md §4.3).
        sa.Column("budget_floor_paise", sa.BigInteger(), nullable=True),
        sa.Column(
            "required_fields",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{intent,is_decision_maker,identity_confirmed}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "enabled_decline_reasons",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text(
                "'{already_enrolled_elsewhere,price_or_emi,degree_validity_doubt,"
                "wrong_programme,no_time,employer_wont_sponsor,still_deciding,"
                "language_barrier,do_not_contact,other}'::text[]"
            ),
            nullable=False,
        ),
        sa.Column(
            "intake_horizon_months", sa.Integer(), server_default=sa.text("12"), nullable=False
        ),
        sa.Column(
            "emi_qualifies_alone", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        # `intent` is a floor, not a default: drop it and rule 4 stops firing,
        # so every unreadable call falls through to the terminal arm and the
        # whole run reads as an extraction failure (`docs/GRADING.md` §7).
        sa.CheckConstraint(
            "'intent' = any(required_fields)",
            name="org_grading_config_intent_required",
        ),
        sa.CheckConstraint(
            "budget_floor_paise is null or budget_floor_paise > 0",
            name="org_grading_config_budget_floor_positive",
        ),
        sa.CheckConstraint(
            "intake_horizon_months > 0",
            name="org_grading_config_horizon_positive",
        ),
        sa.ForeignKeyConstraint(["org_id"], ["public.organisations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("org_id"),
        schema="public",
    )
    # The primary key already indexes org_id; named here so the four-part
    # checklist is visibly satisfied rather than satisfied by accident.
    op.create_index(
        "org_grading_config_org_idx", "org_grading_config", ["org_id"], schema="public"
    )

    op.execute(POLICIES)
    op.execute(GRANTS)
    op.execute(TOUCH_TRIGGER)


def downgrade() -> None:
    op.execute(
        "drop trigger if exists org_grading_config_touch_updated_at on public.org_grading_config"
    )
    op.execute("drop policy if exists org_grading_config_select on public.org_grading_config")
    op.execute("drop policy if exists org_grading_config_insert on public.org_grading_config")
    op.execute("drop policy if exists org_grading_config_update on public.org_grading_config")
    op.drop_index("org_grading_config_org_idx", table_name="org_grading_config", schema="public")
    op.drop_table("org_grading_config", schema="public")

    op.drop_index("call_outcomes_org_result_idx", table_name="call_outcomes", schema="public")
    op.drop_index(
        "call_outcomes_org_decline_reason_idx", table_name="call_outcomes", schema="public"
    )
    op.drop_index("call_outcomes_org_grade_idx", table_name="call_outcomes", schema="public")

    for constraint in (
        "call_outcomes_grade_requires_spoke",
        "call_outcomes_decline_reason_check",
        "call_outcomes_next_action_check",
        "call_outcomes_grade_check",
        "call_outcomes_result_check",
    ):
        op.execute(f"alter table public.call_outcomes drop constraint if exists {constraint}")

    for column in (
        "human_verdict",
        "handoff_brief",
        "decline_note",
        "decline_reason",
        "callback_at",
        "next_action",
        "grade_reason",
        "grade",
        "result",
    ):
        op.drop_column("call_outcomes", column, schema="public")
