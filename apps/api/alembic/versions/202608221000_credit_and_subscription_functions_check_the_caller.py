"""Close a cross-tenant hole in the credit ledger and the subscription webhook path.

**What was wrong.** `credit_append`, `credit_balance`, and `credit_member_spend`
(migration `202608190900`) are `SECURITY DEFINER` and take `target_org_id` as a
plain argument, with no check that the caller has anything to do with that
organisation. Postgres grants `EXECUTE` to `PUBLIC` on every function unless
something revokes it, and nothing did - CLAUDE.md's own warning about this
("function EXECUTE defaults to PUBLIC") describes exactly this shape, and this
one was missed. The practical effect: any authenticated user, with nothing
more than an ordinary session, could call

    select public.credit_append(<any other org's id>, null, 'grant', 999999999,
                                 'exploit', null, null, null);

and hand themselves someone else's usage credit - or call it with `'spend'`
to drain another organisation's balance to nothing. `credit_balance` and
`credit_member_spend` have the same gap in the read direction: either could be
called with an arbitrary `org_id` to read another organisation's balance or a
teammate's spend.

The three subscription-webhook functions from `202608172100`
(`record_gateway_payment`, `apply_subscription_event`,
`lookup_org_for_subscription`) have the identical gap for the same reason - and
that migration's own comment on `attach_gateway_ids` names the intended rule
precisely: *"the one function here a session is meant to call, so it is the
one that has to check who is calling"* - implying the other three were never
meant to be reachable from a session at all. They were not revoked either.

**Two different fixes, because the functions are called two different ways.**

- `credit_append`/`credit_balance`/`credit_member_spend` are called by *both* an
  ordinary authenticated session (for its own organisation - `services/credit.py`
  via `database.as_user()`) *and* the anonymous webhook path (`services/billing.py`
  via `database.anonymous()`, granting on `subscription.active`/`.renewed` and a
  top-up `payment.succeeded`). An outright `revoke` would break the legitimate
  session calls, so these three gain an internal check instead: allowed when the
  session is `anon` (the webhook has already verified the gateway's signature in
  Python before reaching here), or when `public.is_org_member(target_org_id)` is
  true for the session's own `auth.uid()`. `credit_settle` and
  `credit_release_stale_holds` need no separate check - both only ever reach
  `credit_ledger` through `credit_append`, so they inherit it.

  **The "am I anon" half of that check reads `current_setting('role', true)`,
  never `current_user`.** Inside a `SECURITY DEFINER` function, `current_user`
  reports the function's *owner* - `postgres` here - for the whole duration of
  the call, not the session that invoked it; `SET ROLE`/`set_config('role', ...)`
  does not touch that. `current_setting('role', true)` is an ordinary session
  GUC and is untouched by entering a definer function, which is exactly why
  `auth.uid()` (itself `SECURITY DEFINER`, reading `request.jwt.claims` the same
  way) already worked correctly here and `current_user` would not have. Caught
  by `tests/test_credit_ledger.py`'s reaper test, which failed against the
  first draft of this migration with every anonymous grant rejected - a
  webhook-driven grant or top-up would have started failing 100% of the time
  had this shipped as first written.

- `record_gateway_payment`, `apply_subscription_event`, and
  `lookup_org_for_subscription` are called *only* from the anonymous webhook
  path - no session ever calls them, confirmed by grepping every caller in
  `app/services/billing.py`. These simply lose `EXECUTE` from `authenticated`
  and `PUBLIC`, keeping it for `anon`, matching the grant pattern already used
  for `usage_rates`/`provider_tiers` (`grant select ... to authenticated, anon`)
  rather than adding a check nothing needs.

Revision ID: c9a3f7e15d84
Revises: c4e7f2b81d63
"""

from __future__ import annotations

from alembic import op

revision = "c9a3f7e15d84"
down_revision = "c4e7f2b81d63"
branch_labels = None
depends_on = None

CREDIT_APPEND = """
create or replace function public.credit_append(
  target_org_id uuid,
  actor_user_id uuid,
  kind text,
  amount bigint,
  dedupe text,
  call_ref text default null,
  rate_per_minute integer default null,
  why text default null
) returns boolean
language plpgsql volatile security definer
set search_path = public, pg_temp as $$
declare
  inserted uuid;
begin
  if coalesce(current_setting('role', true), '') <> 'anon'
     and not public.is_org_member(target_org_id) then
    raise exception 'Not authorized to write usage credit for this organisation.'
      using errcode = '42501';
  end if;

  if kind not in ('grant', 'hold', 'release', 'spend', 'expiry', 'adjustment') then
    raise exception 'Not a credit entry kind: %', kind using errcode = '22023';
  end if;
  if coalesce(trim(dedupe), '') = '' then
    raise exception 'A credit entry needs a dedupe key.' using errcode = '22023';
  end if;

  if kind in ('hold', 'spend', 'expiry') then
    amount := -abs(amount);
  else
    amount := abs(amount);
  end if;

  insert into public.credit_ledger
    (org_id, user_id, entry_kind, amount_minor, currency, dedupe_key,
     call_key, rate_paise_per_minute, reason)
  values
    (target_org_id, actor_user_id, kind, amount, 'INR', trim(dedupe),
     call_ref, rate_per_minute, why)
  on conflict (org_id, dedupe_key) do nothing
  returning id into inserted;

  if inserted is null then
    return false;
  end if;

  update public.organisations
     set credit_balance_paise = credit_balance_paise + amount
   where id = target_org_id;

  return true;
end;
$$;
"""

