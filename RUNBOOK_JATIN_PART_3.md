# RUNBOOK — Part 3: Internal Team Chat

**Owner:** Jatin
**Source plan:** `PLATFORM_PIVOT_PLAN.md` — ADR-6 (whole), ADR-4's chat API-surface section, §12 Track B (B1–B3)
**Companion runbooks:** `RUNBOOK_HET_PART_1.md` (voice runtime, telephony, CALL-E removal), `RUNBOOK_ARBAAZ_PART_2.md` (voice-agent product surface, extraction/triage)

---

## 0. Grounding — verified against the actual repo, read this before writing any SQL

This is the one workstream in the whole pivot with **zero schema and zero code overlap** with Parts 1/2 — confirmed by a full-repo search, not assumed. But three things the plan's own ADR-6 states as established fact turned out **not to match this repo**, and you need to know that before you start, because it changes what you're actually building:

1. **No `channels`/`channel_members`/`messages` table exists anywhere.** Confirmed — full-text search across `apps/api/app/database/models.py` and every file in `apps/api/alembic/versions/`. This was already expected (the plan itself says so), just stated here for completeness.

2. **`share_requests` and `escalations`/`credit_allocations` are NOT real tables in this repo.** The plan's §1 reuse-map cites `202608101100_share_requests.py` and `202608100900_escalations_and_credit_allocations.py` as already-shipped migrations whose RLS pattern chat should copy. **Neither file exists** — `apps/api/alembic/versions/` has 22 migrations, the newest dated `202608092600`, nothing from `202608100xxx` or `202608101xxx`. `escalations` is not a table at all: `apps/web/lib/app-store.tsx` derives the "Needs a person" worklist client-side from `call_outcomes` rows (`escalations = outcomes.filter(o => lampForOutcome(o).state === 'flare')`) — there is no persisted `escalations` table to model your own RLS after. **Do not go looking for these files or try to diff against them — they aren't prior art you missed, they don't exist on this branch.**

3. **The actual, real prior art for the RLS pattern you need is different from what the plan cites, but it's real and it's better grounding than a citation to a nonexistent file:**
   - The `SECURITY DEFINER`-helper-breaks-RLS-recursion pattern is genuinely in this repo, in `apps/api/alembic/versions/202608060050_initial_schema.py`. Its own comment states the exact reasoning you need: *"a policy on memberships that queried memberships directly would recurse infinitely... running inside a definer function bypasses RLS and breaks the cycle."* `is_org_member(target_org uuid)`, `has_org_role(target_org uuid, allowed org_role[])`, and `current_user_id()` are all real, live, `SECURITY DEFINER`, `search_path`-pinned functions you will call directly — not reimplement.
   - The `RETURNING`-triggers-`SELECT`-policy trap ADR-6 warns about for `create_channel()` is real and already fixed once in this exact repo: `apps/api/alembic/versions/202608072000_organisation_create_function.py`'s `create_organisation()`. Its docstring explains the bug precisely: inserting into an RLS-protected, force-enabled table with `RETURNING` makes Postgres re-check the new row against the table's own `SELECT` policy *before* it can be handed back — and at the moment of that first insert, the row that would satisfy the policy (a membership, in that case; a `channel_members` row, in yours) doesn't exist yet. The fix there is a `SECURITY DEFINER` function that inserts both rows atomically before returning anything. This is your exact template for `create_channel()` — read that migration file directly, don't work from the plan's paraphrase of it.
   - **`ISSUES.md`'s real last entry is `#76`**, not `#84`/`#85` as ADR-6 cites for the "campaign-clone bug" that established this pattern. Verify with `grep '^### #' ISSUES.md | tail -1` before writing your own entry — and don't cite `#84`/`#85` in your own commit messages or migration docstring, since a future reader searching for them will find nothing.

