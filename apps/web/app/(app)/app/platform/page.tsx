'use client';

import { useEffect, useState } from 'react';
import { SessionGate } from '@/components/app/session-gate';
import { NotWiredNotice, SettingsSection } from '@/components/app/settings-section';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/toast';
import {
  api,
  type EntitlementOverride,
  type PlatformAuditEntry,
  type PlatformOrg,
} from '@/lib/api';
import { useSession, type SessionProfile } from '@/lib/hooks/use-session';

/**
 * Cross-tenant support. `docs/PLATFORM_ADMIN.md`.
 *
 * `is_platform_admin` gates this page, but it is only the affordance: every route
 * behind it 404s for anyone without a `platform_admins` row, and the definer
 * functions check the capability a third time in the database. Somebody who guesses
 * this URL sees an empty page and a 404, not a permission error - which is the point
 * of answering 404 rather than 403.
 *
 * Deliberately plain. This is a staff tool that touches other people's commercial
 * terms, and the thing that matters is that every field is legible and every save
 * states its reason - not that it looks like the product.
 */
export default function PlatformPage() {
  const session = useSession();
  return (
    <SessionGate session={session}>
      {(profile) => <PlatformContent profile={profile} />}
    </SessionGate>
  );
}

function PlatformContent({ profile }: { profile: SessionProfile }) {
  if (!profile.is_platform_admin) {
    return (
      <div className="flex flex-col gap-6">
        <h1 className="font-display text-h2 text-text">Platform</h1>
        <NotWiredNotice>
          This area is for CallFlow staff handling support across organisations.
          Your account doesn&apos;t have it.
        </NotWiredNotice>
      </div>
    );
  }
  return <PlatformConsole />;
}

const PLANS = [
  { value: 'free', label: 'Free' },
  { value: 'starter', label: 'Starter' },
  { value: 'growth', label: 'Growth' },
  { value: 'enterprise', label: 'Enterprise' },
];

