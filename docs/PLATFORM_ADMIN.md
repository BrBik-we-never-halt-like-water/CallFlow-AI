# Platform admin: cross-tenant support access

> **Status: built, except the enumerated data writes (§5).** The identity table, the
> capability check, the read path, `as_platform_reader`, the entitlement writes, the audit
> log, `/api/v1/platform/*`, `/app/platform` and the bootstrap script are all real, with
> `tests/test_platform_admin.py` as the security file. Three §5 functions are **not** built:
> `platform_resolve_stuck_run`, `platform_add_suppression`, `platform_purge_org_data`.
>
> **Two departures from this design, both deliberate.** §4 describes appending an `or`
> clause to each of the 17 existing `select` policies; the migration adds a *separate*
> permissive `select` policy per table instead. Postgres ORs permissive policies, so the
> effect is identical — but no existing qual is rewritten, and those quals are where tenant
> isolation lives. §4 also says the session writes its audit row "before yielding": it does,
> but in its own writable transaction *before* the read-only one opens, because
> `readonly=True` would refuse the insert. That also means the trace survives a session that
> later errors.

This is the most dangerous surface in the product. CLAUDE.md §4 #1 calls cross-tenant access
"the most severe bug class this product can ship," and this document describes deliberately
building one. The design is therefore organised around a single question: **when this is
compromised or misused, what is the blast radius, and can we reconstruct what happened?**

---

## 1. What it is, and what it is not

| | |
|---|---|
| **is** | one identity table with a capability set, letting named CallFlow staff read customer data across orgs and perform an enumerated list of writes |
| **is not** | an RLS bypass. RLS evaluates on every row of every platform query. `privileged.acquire()` never appears in a request handler |
| **is not** | an org role. `OrgRole` is scoped to one organisation by definition, so a fifth value would be wrong |
| **is not** | self-granting. No endpoint anywhere creates a `platform_admins` row |

---

## 2. Identity and capabilities

One table, not a `platform_admins` / `super_admins` pair — two tiers of superuser means two
privilege boundaries to reason about, where a capability set gives you tiers for free. This
mirrors `permissions.py` (a set per identity) and CLAUDE.md §3-I's preference for
`supports(capability)` over one fat interface.

```
platform_admins
  user_id      PK → public.users
  capabilities text[]
  granted_by   → public.users
  granted_at, note
```

| capability | grants |
|---|---|
| `orgs:read` | the org list — name, plan, effective entitlements, usage counts. No customer data |
| `data:read` | cross-org read of operational tables (§4), with PII redacted |
| `pii:reveal` | unredacted transcripts and phone numbers |
| `entitlements:write` | set a plan or a per-org entitlement override |
| `data:write` | the enumerated write actions in §5 |

**`pii:reveal` is separate on purpose.** CLAUDE.md §4 #4 already says revealing a full number
is "a separate permissioned, audit-logged action" — this applies that existing rule to the
support surface rather than exempting it. Most support work is reading dispositions, errors and
timings, which needs neither transcripts nor numbers.

`platform_admins` itself has RLS enabled and forced with **no policies and no grant to
`authenticated`** — unreachable through the API entirely.

---

## 3. Why not the simpler options

Both alternatives were considered and rejected for concrete reasons worth keeping.

| approach | why not |
|---|---|
| `privileged.acquire()` in the platform routes | forbidden in request handlers (CLAUDE.md §2), and it is the definition of making RLS decorative — the connection sees every org with no policy evaluated at all |
| extend `public.has_org_role()` to return true for platform admins | **this was the trap.** 9 of 20 `select` policies key on `has_org_role` — including `call_outcomes`, `runs` and `escalations`, the data support actually needs. But *every table's insert and update policies use the same helper*, so extending it hands out blanket write access as a side effect |
| impersonate a member of the target org | clean and needs zero policy changes, but works one org at a time. Ruled out by the decision to allow all-orgs sessions (§7) |

---

## 4. The read path

### A predicate on the select policies

One new helper, added as an `or` clause to the `select` policy of each table in scope. Write
policies are **not** touched, so no policy grants a platform admin write anywhere.

```sql
create function public.platform_can_read(target_org_id uuid) returns boolean
  language plpgsql stable security definer
  set search_path = public, pg_temp as $$
begin
  -- Fast path first, and it is also the security model: an ordinary as_user()
  -- session never sets this flag, so a platform admin browsing normally is
  -- treated as the ordinary org member they are. Elevation is per-session and
  -- explicit, never ambient.
  if current_setting('callflow.platform_session', true) is null then
    return false;
  end if;
  return public.platform_has_capability('data:read');
end;
$$;
```

The flag is the opt-in; the `platform_admins` row is the authority. Both are required, so
setting the flag alone grants nothing.

**The fast path is not just performance.** This predicate is evaluated on every row of every
query by every user across 17 policies, so a table lookup in the default path would be a
tax on the whole product. Returning `false` on an unset session variable makes the ordinary
path a no-op.

