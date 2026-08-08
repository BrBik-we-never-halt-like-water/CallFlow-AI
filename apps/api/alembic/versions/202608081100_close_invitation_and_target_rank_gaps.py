"""close_invitation_and_target_rank_gaps

Three follow-on gaps found by security review of migration `c2f7a9d15e63`
(the admin-to-owner fix), all in the same policy family:

1. **Invitee could still self-escalate a pending invite's role.**
   `invitations_update_own` (migration `202608061530`) lets the invitee update
   *any column* of their own pending invitation - including `role` - with only
   an email match in `USING`/`WITH CHECK`; the table grant was
   column-unrestricted (`grant ... update ... to authenticated`). An invitee
   legitimately invited as `viewer` could run
   `update invitations set role = 'owner' where token = <their token>`
   directly (e.g. through the anon-key client), then `accept()`
   (`app/database/repositories/invitations.py`) inserts the membership with
   the mutated role - no Admin or Owner action required at all. Column-level
   privilege is the fix: `authenticated` can now only ever write
   `accepted_at` on `invitations`; every other column requires the
   `invitations_insert`/`invitations_delete` paths instead, which are already
   role-gated.

2. **`memberships_insert`'s invitation branch didn't pin `user_id`.**
   `has_valid_invitation(org_id, role)` only checks that *the caller* has a
   matching pending invitation - it never compared that to the `user_id`
   being inserted. A caller holding *any* valid invitation for an org+role
   could insert a membership row for an *arbitrary* other `user_id`, not just
   their own. Added `user_id = current_user_id()` to that branch.

3. **`can_grant_role` only ever checked the role being granted, never the
   target member's current role.** In an org with two owners, an Admin could
   still demote or remove one of them - `can_grant_role` said nothing about
   who a write could *target*, only what value it could set, and neither
   `memberships_update` nor `memberships_delete` checked the existing row's
   role at all. New `public.can_act_on_member()` (same rank rule as
   `can_grant_role`, given a distinct name because the two questions -
   "may I grant this role" vs. "may I touch a member who already holds this
   role" - are conceptually different even though they compute the same
   thing today) is added to both policies' `USING` clauses, which is exactly
   where Postgres evaluates a row's *existing* state for an UPDATE or DELETE.
   Self-targeting is explicitly exempted (`user_id = current_user_id()`) so a
   caller can still act on their own row within whatever `can_grant_role`
   already allows (e.g. an Admin stepping themselves down to viewer) - this
   is a target-of-the-write check, not a re-litigation of the grant check.

   Consequence, stated plainly: reusing `can_grant_role`'s rank rule means
   Admin can now only act on members whose *current* role is operator or
   viewer - not just "not owner." An Admin can no longer act on another
   Admin's row either, not only an Owner's. This is a deliberate, symmetric
   choice - you should not be able to un-appoint someone at a rank you could
   not have appointed them to in the first place - broader than the Owner-only
   scenario in the report, disclosed here rather than left implicit.

Revision ID: d94b2c8f1a67
Revises: c2f7a9d15e63
Created: 2026-08-08 11:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "d94b2c8f1a67"
down_revision: str | None = "c2f7a9d15e63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `authenticated` never legitimately writes anything on `invitations` but
# `accepted_at` (accepting one's own invite) - creating, re-rolling, and
# revoking all go through the role-gated `invitations_insert`/`_delete`
# policies instead. Column-level GRANT is enforced independently of, and
# before, any RLS policy check, so this closes the gap even if
# `invitations_update_own`'s USING/WITH CHECK is ever loosened later.
LOCK_INVITATION_COLUMNS = """
revoke update on public.invitations from authenticated;
grant update (accepted_at) on public.invitations to authenticated;
"""


CAN_ACT_ON_MEMBER = """
create or replace function public.can_act_on_member(
  caller_role public.org_role, target_role public.org_role
)
returns boolean language sql immutable as $$
  select public.can_grant_role(caller_role, target_role);
$$;
"""


MEMBERSHIPS_UPDATE_POLICY = """
drop policy if exists memberships_update on public.memberships;
create policy memberships_update on public.memberships for update
  using (
    user_id = public.current_user_id()
    or (
      public.has_org_role(org_id, array['owner','admin']::public.org_role[])
      and public.can_act_on_member(public.current_org_role(org_id), role)
    )
  )
  with check (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    and public.can_grant_role(public.current_org_role(org_id), role)
  );
"""


MEMBERSHIPS_DELETE_POLICY = """
drop policy if exists memberships_delete on public.memberships;
create policy memberships_delete on public.memberships for delete using (
  user_id = public.current_user_id()
  or (
    public.has_org_role(org_id, array['owner','admin']::public.org_role[])
    and public.can_act_on_member(public.current_org_role(org_id), role)
  )
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
    or (
      user_id = public.current_user_id()
      and public.has_valid_invitation(org_id, role)
    )
    or (
      role = 'owner'
      and not exists (select 1 from public.memberships m2 where m2.org_id = memberships.org_id)
    )
  );
"""


def upgrade() -> None:
    op.execute(LOCK_INVITATION_COLUMNS)
    op.execute(CAN_ACT_ON_MEMBER)
    op.execute(MEMBERSHIPS_UPDATE_POLICY)
    op.execute(MEMBERSHIPS_DELETE_POLICY)
    op.execute(MEMBERSHIPS_INSERT_POLICY)


def downgrade() -> None:
    op.execute("drop policy if exists memberships_insert on public.memberships")
    op.execute(
        """
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
    )

    op.execute("drop policy if exists memberships_delete on public.memberships")
    op.execute(
        "create policy memberships_delete on public.memberships for delete using ( "
        "user_id = public.current_user_id() "
        "or public.has_org_role(org_id, array['owner','admin']::public.org_role[]) "
        ")"
    )

    op.execute("drop policy if exists memberships_update on public.memberships")
    op.execute(
        "create policy memberships_update on public.memberships for update "
        "using (public.has_org_role(org_id, array['owner','admin']::public.org_role[])) "
        "with check ( "
        "public.has_org_role(org_id, array['owner','admin']::public.org_role[]) "
        "and public.can_grant_role(public.current_org_role(org_id), role) "
        ")"
    )

    op.execute(
        "drop function if exists public.can_act_on_member(public.org_role, public.org_role) cascade"
    )

    op.execute("revoke update (accepted_at) on public.invitations from authenticated")
    op.execute("grant select, insert, update, delete on public.invitations to authenticated")