function PlatformConsole() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const [orgs, setOrgs] = useState<PlatformOrg[] | null>(null);
  const [audit, setAudit] = useState<PlatformAuditEntry[] | null>(null);
  const [editing, setEditing] = useState<PlatformOrg | null>(null);
  const [nonce, setNonce] = useState(0);

  // Promise chain rather than an async callback awaited in the effect body:
  // `react-hooks/set-state-in-effect` is an error in this repo, and the `cancelled`
  // flag is what keeps a slow response from a previous search term overwriting a
  // newer one (the same shape the billing page uses).
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.platformOrgs(search || undefined), api.platformAudit(50)])
      .then(([nextOrgs, nextAudit]) => {
        if (cancelled) return;
        setOrgs(nextOrgs);
        setAudit(nextAudit);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        toast({
          tone: 'error',
          title: "Couldn't load the platform view",
          body: error instanceof Error ? error.message : undefined,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [search, nonce, toast]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <p className="text-small font-bold text-text-mute">Platform</p>
        <h1 className="font-display text-h2 text-text">Every organisation</h1>
        <p className="measure text-small text-text-dim">
          Plans and agreed limits across all tenants. Every change is recorded with
          the reason you give for it.
        </p>
      </div>

      <SettingsSection
        title="Organisations"
        description="Plan, agreed limits, and how much of the product each one is using."
      >
        <div className="flex flex-col gap-3">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter by name or slug"
          />

          {orgs === null ? (
            <Skeleton className="h-32 w-full" />
          ) : orgs.length === 0 ? (
            <p className="text-small text-text-dim">No organisations match.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-max text-small">
                <thead>
                  <tr className="border-b border-rule text-text-mute">
                    <th className="py-2 pr-4 text-left font-medium">Organisation</th>
                    <th className="py-2 pr-4 text-left font-medium">Plan</th>
                    <th className="py-2 pr-4 text-right font-medium">Members</th>
                    <th className="py-2 pr-4 text-right font-medium">Agents</th>
                    <th className="py-2 pr-4 text-right font-medium">Runs</th>
                    <th className="py-2 text-right font-medium">Limits</th>
                  </tr>
                </thead>
                <tbody>
                  {orgs.map((org) => (
                    <tr key={org.org_id} className="border-b border-rule">
                      <td className="py-2 pr-4">
                        <span className="text-text">{org.name}</span>{' '}
                        <span className="font-mono text-text-mute">{org.slug}</span>
                      </td>
                      <td className="py-2 pr-4 text-text-dim">{org.plan_id}</td>
                      <td className="py-2 pr-4 text-right font-mono tabular-nums text-text-dim">
                        {org.member_count}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono tabular-nums text-text-dim">
                        {org.agent_count}
                      </td>
                      <td className="py-2 pr-4 text-right font-mono tabular-nums text-text-dim">
                        {org.run_count}
                      </td>
                      <td className="py-2 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setEditing(org)}
                        >
                          {org.has_override ? 'Agreed' : 'Set'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </SettingsSection>

      <SettingsSection
        title="Audit"
        description="Every platform action, newest first. Written in the same transaction as the change it records."
      >
        {audit === null ? (
          <Skeleton className="h-24 w-full" />
        ) : audit.length === 0 ? (
          <p className="text-small text-text-dim">Nothing recorded yet.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {audit.map((entry) => (
              <li key={entry.id} className="flex flex-wrap gap-2 text-small">
                <span className="font-mono text-text-mute">
                  {new Date(entry.created_at).toLocaleString()}
                </span>
                <span className="font-medium text-text">{entry.action}</span>
                <span className="text-text-dim">{entry.reason}</span>
              </li>
            ))}
          </ul>
        )}
      </SettingsSection>

      {editing ? (
        <OverrideDialog
          org={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            setNonce((n) => n + 1);
          }}
        />
      ) : null}
    </div>
  );
}

/** The limits an override may set, in the order they read on Billing. */
const LIMITS = [
  { key: 'max_voice_agents', label: 'Voice agents' },
  { key: 'max_seats', label: 'Seats' },
  { key: 'max_organisations', label: 'Organisations' },
  { key: 'max_ai_integrations', label: 'Model providers' },
  { key: 'daily_call_budget', label: 'Calls per day' },
] as const;

type LimitKey = (typeof LIMITS)[number]['key'];

/**
 * Plan and agreed limits for one organisation.
 *
 * Three states per limit, and keeping them distinct is the whole design: **blank**
 * inherits the plan, a **number** is a ceiling (including `0`, which means none
 * allowed), and **Unlimited** removes the ceiling. Collapsing blank and Unlimited
 * would silently give an enterprise customer their plan's cap instead of the none
 * they were sold.
 */
function OverrideDialog({
  org,
  onClose,
  onSaved,
}: {
  org: PlatformOrg;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [existing, setExisting] = useState<EntitlementOverride | null | undefined>(
    undefined,
  );
  const [values, setValues] = useState<Record<LimitKey, string>>({
    max_voice_agents: '',
    max_seats: '',
    max_organisations: '',
    max_ai_integrations: '',
    daily_call_budget: '',
  });
  const [unlimited, setUnlimited] = useState<Set<LimitKey>>(new Set());
  const [plan, setPlan] = useState(org.plan_id);
  const [note, setNote] = useState('');
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .platformOverride(org.org_id)
      .then((row) => {
        if (cancelled) return;
        setExisting(row);
        if (!row) return;
        setValues({
          max_voice_agents: row.max_voice_agents?.toString() ?? '',
          max_seats: row.max_seats?.toString() ?? '',
          max_organisations: row.max_organisations?.toString() ?? '',
          max_ai_integrations: row.max_ai_integrations?.toString() ?? '',
          daily_call_budget: row.daily_call_budget?.toString() ?? '',
        });
        setUnlimited(new Set(row.unlimited as LimitKey[]));
        setNote(row.note ?? '');
      })
      .catch(() => {
        if (!cancelled) setExisting(null);
      });
    return () => {
      cancelled = true;
    };
  }, [org.org_id]);

  async function save() {
    setSaving(true);
    try {
      // The plan is a separate call because it is a separate decision with its own
      // audit row: "moved to Enterprise" and "agreed 40 agents" are different facts
      // and folding them into one entry loses which one someone actually made.
      if (plan !== org.plan_id) {
        await api.platformSetPlan(org.org_id, plan, reason);
      }
      await api.platformSetOverride(org.org_id, {
        max_voice_agents: numberOrNull(values.max_voice_agents),
        max_seats: numberOrNull(values.max_seats),
        max_organisations: numberOrNull(values.max_organisations),
        max_ai_integrations: numberOrNull(values.max_ai_integrations),
        daily_call_budget: numberOrNull(values.daily_call_budget),
        unlimited: [...unlimited],
        note: note.trim() || null,
        reason,
      });
      toast({ tone: 'success', title: `Updated ${org.name}` });
      onSaved();
    } catch (error) {
      toast({
        tone: 'error',
        title: 'Could not save',
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <DialogRoot open onOpenChange={(next) => (next ? null : onClose())}>
      <Dialog
        title={`${org.name} - plan and agreed limits`}
        footer={
          <>
            <Button variant="secondary" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button
              onClick={save}
              loading={saving}
              // The reason is required by the database too. Disabling here spares
              // someone filling in a form that the server will refuse anyway.
              disabled={reason.trim().length < 4}
            >
              Save
            </Button>
          </>
        }
      >
        {existing === undefined ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <div className="flex flex-col gap-4">
            <Field label="Plan">
              <Select value={plan} onValueChange={setPlan} options={PLANS} />
            </Field>

            <div className="flex flex-col gap-2">
              <p className="text-small text-text-dim">
                Leave a limit blank to use the plan&apos;s own number. Tick
                Unlimited to remove the ceiling. <code>0</code> is a real limit -
                it means none allowed.
              </p>
              {LIMITS.map(({ key, label }) => (
                <div key={key} className="flex items-center gap-3">
                  <span className="w-36 shrink-0 text-small text-text-dim">
                    {label}
                  </span>
                  <Input
                    type="number"
                    min={0}
                    value={values[key]}
                    disabled={unlimited.has(key)}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [key]: e.target.value }))
                    }
                    className="max-w-28"
                  />
                  <label className="flex items-center gap-1.5 text-small text-text-dim">
                    <input
                      type="checkbox"
                      checked={unlimited.has(key)}
                      onChange={(e) =>
                        setUnlimited((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(key);
                          else next.delete(key);
                          return next;
                        })
                      }
                    />
                    Unlimited
                  </label>
                </div>
              ))}
            </div>

            <Field label="Note" help="Shown to nobody outside CallFlow.">
              <Input value={note} onChange={(e) => setNote(e.target.value)} />
            </Field>

            <Field
              label="Reason"
              required
              help="Recorded in the audit log with the before and after state. A ticket or order-form reference is what makes this reconstructable later."
            >
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Order form #88"
              />
            </Field>
          </div>
        )}
      </Dialog>
    </DialogRoot>
  );
}

/** `''` is "inherit the plan"; `'0'` is a real ceiling. A `Number()` on an empty
 *  string is `0`, which would quietly turn "unset" into "none allowed". */
function numberOrNull(raw: string): number | null {
  const trimmed = raw.trim();
  if (trimmed === '') return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : null;
}
