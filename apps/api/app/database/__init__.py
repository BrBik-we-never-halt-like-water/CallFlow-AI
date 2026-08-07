"""Database access.

Two ways in, and the distinction is the point of this package:

* `database.as_user(...)` — the normal path. Drops to the `authenticated` role and
  installs the caller's JWT claims, so every RLS policy applies.
* `privileged.acquire(reason=...)` — the escape hatch for jobs with no user. Runs as
  `postgres`, which holds BYPASSRLS, so **row-level security does not apply**.

Reaching for `privileged` inside a request handler is the bug.
"""

from app.database.privileged import PrivilegedAccess, privileged
from app.database.session import Database, DatabaseNotReady, database

__all__ = [
    "Database",
    "DatabaseNotReady",
    "PrivilegedAccess",
    "database",
    "privileged",
]
