"""Alembic environment.

Two things here are deliberate and easy to get wrong.

**The driver is psycopg, not asyncpg.** Migrations are synchronous by nature and
gain nothing from async, while asyncpg prepares every statement and so rejects the
multi-statement DDL blocks that RLS policies and plpgsql functions are written as.
Runtime still uses asyncpg; only migrations use psycopg.

**`SupabaseSchemaFilter` guards autogenerate.** Supabase owns `auth`, `storage`,
`realtime` and friends, and none appear in our metadata. Without the filter,
`alembic revision --autogenerate` proposes dropping every one of them, `auth.users`
included.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import config as app_config
from app.database.models import Base

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

MANAGED_SCHEMA = "public"

SUPABASE_OWNED_SCHEMAS = frozenset(
    {
        "auth",
        "storage",
        "realtime",
        "graphql",
        "graphql_public",
        "extensions",
        "vault",
        "pgbouncer",
        "supabase_functions",
        "supabase_migrations",
        "cron",
        "net",
        "pgsodium",
        "pgsodium_masks",
        "information_schema",
        "pg_catalog",
        "pg_toast",
    }
)


class SupabaseSchemaFilter:
    """Restricts autogenerate to the tables this project owns.

    Two independent checks, because either alone is insufficient: schema filtering
    misses objects Supabase creates inside `public`, and metadata filtering misses
    that reflected `auth` tables are absent from our models and would be marked for
    deletion.
    """

    def __init__(self, metadata) -> None:
        self._known_tables = {table.name for table in metadata.sorted_tables}

    def include_object(self, obj, name, type_, reflected, compare_to) -> bool:
        schema = getattr(obj, "schema", None)

        if schema in SUPABASE_OWNED_SCHEMAS:
            return False

        if type_ == "table":
            if schema not in (None, MANAGED_SCHEMA):
                return False
            if reflected and name not in self._known_tables:
                return False

        # The users -> auth.users link is declared as raw DDL precisely so the auth
        # schema stays out of our metadata. Autogenerate therefore cannot see it and
        # would propose dropping it, which would break signup.
        if type_ == "foreign_key_constraint":
            referred = getattr(obj, "referred_table", None)
            if referred is not None and referred.schema in SUPABASE_OWNED_SCHEMAS:
                return False

        return True

    def include_name(self, name, type_, parent_names) -> bool:
        if type_ == "schema":
            return name in (None, MANAGED_SCHEMA)
        return True


_filter = SupabaseSchemaFilter(target_metadata)


def _database_url() -> str:
    if not app_config.database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and add the Supabase "
            "connection string before running migrations."
        )
    return app_config.database_url.replace("postgresql://", "postgresql+psycopg://", 1)


def _configure(connection=None) -> None:
    context.configure(
        connection=connection,
        url=None if connection else _database_url(),
        target_metadata=target_metadata,
        include_schemas=False,
        include_object=_filter.include_object,
        include_name=_filter.include_name,
        version_table="alembic_version",
        version_table_schema=MANAGED_SCHEMA,
        compare_type=True,
        compare_server_default=True,
        literal_binds=connection is None,
        dialect_opts={"paramstyle": "named"},
    )


def run_migrations_offline() -> None:
    _configure()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config(
        {"sqlalchemy.url": _database_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
