"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, type Campaign, type Health, type Outcome, type Run } from "@/lib/api";
import { parseSheet, toContactInputs, type ParsedRow } from "@/lib/contacts";
import { DispositionBadge, SentimentBadge } from "./badges";
import CampaignBuilder from "./campaign-builder";
import ContactUpload from "./contact-upload";
import { PhoneIcon, PlusIcon, TrashIcon } from "./icons";

const FIELD_LABELS: Record<string, string> = {
  outcome: "Outcome",
  sentiment: "Sentiment",
  frustration_signals: "Frustration",
  wants_human_callback: "Wants human",
  do_not_call: "Do not call",
  service_interest: "Service",
  destination: "Destination",
  travel_date: "Travel date",
  party_size: "Party size",
  budget_inr: "Budget (INR)",
  ready_for_quote: "Ready for quote",
  confirmed: "Confirmed",
  reschedule_to: "Reschedule to",
  cancelled: "Cancelled",
};

const label = (k: string) => FIELD_LABELS[k] ?? k.replace(/_/g, " ");

function formatValue(v: unknown): { text: string; tone: "on" | "off" | "plain" } {
  if (v === true) return { text: "Yes", tone: "on" };
  if (v === false) return { text: "No", tone: "off" };
  if (v === null || v === undefined || v === "") return { text: "—", tone: "off" };
  return { text: String(v), tone: "plain" };
}

// Reserved fictional numbers (+1 555 0100-0199) so seed data can never dial
// a real person, even if someone switches to live mode without editing it.
const SEED_CONTACTS =
  "Aditi Sharma,+15555550100,asked about Bali in December\n" +
  "Rahul Verma,+15555550101,honeymoon package enquiry";