### Tables in scope

| in scope | out of scope | why excluded |
|---|---|---|
| `organisations`, `memberships`, `campaigns`, `runs`, `call_outcomes`, `escalations`, `voice_agents`, `telephony_provisioning`, `org_safety_settings`, `suppressions`, `share_requests`, `invitations`, `member_credit_allocations`, `api_keys`, `provider_credentials`, `ai_provider_credentials`, `users` | `channels`, `channel_members`, `messages` | customers' internal team chat is the most privacy-sensitive table in the schema and the least useful for debugging a call |

`provider_credentials` and `ai_provider_credentials` are readable but the secrets are not:
both are Fernet-encrypted and `PROVIDER_CREDENTIALS_KEY` lives only in process environment, so
a platform admin sees ciphertext. **Customer vendor keys stay protected even here** — a
property worth preserving deliberately rather than by accident.

### The session primitive

A third way into the database, alongside `as_user` and `privileged.acquire`:

```python
async with database.as_platform_reader(admin_auth_user_id, reason="ticket #412") as conn:
    ...
```

| property | mechanism |
|---|---|
| RLS in force | assumes the admin's *own* identity; `platform_can_read` is what widens visibility |
| writes impossible | `connection.transaction(readonly=True)` — asyncpg native. Postgres refuses any write regardless of policy |
| elevation is explicit | sets `callflow.platform_session` via `set_config(..., true)`, transaction-local |
| audited | requires a non-empty `reason` and writes a `platform_audit_log` row before yielding, same discipline as `privileged.acquire` |
| time-boxed | the grant backing the session expires after 1 hour |

**`readonly=True` is load-bearing.** With all-orgs visibility it is the only thing between a
platform admin and a cross-org write, so it belongs in the primitive where it cannot be
forgotten, never at a call site.

This contradicts CLAUDE.md §4b's "two ways into the database, and only two." That section must
be updated as part of the work — an invariant this important should not be quietly false.

---

## 5. The write path: enumerated, never blanket

No policy and no session grants cross-org write. Each action is one narrow `SECURITY DEFINER`
function that re-checks authorisation itself, because **Postgres grants function EXECUTE to
PUBLIC unless revoked** — the route dependency is convenience, the check inside the function
is the boundary.

| function | capability | what it does |
|---|---|---|
| `platform_set_org_plan` | `entitlements:write` | set `organisations.plan_id` for a deal closed offline |
| `platform_set_org_entitlements` | `entitlements:write` | write or clear a per-org override |
| `platform_resolve_stuck_run` | `data:write` | close a run wedged in `running` with no settling outcome |
| `platform_add_suppression` | `data:write` | honour a do-not-call request arriving out of band |
| `platform_purge_org_data` | `data:write` | a DPA/GDPR deletion request |

Every one takes a mandatory `reason` and writes its own audit row in the same transaction as
the change, so a write cannot land unlogged.

Adding to this list is a migration — a reviewable event. That is the point: "what can a
platform admin change" stays a list you can read in one screen.

---

## 6. Audit

```
platform_audit_log        append-only, global
  actor_user_id → users        action        target_org_id (nullable)
  before jsonb                 after jsonb   reason
  created_at
```

Append-only means omitting the delete policy **and** revoking the grant — Supabase's default
`public` ACL hands DELETE back otherwise
(`202608161700_revoke_delete_on_append_only_tables.py`).

This is the in-band equivalent of `privileged.py`'s "a log line every time". A cross-tenant
surface without an audit trail is one you cannot investigate after the fact.

Note `Permission.AUDIT_READ` already exists with no table behind it. This is **not** that
table — org-scoped audit for customers remains unbuilt.

---

## 7. Accepted risks

Recorded because each was a decision, not an oversight.

| risk | why accepted | what limits it |
|---|---|---|
| **A session reads every org at once** | chosen deliberately, so cross-org questions like "which orgs hit this bug" are answerable in one query | read-only transaction, 1-hour expiry, per-session audit row |
| **The audit log says "opened a session", not "read org X"** | the direct cost of all-orgs sessions. Per-org grants would have given a precise trail | the `reason` is mandatory and free-text, so the ticket reference is recoverable |
| **17 policies each gain an `or` clause** | the only way to widen read without bypassing RLS | one migration, mechanical, `select` only; a test asserts no *write* policy references the helper |
| **A leaked platform session exposes all customer data** | inherent to the feature | `pii:reveal` withheld by default, expiry, and staff-only grants issued out of band |

---

## 8. Bootstrap

The first row cannot be created through the product, by design.

**A script, not a migration.** Dev and production are separate Supabase projects
(`DEPLOYMENT.md` §3), so user ids differ and a hardcoded id cannot be correct in both — and it
would put a named person in version control permanently.

`scripts/platform_admin.py`, run on the VM against the production `.env`:

