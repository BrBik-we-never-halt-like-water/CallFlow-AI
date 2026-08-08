"use client";

import { CheckIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { useStoredJson } from "@/lib/hooks/use-external-store";
import { Button } from "@/components/ui/button";
import { Eyebrow, Panel } from "@/components/ui/panel";

const STORAGE_KEY = "callflow.onboarding.steps";

/**
 * First-run state for the dashboard.
 *
 * Three steps, ending with a first real run. Steps tick off permanently once
 * done, so the checklist is a record of progress rather than something that
 * resets and nags.
 */
const NO_STEPS: string[] = [];

export function FirstRunChecklist({ hasCampaigns }: { hasCampaigns: boolean }) {
  const [completed, setCompleted] = useStoredJson<string[]>(STORAGE_KEY, NO_STEPS);
  const done = new Set(completed);

  function complete(id: string) {
    if (done.has(id)) return;
    setCompleted([...completed, id]);
  }

  const steps = [
    {
      id: "contacts",
      title: "Add contacts",
      body: "Paste a list or drop a CSV.",
      cta: "Add contacts",
      href: "/app/contacts",
    },
    {
      id: "campaign",
      title: "Pick a campaign",
      body: "A goal in plain English, plus the fields you want back.",
      cta: hasCampaigns ? "Browse campaigns" : "New campaign",
      href: hasCampaigns ? "/app/campaigns" : "/app/campaigns/new",
    },
    {
      id: "first-run",
      title: "Start your first run",
      body: "See a real typed result from an actual call.",
      cta: "Start a run",
      href: "/app/runs/new",
    },
  ];

  return (
    <Panel className="flex flex-col gap-5 p-5 sm:p-6">
      <div className="flex flex-col gap-1.5">
        <Eyebrow>Getting started</Eyebrow>
        <h2 className="font-display text-h2 text-text">Nothing has been dialled yet</h2>
      </div>

      <ol className="flex flex-col">
        {steps.map((step, i) => {
          const isDone = done.has(step.id);
          return (
            <li
              key={step.id}
              className="flex items-start gap-4 border-t border-rule py-4 last:pb-0"
            >
              <span
                className={cn(
                  "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full border",
                  isDone
                    ? "border-transparent bg-surface-inverse text-text-inverse"
                    : "border-rule-strong font-mono text-label text-text-mute",
                )}
              >
                {isDone ? (
                  <CheckIcon aria-hidden weight="bold" className="size-3.5" />
                ) : (
                  String(i + 1)
                )}
              </span>

              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <h3
                  className={cn(
                    "text-h4 font-medium",
                    isDone ? "text-text-mute line-through" : "text-text",
                  )}
                >
                  {step.title}
                </h3>
                <p className="text-small text-text-dim">{step.body}</p>
              </div>

              <Button asChild variant="secondary" size="sm" className="shrink-0">
                <Link href={step.href} onClick={() => complete(step.id)}>
                  {step.cta}
                </Link>
              </Button>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}
