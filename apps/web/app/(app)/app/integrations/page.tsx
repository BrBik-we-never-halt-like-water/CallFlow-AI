'use client';

import { useCallback, useMemo, useState } from 'react';
import {
  ArrowSquareOutIcon,
  CheckIcon,
  MagnifyingGlassIcon,
} from '@phosphor-icons/react/dist/ssr';
import { BrandMark } from '@/components/app/brand-mark';
import { CarrierNumbers } from '@/components/app/carrier-numbers';
import { VoiceField } from '@/components/brand/voice-field';
import { NotWiredNotice } from '@/components/app/settings-section';
import { SessionGate } from '@/components/app/session-gate';
import { Tag } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/cn';
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
import { PageHeader } from '@/components/app/page-header';

/**
 * One filterable grid, not seven stacked walls of cards.
 *
 * The previous version rendered a titled section per role, each with its own
 * paragraph and its own card grid. With 57 providers that is a page you scroll
 * rather than a page you use: the thing an operator wants - "find Deepgram", or
 * "what do I still need" - was several screens apart from wherever they landed.
 *
 * So the roles become a filter rather than a layout, the readiness line moves to
 * the top as the page's actual thesis, and everything else is one dense grid
 * that search narrows. Nothing was removed; it stopped being stacked.
 */

type Filter = ProviderRole | 'all';

const FILTERS: { id: Filter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'telephony', label: 'Phone' },
  { id: 'transcriber', label: 'STT' },
  { id: 'voice', label: 'TTS' },
  { id: 'intelligence', label: 'Intelligence' },
  { id: 'storage', label: 'Storage' },
  { id: 'automation', label: 'Automation' },
  { id: 'observability', label: 'Tracing' },
];

/** The four a call actually reads. The rest are stored-only, and counting them
 *  towards readiness would invent work nobody has to do. */
const NEEDED: { id: ProviderRole; label: string }[] = [
  { id: 'telephony', label: 'Phone' },
  { id: 'transcriber', label: 'STT' },
  { id: 'voice', label: 'TTS' },
  { id: 'intelligence', label: 'Intelligence' },
];

