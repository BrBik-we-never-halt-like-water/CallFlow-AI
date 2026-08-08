"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { ImageUpload } from "@/components/ui/image-upload";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { useToast } from "@/components/ui/toast";
import { api, type Organisation } from "@/lib/api";
import { useActiveOrg } from "@/lib/hooks/use-active-org";
import { useSession } from "@/lib/hooks/use-session";

type Step = "name" | "logo";

/**
 * A real screen for starting a new organisation, not a name-only popup.
 *
 * Two steps rather than one form: the logo can only be uploaded to a real
 * `{org_id}/...` storage path (the RLS policy on `org-logos` requires it), so the
 * organisation has to exist before that field can do anything. Splitting it this
 * way is also the only way to make the logo step genuinely skippable without a
 * disabled control sitting there unexplained.
 */
export default function NewOrganisationPage() {
  const router = useRouter();
  const toast = useToast();
  const session = useSession();
  const [, setActiveOrgId] = useActiveOrg();

  const [step, setStep] = useState<Step>("name");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<Organisation | null>(null);
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  async function createOrg(event: React.FormEvent) {
    event.preventDefault();
    if (name.trim().length < 2) return;
    setCreating(true);
    try {
      const org = await api.createOrganisation(name.trim());
      setCreated(org);
      setActiveOrgId(org.id);
      await session.refresh();
      setStep("logo");
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't create the organisation",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setCreating(false);
    }
  }

  async function finish() {
    if (!created) return;
    setFinishing(true);
    try {
      if (logoUrl) {
        await api.updateActiveOrganisation({ logo_url: logoUrl });
      }
      toast({ tone: "success", title: "Organisation created", body: created.name });
      router.replace("/app");
    } catch (error) {
      toast({
        tone: "error",
        title: "Created, but the logo didn't save",
        body: error instanceof Error ? error.message : undefined,
      });
      router.replace("/app");
    } finally {
      setFinishing(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">New organisation</p>
        <h1 className="font-display text-h2 text-text">
          {step === "name" ? "Name your organisation" : "Add a logo"}
        </h1>
        <p className="measure text-small text-text-dim">
          {step === "name"
            ? "A separate workspace with its own team, campaigns, and settings."
            : "Optional — everyone you invite will see this next to the name."}
        </p>
      </div>

      <Panel className="flex flex-col gap-5 p-5">
        {step === "name" ? (
          <form onSubmit={createOrg} className="flex flex-col gap-4">
            <Field label="Organisation name" required>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                maxLength={120}
              />
            </Field>
            <div className="flex items-center gap-3 border-t border-rule pt-4">
              <Button type="submit" loading={creating} disabled={name.trim().length < 2}>
                Continue
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => router.back()}
                disabled={creating}
              >
                Cancel
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-col gap-4">
            <Field label="Logo">
              <ImageUpload
                bucket="org-logos"
                ownerId={created?.id ?? ""}
                value={logoUrl}
                onChange={setLogoUrl}
                label="Upload an organisation logo"
                shape="square"
              />
            </Field>
            <div className="flex items-center gap-3 border-t border-rule pt-4">
              <Button onClick={finish} loading={finishing}>
                {logoUrl ? "Finish" : "Skip for now"}
              </Button>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
