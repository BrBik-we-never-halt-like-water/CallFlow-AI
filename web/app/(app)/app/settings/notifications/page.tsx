"use client";

import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select } from "@/components/ui/select";
import { Field } from "@/components/ui/field";
import { useToast } from "@/components/ui/toast";

/**
 * Notifications.
 *
 * The escalation alert defaults on and everything else defaults off. Someone waiting for
 * a callback is the only thing in this product that is genuinely time-sensitive; a run
 * finishing overnight is news that can wait until morning, and defaulting it on is how
 * people learn to ignore the emails.
 */
export default function NotificationsSettingsPage() {
  const toast = useToast();
  const [escalations, setEscalations] = useState(true);
  const [runFinished, setRunFinished] = useState(false);
  const [budgetLow, setBudgetLow] = useState(true);
  const [weeklySummary, setWeeklySummary] = useState(false);
  const [digest, setDigest] = useState("immediate");

  function save() {
    toast({
      tone: "info",
      title: "Notification settings aren't saved yet",
      body: "Email delivery needs an account service, which this deployment doesn't have.",
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="What to tell you about"
        description="Email alerts for things happening in this organisation."
        effect={
          escalations
            ? digest === "immediate"
              ? "You'll be emailed as soon as a call needs a person. Everything else follows the switches below."
              : "Escalations are batched into one email per hour, so a burst of them doesn't become a burst of email."
            : "Nothing will email you about escalations. The count in the nav is the only signal — check it."
        }
        footer={
          <Button size="sm" onClick={save}>
            Save preferences
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <Switch
            checked={escalations}
            onCheckedChange={setEscalations}
            label="A call needs a person"
            subLabel="The only genuinely time-sensitive event in the product."
          />
          <Switch
            checked={budgetLow}
            onCheckedChange={setBudgetLow}
            label="Live-call budget nearly spent"
            subLabel="At 80% of the daily budget, so a run doesn't stop unexpectedly."
          />
          <Switch
            checked={runFinished}
            onCheckedChange={setRunFinished}
            label="A run finished"
            subLabel="Off by default — the results will still be there in the morning."
          />
          <Switch
            checked={weeklySummary}
            onCheckedChange={setWeeklySummary}
            label="Weekly summary"
            subLabel="Calls placed, auto-closed share, and what needed a person."
          />
        </div>
      </SettingsSection>

      <SettingsSection
        title="How often"
        description="Batching applies to escalation alerts only. Budget warnings are always immediate."
        footer={
          <Button size="sm" onClick={save}>
            Save
          </Button>
        }
      >
        <div className="max-w-xs">
          <Field label="Escalation alerts">
            <Select
              value={digest}
              onValueChange={setDigest}
              options={[
                { value: "immediate", label: "As they happen" },
                { value: "hourly", label: "Batched hourly" },
                { value: "daily", label: "Once a day" },
              ]}
            />
          </Field>
        </div>
      </SettingsSection>

      <NotWiredNotice>
        Email delivery needs an account service and a mail provider, neither of which this
        deployment has. The escalation count in the left nav is live and accurate.
      </NotWiredNotice>
    </div>
  );
}
