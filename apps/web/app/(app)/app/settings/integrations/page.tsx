'use client';

import { useState } from 'react';
import {
  NotWiredNotice,
  SettingsSection,
} from '@/components/app/settings-section';
import { SessionGate } from '@/components/app/session-gate';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { api, type Provider, type ProviderCredential } from '@/lib/api';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

const PROVIDERS: {
  id: Provider;
  name: string;
  mark: string;
  identifierLabel: string;
  secretLabel: string;
  description: string;
}[] = [
  {
    id: 'twilio',
    name: 'Twilio',
    mark: 'T',
    identifierLabel: 'Account SID',
    secretLabel: 'Auth token',
    description:
      "Store your organisation's Twilio account credentials, encrypted.",
  },
  {
    id: 'plivo',
    name: 'Plivo',
    mark: 'P',
    identifierLabel: 'Auth ID',
    secretLabel: 'Auth token',
    description:
      "Store your organisation's Plivo account credentials, encrypted.",
  },
];

/**
 * A provider's mark - its initial in a consistent badge, the same monochrome
 * pattern as `OrgMark`. Not the vendor's actual logo: reproducing a trademarked
 * wordmark accurately needs the vendor's own asset, not a guess, and this
 * product's identity is monochrome throughout regardless.
 */
function ProviderMark({ letter }: { letter: string }) {
  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-sm border border-rule bg-surface-sunken font-mono text-small font-medium text-text">
      {letter}
    </span>
  );
}

const COMING_SOON = [
  {
    name: 'Zapier',
    reason: 'Connect CallFlow to thousands of other tools without custom code.',
  },
  {
    name: 'Slack',
    reason:
      'Escalation alerts where the team already lives, the moment a call needs a person.',
  },
  {
    name: 'HubSpot',
    reason:
      'Push typed call results back onto the CRM record your team already works from.',
  },
  {
    name: 'Salesforce',
    reason:
      'The same write-back, for teams whose pipeline lives in Salesforce instead.',
  },
  {
    name: 'Google Sheets',
    reason:
      'For teams running contacts from a spreadsheet - results land back in the same one.',
  },
];

export default function IntegrationsSettingsPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <IntegrationsContent profile={profile} />}
    </SessionGate>
  );
}

function IntegrationsContent({ profile }: { profile: SessionProfile }) {
  const toast = useToast();
  const canRead = profile.permissions.includes('integrations:read');
  const canWrite = profile.permissions.includes('integrations:write');

  const [credentials, setCredentials] = useState<ProviderCredential[] | null>(
    null,
  );
  const [editing, setEditing] = useState<Provider | null>(null);

  function load() {
    if (!canRead) return;
    api
      .listProviderCredentials()
      .then(setCredentials)
      .catch(() =>
        toast({ tone: 'error', title: "Couldn't load integrations" }),
      );
  }

  useOrgScopedEffect(() => {
    load();
  });

  if (!canRead) {
    return (
      <NotWiredNotice>
        Integrations are visible to owners and admins only. Ask one in your
        organisation if you need to connect a number.
      </NotWiredNotice>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <SettingsSection
        title="Your own phone numbers"
        description="Connect Twilio or Plivo and we'll store your organisation's account credentials, encrypted."
      >
        {credentials === null ? (
          <div className="flex flex-col gap-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : (
          <ul className="flex flex-col divide-y divide-rule">
            {PROVIDERS.map((provider) => (
              <ProviderRow
                key={provider.id}
                provider={provider}
                credential={
                  credentials.find((c) => c.provider === provider.id) ?? null
                }
                canWrite={canWrite}
                onEdit={() => setEditing(provider.id)}
                onChanged={load}
              />
            ))}
          </ul>
        )}
      </SettingsSection>

      <NotWiredNotice>
        A connected number stores real, encrypted credentials - but nothing yet
        places a call over it. That&apos;s a separate, not-yet-built piece of
        work (the voice-agent platform); today, connecting a number here
        doesn&apos;t change which numbers your runs dial from.
      </NotWiredNotice>

      <SettingsSection
        title="More integrations"
        description="Coming soon - reach out if one of these would unblock you sooner."
      >
        <ul className="flex flex-col divide-y divide-rule">
          {COMING_SOON.map((integration) => (
            <li
              key={integration.name}
              className="flex flex-wrap items-center justify-between gap-3 py-3"
            >
              <div className="flex min-w-0 flex-col gap-0.5">
                <span className="text-small font-medium text-text">
                  {integration.name}
                </span>
                <span className="measure text-small text-text-dim">
                  {integration.reason}
                </span>
              </div>
              <Tag>Coming soon</Tag>
            </li>
          ))}
        </ul>
      </SettingsSection>

      {editing ? (
        <ConnectDialog
          provider={PROVIDERS.find((p) => p.id === editing)!}
          existing={credentials?.find((c) => c.provider === editing) ?? null}
          onOpenChange={(open) => !open && setEditing(null)}
          onChanged={() => {
            setEditing(null);
            load();
          }}
        />
      ) : null}
    </div>
  );
}

function ProviderRow({
  provider,
  credential,
  canWrite,
  onEdit,
  onChanged,
}: {
  provider: (typeof PROVIDERS)[number];
  credential: ProviderCredential | null;
  canWrite: boolean;
  onEdit: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [disconnecting, setDisconnecting] = useState(false);

  async function disconnect() {
    setDisconnecting(true);
    try {
      await api.disconnectProvider(provider.id);
      toast({ tone: 'info', title: `${provider.name} disconnected` });
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't disconnect",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <ProviderMark letter={provider.mark} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="text-small font-medium text-text">
              {provider.name}
            </span>
            {credential ? <Tag>Connected</Tag> : null}
          </div>
          <span className="measure text-small text-text-dim">
            {credential?.phone_number ?? provider.description}
          </span>
        </div>
      </div>
      {canWrite ? (
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={onEdit}>
            {credential ? 'Update' : 'Connect'}
          </Button>
          {credential ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={disconnect}
              loading={disconnecting}
            >
              Disconnect
            </Button>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function ConnectDialog({
  provider,
  existing,
  onOpenChange,
  onChanged,
}: {
  provider: (typeof PROVIDERS)[number];
  existing: ProviderCredential | null;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  const [phoneNumber, setPhoneNumber] = useState(existing?.phone_number ?? '');
  const [saving, setSaving] = useState(false);

  const valid = identifier.trim().length > 0 && secret.trim().length > 0;

  async function save() {
    if (!valid) return;
    setSaving(true);
    try {
      await api.connectProvider(provider.id, {
        identifier: identifier.trim(),
        secret: secret.trim(),
        phone_number: phoneNumber.trim() || undefined,
      });
      toast({ tone: 'success', title: `${provider.name} connected` });
      onChanged();
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't save credentials",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <DialogRoot open onOpenChange={onOpenChange}>
      <Dialog
        title={`Connect ${provider.name}`}
        description={
          existing
            ? 'Replacing these credentials overwrites the ones on file. The previous values are never shown again.'
            : 'Find these in your ' +
              provider.name +
              ' console. Stored encrypted, never shown again after saving.'
        }
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={save} loading={saving} disabled={!valid}>
              Save
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          <Field label={provider.identifierLabel}>
            <Input
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              autoFocus
              autoComplete="off"
            />
          </Field>
          <Field label={provider.secretLabel}>
            <Input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              autoComplete="off"
            />
          </Field>
          <Field label="Phone number" hint="Optional, E.164 format">
            <Input
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="+15555550100"
            />
          </Field>
        </div>
      </Dialog>
    </DialogRoot>
  );
}
