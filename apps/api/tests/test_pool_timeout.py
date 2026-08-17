"""An exhausted pool must fail fast, not hang.

asyncpg's `acquire()` has no timeout of its own unless one is passed, so before
`_acquire()` existed a saturated pool produced requests that never answered and
never errored - no log line, no status code, just a loading state that never
resolved (`ISSUES.md` #122). These tests pin the two halves of the fix: a
timeout is actually handed to the pool, and the resulting failure surfaces as a
distinct type the API turns into a 503.
"""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from app.core import config as config_module
from app.database import session as session_module
from app.database.session import Database, DatabasePoolBusy


class _SizedPool:
    """The three size getters `Database.stats()` reads off a real asyncpg pool."""

    def get_size(self) -> int:
        return 10

    def get_idle_size(self) -> int:
        return 0

    def get_max_size(self) -> int:
        return 10


class _StuckPool(_SizedPool):
    """Saturation, with asyncpg's own contract: honour `timeout` by raising.

    Emulating the timeout rather than sleeping past it is the point - the
    production code passes `timeout=` and relies on asyncpg to enforce it, so a
    stub that ignored it would test nothing.
    """

    def __init__(self) -> None:
        self.released: list[object] = []
        self.timeouts_seen: list[float] = []

    async def acquire(self, *, timeout: float) -> object:
        self.timeouts_seen.append(timeout)
        await asyncio.sleep(timeout)
        raise TimeoutError

    async def release(self, connection: object) -> None:
        self.released.append(connection)


class _FreePool(_SizedPool):
    """A pool that hands a connection straight back."""

    def __init__(self) -> None:
        self.released: list[object] = []
        self.connection = object()

    async def acquire(self, *, timeout: float) -> object:
        self.timeout = timeout
        return self.connection

    async def release(self, connection: object) -> None:
        self.released.append(connection)


@pytest.fixture
def scoped_timeout(monkeypatch: pytest.MonkeyPatch):
    """Shrink the acquire timeout for the duration of one test.

    Patches the name `session.py` actually reads: it does
    `from app.core.config import config`, so the reference is bound in that
    module at import and reassigning `config_module.config` would not reach it -
    the same discipline `test_email.py` uses on the resend module.
    """

    def apply(seconds: float) -> None:
        monkeypatch.setattr(
            session_module,
            "config",
            dataclasses.replace(config_module.config, db_acquire_timeout=seconds),
        )

    return apply


def _database(pool: object) -> Database:
    database = Database()
    database._pool = pool  # type: ignore[assignment]
    return database


@pytest.mark.asyncio
async def test_a_saturated_pool_raises_instead_of_waiting_forever(scoped_timeout) -> None:
    scoped_timeout(0.05)
    database = _database(_StuckPool())

    with pytest.raises(DatabasePoolBusy) as caught:
        async with database._acquire():
            pass

    # The message must name the limit that was hit - "unavailable" on its own
    # leaves an operator with nothing to change.
    assert "fully in use" in str(caught.value)


@pytest.mark.asyncio
async def test_the_configured_timeout_is_handed_to_the_pool(scoped_timeout) -> None:
    """The regression that matters: calling acquire() with no timeout at all."""
    scoped_timeout(0.05)
    pool = _StuckPool()
    database = _database(pool)

    with pytest.raises(DatabasePoolBusy):
        async with database._acquire():
            pass

    assert pool.timeouts_seen == [0.05]


@pytest.mark.asyncio
async def test_the_wait_is_bounded(scoped_timeout) -> None:
    scoped_timeout(0.05)
    database = _database(_StuckPool())

    started = asyncio.get_running_loop().time()
    with pytest.raises(DatabasePoolBusy):
        async with database._acquire():
            pass

    waited = asyncio.get_running_loop().time() - started
    assert waited < 2.0, f"waited {waited:.2f}s, so the timeout is not applied"


@pytest.mark.asyncio
async def test_a_connection_is_returned_to_the_pool_after_use(scoped_timeout) -> None:
    scoped_timeout(1.0)
    pool = _FreePool()
    database = _database(pool)

    async with database._acquire() as connection:
        assert connection is pool.connection

    assert pool.released == [pool.connection]


@pytest.mark.asyncio
async def test_a_connection_is_returned_even_when_the_body_raises(scoped_timeout) -> None:
    """A leak here is what causes saturation in the first place."""
    scoped_timeout(1.0)
    pool = _FreePool()
    database = _database(pool)

    with pytest.raises(ValueError):
        async with database._acquire():
            raise ValueError("handler blew up")

    assert pool.released == [pool.connection]


def test_stats_are_empty_before_the_pool_is_open() -> None:
    assert Database().stats() == {}
