"use client";

import { useState } from "react";
import Link from "next/link";
import { SettingsSection } from "@/components/app/settings-section";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";

const DEFAULT_DISCLOSURE =
  "Hi, this is an automated assistant calling on behalf of {organisation}.";

const RETENTION = [
  { value: "7", label: "7 days" },
  { value: "30", label: "30 days" },
  { value: "90", label: "90 days" },
  { value: "365", label: "12 months" },
];

/**
 * Compliance.
 *
 * The disclosure line is editable and can be switched between languages, but it cannot
 * be emptied   the control refuses a blank value rather than allowing a call that never
 * says it is automated. That is the one setting in this product a user is not permitted
 * to turn all the way off.
 */
export default function ComplianceSettingsPage() {
  const toast = useToast();
  const [disclosure, setDisclosure] = useState(DEFAULT_DISCLOSURE);
  const [disclosureError, setDisclosureError] = useState<string | null>(null);
  const [requireConsent, setRequireConsent] = useState(false);
  const [recording, setRecording] = useState(false);
  const [retention, setRetention] = useState("30");

  function saveDisclosure() {
    if (disclosure.trim().length < 20) {
      setDisclosureError(
        "The disclosure has to say who is calling and that the caller is automated. It can be reworded, but it can't be removed.",
      );
      return;
    }
    setDisclosureError(null);
    toast({
      tone: "info",
      title: "Compliance settings aren't saved yet",
      body: "There's no account service on this deployment to store them.",
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="AI disclosure"
        description="What the agent says about itself in the opening seconds of every call."
        effect="Every call opens with this line. It is on by default and cannot be fully removed   an agent that hides being automated is not something this product will do."
        footer={
          <Button size="sm" onClick={saveDisclosure}>
            Save disclosure
          </Button>
        }
      >
        <Field
          label="Disclosure line"
          hint="Use {organisation} for your name. Reword it to match your tone or language."
          error={disclosureError}
        >
          <Textarea
            value={disclosure}
            onChange={(e) => setDisclosure(e.target.value)}
            rows={3}
          />
        </Field>
      </SettingsSection>

      <SettingsSection
        title="Consent capture"
        description="Whether the agent asks for consent explicitly and returns the answer as a typed field."
        effect={
          requireConsent
            ? "The agent asks for consent before continuing. The answer comes back as a boolean alongside the words used, and a call where consent is refused ends politely and suppresses the number."
            : "Consent is not captured on the call. You are relying on the lawful basis you already have for contacting these people."
        }
        footer={
          <Button size="sm" onClick={saveDisclosure}>
            Save
          </Button>
        }
      >
        <Switch
          checked={requireConsent}
          onCheckedChange={setRequireConsent}
          label="Ask for consent on every call"
          subLabel="Required in some jurisdictions for automated calling."
        />
      </SettingsSection>

      <SettingsSection
        title="Recording and retention"
        description="Whether calls are recorded, and how long transcripts are kept."
        effect={
          recording
            ? `Calls are recorded, and the disclosure line is extended to say so before the conversation begins. Recordings and transcripts are deleted after ${RETENTION.find((r) => r.value === retention)?.label}.`
            : `Calls are not recorded. Transcripts are kept for ${RETENTION.find((r) => r.value === retention)?.label}, then deleted. Typed results are kept for the life of the account so your reporting stays intact.`
        }
        footer={
          <Button size="sm" onClick={saveDisclosure}>
            Save
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <Switch
            checked={recording}
            onCheckedChange={setRecording}
            label="Record calls"
            subLabel="Adds a recording notice to the disclosure line automatically."
          />
          <div className="max-w-xs">
            <Field label="Keep transcripts for">
              <Select value={retention} onValueChange={setRetention} options={RETENTION} />
            </Field>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Do-not-call list"
        description="Numbers that must never be dialled, across every campaign."
        effect="Anyone who opts out on a call is added automatically. The list is global and permanent, and it cannot be overridden from a run."
        footer={
          <Button asChild variant="secondary" size="sm">
            <Link href="/app/contacts">Manage the suppression list</Link>
          </Button>
        }
      />

      <SettingsSection
        title="Export and deletion"
        description="Get your data out, or have it removed."
        footer={
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                toast({
                  tone: "info",
                  title: "Export the results you can see",
                  body: "Use Export CSV in the runs table. A full account export needs an account service.",
                })
              }
            >
              Export everything
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                toast({
                  tone: "info",
                  title: "Deletion requests go to us directly",
                  body: "Email legal@callflow.ai and we'll action it within 30 days, backups included.",
                })
              }
            >
              Request deletion
            </Button>
          </div>
        }
      >
        <p className="measure text-small text-text-dim">
          Deletion covers transcripts, recordings, typed results, and contacts, including
          backups, and is actioned within 30 days. The suppression list is deliberately kept
            deleting it would mean re-calling people who asked you not to.
        </p>
      </SettingsSection>
    </div>
  );
}