export default function Dashboard() {
  const [health, setHealth] = useState<Health | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState<string>("travel-discovery");
  const [rows, setRows] = useState<ParsedRow[]>(() => parseSheet(SEED_CONTACTS));
  const [dryRun, setDryRun] = useState(true);
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Outcome | null>(null);
  const [builderOpen, setBuilderOpen] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // `health === null` is ambiguous on its own — it means both "not fetched
  // yet" and "failed". Track the phase explicitly so the error banner cannot
  // flash before the first request has even finished.
  const [conn, setConn] = useState<"connecting" | "waking" | "up" | "down">(
    "connecting",
  );
  const [wakeSeconds, setWakeSeconds] = useState(0);
  const waking = conn === "waking";

  useEffect(() => {
    let cancelled = false;

    async function connect() {
      // Try once directly — if the API is already warm this is instant.
      try {
        const h = await api.health();
        if (cancelled) return;
        setHealth(h);
        const cs = await api.campaigns();
        if (cancelled) return;
        setCampaigns(cs);
        if (cs.length && !cs.some((c) => c.id === campaignId)) {
          setCampaignId(cs[0].id);
        }
        setConn("up");
        return;
      } catch {
        /* asleep — fall through to the wake path */
      }

      if (cancelled) return;
      setConn("waking");

      // Count up so the wait is visibly progressing rather than just hanging.
      const started = Date.now();
      const ticker = setInterval(() => {
        setWakeSeconds(Math.floor((Date.now() - started) / 1000));
      }, 1000);

      // Ask our own server to wake the API. No CORS preflight and no browser
      // timeout, so this survives a multi-minute cold start.
      void fetch("/api/wake", { cache: "no-store" }).catch(() => {});

      // Free-tier cold starts can run past two minutes.
      for (let attempt = 0; attempt < 40 && !cancelled; attempt++) {
        await new Promise((r) => setTimeout(r, 4000));
        try {
          const h = await api.health();
          if (cancelled) break;
          setHealth(h);
          const cs = await api.campaigns();
          if (cancelled) break;
          setCampaigns(cs);
          if (cs.length && !cs.some((c) => c.id === campaignId)) {
            setCampaignId(cs[0].id);
          }
          setConn("up");
          clearInterval(ticker);
          return;
        } catch {
          /* still starting */
        }
      }

      clearInterval(ticker);
      if (!cancelled) {
        setConn("down");
        setHealth(null);
      }
    }

    void connect();
    return () => {
      cancelled = true;
    };
    // Intentionally runs once — campaignId is managed after load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const contacts = toContactInputs(rows);
  const active = campaigns.find((c) => c.id === campaignId);
  const noApiKey = !health?.api_key_configured;
  const stats = run?.stats;
  const progress = run ? (stats?.completed ?? 0) / Math.max(1, run.total) : 0;

  async function start() {
    setError(null);
    setSelected(null);
    setBusy(true);
    stopPolling();

    try {
      const { run_id } = await api.startRun(campaignId, contacts, dryRun);
      pollRef.current = setInterval(async () => {
        try {
          const latest = await api.getRun(run_id);
          setRun(latest);
          if (latest.status !== "running") {
            stopPolling();
            setBusy(false);
            if (latest.outcomes.length === 1) setSelected(latest.outcomes[0]);
            // Refresh the remaining live-call budget.
            api.health().then(setHealth).catch(() => {});
          }
        } catch {
          stopPolling();
          setBusy(false);
        }
      }, 1500);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  async function removeCampaign(id: string) {
    try {
      await api.deleteCampaign(id);
      const next = campaigns.filter((c) => c.id !== id);
      setCampaigns(next);
      if (campaignId === id && next.length) setCampaignId(next[0].id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <CampaignBuilder
        open={builderOpen}
        onClose={() => setBuilderOpen(false)}
        onCreated={(c) => {
          setCampaigns((prev) => [...prev, c]);
          setCampaignId(c.id);
        }}
      />

      {/* ---- Page head ---- */}
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-[var(--color-ink)]">
            Campaign desk
          </h1>
          <p className="mt-1.5 text-sm text-[var(--color-ink-soft)]">
            Pick a campaign, load contacts, and triage what comes back.
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs">
          {health?.allowlist_active && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--color-brand-soft)] px-2.5 py-1 font-medium text-[var(--color-brand)] ring-1 ring-inset ring-indigo-200">
              Allowlist on
            </span>
          )}
          <span className="inline-flex items-center gap-2 text-[var(--color-muted)]">
            <span
              className={`relative inline-flex h-2 w-2 rounded-full ${
                conn === "up"
                  ? "bg-emerald-500"
                  : conn === "down"
                    ? "bg-red-500"
                    : "bg-amber-500"
              }`}
            >
              {conn !== "down" && (
                <span
                  className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${
                    conn === "up" ? "bg-emerald-400" : "bg-amber-400"
                  }`}
                />
              )}
            </span>
            {conn === "up"
              ? "Backend connected"
              : conn === "waking"
                ? `Waking the backend… ${wakeSeconds}s`
                : conn === "connecting"
                  ? "Connecting…"
                  : "Backend offline"}
          </span>
        </div>
      </div>

      {/* Free-tier cold start can take a couple of minutes. Say so plainly,
          otherwise a first-time visitor assumes the app is broken. */}
      {waking && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <Spinner dark />
          <div className="text-xs leading-relaxed text-amber-900">
            <strong>Starting the backend.</strong> This demo runs on a free tier
            that sleeps after inactivity, so the first request wakes it — this
            usually takes 30–90 seconds. Everything loads automatically once
            it&apos;s up.
          </div>
        </div>
      )}

      {conn === "down" && (
        <div className="mb-6 flex items-start justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <div className="text-xs leading-relaxed text-red-900">
            <strong>Could not reach the backend.</strong> It may still be
            starting up.
          </div>
          <button
            onClick={() => window.location.reload()}
            className="shrink-0 cursor-pointer rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition hover:brightness-110"
          >
            Retry
          </button>
        </div>
      )}

      {/* ---- Campaign picker ---- */}
      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
            Campaigns
          </h2>
          <button
            onClick={() => setBuilderOpen(true)}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--color-brand)] transition-colors hover:border-[var(--color-brand)] hover:bg-[var(--color-brand-soft)]"
          >
            <PlusIcon className="h-3.5 w-3.5" />
            New campaign
          </button>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {campaigns.map((c) => {
            const isActive = c.id === campaignId;
            const fieldCount = Object.keys(c.outcome_fields).length;
            return (
              <button
                key={c.id}
                onClick={() => setCampaignId(c.id)}
                className={`group relative rounded-xl p-4 text-left transition ${
                  isActive
                    ? "card border-[var(--color-brand)] bg-[var(--color-brand-soft)] ring-1 ring-[var(--color-brand)]"
                    : "card card-hover"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-semibold text-[var(--color-ink)]">
                    {c.name}
                  </span>
                  {!c.built_in && (
                    <span
                      role="button"
                      tabIndex={0}
                      aria-label={`Delete ${c.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        void removeCampaign(c.id);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.stopPropagation();
                          void removeCampaign(c.id);
                        }
                      }}
                      className="shrink-0 cursor-pointer rounded p-1 text-slate-300 opacity-0 transition hover:text-red-500 focus:opacity-100 group-hover:opacity-100"
                    >
                      <TrashIcon className="h-3.5 w-3.5" />
                    </span>
                  )}
                </div>
                <p className="mt-1.5 line-clamp-2 text-[11px] leading-relaxed text-[var(--color-muted)]">
                  {c.goal_preview.replace(/\s+/g, " ").slice(0, 110)}…
                </p>
                <div className="mt-3 flex items-center gap-2 text-[10px] text-[var(--color-muted)]">
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono uppercase">
                    {c.region ?? "—"}/{c.language ?? "—"}
                  </span>
                  {fieldCount > 0 && (
                    <span>
                      +{fieldCount} field{fieldCount === 1 ? "" : "s"}
                    </span>
                  )}
                  {c.built_in && <span className="ml-auto">built-in</span>}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[400px_1fr]">
        {/* ---- Control panel ---- */}
        <section className="card h-fit p-6">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-sm font-semibold text-[var(--color-ink)]">
              Run {active?.name ?? "campaign"}
            </h2>
            <span className="nums text-xs text-[var(--color-muted)]">
              {contacts.length} ready
            </span>
          </div>

          <ContactUpload rows={rows} onRows={setRows} />

          {/* Mode switch */}
          <div className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-medium text-[var(--color-muted)]">Mode</span>
              {!dryRun && (
                <span className="text-[10px] font-semibold uppercase tracking-wide text-red-600">
                  Spends credits
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1">
              <button
                onClick={() => setDryRun(true)}
                className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                  dryRun
                    ? "bg-white text-emerald-700 shadow-sm"
                    : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
                }`}
              >
                Dry run
              </button>
              <button
                onClick={() => setDryRun(false)}
                className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                  !dryRun
                    ? "bg-white text-red-700 shadow-sm"
                    : "text-[var(--color-muted)] hover:text-[var(--color-ink)]"
                }`}
              >
                Live calls
              </button>
            </div>

            <p
              className={`mt-2 text-[11px] leading-relaxed ${
                dryRun ? "text-[var(--color-muted)]" : "text-red-700"
              }`}
            >
              {dryRun
                ? "Validates goals and safety gates. Nothing is dialed, no credits spent."
                : "Dials real phone numbers. Restricted to the allowlist while it is set."}
            </p>
          </div>

          {!dryRun && noApiKey && (
            <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800 ring-1 ring-inset ring-amber-200">
              No <code className="font-mono">CALLE_API_KEY</code> on the backend.
            </p>
          )}

          {!dryRun && health?.limits && (
            <p className="mt-3 rounded-lg bg-[var(--color-subtle)] px-3 py-2 text-[11px] leading-relaxed text-[var(--color-ink-soft)]">
              Shared demo: <strong>{health.limits.per_window} live calls</strong> per{" "}
              {health.limits.window_minutes} minutes per visitor.{" "}
              <span className="nums">
                {Math.max(0, health.limits.daily_budget - health.limits.used_today)}
              </span>{" "}
              of {health.limits.daily_budget} left today. Dry run is unlimited.
            </p>
          )}

          <button
            onClick={start}
            disabled={busy || contacts.length === 0 || (!dryRun && noApiKey)}
            className={`mt-4 w-full rounded-xl px-4 py-3 text-sm font-medium text-white shadow-sm transition hover:brightness-110 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:brightness-100 ${
              dryRun ? "brand-gradient" : "bg-red-600"
            }`}
          >
            {busy ? (
              <span className="inline-flex items-center gap-2">
                <Spinner />
                Running…
              </span>
            ) : dryRun ? (
              `Dry run ${contacts.length} contact${contacts.length === 1 ? "" : "s"}`
            ) : (
              `Call ${contacts.length} contact${contacts.length === 1 ? "" : "s"}`
            )}
          </button>

          {error && (
            <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-inset ring-red-200">
              {error}
            </p>
          )}
        </section>

        {/* ---- Results ---- */}
        <section className="card p-6">
          {!run ? (
            <EmptyState campaign={active} />
          ) : (
            <>
              <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                <Stat label="Progress" value={`${stats?.completed ?? 0}/${run.total}`} />
                <Stat label="Auto-closed" value={stats?.auto_closed ?? 0} tone="good" />
                <Stat label="Needs human" value={stats?.escalated ?? 0} tone="bad" />
                <Stat label="Escalation" value={`${stats?.needs_human_pct ?? 0}%`} />
              </div>

              {run.status === "running" && (
                <div className="mb-5">
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="brand-gradient h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.round(progress * 100)}%` }}
                    />
                  </div>
                  <p className="mt-2 flex items-center gap-2 text-xs text-[var(--color-muted)]">
                    <Spinner dark />
                    Calling… updates every 1.5s
                  </p>
                </div>
              )}

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-muted)]">
                      <th className="pb-2.5 font-medium">Contact</th>
                      <th className="pb-2.5 font-medium">Number</th>
                      <th className="pb-2.5 font-medium">Status</th>
                      <th className="pb-2.5 font-medium">Sentiment</th>
                      <th className="pb-2.5 font-medium">Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.outcomes.map((o, i) => (
                      <tr
                        key={`${o.contact_name}-${i}`}
                        onClick={() => setSelected(selected === o ? null : o)}
                        className={`row-in cursor-pointer border-b border-[var(--color-border)] transition last:border-0 ${
                          selected === o
                            ? "bg-[var(--color-brand-soft)]"
                            : "hover:bg-[var(--color-subtle)]"
                        }`}
                      >
                        <td className="py-3 font-medium text-[var(--color-ink)]">
                          {o.contact_name}
                        </td>
                        <td className="py-3 font-mono text-xs text-[var(--color-muted)]">
                          {o.phone_masked}
                        </td>
                        <td className="py-3">
                          <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] uppercase text-slate-600">
                            {o.status}
                          </span>
                        </td>
                        <td className="py-3">
                          <SentimentBadge value={o.sentiment} />
                        </td>
                        <td className="py-3">
                          <DispositionBadge value={o.disposition} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {run.outcomes.length > 0 && !selected && (
                <p className="mt-4 text-center text-xs text-[var(--color-muted)]">
                  Select a row to see the structured result.
                </p>
              )}

              {selected && <OutcomeDetail outcome={selected} />}
            </>
          )}
        </section>
      </div>
    </main>
  );
}

