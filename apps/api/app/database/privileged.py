"""The one place row-level security is bypassed."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from app.database.session import Database, database

log = logging.getLogger("callflow.database.privileged")


class PrivilegedAccess:
    """RLS-bypassing connections for work that has no user.

    `postgres` holds BYPASSRLS, so a connection from here sees every organisation's
    data. Occasionally necessary - a retention purge, a reconciliation job - and also
    the easiest way to ship a cross-tenant leak, so the bypass is deliberately
    awkward: one module, a mandatory reason, and a log line every time.

    Never call this from a request handler. A request has a user, a user has an
    organisation, and that path is `database.as_user`.
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    @asynccontextmanager
    async def acquire(self, reason: str) -> AsyncIterator[asyncpg.Connection]:
        if not reason.strip():
            raise ValueError(
                "privileged.acquire() requires a reason. If you cannot name why RLS "
                "must be bypassed, use database.as_user() instead."
            )

        log.warning("privileged database access", extra={"reason": reason, "rls": "bypassed"})

        async with self._db.pool.acquire() as connection:
            # No role switch: the connection stays `postgres`, which holds BYPASSRLS.
            # Stated because the absence of a line is easy to miss in review.
            yield connection


privileged = PrivilegedAccess(database)
