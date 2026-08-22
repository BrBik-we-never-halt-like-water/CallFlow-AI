# Plans, entitlements and payments

> **Status: as-built.** The ladder, the entitlement gates, the subscription state machine,
> the Dodo adapter and its webhook, the reconcile fallback, the Billing page, and the
> platform-admin surface behind the enterprise tier are all real. An enterprise deal is
> given custom limits through `/app/platform`, and `has_custom_limits` reflects a genuine
> `org_entitlement_overrides` row. §10 draws the remaining line — the enumerated *data*
> writes in §5 (`platform_resolve_stuck_run`, `platform_add_suppression`,
> `platform_purge_org_data`) are still design; only the entitlement writes are built.

CallFlow bills **per organisation**, on a plan that grants **entitlements** rather than
call volume. Calls are never charged per-call. What a plan limits is how much of the
product an organisation can stand up: voice agents, seats, workspaces, and how many
model vendors it may mix.

---

## 1. The plans

Three plans plus a negotiated tier. `enterprise` has no self-serve checkout — its
entitlements come from a per-organisation override set by a platform admin (§4).

| plan | agents | seats | orgs | AI keys | calls/day | LLM cap | checkout |
|---|---|---|---|---|---|---|---|
| `free` | 1 | 1 | 1 | 2 | 20 | $5 | — |
| `starter` | 3 | 3 | 1 | 3 | 200 | $25 | self-serve |
| `growth` | 10 | 10 | 3 | ∞ | 1000 | $100 | self-serve |
| `enterprise` | custom | custom | custom | custom | custom | custom | contact us |

`∞` is `NULL`, never a sentinel like `-1`. `0` is a real, enforced value and is
deliberately distinguishable from `NULL` — the same distinction
`credits_repo.get_credit_cap()` already relies on.

**`enterprise`'s seeded row is a floor, not a blank.** It carries `growth`'s numbers so
an enterprise organisation created before its override is written is merely
generous, never unlimited. Seeding it `NULL` everywhere would mean a gap between
"deal signed" and "entitlements configured" in which the org has no limits at all.

The numbers live in a seeded `plan_entitlements` table rather than hardcoded in Python,
because the API, several SQL guards, and the platform-admin UI all read them.
`domain/plans.py` holds the type and the fail-closed fallback; a test asserts the two
agree.

### Telephony is deliberately not limited

Earlier drafts capped telephony integrations. That was wrong, and the reason is worth
recording so it does not come back.

| what it costs CallFlow | who pays |
|---|---|
| carrier / phone number | **the organisation** — their own Twilio/Plivo account |
| STT / TTS / own LLM keys | **the organisation** — their own vendor keys |
| LiveKit media minutes | **CallFlow** |
| OpenRouter tokens on the CallFlow-minted per-org key | **CallFlow** |

Only the last two are real cost, and both are already governed — by `calls/day` and by
`llm_spend_limit_usd`. Capping a bring-your-own carrier saves nothing and only adds
friction to the thing that makes the product work at all.

The same logic nearly removes the AI-key limit too: a customer's own key *reduces*
CallFlow's OpenRouter bill, so limiting it is economically backwards. It is kept purely
as **packaging** — "mix any vendors you like" is a legible Growth rung — and never as
cost control. A count of 1 or more does not gate dialling, because one Sarvam key covers
both STT and TTS.

**Free can therefore place calls**, within 20/day. That keeps `pricing.ts`'s existing
Free tagline ("Prove the pipeline before you spend anything") true, which is why §11's
copy list is shorter than it would otherwise be.

---

## 2. Where each limit is enforced

Every gate is a pure function in `domain/`, fed plain values by a thin caller — the
`domain/safety.py` shape, so all of it is testable without a database or a mock.
Denials return **402 Payment Required**, not 403, so the frontend can tell "your plan
doesn't include this" from "your role doesn't allow this" and offer an upgrade instead of
a dead end.

