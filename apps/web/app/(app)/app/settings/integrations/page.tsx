'use client';

import { useCallback, useMemo, useState } from 'react';
import {
  ArrowSquareOut,
  Broadcast,
  Brain,
  Check,
  CloudArrowUp,
  Empty,
  Lightning,
  MagnifyingGlass,
  PhoneCall,
  PlugsConnected,
  SpeakerHigh,
  Waveform,
} from '@phosphor-icons/react';
import { NotWiredNotice, SettingsSection } from '@/components/app/settings-section';
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
 * A flat list of 50-odd vendors answers "which brands do you support"; an
 * operator is asking "what do I still need before a call can happen". The first
 * four groups mirror `voice_agents`' own columns, so the page and the schema
 * describe the same shape - which is what makes the readiness line meaningful.
 *
 * `needed` marks the groups a live call actually reads. The last three are
 * stored-only, and saying so is the whole reason they are a separate band
 * rather than mixed in above.
 */
const GROUPS: {
  id: ProviderRole;
  title: string;
  description: string;
  icon: typeof PhoneCall;
  needed: boolean;
}[] = [
  {
    id: 'telephony',
    title: 'Phone numbers',
    description: 'The carrier calls are placed through. Your number, your account, your rates.',
    icon: PhoneCall,
    needed: true,
  },
  {
    id: 'transcriber',
    title: 'Speech in',
    description: 'Turns what the contact says into text. Pick per agent, so a Hindi and an English agent can differ.',
    icon: Waveform,
    needed: true,
  },
  {
    id: 'voice',
    title: 'Speech out',
    description: 'The voice the agent speaks with.',
    icon: SpeakerHigh,
    needed: true,
  },
  {
    id: 'intelligence',
    title: 'Intelligence',
    description: 'The model the agent thinks with while the call is happening.',
    icon: Brain,
    needed: true,
  },
  {
    id: 'storage',
    title: 'Storage',
    description: 'Where call recordings would be kept, once recording exists.',
    icon: CloudArrowUp,
    needed: false,
  },
  {
    id: 'automation',
    title: 'Automation and CRM',
    description: 'Where a finished call would be sent, once outbound tools exist.',
    icon: Lightning,
    needed: false,
  },
  {
    id: 'observability',
    title: 'Observability',
    description: 'Where model traces would be sent, once tracing exists.',
    icon: Broadcast,
    needed: false,
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
        'flex size-8 shrink-0 items-center justify-center rounded-sm border font-mono text-small font-medium ' +
        (connected
          ? 'border-rule-strong bg-surface-raised text-text'
          : 'border-rule bg-surface-sunken text-text-mute')
      }
    >
      {name.charAt(0)}
    </span>
  );
}

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
  const [query, setQuery] = useState('');

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

  const connectedIds = useMemo(
    () => new Set((credentials ?? []).map((c) => c.provider)),
    [credentials],
  );

  /**
   * Filtered once, then bucketed - so a vendor serving two roles (Deepgram does
   * speech in *and* out) appears under both, which is the truth about the one
   * credential it stores.
   */
  const byRole = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const map = new Map<ProviderRole, ProviderSpec[]>();
    for (const spec of catalogue ?? []) {
      const matches =
        !needle ||
        spec.name.toLowerCase().includes(needle) ||
        spec.summary.toLowerCase().includes(needle);
      if (!matches) continue;
      for (const role of spec.roles) {
        map.set(role, [...(map.get(role) ?? []), spec]);
      }
    }
    return map;
  }, [catalogue, query]);

  if (!canRead) {
    return (
      <NotWiredNotice>
        Integrations are visible to owners and admins only. Ask one in your
        organisation if you need to connect an account.
      </NotWiredNotice>
    );
  }

  const loading = catalogue === null || credentials === null;
  const matched = new Set(
    [...byRole.values()].flat().map((s) => s.id),
  ).size;

  return (
    <div className="flex flex-col gap-4">
      <ReadinessSummary
        byRole={byRole}
        connectedIds={connectedIds}
        loading={loading}
      />

      <label className="relative block">
        <span className="sr-only">Search integrations</span>
        <MagnifyingGlass
          aria-hidden
          weight="bold"
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-mute"
        />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search 50+ integrations"
          className="pl-9"
          type="search"
        />
      </label>

      {loading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : matched === 0 ? (
        <Panel sunken className="flex flex-col items-center gap-2 p-8 text-center">
          <Empty aria-hidden weight="light" className="size-6 text-text-mute" />
          <p className="text-small font-medium text-text">
            Nothing matches &ldquo;{query}&rdquo;
          </p>
          <p className="measure text-small text-text-dim">
            Try the vendor&apos;s name. If you need one CallFlow doesn&apos;t
            support yet, tell us which and we&apos;ll look at adding it.
          </p>
          <Button variant="secondary" size="sm" onClick={() => setQuery('')}>
            Clear search
          </Button>
        </Panel>
      ) : (
        GROUPS.map((group) => {
          const specs = byRole.get(group.id) ?? [];
          if (specs.length === 0) return null;
          return (
            <ProviderGroup
              key={group.id}
              group={group}
              specs={specs}
              credentials={credentials ?? []}
              canWrite={canWrite}
              onEdit={setEditing}
              onChanged={load}
            />
          );
        })
      )}

      {editing ? (
        <ConnectDialog
          spec={editing}
          existing={(credentials ?? []).find((c) => c.provider === editing.id) ?? null}
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

function ProviderGroup({
  group,
  specs,
  credentials,
  canWrite,
  onEdit,
  onChanged,
}: {
  group: (typeof GROUPS)[number];
  specs: ProviderSpec[];
  credentials: ProviderCredential[];
  canWrite: boolean;
  onEdit: (spec: ProviderSpec) => void;
  onChanged: () => void;
}) {
  const Icon = group.icon;
  const connected = specs.filter((s) =>
    credentials.some((c) => c.provider === s.id),
  ).length;

  return (
    <SettingsSection
      title={
        <span className="flex items-center gap-2">
          <Icon aria-hidden weight="regular" className="size-4 text-text-mute" />
          {group.title}
          <span className="font-mono text-small font-normal text-text-mute">
            {connected}/{specs.length}
          </span>
        </span>
      }
      description={group.description}
    >
      {!group.needed ? (
        <p className="measure mb-3 text-small text-text-dim">
          Credentials here are encrypted and saved, and nothing reads them yet -
          the feature each one would drive is still being built. They are listed
          so an account can be connected ahead of it, not because connecting one
          changes what a call does today.
        </p>
      ) : null}
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {specs.map((spec) => (
          <ProviderCard
            key={spec.id}
            spec={spec}
            credential={credentials.find((c) => c.provider === spec.id) ?? null}
            canWrite={canWrite}
            onEdit={() => onEdit(spec)}
            onChanged={onChanged}
          />
        ))}
      </ul>
    </SettingsSection>
  );
}

function ProviderCard({
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
    <li
      className={
        'flex flex-col gap-3 rounded-md border p-3 transition-colors duration-[--dur-micro] ' +
        (credential
          ? 'border-rule-strong bg-surface-raised'
          : 'border-rule bg-surface hover:bg-surface-hover')
      }
    >
      <div className="flex items-start gap-3">
        <ProviderMark name={spec.name} connected={credential !== null} />
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-small font-medium text-text">{spec.name}</span>
            {/* Named only where it is true. A vendor with no login flow shows
                nothing here rather than an "API key" badge that reads as a
                limitation of this product. */}
            {!credential && spec.connect === 'oauth' ? <Tag>Login</Tag> : null}
          </div>
          <p className="text-small text-text-dim">{spec.summary}</p>
        </div>
      </div>

      {credential ? <ConnectedState spec={spec} credential={credential} /> : null}

      {spec.note ? (
        <p className="text-small text-text-mute">{spec.note}</p>
      ) : null}

      {canWrite ? (
        <div className="mt-auto flex items-center gap-2 pt-1">
          <Button
            variant={credential ? 'ghost' : 'secondary'}
            size="sm"
            onClick={credential ? onEdit : connect}
            loading={starting}
          >
            {credential ? 'Update' : spec.connect === 'oauth' ? 'Connect' : 'Add key'}
          </Button>
          {credential ? (
            <Button variant="ghost" size="sm" onClick={disconnect} loading={disconnecting}>
              Disconnect
            </Button>
          ) : (
            <a
              href={spec.docs_url}
              target="_blank"
              rel="noreferrer"
              className="ml-auto inline-flex items-center gap-1 text-small text-text-mute underline-offset-2 hover:text-text hover:underline"
            >
              Console
              <ArrowSquareOut aria-hidden weight="bold" className="size-3" />
            </a>
          )}
        </div>
      ) : null}
    </li>
  );
}

/**
 * What a stored credential actually means for this vendor.
 *
 * The distinction is the point. "Connected" on a carrier or a speech vendor is
 * true - a call reads it. On a storage or automation vendor it would be a
 * success state for something that has not happened (CLAUDE.md non-negotiable
 * #9), so the key being saved and the integration doing nothing are stated as
 * the two separate facts they are.
 */
function ConnectedState({
  spec,
  credential,
}: {
  spec: ProviderSpec;
  credential: ProviderCredential;
}) {
  const detail = credential.phone_number ?? credential.label;
  return (
    <div className="flex flex-col gap-1">
      <span className="flex items-center gap-1.5 text-small text-text">
        {/* The tick is paired with a text state, never colour alone. */}
        <Check aria-hidden weight="bold" className="size-3.5 text-text-mute" />
        {spec.wired ? 'Connected' : 'Key saved'}
        {detail ? <span className="text-text-mute">· {detail}</span> : null}
      </span>
      {!spec.wired ? (
        <span className="text-small text-text-mute">Not in use yet</span>
      ) : null}
    </div>
  );
}

/**
 * What is still missing before a call is possible.
 *
 * A run needs one credential from each of the four call roles. Stating that up
 * front is the difference between a settings page you read and one you act on -
 * without it, "connect some accounts" is a task with no visible finish line.
 * Storage and automation are deliberately excluded: nothing about them blocks a
 * call, and counting them would invent work.
 */
function ReadinessSummary({
  byRole,
  connectedIds,
  loading,
}: {
  byRole: Map<ProviderRole, ProviderSpec[]>;
  connectedIds: Set<Provider>;
  loading: boolean;
}) {
  if (loading) return <Skeleton className="h-16 w-full" />;

  const status = GROUPS.filter((g) => g.needed).map((group) => ({
    ...group,
    ready: (byRole.get(group.id) ?? []).some((s) => connectedIds.has(s.id)),
  }));
  const missing = status.filter((s) => !s.ready);

  return (
    <Panel sunken className="flex flex-col gap-2 p-3">
      <p className="flex items-center gap-2 text-small font-bold text-text-mute">
        <PlugsConnected aria-hidden weight="regular" className="size-4" />
        Before a call can happen
      </p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
        {status.map((s) => (
          <li key={s.id} className="flex items-center gap-1.5 text-small">
            <span aria-hidden className="font-mono text-text-mute">
              {s.ready ? '✓' : '—'}
            </span>
            <span className={s.ready ? 'text-text' : 'text-text-dim'}>{s.title}</span>
            <span className="text-text-mute">
              {s.ready ? 'connected' : 'not connected'}
            </span>
          </li>
        ))}
      </ul>
      {missing.length > 0 ? (
        <p className="measure text-small text-text-dim">
          Connect{' '}
          {missing.map((s) => s.title.toLowerCase()).join(', ').replace(/, ([^,]*)$/, ' and $1')}{' '}
          to finish setting this organisation up.
        </p>
      ) : null}
    </Panel>
  );
}

/**
 * One form, every vendor.
 *
 * The fields come from the server, so a provider added in `domain/providers.py`
 * renders here with no frontend change - which is the only way a 50-vendor
 * catalogue stays in step with what the API will actually store.
 */
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
  const [values, setValues] = useState<Record<string, string>>({});
  const [phoneNumber, setPhoneNumber] = useState(existing?.phone_number ?? '');
  const [saving, setSaving] = useState(false);

  const isCarrier = spec.roles.includes('telephony');
  const valid = spec.fields
    .filter((f) => f.required)
    .every((f) => (values[f.key] ?? '').trim().length > 0);

  async function save() {
    if (!valid) return;
    setSaving(true);
    try {
      await api.connectProvider(spec.id, {
        fields: Object.fromEntries(
          spec.fields
            .map((f) => [f.key, (values[f.key] ?? '').trim()] as const)
            .filter(([, value]) => value.length > 0),
        ),
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
          {spec.fields.map((field, index) => (
            <Field
              key={field.key}
              label={field.label}
              hint={
                field.help ?? (field.required ? undefined : 'Optional')
              }
            >
              {field.multiline ? (
                <textarea
                  value={values[field.key] ?? ''}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.key]: e.target.value }))
                  }
                  autoFocus={index === 0}
                  rows={4}
                  spellCheck={false}
                  placeholder={field.placeholder || undefined}
                  className="w-full rounded-sm border border-rule bg-surface px-3 py-2 font-mono text-small text-text placeholder:text-text-mute focus:border-rule-strong focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              ) : (
                <Input
                  type={field.secret ? 'password' : 'text'}
                  value={values[field.key] ?? ''}
                  onChange={(e) =>
                    setValues((v) => ({ ...v, [field.key]: e.target.value }))
                  }
                  autoFocus={index === 0}
                  autoComplete="off"
                  placeholder={field.placeholder || undefined}
                />
              )}
            </Field>
          ))}

          {/* Only carriers have a number. Asking a speech vendor for one is how
              a form teaches people to ignore its labels. */}
          {isCarrier ? (
            <Field label="Phone number" hint="Optional, E.164 format">
              <Input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+15555550100"
              />
            </Field>
          ) : null}

          {!spec.wired ? (
            <p className="measure text-small text-text-dim">
              This key is encrypted and saved, and nothing reads it yet. Saving
              it now means the account is ready when the feature ships; it
              doesn&apos;t change what a call does today.
            </p>
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