4. **No Realtime/Postgres-Changes wiring exists anywhere in this repo, and it has never been configured — not partially, not once.** Confirmed by three independent checks: no `.channel(` call anywhere in `apps/web`, no `use-org-realtime.ts` file at the path the plan cites (`apps/web/lib/hooks/` has 15 files, none of them this one), and `SUPABASE_SETUP.md` — the project's own dashboard-configuration checklist — has zero mentions of "realtime" or "publication" anywhere. **The plan's claim that `useOrgRealtime` "already accepts an arbitrary table name — no code change needed for chat's realtime wiring" is describing a hook that does not exist in this codebase.** You are building this hook from scratch, not reusing it, and you also need to actually enable the Realtime publication for your new tables (Postgres Changes only fires for tables added to `supabase_realtime`) — nobody has done this for any table in this project yet, so there's no existing publication list to just add to.

5. **The good news: nothing new needs installing.** `apps/web/package.json` already has `@supabase/supabase-js@^2.112.1`, which includes the full Realtime client (`.channel().on('postgres_changes', ...)`). This is a "use the already-installed dependency" job, not a "add a new one" job.

Everything else in ADR-6 — the table shapes, the RLS design, the permission model, the API surface — matches what you'd build from scratch anyway and is sound. The above is about what's *already there to build on*, which is less than the plan implies, not about the target design being wrong.

---

## 1. Objective and scope

Build internal team chat: channels and DMs between teammates within one organisation. Not contact-facing SMS/WhatsApp, not an in-agent text channel — confirmed by the user's own explicit clarification cited in the plan. You own the entire feature, end to end: schema, RLS, repositories, routes, permissions, and the frontend surface, plus the one piece of shared infrastructure (the Realtime hook) that happens to live in `apps/web/lib/hooks/` where a future non-chat feature could also use it, but which you are building for this feature's own need.

**You own everything under this runbook.** There is no "you do NOT own" section the way Parts 1/2 have one, because there's no overlap to carve out.

---

## 2. Dependencies and assumptions

- **Zero dependency on Part 1 or Part 2.** Start immediately, run the entire time they're working.
- **Two files are shared, both trivially additive** (see §7): `apps/api/app/auth/permissions.py` (you add `MESSAGES_READ`/`MESSAGES_SEND`) and `apps/web/components/layout/app-nav.tsx` (you add a nav entry). Neither requires waiting on the other developers — just rebase before you push if either file has moved on.
- **Assumption you should verify, not trust:** that Postgres Changes will actually be enabled for your new tables. Supabase requires each table added to the `supabase_realtime` publication before `postgres_changes` fires for it — either via `alter publication supabase_realtime add table ...` in your own migration, or a manual dashboard step. Since no table in this project has ever been added to this publication, confirm which mechanism this Supabase project actually expects (check whether `supabase_realtime` publication exists at all yet, and whether Alembic's migration role has permission to alter it) before assuming a one-line SQL statement handles it — if it doesn't, this becomes a new `SUPABASE_SETUP.md` checklist item (a human dashboard action), matching that file's own stated purpose ("dashboard settings a human must click," per `CLAUDE.md`'s document map).

---

## 3. Task list — B1: schema, RLS, and the two `SECURITY DEFINER` functions

### P3-T1 — the migration

