'use client';

import {
  PlusIcon,
  QuestionIcon,
  TrashIcon,
} from '@phosphor-icons/react/dist/ssr';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/cn';
import type { CampaignField, FieldType } from '@/lib/api';

/**
 * What the agent has to establish while the call is happening.
 *
 * The same field shape campaigns already use for `extra_fields`, on purpose:
 * both end as structured call results, and a second format would mean a second
 * validator to keep in step. The API rejects unknown types and duplicate keys.
 */

const TYPES: { value: FieldType; label: string }[] = [
  { value: 'string', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'integer', label: 'Whole number' },
  { value: 'boolean', label: 'Yes / no' },
];

/** Keys become identifiers in the returned result, so they are normalised on
 *  entry rather than rejected after the fact. */
function toKey(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9_\s-]/g, '')
    .replace(/[\s-]+/g, '_')
    .slice(0, 40);
}

export function CollectFieldsEditor({
  fields,
  onChange,
  disabled,
}: {
  fields: CampaignField[];
  onChange: (next: CampaignField[]) => void;
  disabled?: boolean;
}) {
  function update(index: number, patch: Partial<CampaignField>) {
    onChange(fields.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  const keys = fields.map((f) => f.key);

  return (
    <section className="flex flex-col gap-3">
      {/* The explanation lives in the tooltip rather than under the heading:
          it is worth reading once, and after that it is a paragraph between
          the builder and the fields they came here to add. */}
      <div className="flex items-center gap-1.5">
        <h2 className="font-display text-h4 leading-none text-text">
          Add fields
        </h2>
        <Tooltip content="What the agent asks the person for during the call. Each one comes back as a field on the result, so a run can be read as data rather than as transcripts.">
          <button
            type="button"
            aria-label="What are fields?"
            className="flex size-4 items-center justify-center rounded-full text-text-mute transition-colors duration-(--dur-fast) hover:text-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--primary)"
          >
            <QuestionIcon aria-hidden className="size-4" />
          </button>
        </Tooltip>
      </div>

      {fields.length === 0 ? (
        <p className="rounded-xl bg-surface-raised p-4 text-small text-text-dim ring-1 ring-rule">
          No fields yet.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {fields.map((field, index) => {
            const duplicate =
              field.key.length > 0 &&
              keys.indexOf(field.key) !== keys.lastIndexOf(field.key);

            return (
              <li
                key={index}
                className="grid gap-2 rounded-xl bg-surface-raised p-3 ring-1 ring-rule md:grid-cols-[12rem_9rem_minmax(0,1fr)_auto] md:items-center"
              >
                 <Select
                  value={field.type}
                  onValueChange={(v) =>
                    update(index, { type: v as FieldType })
                  }
                  options={TYPES}
                  ariaLabel={`Type for ${field.key || `field ${index + 1}`}`}
                />

                <Input
                  value={field.key}
                  onChange={(e) => update(index, { key: toKey(e.target.value) })}
                  placeholder="Field Name"
                  disabled={disabled}
                  aria-label={`Key for field ${index + 1}`}
                  aria-invalid={duplicate || undefined}
                  className={cn(duplicate && 'border-lamp-flare')}
                />

                <Input
                  value={field.description}
                  onChange={(e) =>
                    update(index, { description: e.target.value })
                  }
                  placeholder="Description"
                  disabled={disabled}
                  aria-label={`What ${field.key || 'this field'} means`}
                />

                <span className="flex items-center gap-1">
                  <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap px-1 text-[0.6875rem] text-text-mute">
                    <input
                      type="checkbox"
                      checked={field.required ?? false}
                      disabled={disabled}
                      onChange={(e) =>
                        update(index, { required: e.target.checked })
                      }
                      className="accent-primary"
                    />
                    Required
                  </label>

                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={disabled}
                    aria-label={`Remove ${field.key || `field ${index + 1}`}`}
                    onClick={() =>
                      onChange(fields.filter((_, i) => i !== index))
                    }
                  >
                    <TrashIcon aria-hidden className="size-4" />
                  </Button>
                </span>

                {duplicate ? (
                  <p className="text-[0.6875rem] text-text-dim md:col-span-4">
                    Another field already uses this key. Give each one its own.
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <div>
        <Button
          variant="secondary"
          size="sm"
          disabled={disabled}
          onClick={() =>
            onChange([
              ...fields,
              { key: '', type: 'string', description: '', required: false },
            ])
          }
        >
          <PlusIcon aria-hidden className="size-4" />
          Add field
        </Button>
      </div>
    </section>
  );
}
