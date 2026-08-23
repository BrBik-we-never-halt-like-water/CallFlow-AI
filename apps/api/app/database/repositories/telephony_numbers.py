"""SQL for `telephony_numbers` - the numbers an organisation owns on its carriers.

RLS scopes every query to the caller's org, and the role checks (owner/admin to
write) live in the policies, not here.

There is no `delete`. The table carries no delete grant and no delete policy
(ADR-8): a number that placed real calls is the record of where those calls came
from, so retirement is `status = 'disabled'` and the row stays. `set_status()`
goes through the domain's own transition check, so an illegal move raises rather
than persisting.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

from app.domain.numbers import NumberStatus, check_transition

_COLUMNS = """
    id, org_id, provider, phone_e164, provider_number_ref, label, country,
    capabilities, status, livekit_outbound_trunk_id, livekit_inbound_trunk_id,
    livekit_dispatch_rule_id, carrier_termination_domain, last_error,
    last_synced_at, created_by, created_at, updated_at
"""


async def list_for_org(
    conn: asyncpg.Connection, org_id: UUID, *, provider: str | None = None
) -> list[asyncpg.Record]:
    """Every number this org holds, newest carrier sync first.

    Ordered by provider then number so the picker is stable between loads - an
    ordering that shifts under someone choosing from a list is its own bug.
    """
    if provider:
        return list(
            await conn.fetch(
                f"""
                select {_COLUMNS} from public.telephony_numbers
                where org_id = $1 and provider = $2
                order by provider, phone_e164
                """,
                org_id,
                provider,
            )
        )
    return list(
        await conn.fetch(
            f"""
            select {_COLUMNS} from public.telephony_numbers
            where org_id = $1
            order by provider, phone_e164
            """,
            org_id,
        )
    )


async def list_by_ids(
    conn: asyncpg.Connection, org_id: UUID, ids: list[UUID]
) -> list[asyncpg.Record]:
    """The numbers a run picked.

    Scoped by `org_id` as well as by id even though RLS already scopes it: the
    policy is the guarantee, and this is the statement of intent. A caller
    comparing what it asked for against what came back is how a number belonging
    to another organisation becomes "no longer available" rather than an error
    that confirms the row exists.
    """
    if not ids:
        return []
    return list(
        await conn.fetch(
            f"""
            select {_COLUMNS} from public.telephony_numbers
            where org_id = $1 and id = any($2::uuid[])
            order by provider, phone_e164
            """,
            org_id,
            ids,
        )
    )


async def get(
    conn: asyncpg.Connection, org_id: UUID, number_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLUMNS} from public.telephony_numbers where org_id = $1 and id = $2",
        org_id,
        number_id,
    )


async def by_e164(
    conn: asyncpg.Connection, *, org_id: UUID, provider: str, phone_e164: str
) -> asyncpg.Record | None:
    """The row provisioning is about to configure, found the way it names it.

    Provisioning is handed a number as an E.164 string rather than an id - that
    is what the carrier and LiveKit both speak - and `(org_id, provider,
    phone_e164)` is unique, so this resolves to at most one row.
    """
    return await conn.fetchrow(
        f"""
        select {_COLUMNS} from public.telephony_numbers
        where org_id = $1 and provider = $2 and phone_e164 = $3
        """,
        org_id,
        provider,
        phone_e164,
    )


async def upsert_discovered(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID | None,
    provider: str,
    phone_e164: str,
    provider_number_ref: str | None,
    label: str | None,
    capabilities: dict[str, Any],
) -> asyncpg.Record:
    """Record a number the carrier reported, without undoing what is known.

    A resync must never walk a `verified` number back to `discovered`: the trunks
    still exist at LiveKit and the carrier, and downgrading the status would make
    a working number undiallable until someone noticed. So `status` is only ever
    set on insert, and an existing row keeps its own.
    """
    return await conn.fetchrow(
        f"""
        insert into public.telephony_numbers
            (org_id, created_by, provider, phone_e164, provider_number_ref,
             label, capabilities, last_synced_at)
        values ($1, $2, $3, $4, $5, $6, $7::jsonb, now())
        on conflict (org_id, provider, phone_e164) do update
            set provider_number_ref = coalesce(
                    excluded.provider_number_ref,
                    public.telephony_numbers.provider_number_ref),
                label = coalesce(excluded.label, public.telephony_numbers.label),
                capabilities = excluded.capabilities,
                last_synced_at = now()
        returning {_COLUMNS}
        """,
        org_id,
        created_by,
        provider,
        phone_e164,
        provider_number_ref,
        label,
        capabilities,
    )


async def record_livekit_ids(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    number_id: UUID,
    inbound_trunk_id: str | None = None,
    outbound_trunk_id: str | None = None,
    dispatch_rule_id: str | None = None,
    carrier_termination_domain: str | None = None,
) -> asyncpg.Record | None:
    """Write down what provisioning created, one step at a time.

    Every value is `coalesce`d so a later step cannot blank an earlier one's
    result - the same reason `telephony_provisioning.record_livekit_ids` does it.
    A resumed attempt writes only what it just made.
    """
    return await conn.fetchrow(
        f"""
        update public.telephony_numbers
        set livekit_inbound_trunk_id = coalesce($3, livekit_inbound_trunk_id),
            livekit_outbound_trunk_id = coalesce($4, livekit_outbound_trunk_id),
            livekit_dispatch_rule_id = coalesce($5, livekit_dispatch_rule_id),
            carrier_termination_domain = coalesce($6, carrier_termination_domain)
        where org_id = $1 and id = $2
        returning {_COLUMNS}
        """,
        org_id,
        number_id,
        inbound_trunk_id,
        outbound_trunk_id,
        dispatch_rule_id,
        carrier_termination_domain,
    )


async def record_error(
    conn: asyncpg.Connection, *, org_id: UUID, number_id: UUID, message: str | None
) -> None:
    """The current reason this number is not diallable, or `None` to clear it.

    Deliberately does not change `status`: a part-way failure stays
    `provisioning` so the same attempt can resume, exactly as
    `telephony_provisioning.record_error` reasons about it.

    `None` clears, and that is not a convenience - nothing used to clear this
    column at all, so the first reason a number ever collected outlived whatever
    caused it. A number that had been synced before any agent existed kept
    "Build an agent first" as its displayed reason after the agent was built and
    after later attempts failed for a completely different cause, telling the
    operator to do something they had already done and hiding the real blocker
    (`ISSUES.md` #187).
    """
    await conn.execute(
        "update public.telephony_numbers set last_error = $3 where org_id = $1 and id = $2",
        org_id,
        number_id,
        message,
    )


async def set_status(
    conn: asyncpg.Connection, *, org_id: UUID, number_id: UUID, target: NumberStatus
) -> asyncpg.Record | None:
    """Move a number's status, or raise.

    `select ... for update` first, so two concurrent writers cannot both read
    `provisioning` and both decide they may move to `verified`. The transition
    check is the domain's, not this module's - an invalid move raises before
    anything is written (CLAUDE.md non-negotiable #7).
    """
    current = await conn.fetchval(
        "select status from public.telephony_numbers where org_id = $1 and id = $2 for update",
        org_id,
        number_id,
    )
    if current is None:
        return None

    check_transition(NumberStatus(current), target)
    return await conn.fetchrow(
        f"""
        update public.telephony_numbers set status = $3
        where org_id = $1 and id = $2
        returning {_COLUMNS}
        """,
        org_id,
        number_id,
        target.value,
    )


__all__ = [
    "by_e164",
    "get",
    "list_by_ids",
    "list_for_org",
    "record_error",
    "record_livekit_ids",
    "set_status",
    "upsert_discovered",
]
