/**
 * An in-progress voice agent, kept across a reload or a trip to another tab.
 *
 * The builder is long enough that losing it to a refresh - or to clicking
 * Contacts to check something - costs real work. The same shape and the same
 * failure posture as `campaign-draft.ts`: a read that cannot parse returns
 * null rather than throwing, and a write that cannot store is dropped, so a
 * browser with storage disabled degrades to "this session only" instead of
 * breaking the editor.
 *
 * Drafts are keyed per organisation and then per agent, so editing two agents
 * in two tabs does not have them overwrite each other, and work started in one
 * organisation is not offered back inside another. `new` is its own key.
 */

import type { CampaignField, TelephonyProvider } from './api';

const DRAFT_KEY = 'callflow.agent.draft';

/**
 * Bumped to `v2` when the organisation id entered the key.
 *
 * Every key used to be `callflow.agent.draft.<agentId|new>[.<fingerprint>]`
 * with no organisation anywhere, so `listUnsavedAgentDrafts()` scanned a
 * prefix shared by every organisation and `loadAgentDraft(null)` returned the
 * newest draft in the *browser* - the previous organisation's name, prompt and
 * providers prefilled into a brand-new agent somewhere else entirely
 * (`ISSUES.md` #128).
 *
 * The version segment is what makes the old keys identifiable: `v1` and `v2`
 * shapes are otherwise ambiguous, since an agent id and an organisation id are
 * both UUIDs sitting in the same position.
 */
const VERSION = 'v2';

/**
 * How many unsaved drafts this browser keeps.
 *
 * A drafts tab is for picking up work you walked away from, and past a
 * handful it stops being that and becomes a list to manage. The oldest is
 * dropped when a sixth appears.
 */
const MAX_DRAFTS = 5;

export interface AgentDraft {
  name: string;
  sttProvider: string | null;
  ttsProvider: string | null;
  voiceId: string | null;
  llmModel: string | null;
  systemPrompt: string;
  collectFields: CampaignField[];
  telephonyProvider: TelephonyProvider | null;
  /** What the editor picked on its own, to tell a seeded draft from a built
   *  one. Absent on drafts written before this field existed. */
  seed?: AgentDraftSeed;
  /** Last write, epoch ms. Orders the list and decides what gets evicted.
   *  Absent on drafts written before this field existed - those sort oldest,
   *  which is the right side to err on. */
  savedAt?: number;
}

export function agentDraftKey(orgId: string, agentId: string | null): string {
  return `${DRAFT_KEY}.${VERSION}.${orgId}.${agentId ?? 'new'}`;
}

/**
 * Remove every draft written before drafts were organisation-scoped.
 *
 * Without this they are merely unreachable rather than gone - invisible to the
 * new prefix, but still sitting in storage, and still the drafts someone is
 * looking at right now on a browser that has not reloaded. Cheap, idempotent,
 * and runs from the two places that read drafts.
 */
export function purgeLegacyAgentDrafts(): void {
  const current = `${DRAFT_KEY}.${VERSION}.`;
  const legacy = `${DRAFT_KEY}.`;
  try {
    const doomed: string[] = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (!key?.startsWith(legacy) || key.startsWith(current)) continue;
      doomed.push(key);
    }
    // Collected first, removed after: removing during the scan shifts every
    // later index and silently skips half of them.
    for (const key of doomed) localStorage.removeItem(key);
  } catch {
    /* storage unavailable - nothing to purge */
  }
}

/** The newest unsaved draft in this organisation, which is the one
 *  "Create agent" resumes. */
export function loadAgentDraft(
  orgId: string | null,
  agentId: string | null,
): AgentDraft | null {
  if (!orgId) return null;
  purgeLegacyAgentDrafts();
  if (agentId) {
    try {
      const raw = localStorage.getItem(agentDraftKey(orgId, agentId));
      return raw ? (JSON.parse(raw) as AgentDraft) : null;
    } catch {
      return null;
    }
  }
  return listUnsavedAgentDrafts(orgId).at(-1)?.draft ?? null;
}

export function saveAgentDraft(
  orgId: string | null,
  agentId: string | null,
  draft: AgentDraft,
): void {
  // No organisation resolved yet means no idea which one this belongs to, and
  // guessing is what this whole change exists to stop.
  if (!orgId) return;
  try {
    // An existing agent keeps one draft under its own id. A new agent is
    // keyed by its configuration instead, so a second differently-built
    // agent becomes a second card rather than overwriting the first.
    const key = agentId
      ? agentDraftKey(orgId, agentId)
      : `${agentDraftKey(orgId, null)}.${draftFingerprint(draft)}`;
    localStorage.setItem(key, JSON.stringify({ ...draft, savedAt: Date.now() }));
    if (!agentId) evictOldestDrafts(orgId);
  } catch {
    /* storage unavailable - the draft lives for this session only */
  }
}