function Spinner({ dark }: { dark?: boolean }) {
  return (
    <span
      className={`inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent ${
        dark ? "text-[var(--color-muted)]" : "text-white/70"
      }`}
    />
  );
}

function EmptyState({ campaign }: { campaign?: Campaign }) {
  return (
    <div className="flex h-full min-h-80 flex-col items-center justify-center px-6 text-center">
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--color-brand-soft)] text-[var(--color-brand)]">
        <PhoneIcon className="h-5 w-5" />
      </div>
      <p className="text-sm font-semibold text-[var(--color-ink)]">
        Ready when you are
      </p>
      <p className="mt-1.5 max-w-sm text-xs leading-relaxed text-[var(--color-muted)]">
        {campaign
          ? `“${campaign.name}” is selected. Start a dry run to see the goal each contact would hear — nothing is dialed.`
          : "Pick a campaign and load contacts to begin."}
      </p>
      {campaign && Object.keys(campaign.outcome_fields).length > 0 && (
        <div className="mt-5 w-full max-w-sm rounded-xl border border-[var(--color-border)] bg-white/60 p-4 text-left">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
            This campaign extracts
          </p>
          <div className="flex flex-wrap gap-1.5">
            {Object.keys(campaign.outcome_fields).map((k) => (
              <span
                key={k}
                className="rounded bg-[var(--color-brand-soft)] px-2 py-0.5 font-mono text-[10px] text-[var(--color-brand)]"
              >
                {k}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: "good" | "bad";
}) {
  const color =
    tone === "good"
      ? "text-emerald-600"
      : tone === "bad"
        ? "text-red-600"
        : "text-[var(--color-ink)]";
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-white/60 px-4 py-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-[var(--color-muted)]">
        {label}
      </div>
      <div className={`nums mt-1 text-2xl font-semibold ${color}`}>{value}</div>
    </div>
  );
}

function OutcomeDetail({ outcome }: { outcome: Outcome }) {
  const entries = Object.entries(outcome.extracted ?? {});
  const summaryField = entries.find(([k]) => k === "summary")?.[1];
  const fields = entries.filter(([k]) => k !== "summary");

  return (
    <div className="mt-5 overflow-hidden rounded-xl border border-[var(--color-border)] bg-white/70">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--color-border)] bg-[var(--color-subtle)] px-5 py-3.5">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">
            {outcome.contact_name}
          </h3>
          <p className="font-mono text-[11px] text-[var(--color-muted)]">
            {outcome.phone_masked}
            {outcome.duration_seconds != null &&
              ` · ${Math.round(outcome.duration_seconds)}s`}
          </p>
        </div>
        <DispositionBadge value={outcome.disposition} />
      </div>

      <div className="space-y-4 p-5">
        {outcome.disposition_reason && (
          <p className="text-xs leading-relaxed text-[var(--color-ink-soft)]">
            {outcome.disposition_reason}
          </p>
        )}

        {(summaryField || outcome.summary) && !outcome.dry_run && (
          <div className="rounded-lg border-l-2 border-[var(--color-brand)] bg-[var(--color-brand-soft)] px-4 py-3">
            <p className="text-xs leading-relaxed text-[var(--color-ink)]">
              {String(summaryField ?? outcome.summary)}
            </p>
          </div>
        )}

        {fields.length > 0 && (
          <div>
            <h4 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
              Structured result from CALL-E
            </h4>
            <dl className="grid gap-x-8 sm:grid-cols-2">
              {fields.map(([k, v]) => {
                const { text, tone } = formatValue(v);
                return (
                  <div
                    key={k}
                    className="flex items-baseline justify-between gap-3 border-b border-[var(--color-border)] py-1.5 text-xs last:border-0"
                  >
                    <dt className="shrink-0 text-[var(--color-muted)]">{label(k)}</dt>
                    <dd
                      className={`truncate text-right font-mono ${
                        tone === "on"
                          ? "font-medium text-emerald-700"
                          : tone === "off"
                            ? "text-[var(--color-muted)]"
                            : "text-[var(--color-ink)]"
                      }`}
                    >
                      {text}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </div>
        )}

        {outcome.dry_run && outcome.summary && (
          <div>
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
              Rendered goal — what the agent would say
            </h4>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-subtle)] p-4 font-mono text-[11px] leading-relaxed text-[var(--color-ink-soft)]">
              {outcome.summary}
            </pre>
          </div>
        )}

        {outcome.transcript && (
          <div>
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[var(--color-muted)]">
              Transcript
            </h4>
            <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-lg bg-[var(--color-subtle)] p-4 font-mono text-[11px] leading-relaxed text-[var(--color-ink-soft)]">
              {outcome.transcript}
            </pre>
          </div>
        )}

        {outcome.error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 font-mono text-[11px] text-red-700 ring-1 ring-inset ring-red-200">
            {outcome.error}
          </p>
        )}
      </div>
    </div>
  );
}
