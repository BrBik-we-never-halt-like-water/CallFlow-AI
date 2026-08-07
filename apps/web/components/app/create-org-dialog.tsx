"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, type Organisation } from "@/lib/api";

/** Shared by the user-menu's org switcher and Overview's org strip. */
export function CreateOrgDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (org: Organisation) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (name.trim().length < 2) return;

    setSubmitting(true);
    try {
      const org = await api.createOrganisation(name.trim());
      setName("");
      onOpenChange(false);
      onCreated(org);
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't create the organisation",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="New organisation"
        description="A separate workspace with its own team, campaigns, and settings."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button onClick={submit} loading={submitting}>
              Create
            </Button>
          </>
        }
      >
        <form onSubmit={submit}>
          <Field label="Organisation name" required>
            <Input value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
        </form>
      </Dialog>
    </DialogRoot>
  );
}
