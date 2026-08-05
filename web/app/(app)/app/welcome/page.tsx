"use client";

import { CheckIcon } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { LampStrip } from "@/components/brand/lamp-strip";
import { ContactGrid } from "@/components/app/contact-grid";
import { Rule } from "@/components/ui/rule";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Field } from "@/components/ui/field";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/app-store";
import { useStoredString } from "@/lib/hooks/use-external-store";
import { renderGoalPreview } from "@/lib/campaign-fields";
import { toContactInputs, type ParsedRow } from "@/lib/contacts";
import { lampForOutcome, stripForRun } from "@/lib/lamp";
import { useRunPoll } from "@/lib/hooks/use-run-poll";

const WELCOME_DONE_KEY = "callflow.welcome.done";

const STEPS = ["What you're calling about", "Add contacts", "Pick a campaign", "See a result"];

/**
 * Onboarding. Four screens, skippable, resumable.
 *
 * It ends with the user having watched a real dry run produce a typed result, because
 * that is the moment the product makes sense. Every earlier screen exists only to get
 * them to that one.
 */
export default function WelcomePage() {
  const router = useRouter();
  const toast = useToast();
  const { campaigns, refresh } = useAppStore();

  const [purpose, setPurpose] = useState("");
  const [rows, setRows] = useState<ParsedRow[]>([]);
  const [chosenId, setChosenId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const { run } = useRunPoll(runId);

  // Resumable: the step is persisted, and read as a subscription rather than in a
  // mount-time effect, so someone returning lands on the right screen immediately.
  const [storedStep, setStoredStep] = useStoredString(WELCOME_DONE_KEY, "0");
  const step = Math.min(Math.max(Number(storedStep) || 0, 0), STEPS.length - 1);
  const setStep = (next: number) => setStoredStep(String(next));

  // Derived, so the first available campaign is selected on the first render.
  const campaignId = chosenId ?? (campaigns[0]?.id ?? "");
  const setCampaignId = setChosenId;

  const campaign = campaigns.find((c) => c.id === campaignId);
  const validRows = rows.filter((r) => r.valid);

  const settled = useMemo(
    () => (run ? run.outcomes.filter((o) => o.disposition !== "in_flight") : []),
    [run],
  );
  const lamps = useMemo(
    () => (run ? stripForRun(settled, run.total) : []),
    [run, settled],
  );
  const firstResult = settled[0];

  async function startDryRun() {
    if (!campaignId || validRows.length === 0) return;
    setStarting(true);
    try {
      const { run_id } = await api.startRun(campaignId, toContactInputs(rows), true);
      setRunId(run_id);
      setStep(3);
      refresh();
      toast({ tone: "success", title: "Run started", body: "Dry run — nothing is being dialled." });
    } catch (error) {
      toast({
        tone: "error",
        title: "That run wasn't started",
        body:
          error instanceof Error
            ? error.message
            : "The service didn't respond. Nothing was dialled.",
      });
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      {/* ---- Progress ---------------------------------------------------- */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <Eyebrow>
            Step {step + 1} of {STEPS.length}
          </Eyebrow>
          <Button variant="ghost" size="sm" onClick={() => router.push("/app")}>
            Skip for now
          </Button>
        </div>

        <ol className="flex flex-wrap gap-x-4 gap-y-2">
          {STEPS.map((label, i) => (
            <li key={label} className="flex items-center gap-1.5">
              <span
                className={cn(
                  "flex size-5 items-center justify-center rounded-full border font-mono text-[0.625rem]",
                  i < step
                    ? "border-transparent bg-surface-inverse text-text-inverse"
                    : i === step
                      ? "border-text text-text"
                      : "border-rule text-text-mute",
                )}
              >
                {i < step ? <CheckIcon aria-hidden weight="bold" className="size-3" /> : i + 1}
              </span>
              <span
                className={cn(
                  "text-small",
                  i === step ? "font-medium text-text" : "text-text-mute",
                )}
              >
                {label}
              </span>
            </li>
          ))}
        </ol>

        <Rule />
      </div>

      {/* ---- 1 · Purpose ------------------------------------------------- */}
      {step === 0 ? (
        <Panel className="flex flex-col gap-5 p-5 sm:p-6">
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-h2 text-text">What will you be calling about?</h1>
            <p className="measure text-body text-text-dim">
              This just picks a sensible starting template. You can change everything later,
              and nothing you choose here dials anyone.
            </p>
          </div>

          <Field label="Closest fit">
            <Select
              value={purpose}
              onValueChange={setPurpose}
              options={[
                { value: "recruiting", label: "Screening candidates" },
                { value: "appointments", label: "Confirming or rebooking appointments" },
                { value: "admissions", label: "Following up on enquiries" },
                { value: "leads", label: "Qualifying inbound leads" },
                { value: "other", label: "Something else" },
              ]}
              placeholder="Pick one"
            />
          </Field>

          <div className="flex gap-2">
            <Button onClick={() => setStep(1)}>Next</Button>
          </div>
        </Panel>
      ) : null}

      {/* ---- 2 · Contacts ----------------------------------------------- */}
      {step === 1 ? (
        <Panel className="flex flex-col gap-5 p-5 sm:p-6">
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-h2 text-text">Add three contacts</h1>
            <p className="measure text-body text-text-dim">
              Paste them, drop a CSV, or press <strong className="font-medium text-text">Use
              sample</strong> to load reserved fictional numbers that cannot reach a real
              person.
            </p>
          </div>

          <ContactGrid rows={rows} onChange={setRows} />

          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setStep(0)}>
              Back
            </Button>
            <Button disabled={validRows.length === 0} onClick={() => setStep(2)}>
              Next
            </Button>
            {validRows.length === 0 ? (
              <span className="self-center text-small text-text-mute">
                Add at least one valid row to continue.
              </span>
            ) : null}
          </div>
        </Panel>
      ) : null}

      {/* ---- 3 · Campaign ----------------------------------------------- */}
      {step === 2 ? (
        <Panel className="flex flex-col gap-5 p-5 sm:p-6">
          <div className="flex flex-col gap-2">
            <h1 className="font-display text-h2 text-text">Pick a starter campaign</h1>
            <p className="measure text-body text-text-dim">
              Below is the exact instruction the agent gets, with your first contact
              substituted in. This is what they would hear.
            </p>
          </div>

          <Field label="Campaign">
            <Select
              value={campaignId}
              onValueChange={setCampaignId}
              options={campaigns.map((c) => ({
                value: c.id,
                label: c.name,
                hint: c.built_in ? "Template" : undefined,
              }))}
              placeholder={campaigns.length === 0 ? "No campaigns available" : "Pick a campaign"}
              disabled={campaigns.length === 0}
            />
          </Field>

          {campaign ? (
            <Panel sunken className="flex flex-col gap-2 p-4">
              <Eyebrow>
                What {validRows[0]?.name.split(" ")[0] ?? "your contact"} would hear
              </Eyebrow>
              <div className="max-h-64 overflow-y-auto whitespace-pre-wrap font-mono text-data text-text">
                {renderGoalPreview(campaign.goal_template, {
                  name: validRows[0]?.name ?? "there",
                  context: {
                    enquiry_note: validRows[0]?.note || "no note on file",
                    appointment_time: "tomorrow at 4pm",
                  },
                })}
              </div>
            </Panel>
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => setStep(1)}>
              Back
            </Button>
            <Button loading={starting} disabled={!campaignId} onClick={startDryRun}>
              Run it in dry mode
            </Button>
            <span className="self-center text-small text-text-mute">
              Nothing will be dialled.
            </span>
          </div>
        </Panel>
      ) : null}

      {/* ---- 4 · The result --------------------------------------------- */}
      {step === 3 ? (
        <Panel className="flex flex-col gap-5 border-l-2 border-l-[var(--lamp-ice)] p-5 sm:p-6">
          <div className="flex flex-col gap-2">
            <Eyebrow>Dry run · No credits spent</Eyebrow>
            <h1 className="font-display text-h2 text-text">This is what comes back</h1>
            <p className="measure text-body text-text-dim">
              Not a transcript to read — typed fields, plus a triage decision derived from
              them. That is the whole product.
            </p>
          </div>

          {run ? (
            <LampStrip
              lamps={lamps}
              size="md"
              caption={`${settled.length} of ${run.total} settled`}
              counts
            />
          ) : (
            <p className="font-mono text-data text-text-dim">Waking the service…</p>
          )}

          {firstResult ? (
            <div className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <Tag>{firstResult.contact_name}</Tag>
                <Tag>{lampForOutcome(firstResult).label}</Tag>
                {firstResult.sentiment !== "unknown" ? (
                  <Tag>sentiment: {firstResult.sentiment}</Tag>
                ) : null}
              </div>

              <CodeBlock
                label="Extracted"
                code={JSON.stringify(firstResult.extracted ?? {}, null, 2)}
              />

              {firstResult.disposition_reason ? (
                <p className="text-small text-text-dim">
                  <span className="font-mono text-data text-text-mute">Why: </span>
                  {firstResult.disposition_reason}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="text-small text-text-mute">
              Results appear here as each simulated call settles.
            </p>
          )}

          <div className="flex flex-wrap gap-2 border-t border-rule pt-4">
            <Button asChild>
              <Link href="/app">Go to the dashboard</Link>
            </Button>
            {runId ? (
              <Button asChild variant="secondary">
                <Link href={`/app/runs/${runId}`}>Open the full run</Link>
              </Button>
            ) : null}
            <Button asChild variant="ghost">
              <Link href="/docs/writing-a-good-goal">Read: writing a good goal</Link>
            </Button>
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
