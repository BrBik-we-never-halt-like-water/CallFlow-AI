"use client";

import Link from "next/link";
import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";

const EVENTS = [
  { id: "call.settled", label: "call.settled", hint: "A call reached a terminal disposition" },
  { id: "call.escalated", label: "call.escalated", hint: "A call was routed to a person" },
  { id: "run.finished", label: "run.finished", hint: "Every contact in a run has settled" },
  {
    id: "contact.suppressed",
    label: "contact.suppressed",
    hint: "Someone opted out — wire this one even if you wire nothing else",
  },
];

const SAMPLE_PAYLOAD = `{
  "event": "call.settled",
  "run_id": "run_8f2a1c",
  "occurred_at": "2026-08-05T14:22:09Z",
  "call": {
    "contact_name": "Aditi Sharma",
    "phone_masked": "+91*******210",
    "disposition": "auto_closed",
    "sentiment": "positive",
    "dry_run": false,
    "extracted": { "destination": "Dubai", "party_size": 4 }
  }
}`;

export default function IntegrationsSettingsPage() {
  const toast = useToast();
  const [url, setUrl] = useState("");
  const [schedule, setSchedule] = useState("off");

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Webhooks"
        description="Push each result to your systems as the call settles, instead of polling for it."
        effect={
          url.trim()
            ? "Once saved, every selected event is delivered to this endpoint, signed, and retried with backoff for up to 24 hours."
            : "No endpoint configured. Results are available in the dashboard and over the API."
        }
        footer={
          <Button
            size="sm"
            onClick={() =>
              toast({
                tone: "info",
                title: "Webhooks aren't available on this deployment",
                body: "The service has no webhook registry yet. The payload shape below is accurate.",
              })
            }
          >
            Save endpoint
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <Field
            label="Endpoint URL"
            hint="HTTPS only. Respond 2xx as soon as you've persisted the payload."
          >
            <Input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/hooks/callflow"
              className="font-mono text-data"
            />
          </Field>

          <div className="flex flex-col gap-2">
            <span className="text-small font-medium text-text">Events</span>
            <ul className="flex flex-col">
              {EVENTS.map((event) => (
                <li
                  key={event.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule py-2 last:border-0"
                >
                  <code className="font-mono text-data text-text">{event.label}</code>
                  <span className="text-small text-text-mute">{event.hint}</span>
                </li>
              ))}
            </ul>
          </div>

          <CodeBlock label="Sample payload" code={SAMPLE_PAYLOAD} />

          <p className="text-small text-text-mute">
            Numbers are masked in the payload, the same as everywhere else.{" "}
            <Link
              href="/docs/webhooks"
              className="font-medium text-text underline decoration-rule-strong underline-offset-2 hover:decoration-current"
            >
              Signature verification and replay
            </Link>
            .
          </p>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Delivery log"
        description="Every attempt, with the status and the response body. Any delivery can be replayed."
      >
        <EmptyState
          title="No deliveries yet"
          body="Attempts appear here once an endpoint is configured and a call settles."
        />
      </SettingsSection>

      <SettingsSection
        title="CRM connections"
        description="Write typed results straight into the system your team already uses."
      >
        <EmptyState
          title="No connections"
          body="Until a CRM is connected, use webhooks or Export CSV from the runs table."
        />
      </SettingsSection>

      <SettingsSection
        title="Scheduled CSV export"
        description="Have results emailed on a schedule."
        effect={
          schedule === "off"
            ? "No scheduled export. You can still export any table by hand."
            : `A CSV of new results is sent ${schedule === "daily" ? "every morning" : "every Monday"}.`
        }
        footer={
          <Button
            size="sm"
            onClick={() =>
              toast({
                tone: "info",
                title: "Scheduled export isn't available on this deployment",
                body: "Use Export CSV in the runs table meanwhile.",
              })
            }
          >
            Save schedule
          </Button>
        }
      >
        <div className="max-w-xs">
          <Field label="Frequency">
            <Select
              value={schedule}
              onValueChange={setSchedule}
              options={[
                { value: "off", label: "Off" },
                { value: "daily", label: "Daily" },
                { value: "weekly", label: "Weekly" },
              ]}
            />
          </Field>
        </div>
      </SettingsSection>

      <NotWiredNotice>
        Webhooks, CRM connections, and scheduled exports need services this deployment does
        not run. Export CSV in the runs table works today and uses the columns you have
        visible.
      </NotWiredNotice>

      <div className="flex items-center gap-2">
        <Tag>Growth plan</Tag>
        <p className="text-small text-text-mute">
          Webhooks and CRM connections are included from Growth up.
        </p>
      </div>
    </div>
  );
}