CREDIT_BALANCE = """
create or replace function public.credit_balance(target_org_id uuid)
returns bigint
language sql stable security definer
set search_path = public, pg_temp as $$
  select case
    when current_setting('role', true) = 'anon' or public.is_org_member(target_org_id)
      then coalesce((select sum(amount_minor) from public.credit_ledger
                      where org_id = target_org_id), 0)::bigint
    else null
  end;
$$;
"""

CREDIT_MEMBER_SPEND = """
create or replace function public.credit_member_spend(
  target_org_id uuid, target_user_id uuid, since timestamptz
) returns bigint
language sql stable security definer
set search_path = public, pg_temp as $$
  select case
    when current_setting('role', true) = 'anon' or public.is_org_member(target_org_id)
      then coalesce((select sum(abs(amount_minor)) from public.credit_ledger
                      where org_id = target_org_id and user_id = target_user_id
                        and entry_kind in ('hold', 'spend') and created_at >= since), 0)::bigint
    else null
  end;
$$;
"""


def upgrade() -> None:
    op.execute(CREDIT_APPEND)
    op.execute(CREDIT_BALANCE)
    op.execute(CREDIT_MEMBER_SPEND)

    # No session ever calls these three - confirmed by grepping every caller
    # in `app/services/billing.py`, which reaches all of them exclusively
    # through the anonymous webhook connection. `anon` keeps EXECUTE; the
    # session-facing roles lose it outright, rather than gaining a check
    # nothing legitimate needs.
    for fn in (
        "public.record_gateway_payment"
        "(uuid, uuid, text, text, bigint, char(3), text, text, timestamptz)",
        "public.apply_subscription_event"
        "(uuid, text, text, text, text, timestamptz, boolean, text, text, text)",
        "public.lookup_org_for_subscription(text, text, uuid)",
    ):
        op.execute(f"revoke execute on function {fn} from public, authenticated")
        op.execute(f"grant execute on function {fn} to anon")


def downgrade() -> None:
    for fn in (
        "public.record_gateway_payment"
        "(uuid, uuid, text, text, bigint, char(3), text, text, timestamptz)",
        "public.apply_subscription_event"
        "(uuid, text, text, text, text, timestamptz, boolean, text, text, text)",
        "public.lookup_org_for_subscription(text, text, uuid)",
    ):
        op.execute(f"grant execute on function {fn} to authenticated")

    # Restore the pre-fix bodies, with no caller check.
    op.execute(
        """
        create or replace function public.credit_member_spend(
          target_org_id uuid, target_user_id uuid, since timestamptz
        ) returns bigint
        language sql stable security definer
        set search_path = public, pg_temp as $$
          select coalesce(sum(abs(amount_minor)), 0)::bigint
            from public.credit_ledger
           where org_id = target_org_id and user_id = target_user_id
             and entry_kind in ('hold', 'spend') and created_at >= since;
        $$;
        """
    )
    op.execute(
        """
        create or replace function public.credit_balance(target_org_id uuid)
        returns bigint
        language sql stable security definer
        set search_path = public, pg_temp as $$
          select coalesce(sum(amount_minor), 0)::bigint
            from public.credit_ledger where org_id = target_org_id;
        $$;
        """
    )
    op.execute(
        """
        create or replace function public.credit_append(
          target_org_id uuid,
          actor_user_id uuid,
          kind text,
          amount bigint,
          dedupe text,
          call_ref text default null,
          rate_per_minute integer default null,
          why text default null
        ) returns boolean
        language plpgsql volatile security definer
        set search_path = public, pg_temp as $$
        declare
          inserted uuid;
        begin
          if kind not in ('grant', 'hold', 'release', 'spend', 'expiry', 'adjustment') then
            raise exception 'Not a credit entry kind: %', kind using errcode = '22023';
          end if;
          if coalesce(trim(dedupe), '') = '' then
            raise exception 'A credit entry needs a dedupe key.' using errcode = '22023';
          end if;

          if kind in ('hold', 'spend', 'expiry') then
            amount := -abs(amount);
          else
            amount := abs(amount);
          end if;

          insert into public.credit_ledger
            (org_id, user_id, entry_kind, amount_minor, currency, dedupe_key,
             call_key, rate_paise_per_minute, reason)
          values
            (target_org_id, actor_user_id, kind, amount, 'INR', trim(dedupe),
             call_ref, rate_per_minute, why)
          on conflict (org_id, dedupe_key) do nothing
          returning id into inserted;

          if inserted is null then
            return false;
          end if;

          update public.organisations
             set credit_balance_paise = credit_balance_paise + amount
           where id = target_org_id;

          return true;
        end;
        $$;
        """
    )
