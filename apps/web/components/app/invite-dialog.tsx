'use client';

import { useEffect, useState } from 'react';
import { PlanLimitNotice } from '@/components/app/plan-limit-notice';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import { useSession } from '@/lib/hooks/use-session';

export const ROLES = [
  {
    value: 'admin',
    label: 'Admin',
    hint: 'Everything, including billing, safety, and integrations',
  },
  {
    value: 'operator',
    label: 'Operator',
    hint: 'Start runs, edit campaigns, resolve escalations',
  },
  {
    value: 'viewer',
    label: 'Viewer',
    hint: 'Read results only - cannot start a run',
  },
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
  const session = useSession();
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('operator');
  const [sending, setSending] = useState(false);
  const seats = useSeatUsage(open);

  async function send() {
    if (!email.trim()) return;
    setSending(true);
    try {
      await api.inviteMember(email.trim(), role);
      toast({ tone: 'success', title: 'Invitation sent', body: email.trim() });
      setEmail('');
      onOpenChange(false);
      onInvited();
    } catch (error) {
      toast({
        tone: 'error',
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
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => onOpenChange(false)}
              disabled={sending}
            >
              Cancel
            </Button>
            <Button onClick={send} loading={sending} disabled={seats !== null}>
              Send invitation
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {seats ? (
            <PlanLimitNotice
              reason={seats}
              canUpgrade={
                session.status === 'signed-in' &&
                session.profile.permissions.includes('billing:write')
              }
            />
          ) : null}
          <Field label="Work email" required>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
            />
          </Field>
          <Field
            label="Role"
            help="Operators can run campaigns but not change billing."
          >
            <Select value={role} onValueChange={setRole} options={ROLES} />
          </Field>
        </div>
      </Dialog>
    </DialogRoot>
  );
}


/**
 * The seat refusal to show before someone types an email, or `null` when there is
 * room - or when the answer is not known yet.
 *
 * A pending invitation holds a seat, so `usage.seats` already counts both members
 * and outstanding invitations; that is the same total `check_seat_available`
 * refuses on, and the same one `enforce_seat_limit` re-checks when the invitee
 * actually clicks. Read on open rather than on mount, because the dialog is
 * mounted from three places and the count changes underneath it.
 *
 * Fails open: `TEAM_INVITE` and `BILLING_READ` are both admin+, so this should
 * always resolve for anyone who can see this dialog - but a failed request must
 * not block an invitation the plan permits. The 402 is still the real gate.
 */
function useSeatUsage(open: boolean): string | null {
  const [reason, setReason] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .billingOverview()
      .then((overview) => {
        if (cancelled) return;
        const allowed = overview.entitlements.max_seats;
        setReason(
          allowed !== null && overview.usage.seats >= allowed
            ? `${overview.plan_name} includes ${allowed} ${allowed === 1 ? 'seat' : 'seats'}, ` +
                'and every one is taken or held by a pending invitation.'
            : null,
        );
      })
      .catch(() => {
        if (!cancelled) setReason(null);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  return reason;
}