export default function IntegrationsPage() {
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
  const [filter, setFilter] = useState<Filter>('all');

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
   * Finish an OAuth connection started before leaving the page. The vendor's
   * `?code=` is single-use, so it is cleared from the store and the address bar
   * before exchanging - otherwise a refresh replays a spent code and shows an
   * error for something that actually worked.
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

  /** Carriers only: the numbers section can sync from a phone provider, and
   *  asking a speech or model vendor for numbers is meaningless. */
  const connectedCarriers = useMemo(
    () =>
      (catalogue ?? [])
        .filter((s) => s.roles.includes('telephony') && connectedIds.has(s.id))
        .map((s) => s.id),
    [catalogue, connectedIds],
  );

  const counts = useMemo(() => {
    const map = new Map<Filter, number>([['all', (catalogue ?? []).length]]);
    for (const spec of catalogue ?? []) {
      for (const role of spec.roles) map.set(role, (map.get(role) ?? 0) + 1);
    }
    return map;
  }, [catalogue]);

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return (catalogue ?? []).filter((spec) => {
      if (filter !== 'all' && !spec.roles.includes(filter)) return false;
      if (!needle) return true;
      return (
        spec.name.toLowerCase().includes(needle) ||
        spec.summary.toLowerCase().includes(needle)
      );
    });
  }, [catalogue, filter, query]);

  if (!canRead) {
    return (
      <NotWiredNotice>
        Integrations are visible to owners and admins. Ask one in your
        organisation if you need to connect an account.
      </NotWiredNotice>
    );
  }

  const loading = catalogue === null || credentials === null;

  return (
    // `isolate` for the same reason the Agents page needs it: the field below
    // sits at `-z-10`, and without a stacking context here that escapes to the
    // page root and lands behind `.app-canvas`'s own background, which paints
    // over it. The field renders and is simply never visible.
    <div className="relative isolate flex flex-col gap-6">
      {/* The same atmosphere the Agents page opens with, at the same weight -
          `opacity-40` plus a radial mask so it fades out well before it reaches
          the cards, where it would compete with every provider mark on the
          page. Dimmed with `opacity` rather than `--field-gain`: that variable
          is read off `document.documentElement`, so setting it on this wrapper
          would do nothing and only look like it should. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -top-8 -z-10 h-96 opacity-40 [mask-image:radial-gradient(ellipse_80%_70%_at_50%_30%,#000_20%,transparent_78%)] [-webkit-mask-image:radial-gradient(ellipse_80%_70%_at_50%_30%,#000_20%,transparent_78%)]"
      >
        <VoiceField />
      </div>

      <Readiness
        catalogue={catalogue}
        connectedIds={connectedIds}
        loading={loading}
      />

      {/* Directly under the readiness line, because that line's "ready to place
          a call" is about credentials and a credential is not a diallable line.
          A connected carrier whose numbers are all still `discovered` cannot
          carry a run, and this is the only screen that can say so. */}
      <CarrierNumbers providers={connectedCarriers} canWrite={canWrite} />

      <div className="flex flex-col gap-3">
        <label className="relative block">
          <span className="sr-only">Search integrations</span>
          <MagnifyingGlassIcon
            aria-hidden
            weight="bold"
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-mute"
          />
          <Input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name"
            className="pl-9"
          />
        </label>

        <nav aria-label="Filter by what the credential is for">
          <ul className="flex flex-wrap gap-1.5">
            {FILTERS.map((f) => {
              const count = counts.get(f.id) ?? 0;
              if (f.id !== 'all' && count === 0 && !loading) return null;
              const active = filter === f.id;
              return (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={() => setFilter(f.id)}
                    aria-pressed={active}
                    className={cn(
                      'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-small transition-colors duration-[--dur-micro]',
                      active
                        ? 'border-rule-strong bg-surface-inverse text-text-inverse'
                        : 'border-rule bg-surface text-text-dim hover:bg-surface-hover hover:text-text',
                    )}
                  >
                    {f.label}
                    <span className="font-mono tabular-nums opacity-60">{count}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>

      {loading ? (
        <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 9 }, (_, i) => (
            <li key={i}>
              <Skeleton className="h-[104px] w-full rounded-md" />
            </li>
          ))}
        </ul>
      ) : shown.length === 0 ? (
        <EmptyResult query={query} onClear={() => { setQuery(''); setFilter('all'); }} />
      ) : (
        /* Connected first, then the rest - the same split the Agents page makes
           between what is yours and what is the team's, and for the same
           reason: the accounts you have already wired up are the ones you come
           back to change, and hunting them out of a grid of fifty-seven by
           reading each card's state is work the page can do for you.

           This is not a return to the seven role sections this page removed.
           Those were a *taxonomy* imposed on a search problem, which is why the
           roles became a filter instead. Two groups answer a question someone
           actually arrives with - "what do I have" versus "what could I add" -
           and collapse to a single grid the moment one side is empty, so a
           fresh organisation sees no headings at all. */
        (() => {
          const isConnected = (spec: ProviderSpec) => connectedIds.has(spec.id);
          const connected = shown.filter(isConnected);
          const available = shown.filter((s) => !isConnected(s));

          const grid = (list: ProviderSpec[]) => (
            <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {list.map((spec) => (
                <ProviderCard
                  key={spec.id}
                  spec={spec}
                  credential={(credentials ?? []).find((c) => c.provider === spec.id) ?? null}
                  canWrite={canWrite}
                  onEdit={() => setEditing(spec)}
                  onChanged={load}
                />
              ))}
            </ul>
          );

          if (connected.length === 0 || available.length === 0) {
            return grid(shown);
          }

          return (
            <div className="flex flex-col gap-8">
              <section className="flex flex-col gap-3">
                <GroupHeading count={connected.length}>Connected</GroupHeading>
                {grid(connected)}
              </section>
              <section className="flex flex-col gap-3">
                <GroupHeading count={available.length}>Available</GroupHeading>
                {grid(available)}
              </section>
            </div>
          );
        })()
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

/**
 * What is still missing before a call is possible - the page's thesis, so it
 * leads rather than sitting in a panel below the fold.
 */
function Readiness({
  catalogue,
  connectedIds,
  loading,
}: {
  catalogue: ProviderSpec[] | null;
  connectedIds: Set<Provider>;
  loading: boolean;
}) {
  const status = NEEDED.map((role) => ({
    ...role,
    ready: (catalogue ?? []).some(
      (s) => s.roles.includes(role.id) && connectedIds.has(s.id),
    ),
  }));
  const done = status.filter((s) => s.ready).length;

  return (
    <header className="flex flex-col gap-3">
      <PageHeader title="Integrations">
        {loading ? null : (
          <p className="text-small text-text-dim">
            <span className="dash-num font-semibold" style={{ color: 'var(--dash-figure)' }}>{done}</span>
            <span className="text-text-mute">/{NEEDED.length}</span> ready to
            place a call
          </p>
        )}
      </PageHeader>
      {loading ? (
        <Skeleton className="h-9 w-full max-w-xl rounded-full" />
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {status.map((s) => (
            <li
              key={s.id}
              className={cn(
                'flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-small',
                s.ready
                  ? 'border-rule-strong bg-surface-raised text-text'
                  : 'border-rule border-dashed bg-transparent text-text-mute',
              )}
            >
              {/* Paired with a word, never colour alone. */}
              {s.ready ? (
                <CheckIcon aria-hidden weight="bold" className="size-3.5" />
              ) : (
                <span aria-hidden className="font-mono leading-none">+</span>
              )}
              {s.label}
              <span className="sr-only">
                {s.ready ? 'connected' : 'not connected'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </header>
  );
}

/** Words, a count and a hairline - the same quiet group label the Agents page
 *  uses. A filled header band here would be a third piece of chrome competing
 *  with the readiness line above and the filter pills between them. */
function GroupHeading({
  children,
  count,
}: {
  children: React.ReactNode;
  count: number;
}) {
  return (
    <div className="flex items-center gap-3">
      <h2 className="text-small font-medium text-text">{children}</h2>
      <span className="text-small tabular-nums text-text-mute">{count}</span>
      <span aria-hidden className="h-px flex-1 bg-rule" />
    </div>
  );
}

function EmptyResult({ query, onClear }: { query: string; onClear: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-rule py-16 text-center">
      <p className="text-body font-medium text-text">
        {query ? `Nothing matches “${query}”` : 'Nothing here yet'}
      </p>
      <p className="measure text-small text-text-dim">
        Tell us which vendor you need and we&apos;ll look at adding it.
      </p>
      <Button variant="secondary" size="sm" onClick={onClear}>
        Clear filters
      </Button>
    </div>
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
  const [busy, setBusy] = useState<'connect' | 'disconnect' | null>(null);

  async function disconnect() {
    setBusy('disconnect');
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
      setBusy(null);
    }
  }

  async function connect() {
    if (spec.connect !== 'oauth') {
      onEdit();
      return;
    }
    setBusy('connect');
    try {
      await beginOAuth(spec);
    } catch (error) {
      setBusy(null);
      toast({
        tone: 'error',
        title: `Couldn't open ${spec.name}`,
        body: error instanceof Error ? error.message : undefined,
      });
    }
  }

  return (
    <li
      className={cn(
        'group relative flex h-full flex-col gap-3 rounded-md border p-3',
        'transition-[background-color,border-color,transform] duration-[--dur-micro]',
        credential
          ? 'border-rule-strong bg-surface-raised'
          : 'border-rule bg-surface hover:-translate-y-px hover:border-rule-strong hover:bg-surface-hover',
      )}
    >
      <div className="flex items-start gap-3">
        <BrandMark providerId={spec.id} name={spec.name} connected={!!credential} />
        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <h2 className="truncate text-small font-medium text-text">{spec.name}</h2>
            {!credential && spec.connect === 'oauth' ? <Tag>Login</Tag> : null}
          </div>
          <p className="truncate text-small text-text-dim">{spec.summary}</p>
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between gap-2">
        {credential ? (
          <span className="flex min-w-0 flex-col">
            <span className="text-small text-text">
              {spec.wired ? 'Connected' : 'Key saved'}
            </span>
            {/* Two separate facts, said separately: the key is stored, and
                nothing reads it (CLAUDE.md non-negotiable #9). */}
            {!spec.wired ? (
              <span className="text-small text-text-mute">Not in use yet</span>
            ) : credential.phone_number ? (
              <span className="truncate font-mono text-small text-text-mute">
                {credential.phone_number}
              </span>
            ) : null}
          </span>
        ) : (
          <a
            href={spec.docs_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-small text-text-mute underline-offset-2 hover:text-text hover:underline"
          >
            Console
            <ArrowSquareOutIcon aria-hidden weight="bold" className="size-3" />
          </a>
        )}

        {canWrite ? (
          <span className="flex shrink-0 items-center gap-1">
            <Button
              variant={credential ? 'ghost' : 'secondary'}
              size="sm"
              onClick={credential ? onEdit : connect}
              loading={busy === 'connect'}
            >
              {credential ? 'Update' : 'Connect'}
            </Button>
            {credential ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={disconnect}
                loading={busy === 'disconnect'}
              >
                Remove
              </Button>
            ) : null}
          </span>
        ) : null}
      </div>
    </li>
  );
}

/**
 * One form for every vendor - the fields come from the server, so a provider
 * added in `domain/providers.py` renders here with no frontend change.
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
      const saved = await api.connectProvider(spec.id, {
        fields: Object.fromEntries(
          spec.fields
            .map((f) => [f.key, (values[f.key] ?? '').trim()] as const)
            .filter(([, value]) => value.length > 0),
        ),
        phone_number: isCarrier ? phoneNumber.trim() || undefined : undefined,
      });
      // `verified: null` means the check could not be completed - no probe for
      // this vendor, the vendor was unreachable, or the key is scoped too
      // narrowly to confirm. The credential is stored either way, and saying
      // "connected" for an unverified one is the success state this whole
      // verification path exists to remove (`ISSUES.md` #169).
      if (saved.verified === false) {
        toast({
          tone: 'error',
          title: `${spec.name} didn't accept that`,
          body: saved.verification_note ?? undefined,
        });
      } else if (saved.verified === null) {
        toast({
          tone: 'info',
          title: `${spec.name} saved, not confirmed`,
          body: saved.verification_note ?? undefined,
        });
      } else {
        toast({ tone: 'success', title: `${spec.name} connected` });
      }
      onChanged();
    } catch (error) {
      // The API verifies against the vendor before storing, so this is most
      // often the vendor's own refusal rather than a failure to save. Its
      // message says which, and names where to get a working key - so it is
      // the body, and the dialog stays open with the fields still filled in
      // rather than closing on a credential that was never stored.
      toast({
        tone: 'error',
        title: `${spec.name} didn't accept that`,
        body:
          error instanceof Error
            ? error.message
            : 'The credentials were not saved.',
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <DialogRoot open onOpenChange={onOpenChange}>
      <Dialog
        title={`${existing ? 'Update' : 'Connect'} ${spec.name}`}
        description={
          existing
            ? 'These replace what is on file. The old values are never shown again.'
            : 'Encrypted before it is stored, and never shown again after saving.'
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
              hint={field.help ?? (field.required ? undefined : 'Optional')}
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
                  className="w-full rounded-sm border border-rule bg-surface px-3 py-2 font-mono text-small text-text transition-colors duration-[--dur-micro] placeholder:text-text-mute hover:border-rule-strong"
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
            <Field label="Phone number" hint="Optional, E.164">
              <Input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+15555550100"
              />
            </Field>
          ) : null}

          {!spec.wired ? (
            <p className="measure text-small text-text-dim">
              Nothing reads this key yet. Saving it means the account is ready
              when the feature ships.
            </p>
          ) : null}

          {spec.note ? (
            <p className="measure text-small text-text-mute">{spec.note}</p>
          ) : null}

          <a
            href={spec.docs_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-small text-text-mute underline-offset-2 hover:text-text hover:underline"
          >
            Open the {spec.name} console
            <ArrowSquareOutIcon aria-hidden weight="bold" className="size-3" />
          </a>
        </div>
      </Dialog>
    </DialogRoot>
  );
}
