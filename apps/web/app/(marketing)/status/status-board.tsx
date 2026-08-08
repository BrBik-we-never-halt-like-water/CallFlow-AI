"use client";

import { useEffect, useState } from "react";
import { Lamp } from "@/components/brand/lamp";
import { Button } from "@/components/ui/button";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { api, type Health } from "@/lib/api";
import type { LampState } from "@/lib/lamp";

type Phase = "checking" | "up" | "slow" | "down";

/**
 * A live status board rather than a static page.
 *
 * It reports what it actually measured — including "slow", which is the honest answer
 * for a service that is starting up. Claiming "operational" while a request hangs, or
 * "down" while it is merely waking, are both worse than saying which one it is.
 */
export function StatusBoard() {
  const [nonce, setNonce] = useState(0);
  // One state object keyed by the check it belongs to. Pressing "Check again" bumps the
  // nonce, and the result of an older check is ignored rather than needing a reset.
  const [result, setResult] = useState<{
    nonce: number;
    phase: Phase;
    health: Health | null;
    latency: number | null;
  }>({ nonce: 0, phase: "checking", health: null, latency: null });

  const phase: Phase = result.nonce === nonce ? result.phase : "checking";
  const health = result.nonce === nonce ? result.health : null;
  const latency = result.nonce === nonce ? result.latency : null;

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();

    // Anything past this is reported as slow rather than as healthy.
    const slowTimer = setTimeout(() => {
      if (!cancelled) {
        setResult((current) =>
          current.nonce === nonce && current.phase !== "checking"
            ? current
            : { nonce, phase: "slow", health: null, latency: null },
        );
      }
    }, 3000);

    api
      .health()
      .then((next) => {
        if (cancelled) return;
        const took = Date.now() - started;
        setResult({
          nonce,
          phase: took > 3000 ? "slow" : "up",
          health: next,
          latency: took,
        });
      })
      .catch(() => {
        if (!cancelled) {
          setResult({ nonce, phase: "down", health: null, latency: null });
        }
      })
      .finally(() => clearTimeout(slowTimer));

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
    };
  }, [nonce]);

  const overall: { lamp: LampState; label: string; detail: string } =
    phase === "up"
      ? {
          lamp: "jade",
          label: "All systems normal",
          detail: "The calling service answered and reported its guards.",
        }
      : phase === "slow"
        ? {
            lamp: "brass",
            label: "Slower than usual",
            detail:
              "The service is responding but took a while — most likely it was asleep and is starting up.",
          }
        : phase === "down"
          ? {
              lamp: "flare",
              label: "Not responding",
              detail:
                "The calling service didn't answer. Runs already in progress are unaffected; new runs will fail to start.",
            }
          : {
              lamp: "off",
              label: "Checking…",
              detail: "Asking the service how it is.",
            };

  return (
    <div className="flex flex-col gap-4">
      <Panel className="flex flex-wrap items-center justify-between gap-4 p-5">
        <div className="flex items-center gap-3">
          <Lamp state={overall.lamp} size="lg" label={overall.label} />
          <div className="flex flex-col gap-0.5">
            <p className="text-h3 font-medium text-text">{overall.label}</p>
            <p className="text-small text-text-dim">{overall.detail}</p>
          </div>
        </div>
        <Button variant="secondary" size="sm" onClick={() => setNonce((n) => n + 1)}>
          Check again
        </Button>
      </Panel>

      <Panel className="flex flex-col divide-y divide-rule">
        <Row
          label="Dashboard"
          lamp="jade"
          value="Serving"
          detail="You're reading this, so it's up."
        />
        <Row
          label="Calling service"
          lamp={overall.lamp}
          value={
            phase === "checking" ? "—" : phase === "down" ? "No response" : `${latency ?? "—"} ms`
          }
          detail={
            phase === "down"
              ? "No answer from the API."
              : "Round trip from your browser to the health endpoint."
          }
        />
        <Row
          label="Live calling"
          lamp={health?.api_key_configured ? "jade" : "flare"}
          value={health?.api_key_configured ? "Available" : "Unavailable"}
          detail={
            health?.api_key_configured
              ? "A Voice API key is configured, so runs can dial."
              : "No Voice API key configured on this deployment. Runs can't place calls."
          }
        />
        <Row
          label="Safety guards"
          lamp={health ? "jade" : "off"}
          value={
            health
              ? `Ceiling ${health.max_calls_per_run}, allowlist ${health.allowlist_active ? "on" : "off"}`
              : "—"
          }
          detail="Read directly from the service, not from a cached value."
        />
        {health?.limits ? (
          <Row
            label="Daily call budget"
            lamp="jade"
            value={`${health.limits.daily_budget} calls/day, ${health.limits.per_window} per ${health.limits.window_minutes}min`}
            detail="The deployment default. Each organisation gets its own budget and can raise it in Settings → Safety — this isn't any one organisation's live usage."
          />
        ) : null}
      </Panel>

      <div className="flex flex-col gap-2">
        <Eyebrow>Incidents</Eyebrow>
        <Panel className="p-5">
          <p className="text-small text-text-dim">
            No incidents recorded. This page checks the service live rather than reading a
            status feed, so it reflects the moment you loaded it.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function Row({
  label,
  lamp,
  value,
  detail,
}: {
  label: string;
  lamp: LampState;
  value: string;
  detail: string;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 p-4">
      <div className="flex min-w-0 items-start gap-2.5">
        <span className="mt-1.5">
          <Lamp state={lamp} size="sm" label={`${label}: ${value}`} />
        </span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-small font-medium text-text">{label}</span>
          <span className="text-small text-text-mute">{detail}</span>
        </div>
      </div>
      <span className="shrink-0 font-mono text-data tabular-nums text-text-dim">{value}</span>
    </div>
  );
}
