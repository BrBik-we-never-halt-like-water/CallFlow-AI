"use client";

import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";

const ROLES = [
  {
    value: "admin",
    label: "Admin",
    hint: "Everything, including billing, safety, and going live",
  },
  {
    value: "operator",
    label: "Operator",
    hint: "Start runs, edit campaigns, resolve escalations",
  },
  {
    value: "viewer",
    label: "Viewer",
    hint: "Read results only   cannot start a run",
  },
];

export default function TeamSettingsPage() {
  const toast = useToast();
  const [inviting, setInviting] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("operator");

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Members"
        description="Who can get into this organisation, and what they're allowed to do."
        footer={
          <Button size="sm" onClick={() => setInviting(true)}>
            Invite a teammate
          </Button>
        }
      >
        <EmptyState
          title="It's just you"
          body="Invite the people who triage escalations. Give them Operator, not Admin   only Admins can switch a run to live."
        />
      </SettingsSection>

      <SettingsSection
        title="Roles"
        description="What each role can do. Permissions are fixed rather than per-user, so access is predictable."
      >
        <ul className="flex flex-col">
          {ROLES.map((r) => (
            <li
              key={r.value}
              className="flex flex-wrap items-start justify-between gap-3 border-b border-rule py-3 last:border-0"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="text-small font-medium text-text">{r.label}</span>
                <span className="text-small text-text-dim">{r.hint}</span>
              </div>
              {r.value === "admin" ? <Tag>Can go live</Tag> : null}
            </li>
          ))}
        </ul>
      </SettingsSection>

      <NotWiredNotice>
        Inviting teammates and enforcing roles needs an account service, which this
        deployment does not have. Everything in the dashboard is currently open.
      </NotWiredNotice>

      <DialogRoot open={inviting} onOpenChange={setInviting}>
        <Dialog
          title="Invite a teammate"
          description="They'll get an email with a link. Nothing happens on their account until they set a password."
          size="sm"
          footer={
            <>
              <Button variant="secondary" onClick={() => setInviting(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => {
                  setInviting(false);
                  toast({
                    tone: "info",
                    title: "No invitation was sent",
                    body: "Invitations need an account service, which this deployment doesn't have yet.",
                  });
                }}
              >
                Send invitation
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <Field label="Work email" required>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
              />
            </Field>
            <Field label="Role" help="Operators can run campaigns but not change billing.">
              <Select value={role} onValueChange={setRole} options={ROLES} />
            </Field>
          </div>
        </Dialog>
      </DialogRoot>
    </div>
  );
}