| limit | action gated | route | second guard, below the route |
|---|---|---|---|
| `max_voice_agents` | create an agent | `voice_agents.py:255` | `before insert` trigger on `voice_agents` |
| `max_seats` | invite a teammate | `organisations.py:272` | — |
| `max_seats` | accept an invitation | `invitations.py` accept | — (re-checked at accept) |
| `max_organisations` | create a workspace | `organisations.py:176` | inside `public.create_organisation()` |
| `max_ai_integrations` | connect an STT/TTS/LLM key | `ai_providers.py:65` | `ai_provider_credentials_insert` RLS check |
| `daily_call_budget` | start a run | `runs.py:182` | — (the limiter already gates it) |
| `llm_spend_limit_usd` | mint/update an OpenRouter key | `integrations/openrouter/client.py` | OpenRouter enforces the cap itself |

### Why three of them need a guard below the route

In each case the privileged path does not pass through the Python check:

| surface | why a route check is not enough |
|---|---|
| `voice_agents` | `insert` is granted straight to `authenticated`, so raw SQL bypasses the API |
| `create_organisation()` | `SECURITY DEFINER`, so it bypasses RLS by design, and Postgres grants EXECUTE to PUBLIC unless revoked |
| `ai_provider_credentials` | grants `insert` to `authenticated` |

CLAUDE.md §4b's rule: a limit enforced only in Python is decoration.

### Two rules that are easy to get wrong

**Organisations are counted per *user*, not per organisation** — the only entitlement
that is. A plan belongs to an org, but "how many workspaces may I create" is a property
of a person. The count is orgs where the user holds `owner` **and `deleted_at is null`**;
the limit comes from their currently active org's plan.

- Active-only matters because `DELETE /organisations/me` is a soft delete. Counting
  deleted rows would mean a slot never frees.
- **The signup trigger is exempt.** `handle_new_auth_user()`
  (`202608060050_initial_schema.py:198-256`) creates the first org for every new user and
  must never fail. A plan limit reachable from that path is a signup outage, not a
  paywall.
- Acting from a better-plan org gives the higher ceiling. Intended — the paid plan is
  what buys the workspaces.

**The plan `daily_call_budget` is a ceiling, not a default.** It extends
`resolve_safety_settings()` (`domain/safety.py:77`), deliberately the one place an org
override merges onto deployment defaults so display and enforcement can never disagree.
The merge becomes `min(org_override ?? plan_default, plan_max)`: an org may set itself
*lower* than its plan allows, never higher, and every field stays `is not None`-checked so
an explicit `0` still wins.

---

## 3. Integrations: writes are gated, existing rows are not

Applies to AI keys only, now that telephony is unlimited.

| operation | on a plan that allows it | on a plan at its limit |
|---|---|---|
| `GET /integrations/catalogue`, `GET /providers` | works | **works** — the UI must be able to say "upgrade to connect" |
| connect a new credential | works | 402 |
| update/rotate an existing credential | works | **works** |
| delete a credential | works | works |
| a stored credential being used on a call | works | **works** |

Nothing is deleted or disabled on downgrade. A failed renewal must never break a live
calling operation, and an `ai_provider_credentials` row holds a real vendor secret the
product could not re-create if it dropped it. The SQL guard counts on `insert` only,
never on `update`.

**The bounded leak this accepts:** connect three vendors on Growth, downgrade to Starter,
keep them. Agents, seats and calls/day still apply, so exposure is capped.

**Storage, automation and observability catalogue entries stay ungated** because nothing
reads those credentials yet — a paid limit on a no-op is a limit on nothing. Revisit when
one becomes `wired`.

---

## 4. Enterprise: per-org overrides

`enterprise` has no self-serve checkout and no fixed entitlements. Its limits come from a
per-organisation override written by a platform admin.

| table | scope | notes |
|---|---|---|
| `org_entitlement_overrides` | `org_id` | one nullable column per limit; `NULL` = fall back to the plan |

Resolution order, and the final fallback is what makes it fail closed:

```
org_entitlement_overrides.<limit>   (if not null)
  └─▶ plan_entitlements[organisations.plan_id]
        └─▶ plan_entitlements['free']      ← unknown / hand-edited plan_id
```

An org may be readable by its own members and still only writable by a platform admin,
through a narrow `SECURITY DEFINER` function — so an owner can see what they were granted
but cannot raise it.

**The platform-admin surface that writes these lives in
[`docs/PLATFORM_ADMIN.md`](PLATFORM_ADMIN.md)**, along with the cross-tenant support-read
path, the enumerated write actions, the audit log, and the bootstrap procedure. It is the
highest-risk part of this work and has its own document rather than a section here.

