'use client';

import { useCallback, useMemo, useState } from 'react';
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
import { Panel } from '@/components/ui/panel';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type Provider,
  type ProviderCredential,
  type ProviderRole,
  type ProviderSpec,
} from '@/lib/api';
import { beginOAuth, takePendingOAuth } from '@/lib/oauth';
import { useOrgScopedEffect } from '@/lib/hooks/use-org-scoped-effect';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

/**
 * Grouped by what a credential is *for*, not by vendor.
 *
 * A flat vendor list answers "which brands do you support"; an operator is
 * asking "what do I still need before a call can happen". The three groups
 * mirror `voice_agents`' own columns, so the page and the schema describe the
 * same shape - and the readiness line under each heading is only meaningful
 * because of that.
 */
const ROLES: { id: ProviderRole; title: string; description: string }[] = [
  {
    id: 'telephony',
    title: 'Phone numbers',
    description:
      'The carrier account calls are placed through. Your number, your account, your rates.',
  },
  {
    id: 'speech',
    title: 'Voice',
    description:
      'What turns speech into text and text back into a voice. Pick per agent - an English and a Hindi agent can differ.',
  },
  {
    id: 'intelligence',
    title: 'Intelligence',
    description: 'The model the agent thinks with while the call is happening.',
  },
];

/**
 * A provider's mark - its initial in a consistent badge, the same monochrome
 * pattern as `OrgMark`. Not the vendor's actual logo: reproducing a trademarked
 * wordmark accurately needs the vendor's own asset, not a guess, and this
 * product's identity is monochrome throughout regardless (DESIGN_NOTES.md §9).
 */
function ProviderMark({ name, connected }: { name: string; connected: boolean }) {
  return (
    <span
      aria-hidden
      className={
        'flex size-9 shrink-0 items-center justify-center rounded-sm border font-mono text-small font-medium ' +
        (connected
          ? 'border-rule-strong bg-surface-raised text-text'
          : 'border-rule bg-surface-sunken text-text-mute')
      }
    >
      {name.charAt(0)}
    </span>
  );
}

