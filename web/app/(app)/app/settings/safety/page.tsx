"use client";

import { useState } from "react";
import { SettingsSection } from "@/components/app/settings-section";
import { guardsFromHealth, SafetyBar } from "@/components/app/safety-bar";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { TIMEZONES } from "@/lib/campaign-draft";
import { formatNumber } from "@/lib/format";
import { useAppStore } from "@/lib/app-store";

/**
 * Safety settings.
 *
 * Every control here shows its current effect in plain language beneath it. Values the
 * service enforces are shown as it reports them, and where the environment sets a
 * ceiling the interface says so rather than offering a control that cannot win.
 */
export default function SafetySettingsPage() {
  const toast = useToast();
  const { health } = useAppStore();

  const [allowlist, setAllowlist] = useState("");
  const [ceiling, setCeiling] = useState(String(health?.max_calls_per_run ?? 3));
  const [ratePerHour, setRatePerHour] = useState(String(health?.limits?.per_window ?? 2));
  const [dailyBudget, setDailyBudget] = useState(String(health?.limits?.daily_budget ?? 25));
  const [windowStart, setWindowStart] = useState("09:00");
  const [windowEnd, setWindowEnd] = useState("20:00");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [dryRunDefault, setDryRunDefault] = useState(health?.dry_run_default ?? true);

  const allowlistCount = allowlist
    .split(",")
    .map((n) => n.trim())
    .filter(Boolean).length;

  function notSaved() {
    toast({
      tone: "info",
      title: "Safety settings are set by the environment",
      body: "On this deployment they come from CALLFLOW_* environment variables. The values above show what's in force.",
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Guards in force"
        description="This is the same bar shown above every run composer."
      >
        <SafetyBar guards={guardsFromHealth(health)} />
      </SettingsSection>

      <SettingsSection
        title="Dry run"
        description="Whether new runs start in dry mode."
        effect={
          dryRunDefault
            ? "New runs start in dry mode. Turning dry run off on a run requires a confirmation showing the contact count and credit estimate."
            : "New runs start live. Real calls will be placed as soon as someone presses Start run."
        }
        footer={
          <Button size="sm" onClick={notSaved}>
            Save changes
          </Button>
        }
      >
        <Switch
          checked={dryRunDefault}
          onCheckedChange={setDryRunDefault}
          label="Start new runs in dry mode"
          subLabel="Strongly recommended. Nothing is dialled until it's turned off."
          tone={dryRunDefault ? "ice" : "brass"}
        />
      </SettingsSection>

      <SettingsSection
        title="Allowlist"
        description="While this has anything in it, those are the only numbers any run may dial."
        effect={
          health?.allowlist_active
            ? "The allowlist is active. Contacts that are not on it are skipped before a call is placed, and the row says why."
            : allowlistCount > 0
              ? `Once saved, only these ${allowlistCount} ${allowlistCount === 1 ? "number" : "numbers"} could be dialled. Everything else would be skipped.`
              : "The allowlist is empty, so any valid number in a run can be dialled. While you're still setting up, put your own number here."
        }
        footer={
          <Button size="sm" onClick={notSaved}>
            Save allowlist
          </Button>
        }
      >
        <Field
          label="Allowed numbers"
          hint="Comma separated, in E.164 format."
          help="Leave empty to allow any valid number."
        >
          <Input
            value={allowlist}
            onChange={(e) => setAllowlist(e.target.value)}
            placeholder="+919876543210, +15555550100"
            className="font-mono text-data"
          />
        </Field>
      </SettingsSection>

      <SettingsSection
        title="Ceilings and pacing"
        description="How many calls a run may place, and how fast they go out."
        effect={`A run stops after ${ceiling} real ${Number(ceiling) === 1 ? "call" : "calls"} even if the list is longer. Calls go out at ${ratePerHour} per hour, and everything stops for the day after ${formatNumber(Number(dailyBudget))}.`}
        footer={
          <Button size="sm" onClick={notSaved}>
            Save ceilings
          </Button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Per-run ceiling">
            <Input
              type="number"
              min={1}
              value={ceiling}
              onChange={(e) => setCeiling(e.target.value)}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Calls per hour">
            <Input
              type="number"
              min={1}
              value={ratePerHour}
              onChange={(e) => setRatePerHour(e.target.value)}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Daily budget">
            <Input
              type="number"
              min={1}
              value={dailyBudget}
              onChange={(e) => setDailyBudget(e.target.value)}
              className="font-mono tabular-nums"
            />
          </Field>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Calling window"
        description="The organisation default. A campaign can narrow it, but not widen it."
        effect={`Nothing is dialled outside ${windowStart}–${windowEnd} ${timezone}. A contact reached outside the window is queued for the next opening rather than counted as a failure.`}
        footer={
          <Button size="sm" onClick={notSaved}>
            Save window
          </Button>
        }
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="From">
            <Input
              type="time"
              value={windowStart}
              onChange={(e) => setWindowStart(e.target.value)}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Until">
            <Input
              type="time"
              value={windowEnd}
              onChange={(e) => setWindowEnd(e.target.value)}
              className="font-mono tabular-nums"
            />
          </Field>
          <Field label="Timezone">
            <Select value={timezone} onValueChange={setTimezone} options={TIMEZONES} />
          </Field>
        </div>
      </SettingsSection>
    </div>
  );
}
