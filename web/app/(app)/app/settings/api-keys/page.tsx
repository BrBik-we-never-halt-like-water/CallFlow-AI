"use client";

import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { LampBadge, Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Panel } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import { useAppStore } from "@/lib/app-store";

const SCOPES = [
  { id: "campaigns:read", label: "Read campaigns" },
  { id: "campaigns:write", label: "Create and edit campaigns" },
  { id: "runs:read", label: "Read runs and results" },
  { id: "runs:write", label: "Start runs (can place live calls)" },
];

export default function ApiKeysSettingsPage() {
  const toast = useToast();
  const { health } = useAppStore();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<Set<string>>(new Set(["runs:read"]));

  return (
    <div className="flex flex-col gap-4">
      {/* The voice credential is labelled by what it does, never by the vendor that
          issues it. The environment variable keeps its own name in code. */}
      <SettingsSection
        title="Voice API key"
        description="The credential the service uses to place calls. Without it, only dry runs are possible."
        effect={
          health?.api_key_configured
            ? "A Voice API key is configured, so live calls can be placed once dry run is turned off."
            : "No Voice API key is configured. Dry runs work; live runs will be refused with an explanation."
        }
      >
        <div className="flex flex-wrap items-center gap-3">
          <LampBadge state={health?.api_key_configured ? "jade" : "brass"}>
            {health?.api_key_configured ? "Configured" : "Not configured"}
          </LampBadge>
          <p className="text-small text-text-mute">
            Set on the server, never shown in the interface.
          </p>
        </div>
      </SettingsSection>

      <SettingsSection
        title="Your API keys"
        description="For calling CallFlow from your own systems. Shown once at creation, then stored hashed."
        footer={
          <Button size="sm" onClick={() => setCreating(true)}>
            Create a key
          </Button>
        }
      >
        <EmptyState
          title="No keys yet"
          body="Create one to start runs or read results from your own code. Give each system its own key so you can revoke one without breaking the others."
        />
      </SettingsSection>

      <NotWiredNotice>
        Issuing and revoking API keys needs an account service, which this deployment does
        not have. The Voice API key status above is real — it is read from the calling
        service.
      </NotWiredNotice>

      <DialogRoot open={creating} onOpenChange={setCreating}>
        <Dialog
          title="Create an API key"
          description="Pick the narrowest set of scopes that does the job. A key with runs:write can place real calls."
          footer={
            <>
              <Button variant="secondary" onClick={() => setCreating(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  setCreating(false);
                  toast({
                    tone: "info",
                    title: "No key was created",
                    body: "Key issuing needs an account service, which this deployment doesn't have yet.",
                  });
                }}
              >
                Create key
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <Field label="What is this key for" hint="A name you'll recognise in six months.">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="CRM sync (production)"
                autoFocus
              />
            </Field>

            <fieldset className="flex flex-col gap-2">
              <legend className="text-small font-medium text-text">Scopes</legend>
              {SCOPES.map((scope) => (
                <Checkbox
                  key={scope.id}
                  id={scope.id}
                  checked={scopes.has(scope.id)}
                  onCheckedChange={(next) =>
                    setScopes((current) => {
                      const updated = new Set(current);
                      if (next) updated.add(scope.id);
                      else updated.delete(scope.id);
                      return updated;
                    })
                  }
                  label={scope.label}
                />
              ))}
            </fieldset>

            <Panel sunken className="flex items-center justify-between gap-3 p-3">
              <div className="flex min-w-0 flex-col">
                <span className="text-small text-text-dim">You&apos;ll see the key once</span>
                <span className="truncate font-mono text-data text-text-mute">
                  cf_live_••••••••••••••••
                </span>
              </div>
              <Tag>Reveal once</Tag>
            </Panel>
          </div>
        </Dialog>
      </DialogRoot>
    </div>
  );
}
