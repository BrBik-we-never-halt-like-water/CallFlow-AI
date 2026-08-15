"""SQL for `telephony_provisioning` - one row per attempt to connect a number.

RLS scopes every query to the caller's org; the role checks (owner/admin/
operator to write) live in the policies, not here.

The point of this module is `start_attempt()`. Creating a LiveKit trunk is not
idempotent at the vendor: calling it twice makes two trunks, and the second is
an orphan nobody will ever clean up. So the attempt row is claimed *first*, and
a retry that presents the same idempotency key gets the existing row back
instead of a fresh one - carrying whatever trunk ids the first attempt already
recorded, which is exactly what the caller needs to know what to skip.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from app.domain.provisioning import ProvisioningStatus, check_transition

_COLUMNS = """
    id, seq, voice_agent_id, org_id, status, idempotency_key,
    livekit_inbound_trunk_id, livekit_outbound_trunk_id, livekit_dispatch_rule_id,
    carrier_termination_domain, last_error, created_at, updated_at
"""


async def start_attempt(
    conn: asyncpg.Connection,
    *,
    voice_agent_id: UUID,
    org_id: UUID,
    idempotency_key: str,
) -> tuple[asyncpg.Record, bool]:
    """Claim an attempt. Returns `(row, created)`.

    `created is False` means this key has been seen before and the row returned
    is the original attempt, mid-flight or finished. The caller must read its
    `livekit_*` columns and skip any step already recorded there rather than
    re-running it - re-running trunk creation is what orphans a second trunk.

    Two statements rather than `on conflict ... do update`, because the update
    form would fire the `updated_at` trigger and make a read look like a write.
    Both run inside the caller's transaction, so the insert-then-select cannot
    interleave with another attempt on the same key - the unique index on
    (voice_agent_id, idempotency_key) is what actually serialises them.
    """
    row = await conn.fetchrow(
        f"""
        insert into public.telephony_provisioning (voice_agent_id, org_id, idempotency_key)
        values ($1, $2, $3)
        on conflict (voice_agent_id, idempotency_key) do nothing
        returning {_COLUMNS}
        """,
        voice_agent_id,
        org_id,
        idempotency_key,
    )
    if row is not None:
        return row, True

    existing = await conn.fetchrow(
        f"""
        select {_COLUMNS} from public.telephony_provisioning
        where voice_agent_id = $1 and idempotency_key = $2
        """,
        voice_agent_id,
        idempotency_key,
    )
    if existing is None:
        # The insert conflicted, so a row with this key exists - if it is not
        # readable now, RLS filtered it, which means it belongs to another org.
        # Failing closed here beats returning None and letting the caller treat
        # "not visible" as "not created" and dial anyway.
        raise PermissionError(
            "This provisioning attempt belongs to another organisation."
        )
    return existing, False


async def get_attempt(
    conn: asyncpg.Connection, attempt_id: UUID
) -> asyncpg.Record | None:
    return await conn.fetchrow(
        f"select {_COLUMNS} from public.telephony_provisioning where id = $1",
        attempt_id,
    )


async def latest_for_agent(
    conn: asyncpg.Connection, voice_agent_id: UUID
) -> asyncpg.Record | None:
    """The attempt the connect-number status poll reports on.

    Ordered by `seq`, not `created_at`: `created_at` defaults to `now()`, which
    is the *transaction* timestamp, so two attempts can carry the identical
    value and the "newest" of them is then decided by `id` - a random uuid. That
    made this a coin flip between polls, which is how the status page would show
    a stale failed attempt while a live one was running.
    """
    return await conn.fetchrow(
        f"""
        select {_COLUMNS} from public.telephony_provisioning
        where voice_agent_id = $1
        order by seq desc
        limit 1
        """,
        voice_agent_id,
    )


async def record_livekit_ids(
    conn: asyncpg.Connection,
    attempt_id: UUID,
    *,
    inbound_trunk_id: str | None = None,
    outbound_trunk_id: str | None = None,
    dispatch_rule_id: str | None = None,
    carrier_termination_domain: str | None = None,
) -> asyncpg.Record | None:
    """Persist what a step created, as soon as it is created.

    Written per step rather than once at the end: a crash between creating a
    trunk and finishing the workflow must still leave the id recorded, or the
    retry has no way to know the trunk exists and will make a second one.

    `coalesce` means a `None` argument leaves the stored value alone, so one
    step recording its own id cannot blank out an earlier step's.
    """
    return await conn.fetchrow(
        f"""
        update public.telephony_provisioning set
            livekit_inbound_trunk_id = coalesce($2, livekit_inbound_trunk_id),
            livekit_outbound_trunk_id = coalesce($3, livekit_outbound_trunk_id),
            livekit_dispatch_rule_id = coalesce($4, livekit_dispatch_rule_id),
            carrier_termination_domain = coalesce($5, carrier_termination_domain)
        where id = $1
        returning {_COLUMNS}
        """,
        attempt_id,
        inbound_trunk_id,
        outbound_trunk_id,
        dispatch_rule_id,
        carrier_termination_domain,
    )


async def set_status(
    conn: asyncpg.Connection,
    attempt_id: UUID,
    target: ProvisioningStatus,
    *,
    last_error: str | None = None,
) -> asyncpg.Record | None:
    """Move an attempt to `target`, or raise if the machine forbids it.

    The current status is read `for update` so two concurrent workers cannot
    both see `provisioning` and both write a terminal status - the row lock
    holds until the caller's transaction ends.

    Returns `None` when the row is not visible, which under RLS means it is not
    this caller's to move.
    """
    current_value = await conn.fetchval(
        "select status from public.telephony_provisioning where id = $1 for update",
        attempt_id,
    )
    if current_value is None:
        return None

    check_transition(ProvisioningStatus(current_value), target)

    return await conn.fetchrow(
        f"""
        update public.telephony_provisioning
        set status = $2, last_error = $3
        where id = $1
        returning {_COLUMNS}
        """,
        attempt_id,
        target.value,
        last_error,
    )
