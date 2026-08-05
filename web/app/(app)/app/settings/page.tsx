"use client";

import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { REGIONS, TIMEZONES } from "@/lib/campaign-draft";

/** Version string. Moved here out of the site footer, where it was noise for visitors. */
const APP_VERSION = "0.2.0";

export default function OrganisationSettingsPage() {
  const toast = useToast();
  const [name, setName] = useState("Your organisation");
  const [region, setRegion] = useState("IN");
  const [timezone, setTimezone] = useState("Asia/Kolkata");

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Organisation"
        description="The name that appears on invitations and in the caller's disclosure line."
        effect={`Calls introduce themselves as calling on behalf of “${name}”.`}
        footer={
          <Button
            size="sm"
            onClick={() =>
              toast({
                tone: "info",
                title: "Organisation settings aren't saved yet",
                body: "There's no account service on this deployment to store them.",
              })
            }
          >
            Save changes
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label="Organisation name">
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Default calling region">
              <Select value={region} onValueChange={setRegion} options={REGIONS} />
            </Field>
            <Field label="Default timezone">
              <Select value={timezone} onValueChange={setTimezone} options={TIMEZONES} />
            </Field>
          </div>
        </div>
      </SettingsSection>

      <SettingsSection title="About this deployment">
        <dl className="flex flex-col gap-2">
          <Row label="Interface version" value={APP_VERSION} />
          <Row label="Surface modes" value="Paper and Panel" />
        </dl>
      </SettingsSection>

      <NotWiredNotice>
        Organisation, team, and billing settings need an account service, which this
        deployment does not have yet. The safety and compliance panes read real values
        from the calling service and are accurate.
      </NotWiredNotice>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-small text-text-dim">{label}</dt>
      <dd className="font-mono text-data tabular-nums text-text">{value}</dd>
    </div>
  );
}
