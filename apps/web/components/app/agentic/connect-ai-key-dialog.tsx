'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogRoot } from '@/components/ui/dialog';
import { Field } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { useToast } from '@/components/ui/toast';
import { api, type AiProvider, type AiProviderCredential } from '@/lib/api';

/**
 * Inline "connect your API key" dialog for a single AI vendor.
 *
 * Same shape as `settings/integrations`'s own `ConnectDialog`, collapsed to
 * the one field an AI vendor credential actually needs - `api_key`, no
 * identifier, no phone number.
 */
export function ConnectAiKeyDialog({
  provider,
  vendorName,
  existing,
  onOpenChange,
  onChanged,
}: {
  provider: AiProvider;
  /** Display name, e.g. "Sarvam AI" - for the dialog title/copy. */
  vendorName: string;
  existing: AiProviderCredential | null;
  onOpenChange: (open: boolean) => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [apiKey, setApiKey] = useState('');
  const [saving, setSaving] = useState(false);

  const valid = apiKey.trim().length > 0;

  async function save() {
    if (!valid) return;
    setSaving(true);
    try {
      await api.connectAiProvider(provider, {
        api_key: apiKey.trim(),
        label: undefined,
      });
      toast({ tone: 'success', title: `${vendorName} connected` });
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
        title={`Connect ${vendorName}`}
        description={
          existing
            ? 'Replacing this key overwrites the one on file. The previous value is never shown again.'
            : `Find this in your ${vendorName} console. Stored encrypted, never shown again after saving.`
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
        <Field label="API key">
          <Input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            autoFocus
            autoComplete="off"
          />
        </Field>
      </Dialog>
    </DialogRoot>
  );
}
