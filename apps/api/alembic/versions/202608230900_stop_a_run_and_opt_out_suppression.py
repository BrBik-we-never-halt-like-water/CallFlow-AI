"""stop_a_run_and_opt_out_suppression

Two gaps in the Runs / "needs a person" pair, both of which need a column
before any code can close them.

**1. A run could not be stopped.** Once `POST /api/v1/runs` returned, the
dispatcher dialled every contact and nothing could interrupt it. The obvious
fix - an in-process cancellation flag - does not work here: the dispatcher runs
in `BackgroundTasks` on whichever uvicorn worker served the start request, and
the stop request lands on whichever worker the load balancer picks. The signal
has to be somewhere both workers can see, which means the database.

`stop_requested_at` is that signal, and it is deliberately a *request* rather
than a status flip. A stop does not end a run: calls already in conversation
keep going and report back normally, because hanging up on someone mid-sentence
to satisfy a button is a worse outcome for the person on the phone than letting
their call finish. The run stays `running` (rendered "Stopping…") until the last
live call settles, and only then closes - as `stopped`, not `completed`, because
a run that dialled 12 of 50 contacts did not complete (CLAUDE.md non-negotiable
#9).

That fourth status is why `runs.status` gains a check constraint it never had.
Three values were only ever a convention, and adding a fourth by convention is
how a typo becomes a run nobody can query. The constraint mirrors
`domain/run_state.py`'s enum exactly, the same way
`telephony_numbers_status_check` mirrors `domain/numbers.py`.

**2. A `do_not_call` never reached the suppression list.** Triage has always
detected it and escalated, but the completion callback receives only
`contact_name` and `phone_masked` - and a masked number cannot be hashed, so
there was nothing to write to `suppressions.phone_hash`. Somebody had to notice
the disposition and re-type the number by hand, which is a promise held by
vigilance rather than by the system.

`call_outcomes.phone_hash` closes that without storing a dialable number
anywhere new. The dialler has the real E.164 and already computes this exact
hash for the suppression *check*; persisting it means the callback can write the
suppression row from the hash alone. `suppressions` is keyed on
`(org_id, phone_hash)` and its `phone_e164` column is already nullable, so an
auto-suppression is a complete, enforceable row with no plaintext number in it.
The value is a SHA-256 over the number plus the per-deployment pepper, which is
the same thing `suppressions` has stored since the initial schema - this adds no
class of data the database did not already hold.

Nullable with no backfill: rows written before this migration were dialled by a
process that never computed the hash, and inventing one is not possible without
the number. They read as null, which is what they are - an opt-out on one of
those still has to be added by hand, and the honest UI says so.

Revision ID: f3c7b21a9d04
Revises: ce1d5fc1faef
Created: 2026-08-23 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3c7b21a9d04"
down_revision: str | None = "ce1d5fc1faef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: Mirrors `domain.run_state.RunStatus`. Both move together or the application
#: and the database disagree about what a run can be.
_RUN_STATUSES = ("running", "completed", "failed", "stopped")


def upgrade() -> None:
    op.add_column(
        "runs",
        sa.Column("stop_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.add_column(
        "runs",
        sa.Column("stopped_by", sa.UUID(), nullable=True),
        schema="public",
    )
    op.create_foreign_key(
        "runs_stopped_by_fkey",
        "runs",
        "users",
        ["stopped_by"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="SET NULL",
    )

    # Safe to add without a data fix: `finish_run`/`finish_if_all_settled` have
    # only ever written these three, and the column's own server default is
    # 'running'. Verified against the constraint rather than assumed - a row
    # outside the set would fail the ALTER loudly here rather than silently
    # later.
    op.create_check_constraint(
        "runs_status_check",
        "runs",
        "status in ({})".format(", ".join(f"'{s}'" for s in _RUN_STATUSES)),
        schema="public",
    )

    # Partial: the reconciler and the dialler's stop check both ask "is this
    # run still open", never "which runs are stopped", so indexing the closed
    # majority would pay for rows nothing reads.
    op.create_index(
        "runs_open_idx",
        "runs",
        ["org_id"],
        unique=False,
        schema="public",
        postgresql_where=sa.text("finished_at is null"),
    )

    op.add_column(
        "call_outcomes",
        sa.Column("phone_hash", sa.String(length=64), nullable=True),
        schema="public",
    )
    # Same shape as `suppressions_hash_length`, and for the same reason: a
    # truncated hash would silently never match a suppression row, so a
    # do-not-call would look recorded and enforce nothing.
    op.create_check_constraint(
        "call_outcomes_phone_hash_length",
        "call_outcomes",
        "phone_hash is null or length(phone_hash) = 64",
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "call_outcomes_phone_hash_length", "call_outcomes", schema="public", type_="check"
    )
    op.drop_column("call_outcomes", "phone_hash", schema="public")

    op.drop_index("runs_open_idx", table_name="runs", schema="public")
    op.drop_constraint("runs_status_check", "runs", schema="public", type_="check")
    # A run stopped while this revision was applied has a status the older
    # constraint-free column tolerates but the older *code* does not understand,
    # so it is folded into the closest thing that predates it. `completed` would
    # claim the run finished its list; `failed` is the honest one - it did not.
    op.execute("update public.runs set status = 'failed' where status = 'stopped'")
    op.drop_constraint("runs_stopped_by_fkey", "runs", schema="public", type_="foreignkey")
    op.drop_column("runs", "stopped_by", schema="public")
    op.drop_column("runs", "stop_requested_at", schema="public")
