"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

export const ROLES = [
  { value: "admin", label: "Admin", hint: "Everything, including billing, safety, and integrations" },
  { value: "operator", label: "Operator", hint: "Start runs, edit campaigns, resolve escalations" },
  { value: "viewer", label: "Viewer", hint: "Read results only — cannot start a run" },
];

/** Mounted from three places: the dashboard's Team preview, the header's Team
 * popover (`TeamControls`), and Settings → Team. */
export function InviteDialog({
  open,
  onOpenChange,
  onInvited,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: () => void;
}) {
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("operator");
  const [sending, setSending] = useState(false);

  async function send() {
    if (!email.trim()) return;
    setSending(true);
    try {
      await api.inviteMember(email.trim(), role);
      toast({ tone: "success", title: "Invitation sent", body: email.trim() });
      setEmail("");
      onOpenChange(false);
      onInvited();
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't send the invitation",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSending(false);
    }
  }

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="Invite a teammate"
        description="They'll get an email with a link. Nothing happens on their account until they accept it."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={sending}>
              Cancel
            </Button>
            <Button onClick={send} loading={sending}>
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
  );
}