Two consequences that belong in *this* doc:

- **`enterprise`'s seeded `plan_entitlements` row carries `growth`'s numbers**, so an org
  whose deal is signed but whose override is not yet written is generous, never unlimited.
- **An `enterprise` org may have no `org_subscriptions` row at all** — an invoiced deal is
  not a Dodo subscription. Entitlement resolution must never require one.

---

## 5. Subscription states

Statuses mirror the gateway's vocabulary so there is no translation layer to get wrong.
The machine is modelled on `domain/provisioning.py`, the repo's only existing explicit
state machine.

| status | meaning | grants the paid plan? |
|---|---|---|
| `pending` | checkout created, not yet paid | no |
| `active` | paid and billing normally | **yes** |
| `on_hold` | a renewal failed; recoverable by fixing the payment method | **yes, until `current_period_end`** |
| `cancelled` | ended by the customer or by us — terminal | until `current_period_end`, then no |
| `expired` | the term ended without renewal — terminal | no |
| `failed` | mandate never established at signup — terminal | no |

| from | legal targets | trigger |
|---|---|---|
| `pending` | `active`, `failed`, `cancelled` | `subscription.active` / `.failed` / abandoned |
| `active` | `on_hold`, `cancelled`, `expired` | `.on_hold` / cancel / term ends |
| `on_hold` | `active`, `cancelled`, `expired` | payment method fixed / cancel / term ends |
| `cancelled`, `expired`, `failed` | — | terminal |

Three decisions with a wrong-looking obvious alternative:

- **`on_hold` keeps the paid plan until the period ends.** The gateway's own guidance is
  to revoke on `on_hold`, and an earlier draft followed it — but `on_hold` is *exactly*
  when a renewal fails, so revoking there hard-stops a running campaign at the worst
  moment. One rule now covers cancel, downgrade and payment failure: entitlements survive
  to the end of the paid period, then drop to `free`. Still fail-closed, because it is
  time-bounded rather than open-ended.
- **Renewal is not a transition.** `subscription.renewed` extends `current_period_end`
  while the status stays `active`. Modelling it as `active → active` would mean permitting
  a self-transition, which the provisioning machine deliberately rejects.
- **Resubscribing inserts a new row.** Terminal means terminal. A partial unique index
  permits one live subscription (`pending`/`active`/`on_hold`) per org, so the machine
  stays one-way and the record of what was tried survives.

`enterprise` orgs may have no subscription row at all — an invoiced deal is not a Dodo
subscription. Entitlement resolution must therefore never require one; the override table
is the source of truth for those orgs.

---

## 6. The gateway

**Dodo Payments**, as Merchant of Record, behind a `PaymentProvider` protocol.

