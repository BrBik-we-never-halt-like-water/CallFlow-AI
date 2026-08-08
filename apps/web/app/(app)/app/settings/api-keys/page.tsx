"use client";

import { useState } from "react";
import { NotWiredNotice, SettingsSection } from "@/components/app/settings-section";
import { SessionGate } from "@/components/app/session-gate";
import { Button } from "@/components/ui/button";
import { CodeBlock } from "@/components/ui/code-block";
import { Dialog, DialogRoot } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { formatAge } from "@/lib/format";
import { api, type ApiKey } from "@/lib/api";
import { useOrgScopedEffect } from "@/lib/hooks/use-org-scoped-effect";
import { useSession, type SessionProfile } from "@/lib/hooks/use-session";

export default function ApiKeysSettingsPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <ApiKeysContent profile={profile} />}
    </SessionGate>
  );
}

function ApiKeysContent({ profile }: { profile: SessionProfile }) {
  const toast = useToast();
  const canRead = profile.permissions.includes("api_keys:read");
  const canWrite = profile.permissions.includes("api_keys:write");

  const [keys, setKeys] = useState<ApiKey[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [justCreated, setJustCreated] = useState<{ name: string; key: string } | null>(null);

  function load() {
    if (!canRead) return;
    api
      .listApiKeys()
      .then(setKeys)
      .catch(() => toast({ tone: "error", title: "Couldn't load API keys" }));
  }

  useOrgScopedEffect(() => {
    load();
  });

  if (!canRead) {
    return (
      <NotWiredNotice>
        API keys are visible to owners and admins only. Ask one in your organisation
        if you need programmatic access.
      </NotWiredNotice>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="API keys"
        description="Authenticate requests to CallFlow's own API without a user session — send one as a bearer token: Authorization: Bearer cfk_..."
        footer={
          canWrite ? (
            <Button size="sm" onClick={() => setCreating(true)}>
              Create key
            </Button>
          ) : undefined
        }
      >
        {keys === null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : keys.length === 0 ? (
          <EmptyState
            title="No API keys yet"
            body="Create one to call CallFlow's API from a script, a cron job, or another service."
          />
        ) : (
          <ul className="flex flex-col divide-y divide-rule">
            {keys.map((key) => (
              <ApiKeyRow key={key.id} apiKey={key} canRevoke={canWrite} onChanged={load} />
            ))}
          </ul>
        )}
      </SettingsSection>

      <CreateKeyDialog
        open={creating}
        onOpenChange={setCreating}
        onCreated={(name, key) => {
          setJustCreated({ name, key });
          load();
        }}
      />

      <RevealKeyDialog
        created={justCreated}
        onClose={() => setJustCreated(null)}
      />
    </div>
  );
}

function ApiKeyRow({
  apiKey,
  canRevoke,
  onChanged,
}: {
  apiKey: ApiKey;
  canRevoke: boolean;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [revoking, setRevoking] = useState(false);
  const [confirming, setConfirming] = useState(false);

  async function revoke() {
    setRevoking(true);
    try {
      await api.revokeApiKey(apiKey.id);
      toast({ tone: "info", title: "Key revoked" });
      setConfirming(false);
      onChanged();
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't revoke the key",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setRevoking(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-small font-medium text-text">{apiKey.name}</span>
        <span className="truncate font-mono text-data text-text-mute">
          {apiKey.key_prefix}… · created {formatAge(apiKey.created_at)} ·{" "}
          {apiKey.last_used_at
            ? `last used ${formatAge(apiKey.last_used_at)}`
            : "never used"}
        </span>
      </div>
      {canRevoke ? (
        <>
          <Button variant="ghost" size="sm" onClick={() => setConfirming(true)}>
            Revoke
          </Button>
          <DialogRoot open={confirming} onOpenChange={setConfirming}>
            <Dialog
              title={`Revoke "${apiKey.name}"?`}
              description="Any request using this key stops working immediately. This can't be undone."
              size="sm"
              footer={
                <>
                  <Button variant="secondary" onClick={() => setConfirming(false)}>
                    Keep it
                  </Button>
                  <Button variant="danger" onClick={revoke} loading={revoking}>
                    Revoke key
                  </Button>
                </>
              }
            />
          </DialogRoot>
        </>
      ) : null}
    </li>
  );
}

function CreateKeyDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (name: string, key: string) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    try {
      const created = await api.createApiKey(trimmed);
      onOpenChange(false);
      setName("");
      onCreated(created.name, created.key);
    } catch (error) {
      toast({
        tone: "error",
        title: "Couldn't create the key",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setCreating(false);
    }
  }

  return (
    <DialogRoot open={open} onOpenChange={onOpenChange}>
      <Dialog
        title="Create an API key"
        description="Name it after what will use it — you'll only see the full key once."
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={submit} loading={creating} disabled={!name.trim()}>
              Create key
            </Button>
          </>
        }
      >
        <Field label="Name">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="CI pipeline"
            autoFocus
            maxLength={120}
          />
        </Field>
      </Dialog>
    </DialogRoot>
  );
}

function RevealKeyDialog({
  created,
  onClose,
}: {
  created: { name: string; key: string } | null;
  onClose: () => void;
}) {
  return (
    <DialogRoot open={created !== null} onOpenChange={(open) => !open && onClose()}>
      {created ? (
        <Dialog
          title={`"${created.name}" is ready`}
          description="Copy it now — this is the only time it's shown. If you lose it, revoke the key and create another."
          size="sm"
          footer={
            <Button onClick={onClose}>Done — I&apos;ve saved it</Button>
          }
        >
          <CodeBlock code={created.key} language="text" />
        </Dialog>
      ) : null}
    </DialogRoot>
  );
}