const COMING_SOON = [
  { name: 'Zapier', reason: 'Reach thousands of other tools without custom code.' },
  {
    name: 'Slack',
    reason: 'Escalation alerts where the team already lives, the moment a call needs a person.',
  },
  {
    name: 'HubSpot',
    reason: 'Push typed call results back onto the CRM record your team already works from.',
  },
  {
    name: 'Salesforce',
    reason: 'The same write-back, for teams whose pipeline lives in Salesforce instead.',
  },
  {
    name: 'Google Sheets',
    reason: 'For teams running contacts from a spreadsheet - results land back in the same one.',
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

  const [catalogue, setCatalogue] = useState<ProviderSpec[] | null>(null);
  const [credentials, setCredentials] = useState<ProviderCredential[] | null>(null);
  const [editing, setEditing] = useState<ProviderSpec | null>(null);

  const load = useCallback(() => {
    if (!canRead) return;
    Promise.all([api.listProviderCatalogue(), api.listProviderCredentials()])
      .then(([specs, creds]) => {
        setCatalogue(specs);
        setCredentials(creds);
      })
      .catch(() => toast({ tone: 'error', title: "Couldn't load integrations" }));
  }, [canRead, toast]);

  /**
   * Finish an OAuth connection the user started before leaving the page.
   *
   * The vendor redirects back with `?code=`, which is single-use - so this
   * clears it from both the store and the address bar before exchanging, or a
   * refresh replays a code the vendor has already spent and shows an error for
   * something that actually worked.
   */
  const resume = useCallback(async () => {
    const pending = takePendingOAuth();
    if (!pending) return;
    try {
      await api.exchangeOAuthCode(pending.provider, {
        code: pending.code,
        code_verifier: pending.verifier,
      });
      toast({ tone: 'success', title: `${pending.providerName} connected` });
    } catch (error) {
      toast({
        tone: 'error',
        title: "Couldn't finish connecting",
        body: error instanceof Error ? error.message : undefined,
      });
    }
  }, [toast]);

  useOrgScopedEffect(() => {
    void resume().then(load);
  });

  const byRole = useMemo(() => {
    const map = new Map<ProviderRole, ProviderSpec[]>();
    for (const spec of catalogue ?? []) {
      map.set(spec.role, [...(map.get(spec.role) ?? []), spec]);
    }
    return map;
  }, [catalogue]);

  const connectedIds = useMemo(
    () => new Set((credentials ?? []).map((c) => c.provider)),
    [credentials],
  );

  if (!canRead) {
    return (
      <NotWiredNotice>
        Integrations are visible to owners and admins only. Ask one in your
        organisation if you need to connect an account.
      </NotWiredNotice>
    );
  }

  const loading = catalogue === null || credentials === null;

  return (
    <div className="flex flex-col gap-4">
      <ReadinessSummary
        roles={ROLES}
        byRole={byRole}
        connectedIds={connectedIds}
        loading={loading}
      />

      {ROLES.map((role) => (
        <SettingsSection
          key={role.id}
          title={role.title}
          description={role.description}
        >
          {loading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-14 w-full" />
            </div>
          ) : (
            <ul className="flex flex-col divide-y divide-rule">
              {(byRole.get(role.id) ?? []).map((spec) => (
                <ProviderRow
                  key={spec.id}
                  spec={spec}
                  credential={
                    (credentials ?? []).find((c) => c.provider === spec.id) ?? null
                  }
                  canWrite={canWrite}
                  onEdit={() => setEditing(spec)}
                  onChanged={load}
                />
              ))}
            </ul>
          )}
        </SettingsSection>
      ))}

      <NotWiredNotice>
        Connecting an account stores real, encrypted credentials. Pointing a
        phone number at CallFlow is a further step, and it isn&apos;t wired up
        yet - so connecting a carrier here doesn&apos;t change which number your
        runs dial from.
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
          spec={editing}
          existing={
            (credentials ?? []).find((c) => c.provider === editing.id) ?? null
          }
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

/**
 * What is still missing before a call is possible.
 *
 * A run needs one credential from each of the three roles. Stating that up
 * front is the difference between a settings page you read and one you act on -
 * without it, "connect some accounts" is a task with no visible finish line.
 */
function ReadinessSummary({
  roles,
  byRole,
  connectedIds,
  loading,
}: {
  roles: typeof ROLES;
  byRole: Map<ProviderRole, ProviderSpec[]>;
  connectedIds: Set<Provider>;
  loading: boolean;
}) {
  if (loading) return <Skeleton className="h-16 w-full" />;

  const status = roles.map((role) => ({
    ...role,
    ready: (byRole.get(role.id) ?? []).some((s) => connectedIds.has(s.id)),
  }));
  const missing = status.filter((s) => !s.ready);

  return (
    <Panel sunken className="flex flex-col gap-2 p-3">
      <p className="text-small font-bold text-text-mute">Before a call can happen</p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
        {status.map((s) => (
          <li key={s.id} className="flex items-center gap-1.5 text-small">
            {/* The tick is paired with a text state, never colour alone. */}
            <span aria-hidden className="font-mono text-text-mute">
              {s.ready ? '✓' : '—'}
            </span>
            <span className={s.ready ? 'text-text' : 'text-text-dim'}>
              {s.title}
            </span>
            <span className="text-text-mute">
              {s.ready ? 'connected' : 'not connected'}
            </span>
          </li>
        ))}
      </ul>
      {missing.length > 0 ? (
        <p className="measure text-small text-text-dim">
          Connect{' '}
          {missing.map((s) => s.title.toLowerCase()).join(' and ')} to finish
          setting this organisation up.
        </p>
      ) : null}
    </Panel>
  );
}

function ProviderRow({
  spec,
  credential,
  canWrite,
  onEdit,
  onChanged,
}: {
  spec: ProviderSpec;
  credential: ProviderCredential | null;
  canWrite: boolean;
  onEdit: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [disconnecting, setDisconnecting] = useState(false);
  const [starting, setStarting] = useState(false);

  async function disconnect() {
    setDisconnecting(true);
    try {
      await api.disconnectProvider(spec.id);
      toast({ tone: 'info', title: `${spec.name} disconnected` });
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

  async function connect() {
    if (spec.connect !== 'oauth') {
      onEdit();
      return;
    }
    setStarting(true);
    try {
      await beginOAuth(spec);
    } catch (error) {
      setStarting(false);
      toast({
        tone: 'error',
        title: `Couldn't open ${spec.name}`,
        body: error instanceof Error ? error.message : undefined,
      });
    }
  }

  return (
    <li className="flex flex-wrap items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <ProviderMark name={spec.name} connected={credential !== null} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-small font-medium text-text">{spec.name}</span>
            {credential ? <Tag>Connected</Tag> : null}
            {/* Named only where it is true. A vendor with no login flow shows
                nothing here rather than an "API key" badge that reads as a
                limitation of this product. */}
            {!credential && spec.connect === 'oauth' ? <Tag>Login</Tag> : null}
          </div>
          <span className="measure text-small text-text-dim">
            {credential?.phone_number ?? credential?.label ?? spec.summary}
          </span>
        </div>
      </div>
      {canWrite ? (
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={credential ? onEdit : connect}
            loading={starting}
          >
            {credential
              ? 'Update'
              : spec.connect === 'oauth'
                ? `Connect with ${spec.name}`
                : 'Add key'}
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
  spec,
  existing,
  onOpenChange,
  onChanged,
}: {
  spec: ProviderSpec;
  existing: ProviderCredential | null;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  const [phoneNumber, setPhoneNumber] = useState(existing?.phone_number ?? '');
  const [saving, setSaving] = useState(false);

  const needsIdentifier = spec.identifier_label !== null;
  const isCarrier = spec.role === 'telephony';
  const valid =
    secret.trim().length > 0 && (!needsIdentifier || identifier.trim().length > 0);

  async function save() {
    if (!valid) return;
    setSaving(true);
    try {
      await api.connectProvider(spec.id, {
        identifier: needsIdentifier ? identifier.trim() : undefined,
        secret: secret.trim(),
        phone_number: isCarrier ? phoneNumber.trim() || undefined : undefined,
      });
      toast({ tone: 'success', title: `${spec.name} connected` });
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
        title={existing ? `Update ${spec.name}` : `Connect ${spec.name}`}
        description={
          existing
            ? 'Replacing these credentials overwrites the ones on file. The previous values are never shown again.'
            : `Find these in your ${spec.name} console. Stored encrypted, never shown again after saving.`
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
          {needsIdentifier ? (
            <Field label={spec.identifier_label ?? ''}>
              <Input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                autoFocus
                autoComplete="off"
              />
            </Field>
          ) : null}
          <Field label={spec.secret_label}>
            <Input
              type="password"
              value={secret}
              onChange={(e) => setSecret(e.target.value)}
              autoFocus={!needsIdentifier}
              autoComplete="off"
            />
          </Field>
          {/* Only carriers have a number. Asking an STT vendor for one is how a
              form teaches people to ignore its labels. */}
          {isCarrier ? (
            <Field label="Phone number" hint="Optional, E.164 format">
              <Input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+15555550100"
              />
            </Field>
          ) : null}
          <p className="text-small text-text-mute">
            Your key is encrypted before it is stored and is never shown again.{' '}
            <a
              href={spec.docs_url}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:text-text"
            >
              Open the {spec.name} console
            </a>
          </p>
        </div>
      </Dialog>
    </DialogRoot>
  );
}
