"""Grant or revoke platform admin. The only path that exists, and deliberately so.

`docs/PLATFORM_ADMIN.md` §8. No endpoint anywhere creates a `platform_admins` row -
the table has RLS forced, no policies, and no grant to `authenticated`, so this
script and a `postgres` connection are the whole surface. A superuser tier that can
grant itself through its own API is the classic escalation hole, and closing it
structurally beats remembering not to build the endpoint.

Revocation is the more important half and uses the same tool, because a separate one
is a tool nobody has installed at the moment they need it.

    python scripts/platform_admin.py --list
    python scripts/platform_admin.py --grant someone@brbik.com \\
        --capabilities orgs:read,data:read --i-confirm-grantee-has-prod-access
    python scripts/platform_admin.py --revoke someone@brbik.com

`--i-confirm-grantee-has-prod-access` is mandatory on a grant. The script cannot
verify prod access itself, so it forces whoever is granting to state it at the moment
of the decision rather than trusting they read the doc. The assertion lands in the
audit row beside granter and grantee.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

# Windows consoles default to cp1252 and the capability strings are fine, but an
# organisation name in --list may not be. Same reasoning as scripts/dodo_products.py.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

CAPABILITIES = (
    "orgs:read",
    "data:read",
    "pii:reveal",
    "entitlements:write",
    "data:write",
)

# What a new grant gets when --capabilities is omitted. Read-only, and without
# `pii:reveal`: most support work is dispositions, errors and timings, and CLAUDE.md
# §4 #4 makes revealing a number a separate permissioned action rather than
# something bundled into a support role.
DEFAULT_CAPABILITIES = ("orgs:read", "data:read")


async def _resolve_user(conn, email: str) -> tuple[str, str]:
    """`(user_id, email)` for exactly one match, or exit.

    Refuses on zero *and* on multiple: granting cross-tenant read to the wrong
    person because two accounts shared a prefix is not a mistake worth allowing a
    fuzzy match to make.
    """
    rows = await conn.fetch(
        "select id, email from public.users where lower(email) = lower($1)", email
    )
    if not rows:
        sys.exit(f"No user with the email {email}. They have to sign up first.")
    if len(rows) > 1:
        sys.exit(f"{len(rows)} users share the email {email}. Resolve that first.")
    return str(rows[0]["id"]), rows[0]["email"]


async def grant(email: str, capabilities: list[str], *, note: str | None) -> None:
    from app.database import database, privileged

    unknown = sorted(set(capabilities) - set(CAPABILITIES))
    if unknown:
        sys.exit(
            f"Not a capability this schema knows: {', '.join(unknown)}. "
            f"Use one or more of: {', '.join(CAPABILITIES)}."
        )

    await database.connect()
    try:
        async with privileged.acquire(f"grant platform admin to {email}") as conn:
            user_id, real_email = await _resolve_user(conn, email)
            async with conn.transaction():
                await conn.execute(
                    """
                    insert into public.platform_admins (user_id, capabilities, note)
                    values ($1, $2::text[], $3)
                    on conflict (user_id) do update
                       set capabilities = excluded.capabilities,
                           note = excluded.note,
                           granted_at = now()
                    """,
                    user_id,
                    capabilities,
                    note,
                )
                # Written directly rather than through `platform_append_audit`,
                # which requires already being an admin - the first grant cannot
                # audit itself through the normal route.
                await conn.execute(
                    """
                    insert into public.platform_audit_log
                      (actor_user_id, action, target_org_id, before_state, after_state, reason)
                    values (null, 'admin.granted', null, null, $1::jsonb, $2)
                    """,
                    {
                        "grantee": real_email,
                        "capabilities": capabilities,
                        "prod_access_confirmed": True,
                    },
                    f"granted by {os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'} "
                    f"via scripts/platform_admin.py{f'; {note}' if note else ''}",
                )
        print(f"Granted {', '.join(capabilities)} to {real_email}.")
    finally:
        await database.disconnect()


async def revoke(email: str) -> None:
    from app.database import database, privileged

    await database.connect()
    try:
        async with privileged.acquire(f"revoke platform admin from {email}") as conn:
            user_id, real_email = await _resolve_user(conn, email)
            async with conn.transaction():
                deleted = await conn.fetchval(
                    "delete from public.platform_admins where user_id = $1 returning user_id",
                    user_id,
                )
                if deleted is None:
                    print(f"{real_email} was not a platform admin. Nothing to do.")
                    return
                await conn.execute(
                    """
                    insert into public.platform_audit_log
                      (actor_user_id, action, target_org_id, before_state, after_state, reason)
                    values (null, 'admin.revoked', null, $1::jsonb, null, $2)
                    """,
                    {"grantee": real_email},
                    f"revoked by {os.environ.get('USER') or os.environ.get('USERNAME') or 'unknown'} "
                    "via scripts/platform_admin.py",
                )
        print(f"Revoked platform admin from {real_email}.")
    finally:
        await database.disconnect()


async def show() -> None:
    from app.database import database, privileged

    await database.connect()
    try:
        async with privileged.acquire("list platform admins") as conn:
            rows = await conn.fetch(
                """
                select u.email, a.capabilities, a.granted_at, a.expires_at, a.note
                  from public.platform_admins a
                  join public.users u on u.id = a.user_id
                 order by a.granted_at
                """
            )
        if not rows:
            print("No platform admins. That is the correct state for most deployments.")
            return
        for row in rows:
            expiry = (
                f" expires {row['expires_at']:%Y-%m-%d}" if row["expires_at"] else ""
            )
            print(
                f"{row['email']:40} {','.join(row['capabilities']):45}"
                f" granted {row['granted_at']:%Y-%m-%d}{expiry}"
            )
    finally:
        await database.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--grant", metavar="EMAIL")
    action.add_argument("--revoke", metavar="EMAIL")
    action.add_argument("--list", action="store_true")
    parser.add_argument(
        "--capabilities",
        default=",".join(DEFAULT_CAPABILITIES),
        help=f"Comma-separated. One or more of: {', '.join(CAPABILITIES)}.",
    )
    parser.add_argument("--note", help="Why this grant exists. Recorded on the row.")
    parser.add_argument(
        "--i-confirm-grantee-has-prod-access",
        action="store_true",
        help=(
            "Required to grant. Asserts the grantee already holds production access "
            "(GitHub write, the VM's deploy user, or the Supabase prod project), so "
            "this grant widens no trust boundary that is not already open to them."
        ),
    )
    args = parser.parse_args()

    if args.list:
        asyncio.run(show())
    elif args.revoke:
        asyncio.run(revoke(args.revoke))
    else:
        if not args.i_confirm_grantee_has_prod_access:
            sys.exit(
                "Refusing to grant without --i-confirm-grantee-has-prod-access.\n"
                "A platform admin can read every customer's data. Give it only to "
                "someone who could already reach that data another way - see "
                "docs/PLATFORM_ADMIN.md §8. Revoke with --revoke."
            )
        capabilities = [c.strip() for c in args.capabilities.split(",") if c.strip()]
        asyncio.run(grant(args.grant, capabilities, note=args.note))


if __name__ == "__main__":
    main()