New Alembic revision (follow the `down_revision` chain — check `apps/api/alembic/versions/` for the current head before setting yours). Table shapes are fully specified in ADR-6; reproduce them as given, with the corrections below already folded in (the plan's own adversarial review caught real recursion bugs in an earlier draft — the SQL below is the corrected version, not the first draft):

```sql
create table public.channels (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,
  kind text not null check (kind in ('channel', 'dm')),
  name text,
  created_by uuid references public.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.channel_members (
  channel_id uuid not null references public.channels(id) on delete cascade,
  user_id uuid not null references public.users(id) on delete cascade,
  joined_at timestamptz not null default now(),
  primary key (channel_id, user_id)
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  org_id uuid not null references public.organisations(id) on delete cascade,
  channel_id uuid not null references public.channels(id) on delete cascade,
  sender_id uuid references public.users(id) on delete set null,
  body text not null,
  created_at timestamptz not null default now(),
  edited_at timestamptz,
  deleted_at timestamptz
);
```

- `messages.org_id` is denormalised (derivable via `channel_id`) — deliberately, matching the exact reasoning `escalations.org_id` would use if that table existed: direct RLS/index without a join. Don't "clean this up" to a pure foreign-key-only design.
- `messages.deleted_at` is a soft delete — a hard-deleted row re-checked by RLS on a lagging Realtime event is a real edge case worth avoiding for free; a client-side filter on `deleted_at is null` is cheap insurance.

**The two `SECURITY DEFINER` helpers — write these using the exact syntax `apps/api/alembic/versions/202608060050_initial_schema.py`'s `is_org_member`/`has_org_role` already use** (`language sql stable security definer set search_path = public, pg_temp`), not a new style:

```sql
create or replace function public.is_channel_member(target_channel uuid)
returns boolean language sql stable security definer
set search_path = public, pg_temp as $$
  select exists (
    select 1 from public.channel_members
    where channel_id = target_channel and user_id = public.current_user_id()
  );
$$;

create or replace function public.channel_org_id(target_channel uuid)
returns uuid language sql stable security definer
set search_path = public, pg_temp as $$
  select org_id from public.channels where id = target_channel;
$$;
```

**RLS — the exact policies, with the two real recursion cycles the plan's own review caught, both avoided the same way `#84`-shaped bugs are avoided elsewhere in this codebase** (a policy on a table must never query that same table directly; go through a `SECURITY DEFINER` helper instead):

```sql
alter table public.channels enable row level security;
alter table public.channels force row level security;
alter table public.channel_members enable row level security;
alter table public.channel_members force row level security;
alter table public.messages enable row level security;
alter table public.messages force row level security;

create policy channels_select on public.channels for select
  using (public.is_channel_member(id));

create policy channel_members_select on public.channel_members for select
  using (
    public.is_channel_member(channel_id)
    or public.has_org_role(public.channel_org_id(channel_id), array['owner','admin']::public.org_role[])
  );

-- Adding a teammate to an EXISTING channel — not the creation path, see create_channel() below.
create policy channel_members_insert on public.channel_members for insert
  with check (
    public.is_channel_member(channel_id)
    and public.is_org_member(public.channel_org_id(channel_id))
  );

create policy messages_select on public.messages for select
  using (public.is_channel_member(channel_id));

create policy messages_insert on public.messages for insert
  with check (sender_id = public.current_user_id() and public.is_channel_member(channel_id));

grant select, insert on public.channels, public.channel_members, public.messages to authenticated;
```

**Note what's deliberately absent:** no `channels_insert` policy, because channel *creation* never goes through a plain client-side `INSERT ... RETURNING` — see `create_channel()` below, which is why this table doesn't need one. No admin-approval gate on creating a DM/channel — unlike a resource-sharing model, chat membership is opt-in social structure, matching the plan's own explicit reasoning.

**`create_channel()` — this is your `create_organisation()` template, read that migration file, don't reinvent the shape:**

```sql
create or replace function public.create_channel(
  target_org uuid, target_kind text, target_name text, member_ids uuid[]
)
returns uuid language plpgsql security definer
set search_path = public, pg_temp as $$
declare new_channel_id uuid;
begin
  if not public.is_org_member(target_org) then
    raise exception 'not a member of this organisation';
  end if;
  insert into public.channels (org_id, kind, name, created_by)
    values (target_org, target_kind, target_name, public.current_user_id())
    returning id into new_channel_id;
  insert into public.channel_members (channel_id, user_id)
    select new_channel_id, unnest(member_ids || array[public.current_user_id()]);
  return new_channel_id;
end;
$$;
```

This exists for exactly the reason `create_organisation()` does: a plain client-side insert into `channels` followed by a separate insert into `channel_members` would hit the same `RETURNING`-before-membership-exists race `202608072000_organisation_create_function.py` documents — at the moment `channels`' own insert tries to `RETURNING` its new row, `channels_select`'s `is_channel_member(id)` policy is checked, and no `channel_members` row exists yet to satisfy it. Doing both inserts atomically inside a `SECURITY DEFINER` function, which bypasses RLS entirely for its own body, is what `create_organisation()` already proved is the fix — apply it identically here, don't invent a different workaround.

**Realtime publication — verify before assuming this line is sufficient (see §2's caveat):**

```sql
alter publication supabase_realtime add table public.channels, public.channel_members, public.messages;
```

If the migration role lacks permission to alter this publication, or the publication doesn't exist yet on this Supabase project, this needs to become a `SUPABASE_SETUP.md` checklist entry instead — check which is true for this project before shipping either path silently.

### P3-T2 — repositories

New files, raw asyncpg, following `apps/api/app/database/repositories/campaigns.py`'s or `organisations.py`'s shape (both already call into `SECURITY DEFINER` functions the same way you will — `organisations.py`'s `create()` is literally `return await conn.fetchrow("select * from public.create_organisation($1)", name)`; yours is the same call shape with more arguments):

- `apps/api/app/database/repositories/channels.py`:
  - `create_channel(conn, *, org_id, kind, name, member_ids, ...) -> uuid` → `select public.create_channel($1, $2, $3, $4)`.
  - `list_my_channels(conn, org_id) -> list[Record]` — relies on RLS (`channels_select`) to narrow to the caller's own channels, the same way `runs_repo.summarize_by_member()` leans entirely on RLS rather than filtering itself.
  - `add_member(conn, channel_id, user_id)` — a plain insert, governed by `channel_members_insert`'s RLS policy (not a `SECURITY DEFINER` function — the docstring in ADR-6 is explicit that this one is safe as an ordinary insert precisely because the app never asks for that insert's row back via `RETURNING`).
- `apps/api/app/database/repositories/messages.py`:
  - `list_messages(conn, channel_id) -> list[Record]`.
  - `send_message(conn, *, channel_id, sender_id, body) -> Record` — plain insert with `RETURNING`, safe here because `messages_insert`'s check (`sender_id = current_user_id() and is_channel_member(channel_id)`) is already satisfiable at insert time (the sender is, by definition, already a channel member — no chicken-and-egg the way channel creation has).

### P3-T3 — routes

New file `apps/api/app/api/v1/routes/messages.py`, following `routes/campaigns.py`'s structure (Pydantic models next to the router, `Depends(RequirePermission(...))` for writes, plain `Depends(current_user)` for reads):

```python
class ChannelIn(BaseModel):
    kind: Literal["channel", "dm"]
    name: str | None = None
    member_ids: list[UUID]

class ChannelOut(BaseModel):
    id: UUID
    kind: Literal["channel", "dm"]
    name: str | None
    member_ids: list[UUID]
    created_at: datetime

class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

class MessageOut(BaseModel):
    id: UUID
    channel_id: UUID
    sender_id: UUID | None
    sender_name: str | None
    body: str
    created_at: datetime
    edited_at: datetime | None

# GET  /api/v1/channels                  - list mine, MESSAGES_READ
# POST /api/v1/channels                  - create, MESSAGES_SEND
# GET  /api/v1/channels/{id}/messages    - MESSAGES_READ (RLS narrows to membership regardless)
# POST /api/v1/channels/{id}/messages    - MESSAGES_SEND
```

- Validate `name` is required when `kind == "channel"` and ignored for `kind == "dm"` (a 400 with a specific message per `CLAUDE.md`'s error-writing convention, matching how `routes/campaigns.py` validates `extra_fields[].type`).
- Wire this router into `apps/api/app/main.py`'s router includes, the same way every other route module is registered.

### P3-T4 — permissions

`apps/api/app/auth/permissions.py`: add two new `Permission` enum values, `MESSAGES_READ = "messages:read"` and `MESSAGES_SEND = "messages:send"`. Placement: `MESSAGES_READ` goes in `_READ_ONLY` (every role, including viewer — opening the chat surface at all is a breadth question the same way viewing the dashboard is, matching the plan's own reasoning). `MESSAGES_SEND` goes in `_OPERATOR` (operator and above — viewer stays read-only everywhere else in the product, and chat shouldn't be the one exception). Follow the exact existing pattern — don't add a new role-set constant, extend the existing `_READ_ONLY`/`_OPERATOR` frozensets the same way `CAMPAIGNS_READ`/`CAMPAIGNS_WRITE` already do.

**Important, and easy to get wrong by analogy with campaigns/runs:** resource visibility within chat is **not** governed by role at all beyond the read/send split above — it's entirely `channel_members` membership, enforced by RLS. A viewer who isn't a member of a given DM cannot see it, the same way an operator who isn't assigned an escalation can't see it. Don't add any per-role narrowing beyond `MESSAGES_READ`/`MESSAGES_SEND` — the membership check is the real access control, and it lives in the database, not in `permissions.py`.

---

## 4. Task list — B2: frontend

### P3-T5 — `useOrgRealtime` (build from scratch — see §0 point 4)

New file `apps/web/lib/hooks/use-org-realtime.ts`. This does not exist yet anywhere in this codebase; you are not adapting an existing hook, you're writing the first one. Shape it as a generic subscription over an arbitrary table name (so a future feature — the plan's own aside about `TEAM_COLLABORATION_ROADMAP.md` Phase 3 notifications — could reuse it later, but don't build for that use case now; build it for exactly what chat needs):

```ts
export function useOrgRealtime(table: string, orgId: string | null, onChange: () => void): void
```

- Use `supabaseBrowser()` (already exists at `apps/web/lib/supabase/client.ts`) and its `.channel(...)` API — `@supabase/supabase-js@^2.112.1` is already installed, this needs no new dependency.
- Subscribe to `postgres_changes` filtered by `org_id=eq.${orgId}` on the given table — **document in this hook's own docstring, explicitly, the security caveat ADR-6 itself raises**: this `org_id` filter is a bandwidth optimisation evaluated server-side, **not** the security boundary. For a public/org-wide table this distinction doesn't matter; for `messages`/`channels`, RLS (`messages_select`/`channels_select`, both requiring `is_channel_member`) is what actually authorises which rows a Postgres Changes event is delivered for at all — a teammate who isn't in a channel never receives its events regardless of what this hook's own filter says. Get the RLS policies right (P3-T1); this hook is a refetch trigger, not a permission check.
- On event: call `onChange()` (a refetch, not a direct cache mutation) — this matches every other data-loading pattern already in `apps/web/lib/app-store.tsx` (fetch-then-set-state), and keeps this hook simple: it doesn't need to know the shape of what it's watching.
- Clean up the channel subscription on unmount and on `orgId`/`table` change — mirror `use-run-poll.ts`'s cleanup discipline (`cancelled` flag + explicit `clearInterval`/equivalent teardown).

### P3-T6 — channel list + message view

New route(s) under `apps/web/app/(app)/app/` — the plan doesn't mandate an exact path; `/app/chat` is a reasonable, discoverable choice consistent with the existing five-item nav (`/app`, `/app/campaigns`, `/app/runs`, `/app/escalations`, `/app/contacts`). Structure this closer to the Escalations worklist pattern than anything else in the codebase (a list + a detail/sheet view), per the plan's own comparison:
- A channel/DM list (left rail or top-level list), built via `POST /api/v1/channels` for creation and `GET /api/v1/channels` for listing, subscribed to Realtime updates via `useOrgRealtime('channels', orgId, refetch)`.
- A message view per selected channel: `GET .../messages` for history, `POST .../messages` to send, `useOrgRealtime('messages', orgId, refetch)` for live updates. Follow `apps/web/app/(app)/app/escalations/page.tsx`'s `DialogRoot`/`Sheet` pattern for how a list item opens into a detail view if a sheet-based layout fits better than a persistent two-pane view — either is reasonable, pick based on how much screen real estate a chat surface actually needs versus the Sheet pattern used for transcripts.
- Add `channels`/`messages` client methods to `apps/web/lib/api.ts`, following the existing `api.listRuns`/`api.getRun` naming and `authReq<T>()` wrapper pattern exactly — don't introduce a second fetch helper.
- Nav entry in `apps/web/components/layout/app-nav.tsx`'s `NAV_ITEMS` array — add a "Chat" (or similar) entry. This is a shared-file edit with Part 2 (who adds an "Agentic" entry) — see §7.
- Permission-gate the UI the same way `runs/new/page.tsx` already gates on `session.profile.permissions.includes(...)` — hide the send composer (not the whole surface) for a viewer, matching `MESSAGES_READ`/`MESSAGES_SEND`'s split.

---

## 5. Step-by-step implementation order

1. **P3-T1** (migration: tables, RLS, both `SECURITY DEFINER` functions, Realtime publication) — everything else depends on this existing, even locally/unmigrated, so do it first and iterate.
2. **P3-T2** (repositories) — thin wrappers, quick once the SQL is settled.
3. **P3-T4** (permissions) — small, do it alongside T2 so T3's route dependencies have something to reference.
4. **P3-T3** (routes) — depends on T2 and T4.
5. **P3-T5** (`useOrgRealtime`) — has no dependency on T1–T4 at all; can be built and unit-tested against a stub Supabase client in parallel with the backend work, then wired into T6 once both are ready.
6. **P3-T6** (frontend UI) — depends on T3 (real endpoints) and T5 (the hook); build against a mocked API response first if you reach this before T3 merges, matching the plan's own stated pattern for exactly this situation ("build against the API contract from day one, against a mocked response; swap to the real endpoint once it lands").

---

## 6. Expected inputs/outputs summary

| Operation | Input | Output |
|---|---|---|
| `create_channel()` (SQL function) | `org_id, kind ('channel'\|'dm'), name (nullable), member_ids[]` | new `channel_id` (uuid); caller is auto-added as a member |
| `POST /api/v1/channels` | `ChannelIn` | `ChannelOut`, `201` |
| `GET /api/v1/channels` | — (caller's org + identity from auth) | `list[ChannelOut]`, only channels the caller is a member of |
| `GET /api/v1/channels/{id}/messages` | channel id | `list[MessageOut]`, oldest-first or newest-first (pick one, be consistent with how the message view scrolls) |
| `POST /api/v1/channels/{id}/messages` | `MessageIn` | `MessageOut`, `201` |
| `useOrgRealtime(table, orgId, onChange)` | table name, org id, refetch callback | no return value; fires `onChange()` on any insert/update/delete Postgres Changes event RLS allows through |

---

## 7. Integration points, shared files, and how to avoid conflicts

You have exactly two shared files in the entire pivot, both purely additive:

| File | Your edit | Who else touches it | How to avoid conflict |
|---|---|---|---|
| `apps/api/app/auth/permissions.py` | Add `MESSAGES_READ`/`MESSAGES_SEND` enum values + role-set placement | Part 2 adds `AGENTS_READ`/`AGENTS_WRITE`/`AGENTS_DELETE` (unrelated permission group) | Both are additive enum entries in unrelated groups. If you both edit around the same time, it's a two-line merge, not a design conflict — just rebase before pushing. |
| `apps/web/components/layout/app-nav.tsx` | Add a Chat nav entry to `NAV_ITEMS` | Part 2 adds an Agentic nav entry | Same — additive array entries. Check whether Part 2's entry already landed before you add yours (`git log -p` on this file), and append after theirs rather than reordering the array, so the diff stays minimal for whoever reviews next. |

**Nothing else in either other runbook touches your tables, your routes, or your components.** You do not need to coordinate sequencing with Part 1 or Part 2 beyond these two files — you can genuinely work heads-down and only need to sync near the end to resolve the two trivial file conflicts above.

---

## 8. Testing requirements

- **Cross-tenant AND cross-membership RLS tests are required — this is the most important test class in this entire runbook.** Follow `apps/api/tests/test_rls_isolation.py`'s existing pattern, hitting the database directly:
  - Org A's member cannot see Org B's channels/messages at all (standard cross-tenant check, same as every other tenant table).
  - **Within the same org**, a member who is *not* in a given channel cannot see its messages, cannot see the channel in their list, and — this is the one that's easy to get wrong — does not receive its Realtime events either (test this by asserting the `messages_select`/`channels_select` policies reject a direct query as that user, which is what actually gates Postgres Changes delivery, not by trying to simulate a live Realtime subscription in a unit test).
  - An admin/owner (per `channel_members_select`'s second branch) can see channel *membership* rows for channels they're not in, but confirm this does **not** leak into being able to read `messages` for a channel they're not a member of — `messages_select` has no admin/owner branch, deliberately; write a test that proves it.
- Test `create_channel()` directly: calling it seats the caller as a member atomically, and a second call with the same org/kind/members doesn't need idempotency the way `telephony_provisioning` does (chat creation isn't retried the way a provisioning workflow is) — but do verify a normal two-insert failure (e.g. an invalid `member_ids` entry) doesn't leave an orphaned `channels` row with no members.
- Test the `channel_members_insert` policy directly (adding a teammate to an existing channel): a non-member cannot add themselves or anyone else; an existing member can add another org member; adding a non-org-member is rejected.
- `useOrgRealtime`: at minimum, a test (or manual verification, matching this repo's existing frontend-testing conventions — no component test runner exists in `apps/web` beyond `tsc`/`eslint` today, don't introduce one for this alone) that the hook unsubscribes on unmount and doesn't leak a stale subscription across an org switch, mirroring `use-run-poll.ts`'s own cancellation discipline.
- `ruff check app tests` / `pytest -q` in `apps/api`; `npm run lint && npm run type-check && npm run build` in `apps/web`.

---

## 9. Validation checklist / Definition of Done

- [ ] `channels`, `channel_members`, `messages` tables exist with full RLS (enable + force, per-command policies, grants to `authenticated`) — no table shipped with only some of the four required pieces (`CLAUDE.md` §4b's "a table with three of the four is a data leak").
- [ ] `is_channel_member()` and `channel_org_id()` exist as `SECURITY DEFINER`, `search_path`-pinned functions, and no policy queries `channel_members`/`channels` directly from within a policy on that same table (verified by reading the SQL, not just by it passing tests).
- [ ] `create_channel()` seats the creator as a member atomically; a direct two-step client insert is never used for channel creation.
- [ ] Cross-tenant AND cross-membership RLS tests pass, including the admin/owner-sees-membership-but-not-messages distinction.
- [ ] The Realtime publication question (§2/§3's caveat) is resolved one way or the other — either your migration successfully adds the tables to `supabase_realtime`, or `SUPABASE_SETUP.md` gains a new checklist entry documenting the manual step, but it is not left silently unresolved.
- [ ] `MESSAGES_READ`/`MESSAGES_SEND` exist in `permissions.py`, correctly placed (`READ` for every role, `SEND` for operator and above), and chat's actual per-conversation visibility is governed by `channel_members`, not by a role check anywhere in the route or repository layer.
- [ ] `useOrgRealtime` exists, is generic over table name, subscribes/unsubscribes cleanly, and its docstring states plainly that its `org_id` filter is a bandwidth optimisation, not the security boundary.
- [ ] Channel list + message view are reachable from a new nav entry, permission-gated (send composer hidden for viewers), and update live via Realtime without a manual refresh.
- [ ] `SYSTEM.md` gains a new module/endpoint section for chat (per `CLAUDE.md`'s "a PR that changes an endpoint and not `SYSTEM.md` is incomplete" rule) and `ISSUES.md` gets an entry at whatever the real next number is (verified, not assumed to be `#77`+something already claimed by another workstream).
