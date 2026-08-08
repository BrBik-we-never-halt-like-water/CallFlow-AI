"use client";

import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { guardsFromSafety, SafetyBar } from "@/components/app/safety-bar";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { TIMEZONES } from "@/lib/campaign-draft";
import { formatNumber } from "@/lib/format";
import { isE164, normalisePhone } from "@/lib/format/phone";
import { api, type SafetySettings } from "@/lib/api";
import { useAppStore } from "@/lib/app-store";

/**
 * Safety settings.
 *
 * Every control here shows its current effect in plain language beneath it, and
 * every value shown is what's actually enforced — saved to this organisation, not
 * the deployment's shared env vars. Calling-window fields stay honestly marked as
 * not enforced (`ISSUES.md` #20) until that guard is real.
 */
export default function SafetySettingsPage() {
  const toast = useToast();
  const { safetySettings, refreshSafety } = useAppStore();

  const [allowlist, setAllowlist] = useState("");
  const [ceiling, setCeiling] = useState("3");
  const [ratePerHour, setRatePerHour] = useState("5");
  const [dailyBudget, setDailyBudget] = useState("20");
  const [windowStart, setWindowStart] = useState("09:00");
  const [windowEnd, setWindowEnd] = useState("20:00");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [saving, setSaving] = useState(false);
  const [loadedFrom, setLoadedFrom] = useState<SafetySettings | null>(null);

  // Seed the form from the org's real settings once they load, without fighting
  // the user's in-progress edits on every background refresh. Set during render
  // (React's own pattern for "reset derived state when a prop changes"), not in
  // an effect — an effect here would just be a second render of the same update.
  if (safetySettings && loadedFrom !== safetySettings) {
    setAllowlist(safetySettings.allowlist.join(", "));
    setCeiling(String(safetySettings.max_calls_per_run));
    setRatePerHour(String(safetySettings.calls_per_window));
    setDailyBudget(String(safetySettings.daily_budget));
    setLoadedFrom(safetySettings);
  }

  const allowlistNumbers = allowlist
    .split(",")
    .map((n) => normalisePhone(n.trim()))
    .filter(Boolean);
  const allowlistCount = allowlistNumbers.length;

  async function saveAllowlist() {
    const invalid = allowlistNumbers.filter((n) => !isE164(n));
    if (invalid.length > 0) {
      toast({
        tone: "error",
        title: "That allowlist has an invalid number",
        body: `Not E.164: ${invalid.join(", ")}`,
      });
      return;
    }
    await save({ allowlist: allowlistNumbers });
  }

  async function saveCeilings() {
    await save({
      max_calls_per_run: Number(ceiling),
      calls_per_window: Number(ratePerHour),
      daily_budget: Number(dailyBudget),
    });
  }

  async function save(patch: Partial<Omit<SafetySettings, "used_today">>) {
    if (!safetySettings) return;
    setSaving(true);
    try {
      // The two save buttons are section-scoped, but the API call always
      // writes every field. Fields outside the section being saved must fall
      // back to what's currently on screen — not `safetySettings` (server
      // truth) — or clicking "Save ceilings" while the allowlist field has an
      // unsaved edit would silently revert that edit the moment the response
      // comes back and reseeds the form from the server.
      const updated = await api.updateSafetySettings({
        allowlist: patch.allowlist ?? allowlistNumbers,
        max_calls_per_run: patch.max_calls_per_run ?? Number(ceiling),
        calls_per_window: patch.calls_per_window ?? Number(ratePerHour),
        window_minutes: safetySettings.window_minutes,
        daily_budget: patch.daily_budget ?? Number(dailyBudget),
      });
      setLoadedFrom(updated);
      refreshSafety();
      toast({ tone: "success", title: "Safety settings saved" });
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't save",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  if (!safetySettings) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Guards in force"
        description="This is the same bar shown above every run composer."
      >
        <SafetyBar guards={guardsFromSafety(safetySettings)} />
      </SettingsSection>

      <SettingsSection
        title="Allowlist"
        description="While this has anything in it, those are the only numbers any run may dial."
        effect={
          allowlistCount > 0
            ? `Only these ${allowlistCount} ${allowlistCount === 1 ? "number" : "numbers"} can be dialled. Everything else is skipped before it rings.`
            : "The allowlist is empty, so any valid number in a run can be dialled. While you're still setting up, put your own number here."
        }
        footer={
          <Button size="sm" onClick={saveAllowlist} loading={saving}>
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
        effect={`A run stops after ${ceiling} real ${Number(ceiling) === 1 ? "call" : "calls"} even if the list is longer. Calls go out at ${ratePerHour} per hour, up to a daily budget of ${formatNumber(Number(dailyBudget))} calls — ${safetySettings.used_today} used so far today.`}
        footer={
          <Button size="sm" onClick={saveCeilings} loading={saving}>
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

      <SettingsSection title="Calling window" description="The organisation default.">
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

        <NotWiredNotice>
          Not enforced yet — a run can still dial outside these hours. Setting a
          window here doesn&apos;t change that until this ships.
        </NotWiredNotice>
      </SettingsSection>
    </div>
  );
}
