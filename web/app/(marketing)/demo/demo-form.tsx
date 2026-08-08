"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorSummary, Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { VERTICALS } from "@/lib/verticals";

const VOLUMES = [
  { value: "under-100", label: "Under 100 calls a month" },
  { value: "100-500", label: "100 – 500" },
  { value: "500-2000", label: "500 – 2,000" },
  { value: "2000-plus", label: "More than 2,000" },
  { value: "unsure", label: "Not sure yet" },
];

/**
 * Demo request form.
 *
 * No scheduler is connected yet, so this collects and validates the details and then
 * says plainly that nothing has been booked, with a mailto that carries everything
 * across. A fake confirmation screen would mean someone sitting waiting for a call
 * that was never scheduled.
 */
export function DemoForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [volume, setVolume] = useState("");
  const [vertical, setVertical] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [done, setDone] = useState(false);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (!name.trim()) next.name = "Add your name.";
    if (!email.trim()) next.email = "Add a work email so we can send the invite.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      next.email = "That doesn't look like an email address.";
    }
    if (!company.trim()) next.company = "Add your company.";
    if (!volume) next.volume = "Pick the volume closest to yours.";

    setErrors(next);
    if (Object.keys(next).length === 0) setDone(true);
  }

  if (done) {
    const body = [
      `Name: ${name}`,
      `Company: ${company}`,
      `Monthly call volume: ${VOLUMES.find((v) => v.value === volume)?.label ?? volume}`,
      vertical
        ? `Use case: ${VERTICALS.find((v) => v.slug === vertical)?.name ?? vertical}`
        : null,
    ]
      .filter(Boolean)
      .join("\n");

    return (
      <Panel className="flex flex-col gap-4 p-5 sm:p-6">
        <h2 className="font-display text-h3 text-text">Send this and we&apos;ll book it</h2>
        <p className="text-small text-text-dim">
          The scheduler isn&apos;t connected yet, so nothing has been booked. Send the
          email below   it already has your details in it   and we&apos;ll come back with
          two or three times within one business day.
        </p>

        <Panel sunken className="p-3">
          <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-data text-text-dim">
            {body}
          </pre>
        </Panel>

        <div className="flex flex-wrap gap-2">
          <Button asChild>
            <a
              href={`mailto:hello@callflow.ai?subject=${encodeURIComponent(
                `Demo request   ${company}`,
              )}&body=${encodeURIComponent(`${body}\n\nReply-to: ${email}\n`)}`}
            >
              Send the request
            </a>
          </Button>
          <Button variant="secondary" onClick={() => setDone(false)}>
            Change my details
          </Button>
        </div>
      </Panel>
    );
  }

  const summary = Object.entries(errors).map(([id, message]) => ({
    id: `demo-${id}`,
    label:
      { name: "Name", email: "Work email", company: "Company", volume: "Monthly call volume" }[
        id
      ] ?? id,
    message,
  }));

  return (
    <Panel className="flex flex-col gap-5 p-5 sm:p-6">
      <div className="flex flex-col gap-1">
        <h2 className="font-display text-h3 text-text">Request a time</h2>
        <p className="text-small text-text-mute">
          No phone number needed   everything happens over a screen share.
        </p>
      </div>

      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <ErrorSummary errors={summary} />

        <Field label="Name" error={errors.name} required>
          <Input
            id="demo-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
          />
        </Field>

        <Field label="Work email" error={errors.email} required>
          <Input
            id="demo-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
        </Field>

        <Field label="Company" error={errors.company} required>
          <Input
            id="demo-company"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            autoComplete="organization"
          />
        </Field>

        <Field label="Monthly call volume" error={errors.volume} required>
          <Select
            id="demo-volume"
            value={volume}
            onValueChange={setVolume}
            options={VOLUMES}
            placeholder="Pick a range"
          />
        </Field>

        <Field label="What you'd use it for" help="Optional   it helps us prepare.">
          <Select
            id="demo-vertical"
            value={vertical}
            onValueChange={setVertical}
            options={VERTICALS.map((v) => ({ value: v.slug, label: v.name }))}
            placeholder="Pick the closest fit"
          />
        </Field>

        <Button type="submit" size="lg">
          Book a 15-min demo
        </Button>
      </form>
    </Panel>
  );
}