/**
 * Keep the newest `MAX_DRAFTS` and drop the rest.
 *
 * Run after the write, not before, so the draft just saved is one of the
 * candidates - editing the oldest draft makes it the newest and something
 * else falls off, rather than the one being worked on being evicted.
 */
function evictOldestDrafts(orgId: string): void {
  const drafts = listUnsavedAgentDrafts(orgId);
  if (drafts.length <= MAX_DRAFTS) return;
  for (const stale of drafts.slice(0, drafts.length - MAX_DRAFTS)) {
    clearAgentDraftByKey(stale.key);
  }
}

/** Discard one specific draft by the key `listUnsavedAgentDrafts` returned. */
export function clearAgentDraftByKey(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch {
    /* nothing to clear if storage is unavailable */
  }
}

/** Called after a successful save: the server copy is now the truth, and a
 *  stale draft would otherwise reappear over it on the next visit. */
export function clearAgentDraft(
  orgId: string | null,
  agentId: string | null,
): void {
  if (!orgId) return;
  try {
    localStorage.removeItem(agentDraftKey(orgId, agentId));
  } catch {
    /* nothing to clear if storage is unavailable */
  }
}

/** A draft plus the id it belongs to - `null` for one that has never been
 *  saved, which is the id the editor route uses for a new agent. */
export interface StoredAgentDraft {
  agentId: string | null;
  /** The storage key, so a card can discard exactly this one. */
  key: string;
  draft: AgentDraft;
}

/**
 * What makes two drafts the same draft.
 *
 * Keying on the *configuration* rather than on "the new-agent slot" means
 * going back to build a second, differently-configured agent starts a second
 * draft instead of overwriting the first - while returning to the same one
 * and continuing to edit it keeps updating the one card.
 */
export function draftFingerprint(draft: AgentDraft): string {
  return [
    draft.name.trim().toLowerCase(),
    draft.sttProvider ?? '',
    draft.ttsProvider ?? '',
    draft.llmModel ?? '',
    draft.voiceId ?? '',
  ].join('|');
}

/**
 * The providers the editor fills in by itself, so a draft holding nothing but
 * these is the seed state rather than a decision. Recorded on the first write
 * of each draft; a draft from before this existed has none, and is judged on
 * its other fields alone.
 */
export interface AgentDraftSeed {
  sttProvider: string | null;
  ttsProvider: string | null;
  llmModel: string | null;
}

/**
 * Has anyone actually built something here?
 *
 * The editor writes a draft on its first render, before any interaction, so
 * "a draft exists" is not the same as "there is work to resume". Anything the
 * builder could only have set themselves counts - and that includes the
 * providers: changing just the model and walking away is exactly the case a
 * drafts list has to catch. An earlier version checked only the name and the
 * prompt, so that walk-away vanished.
 */
function hasWork(draft: AgentDraft): boolean {
  if (
    draft.name?.trim() ||
    draft.systemPrompt?.trim() ||
    draft.collectFields?.length ||
    draft.voiceId ||
    draft.telephonyProvider
  ) {
    return true;
  }

  const seed = draft.seed;
  if (!seed) return false;
  return (
    draft.sttProvider !== seed.sttProvider ||
    draft.ttsProvider !== seed.ttsProvider ||
    draft.llmModel !== seed.llmModel
  );
}

/**
 * Every draft this browser is holding, for the "Drafts" row on the agents
 * page.
 *
 * A draft of an agent that already exists is deliberately excluded: that agent
 * is already on the page as a real card, and listing it twice would say there
 * are two of something there is one of. What this surfaces is the work that
 * exists *nowhere else* - a new agent someone walked away from.
 */
export function listUnsavedAgentDrafts(
  orgId: string | null,
): StoredAgentDraft[] {
  if (!orgId) return [];
  purgeLegacyAgentDrafts();
  // Scoped to one organisation: this prefix used to be shared by all of them,
  // which is how work started elsewhere showed up on this page.
  const prefix = `${agentDraftKey(orgId, null)}.`;
  const found: StoredAgentDraft[] = [];
  try {
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (!key?.startsWith(prefix)) continue;
      const raw = localStorage.getItem(key);
      if (!raw) continue;
      const draft = JSON.parse(raw) as AgentDraft;
      if (!hasWork(draft)) continue;
      found.push({ agentId: null, key, draft });
    }
  } catch {
    return [];
  }
  // Oldest first: `evictOldestDrafts` takes from the front, and the tab reads
  // top-to-bottom as least- to most-recent.
  return found.sort((a, b) => (a.draft.savedAt ?? 0) - (b.draft.savedAt ?? 0));
}
