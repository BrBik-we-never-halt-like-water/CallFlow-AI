"""Reconciling what the carrier says an organisation owns with what we recorded.

`services/`, because it does I/O across a vendor and the database. What it
returns is plain rows, so the route above it stays a thin shaping layer.

The one rule worth stating: **a resync never walks a number backwards.** The
carrier is authoritative about which numbers exist and what they are called; it
knows nothing about whether CallFlow has pointed one at LiveKit. Downgrading a
`verified` number to `discovered` because a sync ran would make a working line
undiallable until somebody noticed.
"""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg

from app.database.repositories import telephony_numbers as numbers_repo
from app.domain.numbers import NumberStatus
from app.integrations.telephony import CarrierNumber
from app.services.number_provisioning import CARRIERS

log = logging.getLogger("app.services.number_directory")


class UnsupportedCarrier(Exception):
    """Named rather than a bare ValueError so the route can say which one."""

    def __init__(self, provider: str) -> None:
        supported = ", ".join(sorted(CARRIERS))
        super().__init__(
            f"{provider} is not a carrier CallFlow can list numbers from. "
            f"Supported: {supported}."
        )


async def sync_numbers(
    conn: asyncpg.Connection,
    *,
    org_id: UUID,
    created_by: UUID | None,
    provider: str,
    credentials: dict[str, str],
) -> list[asyncpg.Record]:
    """List the carrier's numbers and reconcile them into `telephony_numbers`.

    Returns every number this organisation holds on that carrier afterwards, so
    the caller renders one list rather than merging two.
    """
    factory = CARRIERS.get(provider)
    if factory is None:
        raise UnsupportedCarrier(provider)

    async with factory(**credentials) as carrier:
        found: list[CarrierNumber] = await carrier.list_numbers()

    log.info("carrier %s reported %d number(s)", provider, len(found))

    seen: set[str] = set()
    for number in found:
        # Skipped rather than stored as undiallable: a number the carrier says
        # cannot do voice is not a line this product has any use for, and
        # offering it in a picker would be a run that fails at the carrier.
        if not number.can_call:
            log.info("skipping a %s number with no voice capability", provider)
            continue
        seen.add(number.e164)
        await numbers_repo.upsert_discovered(
            conn,
            org_id=org_id,
            created_by=created_by,
            provider=provider,
            phone_e164=number.e164,
            provider_number_ref=number.number_ref,
            label=number.label,
            capabilities={name: True for name in sorted(number.capabilities)},
        )

    # A number CallFlow knows about that the carrier no longer reports has been
    # released or moved. Retired, not deleted: it may have placed real calls, and
    # `telephony_numbers` carries no delete grant for exactly that reason.
    existing = await numbers_repo.list_for_org(conn, org_id, provider=provider)
    for row in existing:
        if row["phone_e164"] in seen:
            continue
        current = NumberStatus(row["status"])
        if current is NumberStatus.DISABLED:
            continue
        try:
            await numbers_repo.set_status(
                conn,
                org_id=org_id,
                number_id=row["id"],
                target=NumberStatus.DISABLED,
            )
            log.info("retired a %s number the carrier no longer reports", provider)
        except Exception:  # noqa: BLE001 - one number must not fail the sync
            # `provisioning -> disabled` is not a declared move, so a number
            # mid-provisioning stays where it is. That is correct: it is being
            # worked on, and the carrier not listing it yet is expected.
            log.info("left a %s number in %s during sync", provider, current.value)

    return await numbers_repo.list_for_org(conn, org_id, provider=provider)


__all__ = ["UnsupportedCarrier", "sync_numbers"]
