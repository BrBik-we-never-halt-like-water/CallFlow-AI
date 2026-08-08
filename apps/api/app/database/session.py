"""Connection pool and the RLS-scoped connection every request must use."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg

from app.core.config import config

log = logging.getLogger("callflow.database")

# Idle sockets behind a NAT are often already dead; recycling keeps a stale one
# out of a live request.
IDLE_LIFETIME_SECONDS = 300.0


class DatabaseNotReady(RuntimeError):
    """Raised when the pool is used before startup has run."""


class Database:
    """Owns the asyncpg pool and hands out scoped connections.

    `postgres` holds the BYPASSRLS attribute, which means a plain connection sees
    every organisation's rows and `FORCE ROW LEVEL SECURITY` does not change that.
    Row-level security is therefore only real when a request drops to a role that
    lacks the attribute — which is what `as_user` does.
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise DatabaseNotReady("Database.connect() has not been called.")
        return self._pool

    @property
    def is_connected(self) -> bool:
        return self._pool is not None

    async def connect(self) -> None:
        if self._pool is not None:
            return

        if not config.database_url:
            raise DatabaseNotReady(
                "DATABASE_URL is not set. Copy .env.example to .env and add the "
                "Supabase connection string."
            )

        self._pool = await asyncpg.create_pool(
            config.database_url,
            min_size=config.db_pool_min,
            max_size=config.db_pool_max,
            max_inactive_connection_lifetime=IDLE_LIFETIME_SECONDS,
            command_timeout=config.db_command_timeout,
            init=self._register_codecs,
            setup=self._reset,
        )
        log.info(
            "database pool ready",
            extra={"min_size": config.db_pool_min, "max_size": config.db_pool_max},
        )

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            log.info("database pool closed")

    @staticmethod
    async def _register_codecs(connection: asyncpg.Connection) -> None:
        """Round-trip `jsonb` as plain Python dicts/lists.

        Runs once per physical connection (not per acquire) — asyncpg has no
        opinion on JSON by default, so every jsonb column would otherwise come
        back as a raw string a caller has to remember to `json.loads`.
        """
        await connection.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
            format="text",
        )

    @staticmethod
    async def _reset(connection: asyncpg.Connection) -> None:
        await connection.execute("reset role")

    @asynccontextmanager
    async def as_user(self, auth_user_id: UUID | str) -> AsyncIterator[asyncpg.Connection]:
        """A connection scoped to one user, with RLS in force.

        Runs inside a transaction because `SET LOCAL` requires one, which also means
        a handler commits all of its writes or none.

        `auth_user_id` is the provider id (the JWT `sub`) because that is what
        `auth.uid()` returns and what the RLS helpers join on. Everything above this
        layer still deals in `public.users.id`.
        """
        async with self.pool.acquire() as connection, connection.transaction():
            await self._assume(connection, "authenticated", str(auth_user_id))
            yield connection
            # Only on the way out clean: if the body raised, the transaction is
            # already rolling back (or aborted), and this `SET LOCAL` reset would
            # itself fail with `InFailedSQLTransactionError` — replacing whatever
            # real error the body raised with a confusing one about the cleanup
            # instead. The rollback already discards the `SET LOCAL` role for us.
            await self._release(connection)

    @asynccontextmanager
    async def anonymous(self) -> AsyncIterator[asyncpg.Connection]:
        """A connection with no identity. Every tenant policy evaluates false."""
        async with self.pool.acquire() as connection, connection.transaction():
            await connection.execute("select set_config('role', 'anon', true)")
            yield connection
            # See as_user()'s matching comment: skip cleanup on the error path, or a
            # `SET LOCAL` reset on an already-aborted transaction masks the real error.
            await self._release(connection)

    @staticmethod
    async def _assume(connection: asyncpg.Connection, role: str, subject: str) -> None:
        # Parameterised, never interpolated: the claims blob reaches auth.uid() via
        # current_setting(), so an injected value here would be an authorisation bypass.
        claims = json.dumps({"sub": subject, "role": role})
        await connection.execute("select set_config('request.jwt.claims', $1, true)", claims)
        await connection.execute("select set_config('role', $1, true)", role)

    @staticmethod
    async def _release(connection: asyncpg.Connection) -> None:
        # Redundant given SET LOCAL, but it means a future refactor that drops the
        # transaction cannot leak the role to the next borrower.
        await connection.execute("select set_config('role', 'postgres', true)")


database = Database()
