"""role_hierarchy_grant_guard

Closes a privilege-escalation hole (found by the R5 audit): `PATCH
/api/v1/organisations/me/members/{id}` and `POST
/api/v1/organisations/me/invitations` were guarded only by
`Permission.TEAM_SET_ROLE`/`TEAM_INVITE`, which Admin already holds - same as
Owner. Neither the API nor RLS checked *which* role was being granted, so an
Admin could set their own role to `owner`, or invite a new email straight into
`owner`, then use that to demote or remove the original owner (the last-owner
guard only blocks removing the *last* owner, not a non-last one) - full
account takeover from an Admin seat.

This is the RLS half of the fix. `app/auth/permissions.py`
(`can_grant_role()`) and `app/api/v1/routes/organisations.py`
(`_ensure_can_grant()`) add the same check at the API layer, which is where a
normal request is actually stopped - this migration is defense-in-depth per
CLAUDE.md §4b's stated model of an API check *and* an RLS check, neither
alone.

`public.can_grant_role()` mirrors the Python function of the same name: Owner
may grant any role, including owner itself - that's how ownership transfers.
Every other role may only grant a role strictly below its own, so Admin gets
operator/viewer only, never admin or owner, not even to itself.
`public.current_org_role()` is a new `SECURITY DEFINER` helper, alongside the
existing `has_org_role`, that returns the caller's own role in an organisation
rather than a boolean - needed here to compare ranks instead of just testing
set membership.

Three write paths get the check added to their `WITH CHECK`:

* `memberships_update` - an owner/admin editing an existing row directly.
* `memberships_insert`'s owner/admin branch - inserting one directly.
* `invitations_insert` - creating the pending invite that an acceptance later
  turns into a membership row via `has_valid_invitation`. Gating this is what
  actually closes the invite-to-owner path: `has_valid_invitation` only checks
  that the invitation's role matches, not who was allowed to set that role in
  the first place.

Revision ID: c2f7a9d15e63
Revises: b9d4f1a6c832
Created: 2026-08-08 09:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "c2f7a9d15e63"
down_revision: str | None = "b9d4f1a6c832"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Not security definer and touches no table, so - like `is_free_email_domain`/
# `slugify` - no pinned search_path is needed; only definer functions carry
# that risk.
RANK_AND_GRANT_HELPERS = """
create or replace function public.org_role_rank(role public.org_role)
returns int language sql immutable as $$
  select case role
    when 'viewer' then 0
    when 'operator' then 1
    when 'admin' then 2
    when 'owner' then 3
  end;
$$;

create or replace function public.can_grant_role(
  caller_role public.org_role, target_role public.org_role
)
returns boolean language sql immutable as $$
  select caller_role = 'owner'
    or public.org_role_rank(target_role) < public.org_role_rank(caller_role);
$$;

create or replace function public.current_org_role(target_org uuid)
returns public.org_role language sql stable security definer
set search_path = public, pg_temp as $$
  select m.role from public.memberships m
  where m.org_id = target_org and m.user_id = public.current_user_id();
$$;
"""


MEMBERSHIPS_UPDATE_POLICY = """
drop policy if exists memberships_update on public.memberships;
create policy memberships_update on public.memberships for update
  using (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))
  with check (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    and public.can_grant_role(public.current_org_role(org_id), role)
  );
"""


MEMBERSHIPS_INSERT_POLICY = """
drop policy if exists memberships_insert on public.memberships;
create policy memberships_insert on public.memberships for insert
  with check (
    (
      public.has_org_role(org_id, array['owner','admin']::public.org_role[])
      and public.can_grant_role(public.current_org_role(org_id), role)
    )
    or public.has_valid_invitation(org_id, role)
    or (
      role = 'owner'
      and not exists (select 1 from public.memberships m2 where m2.org_id = memberships.org_id)
    )
  );
"""


INVITATIONS_INSERT_POLICY = """
drop policy if exists invitations_insert on public.invitations;
create policy invitations_insert on public.invitations for insert
  with check (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    and public.can_grant_role(public.current_org_role(org_id), role)
  );
"""


def upgrade() -> None:
    op.execute(RANK_AND_GRANT_HELPERS)
    op.execute(MEMBERSHIPS_UPDATE_POLICY)
    op.execute(MEMBERSHIPS_INSERT_POLICY)
    op.execute(INVITATIONS_INSERT_POLICY)


def downgrade() -> None:
    op.execute("drop policy if exists invitations_insert on public.invitations")
    op.execute(
        "create policy invitations_insert on public.invitations for insert "
        "with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))"
    )

    op.execute("drop policy if exists memberships_insert on public.memberships")
    op.execute(
        """
        create policy memberships_insert on public.memberships for insert
          with check (
            public.has_org_role(org_id, array['owner','admin']::public.org_role[])
            or public.has_valid_invitation(org_id, role)
            or (
              role = 'owner'
              and not exists (select 1 from public.memberships m2 where m2.org_id = memberships.org_id)
            )
          );
        """
    )

    op.execute("drop policy if exists memberships_update on public.memberships")
    op.execute(
        "create policy memberships_update on public.memberships for update "
        "using (public.has_org_role(org_id, array['owner','admin']::public.org_role[])) "
        "with check (public.has_org_role(org_id, array['owner','admin']::public.org_role[]))"
    )

    op.execute("drop function if exists public.current_org_role(uuid) cascade")
    op.execute(
        "drop function if exists public.can_grant_role(public.org_role, public.org_role) cascade"
    )
    op.execute("drop function if exists public.org_role_rank(public.org_role) cascade")
