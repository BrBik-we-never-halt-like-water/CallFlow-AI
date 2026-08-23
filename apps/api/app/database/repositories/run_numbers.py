"""SQL for `run_numbers` - which lines a run was allowed to dial from.

Write-once. The table carries `select` and `insert` grants and nothing else
(ADR-8): a run's record of where its calls came from is part of the call history,
so there is no update and no delete to offer. A run that should dial differently
is a new run.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def attach(
    conn: asyncpg.Connection, *, run_id: str, org_id: UUID, number_ids: list[str | UUID]
) -> None:
    """Record the lines this run may use.

    `on conflict do nothing` so a retried start is idempotent (CLAUDE.md #6) -
    the primary key is (run_id, number_id), and re-attaching the same set is a
    no-op rather than an integrity error.
    """
    if not number_ids:
        return
    await conn.executemany(
        """
        insert into public.run_numbers (run_id, number_id, org_id)
        values ($1, $2::uuid, $3)
        on conflict (run_id, number_id) do nothing
        """,
        [(run_id, str(number_id), org_id) for number_id in number_ids],
    )


async def list_for_run(
    conn: asyncpg.Connection, *, run_id: str, org_id: UUID
) -> list[asyncpg.Record]:
    """The numbers a run dialled from, joined for display.

    Left join to `telephony_numbers` rather than inner: the number cannot be
    deleted (no delete grant), but it can be `disabled`, and a retired line must
    still name itself on the runs it placed calls for.
    """
    return list(
        await conn.fetch(
            """
            select rn.number_id, n.phone_e164, n.provider, n.status, n.label
            from public.run_numbers rn
            left join public.telephony_numbers n on n.id = rn.number_id
            where rn.run_id = $1 and rn.org_id = $2
            order by n.provider, n.phone_e164
            """,
            run_id,
            org_id,
        )
    )


__all__ = ["attach", "list_for_run"]