| behaviour | detail |
|---|---|
| input | an **email**, resolved to exactly one `public.users.id`; refuses on zero or multiple matches |
| write path | `privileged.acquire("grant platform admin to <email>")` — mandates a reason, logs every call |
| idempotent | `on conflict do nothing`, safe to re-run |
| revokes too | `--revoke`. Revocation is the more important half and must not need a different tool |
| asserts the rule | `--i-confirm-grantee-has-prod-access` is mandatory on grant. The script cannot verify prod access itself, so it forces the granter to state it at the moment of the decision instead of trusting they read this file. The assertion lands in the audit row beside granter and grantee |
| self-audits | writes its own `platform_audit_log` row directly, since the definer write path requires already being an admin — the first grant cannot audit itself through the normal route |

### Who

The selection rule, which matters more than the names: **platform admins must be a subset of
the people who already hold production database or deploy access.** Anyone with
`SUPABASE_SECRET_KEY` can already do all of this and more with raw SQL, so for them this is a
*reduction* — audited and narrow instead of unrestricted psql. For anyone else it is a genuine
privilege escalation.

**The rule enforces itself for the granter.** The bootstrap script needs `DATABASE_URL` and
`SUPABASE_SECRET_KEY` from the production `.env` to run at all, so only someone who already
holds prod access can grant platform admin in the first place. What it cannot prevent is a
prod-access holder granting it to someone *without* prod access — a policy question, which is
what `--i-confirm-grantee-has-prod-access` exists to make explicit.

**Decided:** the first holder is the person who owns the production environment. Adding a
second is optional. When you do, the eligible set is the union of these three lists:

| where | what counts as access |
|---|---|
| GitHub → Collaborators | **write or above** — write access to a workflow-triggering branch means adding a step that echoes `ENV_FILE_B64`, so write access *is* prod-secret access unless the deploy branch is protected |
| the VM's `deploy` user | a key in `~/.ssh/authorized_keys` |
| Supabase → prod project → Members | where the secret key and database password actually live |

Worth auditing that middle row regardless of this feature: if the deploy branch is
unprotected, prod secrets are already reachable by every repo collaborator — a wider exposure
than anything in this document.

**One holder is sufficient to ship.** An earlier draft argued for two on the grounds that
revoking a compromised admin needs a second admin. That was wrong: `--revoke` runs through
`privileged.acquire()` against the production `.env`, so **anyone with production access can
revoke, platform admin or not.** Revocation is covered by prod access, not by a second grant.

Add a second holder for **availability** — one person unavailable should not block an
enterprise configuration — and to avoid concentrating the knowledge. Real reasons, but not
security-critical and not a reason to delay. Not four: blast radius grows and the audit log's
value falls as the set widens.

**Never a shared or service account.** `platform_audit_log.actor_user_id` is the entire value
of the log; a shared `admin@` makes every row identical and the trail worthless.

---

## 9. The tests that matter most

Write these first. They are the feature.

| test | catches |
|---|---|
| a normal user calls `select public.platform_set_org_entitlements(...)` directly | **EXECUTE defaults to PUBLIC** — the one hole a route-only check leaves wide open |
| a platform admin in an ordinary `as_user()` session sees only their own orgs | elevation is per-session, never ambient |
| `set_config('callflow.platform_session', ...)` by a non-admin grants nothing | the flag is opt-in, the table is authority |
| every write attempt inside `as_platform_reader` raises | `readonly=True` holds |
| no `insert`/`update`/`delete` policy references `platform_can_read` | a grep-style assertion so a future migration cannot widen writes by accident |
| `channels`, `channel_members`, `messages` stay invisible to a platform session | the chat exclusion is real, not documented-only |
| `provider_credentials` read returns ciphertext | customer vendor keys survive this surface |
| an expired grant grants nothing | the 1-hour bound holds |
| every platform write leaves an audit row with actor, before, after, reason | investigability |
| no endpoint can create a `platform_admins` row | escalation stays out of band |
| a normal customer's query plan is unchanged by the new predicate | the fast path is actually fast |

---

## 10. Documentation this changes

| file | change |
|---|---|
| `CLAUDE.md` §4b | "two ways into the database, and only two" becomes three. Document `as_platform_reader` and why it is not a bypass |
| `CLAUDE.md` §4 #1 | note the one deliberate cross-tenant surface and point here |
| `SYSTEM.md` | the tables, the routes, the new session primitive |
| `docs/BILLING.md` §4 | already points here for the enterprise-override half |
| `apps/web/DESIGN_NOTES.md` | the `/app/platform` area and its redaction behaviour |
| `DEPLOYMENT.md` | the bootstrap procedure and who holds it |

---

## 11. Open decisions

| question | why it matters |
|---|---|
| Is the 1-hour session expiry right? | added on my own judgment, not requested. Longer is more convenient; shorter is safer |
| Should `pii:reveal` require a second approver? | it is the capability that turns a leak into a disclosure incident |
| Does chat stay out of scope permanently? | if support genuinely needs it to debug the chat feature, it needs its own capability rather than a quiet inclusion |