| property | value |
|---|---|
| model | Merchant of Record — Dodo is the seller of record |
| what it owns | the mandate, dunning, and tax across 190+ jurisdictions |
| what we own | reacting to five webhook events |
| India domestic | 4% + ₹4, plus a 0.5% subscription surcharge |
| cross-border subscription | ~6–7% effective |
| settlement to an Indian entity | export-of-services inward remittance, per RBI/FEMA |
| webhook spec | [Standard Webhooks](https://www.standardwebhooks.com/) |
| Python SDK | `dodopayments` |

Razorpay is ~2% on domestic cards and near-zero on UPI, for comparison. The ~2×
difference on domestic revenue is the price of not building tax handling, mandates and a
dunning ladder.

**Why a protocol, not a direct SDK call.** If domestic MDR later dominates cost, a
Razorpay adapter becomes a new file under `integrations/payments/` rather than a rewrite.
It also gives CLAUDE.md §3-L its first genuine two-implementation abstraction:
`integrations/voice/protocol.py` has none today, and `engine.py` — still cited in
CLAUDE.md §3-D as *the* canonical example — was deleted with CALL-E.

Only `starter` and `growth` have Dodo products, so four ids in config
(two plans × monthly/annual). `enterprise` is invoiced outside the product.

### Webhook events → what we do

| event | action | writes |
|---|---|---|
| `subscription.active` | grant the plan | `status = active`, mirror `plan_id`, insert `payments` |
| `subscription.renewed` | extend the period | `current_period_end` |
| `subscription.on_hold` | record it, keep entitlements to period end | `status = on_hold`, `last_error` |
| `subscription.failed` | terminal failure | `status = failed`, `last_error` |
| `subscription.updated` | reconcile changed fields | whichever changed |
| `subscription.plan_changed` | mapped onto the same kind as `.updated` (`ISSUES.md` #141) | plan swap, gated on settlement |
| `payment.succeeded` / `.failed` | ledger only; a credit-pack top-up (no subscription row) grants usage credit instead | insert `payments`, maybe `credit_ledger` |

Callers read a **normalised** internal event kind, never the vendor string — the same
reason `DialFailure` (`domain/entities.py:39-63`) exists for call failures.

### Webhook response codes

| condition | status | why |
|---|---|---|
| webhook secret unset in config | 404 | a misconfigured deployment refuses rather than accepting anonymous writes |
| signature invalid | 404 | a prober learns nothing about whether the path means anything |
| timestamp older than 5 minutes | 404 | replay window, matching the outbound scheme this repo documents |
| `webhook-id` already seen | 200 | idempotent no-op |
| subscription unknown (id *and* metadata miss) | 200 | an event for something we never created |
| transition illegal from current status | 200 | park it in `last_error` |
| applied | 200 | — |

The 404 group follows `internal.py:78-85`'s `_require_internal_key`, constant-time compare
included. The 200 group exists because delivery is at-least-once with 8 retries over 10
hours, and a retry cannot fix any of those conditions.

---

## 7. Billing endpoints

| endpoint | permission | what it does |
|---|---|---|
| `GET /api/v1/billing/plans` | signed in | the ladder, entitlements, and live prices read back from Dodo |
| `GET /api/v1/billing/subscription` | `billing:read` | current subscription, effective entitlements, live usage against each |
| `POST /api/v1/billing/checkout` | `billing:write` | returns a `checkout_url`; body carries an `idempotency_key` |
| `POST /api/v1/billing/change-plan` | `billing:write` | upgrade or downgrade, prorated immediately |
| `POST /api/v1/billing/cancel` | `billing:write` | cancel at period end |
| `GET /api/v1/billing/credit-ledger` | `billing:read` | the usage-credit statement: every grant/hold/release/spend/expiry |
| `POST /api/v1/billing/top-up` | `billing:write` | one-time credit-pack checkout; 404 if `DODO_PRODUCT_CREDIT_PACK` is unset |
| `PATCH /api/v1/organisations/me/members/{id}/credit-cap` | `credits:write` | one teammate's share of the organisation's usage credit, in paise |
| `POST /api/v1/webhooks/dodo` | none — signature is the boundary | the only inbound write path |

`billing:read` is admin+, `billing:write` is **owner only**
(`apps/api/app/auth/permissions.py:58-59, 141`). `BILLING_WRITE` already exists and is
documented in that file as "upgrading/downgrading the plan itself" — currently attached to
no endpoint, and this is what it was reserved for.

**Prices are not in this repo.** Dodo is the seller of record and holds the price;
`GET /billing/plans` reads them back. That resolves `pricing.ts`'s all-`null` price fields
without inventing a number — a wrong price is worse than a missing one, which is why the
public `/pricing` page was deleted in the first place.

---

## 8. Schema

| table | scope | notes |
|---|---|---|
| `plan_entitlements` | reference | the numbers, seeded. `select` to `authenticated`; no insert/update/delete |
| `org_subscriptions` | `org_id` | current state + history. Unique `gateway_subscription_id`; partial unique index for one live row per org |
| `payments` | `org_id` | append-only. Unique `gateway_payment_id` is the idempotency key |
| `payment_webhook_events` | none | RLS on, **no policies, no grant** — a raw payload may hold data before we know whose it is |
| `org_entitlement_overrides` | `org_id` | the enterprise tier. Readable by the org; writable only via the platform definer function |
| `platform_admins` | none | RLS on, **no policies, no grant**. Rows created out of band only |
| `platform_audit_log` | none | append-only |
| `credit_ledger` | `org_id` | usage credit, append-only signed deltas (`grant`/`hold`/`release`/`spend`/`expiry`). `select` to `authenticated`; writes only through `credit_append`/`credit_settle`/`credit_release_stale_holds` (`SECURITY DEFINER`, and — since `ISSUES.md` #139 — checking the caller belongs to `org_id` unless the session is `anon`) |
| `usage_rates`, `provider_tiers` | reference | the published rate card: one platform-fee row plus per-leg tier add-ons, and which tier each vendor sits in. `select` to `authenticated, anon` — a public rate card, not tenant data |
| `member_credit_allocations` | `org_id` | `monthly_credit_cap_paise` — one per-teammate usage-credit ceiling, in money. Used to also hold `daily_allocation` (a call-count ceiling); retired (`ISSUES.md` #146) |

`payments.amount_minor` is BIGINT and holds the currency's minor unit — paise for INR,
cents for USD. This generalises CLAUDE.md §4 #3's "money is integers, paise, BIGINT" to a
multi-currency gateway; it does not weaken it. No floats anywhere in the path.

A webhook has no user JWT, so it resolves identity through a narrow `SECURITY DEFINER`
function on a `database.anonymous()` connection and writes through a second one — the
pattern `lookup_run_owner_for_webhook` established
(`202608091200_calle_webhook_run_lookup.py`). Attributing the write to the checkout
initiator via `as_user` would fail closed if that person were later removed or downgraded,
silently dropping a paid subscription.

---

## 9. What this does *not* do

**Superseded: a credit ledger shipped.** The row directly below described the state before
usage credit existed; it is kept, struck through in spirit, as a marker of what changed
rather than silently deleted. `credit_ledger` (migration `202608190900`) is real, append-only,
and `organisations.credit_balance_paise` is now a live, written cache of it — not dead. See
§8 and `docs/PRICING_DECISIONS.md` for the model: a platform fee per connected minute, plus
per-leg tier add-ons only when CallFlow's own key paid for that leg.

| not built | why |
|---|---|
| overage billing | calls are never charged per-call; the daily budget is a hard stop, not a metered overflow |
| a telephony limit | bring-your-own carrier costs CallFlow nothing (§1) |
| self-serve enterprise checkout | invoiced outside the product |
| a public `/pricing` page | unblocked once prices are real, but out of scope |
| a Razorpay adapter | the protocol exists and a stub is the second implementation; only Dodo is live |
| in-app invoices and receipts | Dodo hosts them as seller of record; Billing links out |
| per-token LLM billing | ADR-7's markup mechanism stays unbuilt. We cap per-org spend; we do not bill usage |
| dunning emails from us | Dodo owns dunning |
| org-scoped audit log | `platform_audit_log` is global and platform-only. `Permission.AUDIT_READ` still has no table |
| run pause/resume | does not exist, which is why `PRICING_FAQ`'s "the run pauses and resumes once you top up" gets rewritten rather than honoured |

### Pre-existing gaps this does not fix

| gap | status |
|---|---|
| `GET /api/health`'s org-wide `used_today` | still the in-process rate-limiter counter — resets on deploy, wrong across replicas |
| calling-window enforcement | still absent server-side (`ISSUES.md` #20) |
| per-teammate usage-credit cap | now real: `monthly_credit_cap_paise` on `member_credit_allocations`, enforced at the run gate (`ISSUES.md` #144) — the one per-teammate ceiling this ladder has. A separate call-count allowance (`daily_allocation`) used to sit alongside it and was retired (`ISSUES.md` #146) |

---

## 10. What exists today, precisely

| piece | state | source |
|---|---|---|
| the ladder | real, one home per side, with a test asserting the two agree | `domain/plans.py`, seeded `plan_entitlements` |
| the entitlement gates | real and pure; 402, plus a SQL-side guard where the route is not the only write path | `domain/entitlements.py` |
| the subscription state machine | real, exhaustive transition table, self-transitions rejected | `domain/subscriptions.py` |
| Dodo adapter + `PaymentProvider` protocol | real, two implementations; the stub signs its own webhooks so CI needs no account | `integrations/payments/` |
| `POST /api/v1/webhooks/dodo` | real, signature-verified, idempotent on `webhook-id`; confirmed end to end against a live gateway | `api/v1/routes/billing.py` |
| reconcile (`POST /billing/sync`) | real — the fallback for a webhook that was delayed, missed, or never configured | `services/billing.py` |
| `/app/billing` | real: plan, meters, live gateway prices, checkout/switch/cancel, payments | `app/(app)/app/billing/page.tsx` |
| `GET /api/v1/public/billing/plans` | real, unauthenticated, opens no connection — the marketing site's pricing section | `api/v1/routes/billing.py` |
| `pricing.ts` prices | still absent **by design** — the gateway is the price of record and the UI reads it back | `lib/pricing.ts` |
| `credit_ledger` | real — usage credit, append-only, granted on subscribe/renew/top-up, spent per connected second at the platform fee (no leg runs on CallFlow's own keys yet, so tier add-ons are seeded and unreachable) | `services/credit.py`, `database/repositories/credits.py` |
| `organisations.credit_balance_paise` | real — a live cache of `credit_ledger`'s sum, moved in the same statement as every ledger row | `database/models.py` |
| per-teammate daily call allowance | real **and enforced** at dial time; a separate layer from usage credit | `repositories/credits.py`, `domain/safety.py:112` |
| per-teammate usage-credit cap | real and enforced at the run gate, independent of the call allowance above | `domain/entitlements.py::check_member_credit_cap`, `routes/runs.py` |
| the subscription webhook's plan-change and cancellation path | real — `subscription.plan_changed`/`.updated` now apply, where before they were silently dropped | `services/billing.py` (`ISSUES.md` #141) |
| credit-pack top-ups | real end to end once `DODO_PRODUCT_CREDIT_PACK` is configured | `services/billing.py`, `services/credit.py` (`ISSUES.md` #142) |
| platform-admin identity + capabilities | real — `platform_admins`, RLS forced, no policies, no grants; granted only by `scripts/platform_admin.py` through `privileged.acquire` | `auth/platform.py` |
| the cross-tenant read path | real — `platform_can_read` on 17 `select` policies as *separate* permissive policies, plus `as_platform_reader` (read-only, audited, flag transaction-local) | `database/session.py` |
| entitlement overrides | real, and they reach the SQL guards via `effective_limit`, not just the Billing display | `platform_set_org_entitlements` |
| the enumerated **data** writes (§5) | **still design** — resolve-stuck-run, add-suppression, purge-org-data do not exist | — |
| public `/pricing` page | still deleted. The home page's `#pricing` section replaced it; the comparison matrix has no route | `components/marketing/pricing-preview.tsx` |

---

## 11. Copy that becomes false, and must change with the code

CLAUDE.md §4 #9 forbids showing a success state for something that did not happen. The
inverse bites here: shipping these limits makes existing copy wrong, and the copy is part
of the change.

| file | what is wrong once this ships |
|---|---|
| `pricing.ts` — `PlanId` and `PLANS` | `scale` becomes `enterprise`; the existing `ENTERPRISE` export becomes the fourth card rather than a separate block |
| `pricing.ts` — `FEATURE_MATRIX` | every row's `values` is `Record<PlanId, …>`, so every `scale:` key must be renamed. Add rows for Agents and Organisations |
| `pricing.ts` — Free's `Your own caller ID: false` and `Live calls included: false` | both become true — Free dials within 20/day now that telephony is unlimited |
| `pricing.ts` — `PRICING_FAQ` | four of eight answers describe overage, "not cut off mid-run", top-up/resume, and a pro-rata refund window — none of which this model has |
| `lib/verticals.ts` | its goal script is **read aloud to real people on real calls** and says pricing is "published on the website". Still false — `/pricing` stays deleted |
| `CAPABILITIES.md` §8 | "no payment processor wired up at all" becomes false |
| `docs/webhooks/page.mdx` | "Available from the Growth plan" becomes an enforced claim rather than aspirational copy |

Free's tagline and feature bullets **survive unchanged**, because telephony ended up
unlimited. An earlier draft required rewriting them.

---

## 12. Open decisions

| question | why it matters |
|---|---|
| Does Dodo's MoR invoice let an Indian B2B customer claim input tax credit? | If not, it constrains selling domestically through an MoR. The one item that could still change the gateway choice |
| Confirm the seeded ladder numbers | Deliberate defaults, not researched ones. Tune once there is real per-call cost data |
| Who gets the first `platform_admins` row, and how is that script run in production? | It is the bootstrap of a cross-tenant identity. Needs a named owner and a documented, logged procedure before the surface ships |
| Should `enterprise` orgs appear in `GET /billing/plans`? | They cannot check out, so showing a price is misleading; showing nothing hides the tier |
