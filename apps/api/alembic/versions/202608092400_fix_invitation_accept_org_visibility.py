"""fix_invitation_accept_org_visibility

Critical bug found via real-world testing (not caught by any existing test -
this path had zero coverage): a genuinely brand-new invitee - someone who
just signed up for the first time via an invite link, with no prior org
memberships - could never actually accept their invitation.

`invitations_repo.accept()`'s lookup does:

    select ... from public.invitations i
    join public.organisations o on o.id = i.org_id
    where i.token = $1

on the RLS-scoped `authenticated` connection. `invitations_select`'s policy
correctly lets the invitee see their own pending invitation by email match -
but `organisations_select` is plain `is_org_member(id)`, and a brand-new
invitee is by definition not yet a member of the org they're being invited
to. The `join` silently drops the row the moment it reaches `organisations`,
so the whole query returns nothing, `accept()` returns `None`, and the route
reports the generic "this invitation isn't valid" - even though the
invitation is completely valid and addressed to exactly the right person.
This is a chicken-and-egg RLS problem: you need to already be a member to
see the org row, but seeing the org row was a precondition (via this join)
for becoming a member.

Every real acceptance attempt by a new signup has been failing this way
since the tables were created - masked because no test exercised a genuine
brand-new-user acceptance end to end (existing coverage only exercised
invitation *creation* and RLS *write* guards, never a first-time accept).

Fix: the same pattern already used for `create_organisation()` and
`create_or_refresh_invitation()` (both SECURITY DEFINER, both anchored to
`current_user_id()` rather than trusting a caller-supplied identity) -
narrowly scoped to just the lookup step. `public.lookup_invitation_for_accept()`
bypasses RLS to resolve token -> invitation + org name/slug, exposing nothing
the existing *anonymous* `lookup_invitation()` preview function doesn't
already expose to anyone holding the token, unauthenticated. It takes no
identity as an argument and needs none - a token is the credential, same
trust model as the preview endpoint. The actual state-mutating operations
(the membership INSERT and the invitation UPDATE) are deliberately left as
plain RLS-scoped queries in `invitations_repo.accept()`, unchanged - so the
`memberships_insert` policy's `has_valid_invitation()` check still applies
as a second, independent guard on the one operation that actually grants
access, preserving the defense-in-depth CLAUDE.md calls for.

Also closes a minor, separate gap surfaced while fixing this: `accept()`
never checked `expires_at` at all, only `accepted_at` - an expired-but-
never-accepted invitation could still be accepted. The new lookup computes
`expired` server-side (avoiding any app/DB clock-skew comparison, ISSUES.md
`#16`'s lesson) and `accept()` now checks it.

Revision ID: b4e9c7f1a385
Revises: d7f3a8c2e951
Created: 2026-08-09 21:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b4e9c7f1a385"
down_revision: str | None = "d7f3a8c2e951"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CREATE_FUNCTION = """
create function public.lookup_invitation_for_accept(token_in text)
returns table (
  id uuid,
  org_id uuid,
  role public.org_role,
  invited_by uuid,
  accepted_at timestamptz,
  expired boolean,
  org_name text,
  org_slug text
)
language plpgsql security definer
set search_path = public, pg_temp as $$
begin
  return query
    select i.id, i.org_id, i.role, i.invited_by, i.accepted_at,
           (i.expires_at <= now()) as expired,
           o.name as org_name, o.slug as org_slug
    from public.invitations i
    join public.organisations o on o.id = i.org_id
    where i.token = token_in;
end;
$$;
"""

DROP_FUNCTION = "drop function if exists public.lookup_invitation_for_accept(text)"


def upgrade() -> None:
    op.execute(CREATE_FUNCTION)


def downgrade() -> None:
    op.execute(DROP_FUNCTION)
