'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Textarea } from '@/components/ui/input';
import { api, type ShareResourceType } from '@/lib/api';
import { useToast } from '@/components/ui/toast';

/**
 * "Request access" / "Request to help" - the one dialog both directories
 * (escalations) open. The server resolves who actually owns the
 * target resource (`resolve_resource_owner()`) - this dialog never needs to
 * know or send that itself.
 */
export function ShareRequestDialog({
  open,
  onOpenChange,
  resourceType,
  resourceId,
  resourceLabel,
  onRequested,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  resourceType: ShareResourceType;
  resourceId: string | null;
  resourceLabel: string;
  onRequested: () => void;
}) {
  const toast = useToast();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  async function send() {
    if (!resourceId) return;
    setSending(true);
    try {
      await api.createShareRequest(resourceType, resourceId, message.trim());
      toast({ tone: 'success', title: 'Request sent' });
      setMessage('');
      onOpenChange(false);
      onRequested();
    } catch (error) {
      toast({
        tone: 'error',
        title: "That request wasn't sent",
        body: error instanceof Error ? error.message : undefined,
      });
    } finally {
      setSending(false);
    }
  }

  return (
    <DialogRoot
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setMessage('');
      }}
    >
      <Dialog
        title="Request to help"
        description={`${resourceLabel} - the owner decides whether to say yes.`}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button onClick={send} loading={sending}>
              Send request
            </Button>
          </>
        }
      >
        <Field label="Message" help="Optional - why you're asking.">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="I'm free to follow up on this one."
            rows={3}
            autoFocus
          />
        </Field>
      </Dialog>
    </DialogRoot>
  );
}
