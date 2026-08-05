"use client";

import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { LampBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { REGIONS } from "@/lib/campaign-draft";
import { useAppStore } from "@/lib/app-store";

export default function NumbersSettingsPage() {
  const toast = useToast();
  const { health } = useAppStore();

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Caller IDs"
        description="The number your contacts see when a call comes in."
        effect={
          health?.api_key_configured
            ? "Calls are placed from the number configured on the service. Verify your own caller ID to have contacts see a number they recognise."
            : "No calling credential is configured yet, so no caller ID is in use."
        }
        footer={
          <Button
            size="sm"
            onClick={() =>
              toast({
                tone: "info",
                title: "Caller ID verification isn't available here",
                body: "Verifying a number you own needs the number-management service.",
              })
            }
          >
            Verify a number
          </Button>
        }
      >
        <EmptyState
          title="No verified caller IDs"
          body="Verify a number you already own and campaigns will dial from it. Contacts are far more likely to answer a number they recognise."
        />
      </SettingsSection>

      <SettingsSection
        title="Regional availability"
        description="Where calls can be placed, and what each region implies."
      >
        <ul className="flex flex-col">
          {REGIONS.map((region) => (
            <li
              key={region.value}
              className="flex flex-wrap items-center gap-3 border-b border-rule py-2.5 last:border-0"
            >
              <span className="min-w-0 flex-1 text-small text-text">{region.label}</span>
              <span className="font-mono text-data text-text-mute">{region.value}</span>
              <LampBadge state="jade">Available</LampBadge>
            </li>
          ))}
        </ul>
      </SettingsSection>

      <NotWiredNotice>
        Number management needs a provisioning service. The calling region on a campaign is
        real and is sent with every call.
      </NotWiredNotice>
    </div>
  );
}
