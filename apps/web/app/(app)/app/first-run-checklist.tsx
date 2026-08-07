"use client";

import { CheckIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { useStoredJson } from "@/lib/hooks/use-external-store";
import { LampStrip } from "@/components/brand/lamp-strip";
import { Button } from "@/components/ui/button";
import { Eyebrow, Panel } from "@/components/ui/panel";
import type { LampSpec } from "@/lib/lamp";

const STORAGE_KEY = "callflow.onboarding.steps";

const PREVIEW: LampSpec[] = [
  { state: "off", label: "Not yet dialled" },
  { state: "off", label: "Not yet dialled" },
  { state: "off", label: "Not yet dialled" },
  { state: "off", label: "Not yet dialled" },
  { state: "off", label: "Not yet dialled" },
];

/**
 * First-run state for the whole overview page.
 *
 * Three steps, ending with a first real run — because seeing one typed result is the
 * moment the product makes sense, and nothing before that moment explains it as well.
 *
 * Steps tick off permanently once done, so the checklist is a record of progress
 * rather than something that resets and nags.
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
      body: "Paste a list or drop a CSV. Numbers are validated before anything is dialled.",
      cta: "Add contacts",
      href: "/app/contacts",
    },
    {
      id: "campaign",
      title: "Pick a campaign",
      body: "A campaign is a goal written in plain English plus the fields you want back from every call.",
      cta: hasCampaigns ? "Browse campaigns" : "New campaign",
      href: hasCampaigns ? "/app/campaigns" : "/app/campaigns/new",
    },
    {
      id: "first-run",
      title: "Start your first run",
      body: "Walks the whole pipeline and shows you a real typed result from an actual call.",
      cta: "Start a run",
      href: "/app/runs/new",
    },
  ];

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,320px)]">
      <Panel className="flex flex-col gap-5 p-5 sm:p-6">
        <div className="flex flex-col gap-2">
          <Eyebrow>Getting started</Eyebrow>
          <h2 className="font-display text-h2 text-text">Nothing has been dialled yet</h2>
          <p className="measure text-body text-text-dim">
            Three steps, about five minutes. The last one places a real call and ends
            with a typed result in front of you.
          </p>
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

                <Button
                  asChild
                  variant={i === 0 || isDone ? "secondary" : "secondary"}
                  size="sm"
                  className="shrink-0"
                >
                  <Link href={step.href} onClick={() => complete(step.id)}>
                    {step.cta}
                  </Link>
                </Button>
              </li>
            );
          })}
        </ol>
      </Panel>

      <Panel sunken className="flex flex-col gap-4 p-5">
        <Eyebrow>What you&apos;ll see</Eyebrow>
        <LampStrip lamps={PREVIEW} size="md" />
        <p className="text-small text-text-dim">
          One lamp per call. They light as results land — jade for a clean outcome, brass
          for a retry, flare for anything that needs a person.
        </p>
        <Button asChild variant="ghost" size="sm" className="w-fit">
          <Link href="/app/welcome">Take the full walkthrough</Link>
        </Button>
      </Panel>
    </div>
  );
}
