"use client";

import { PlusIcon, TrashIcon } from "@phosphor-icons/react/dist/ssr";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { NotWiredNotice } from "@/components/app/settings-section";
import { Tag } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { CodeBlock } from "@/components/ui/code-block";
import { Field } from "@/components/ui/field";
import { Input, MinLengthCounter, Textarea } from "@/components/ui/input";
import { Eyebrow, Panel } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/toast";
import { api, type Campaign } from "@/lib/api";
import {
  EDITOR_FIELD_TYPES,
  fieldKeyError,
  GOAL_MIN_LENGTH,
  GOAL_MIN_REASON,
  newEditorField,
  previewSchema,
  renderGoalPreview,
  templateVariables,
  toWireFields,
  type EditorField,
  type EditorFieldType,
} from "@/lib/campaign-fields";
import {
  CAMPAIGN_DRAFT_KEY,
  DEFAULT_SETTINGS,
  LANGUAGES,
  PREVIEW_CONTACTS,
  REGIONS,
  saveLocalSettings,
  settingsKey,
  TIMEZONES,
  type LocalCampaignSettings,
} from "@/lib/campaign-draft";
import { useStoredJson } from "@/lib/hooks/use-external-store";

/**
 * The campaign editor. Two panes: compose on the left, live preview on the right.
 *
 * The preview is the point of the layout. A goal is a piece of writing whose effect is
 * invisible until it is rendered with a real contact substituted in, so the rendered
 * version and the schema it will return sit permanently beside the field you are
 * typing into — not behind a "preview" button nobody presses.
 */
export function CampaignEditor({ existing }: { existing?: Campaign }) {
  const router = useRouter();
  const toast = useToast();

  // `existing` is available on the first render, so everything it seeds is a lazy
  // initialiser rather than an effect — the editor is never briefly empty.
  const [name, setName] = useState(existing?.name ?? "");
  const [goal, setGoal] = useState(existing?.goal_template ?? "");
  const [region, setRegion] = useState(existing?.region ?? "IN");
  const [language, setLanguage] = useState(existing?.language ?? "en");
  const [fields, setFields] = useState<EditorField[]>(() => fieldsFrom(existing));
  const [previewIndex, setPreviewIndex] = useState(0);
  const [saving, setSaving] = useState(false);
  const [nextId, setNextId] = useState(
    () => Object.keys(existing?.outcome_fields ?? {}).length + 1,
  );

  // Subscribed, so the calling window and retry policy are correct on first paint.
  const [settings, setSettings] = useStoredJson<LocalCampaignSettings>(
    settingsKey(existing?.id ?? ""),
    DEFAULT_SETTINGS,
  );

  const readOnly = existing?.built_in ?? false;

  /**
   * Pick up a duplicate handed over in sessionStorage.
   *
   * This is a genuine one-shot read of an external store that also has to *clear* the
   * handoff, so it cannot be a subscription or a lazy initialiser — a lazy initialiser
   * would run during SSR where sessionStorage does not exist, and would disagree with
   * the client on hydration.
   */
  /* eslint-disable react-hooks/set-state-in-effect -- see the comment above: a
     one-shot read that also clears the handoff cannot be a subscription. */
  useEffect(() => {
    if (existing) return;

    try {
      const raw = sessionStorage.getItem(CAMPAIGN_DRAFT_KEY);
      if (!raw) return;
      sessionStorage.removeItem(CAMPAIGN_DRAFT_KEY);
      const draft = JSON.parse(raw) as {
        name?: string;
        goal_template?: string;
        region?: string | null;
        language?: string | null;
        outcome_fields?: Record<string, string>;
      };
      if (draft.name) setName(draft.name);
      if (draft.goal_template) setGoal(draft.goal_template);
      if (draft.region) setRegion(draft.region);
      if (draft.language) setLanguage(draft.language);
      if (draft.outcome_fields) {
        setFields(
          Object.entries(draft.outcome_fields).map(([key, description], i) => ({
            id: `dup-${i}`,
            key,
            type: "string" as EditorFieldType,
            description,
            options: [],
            required: false,
          })),
        );
        setNextId(Object.keys(draft.outcome_fields).length + 1);
      }
    } catch {
      /* nothing to restore */
    }
  }, [existing]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const variables = useMemo(() => templateVariables(goal), [goal]);
  const previewContact = PREVIEW_CONTACTS[previewIndex] ?? PREVIEW_CONTACTS[0];
  const renderedGoal = useMemo(
    () => renderGoalPreview(goal, previewContact),
    [goal, previewContact],
  );
  const schema = useMemo(() => previewSchema(fields), [fields]);

  /**
   * Exactly why saving is blocked, as one sentence.
   *
   * Never "please fill all fields" — the operator should not have to hunt for which
   * one. This string becomes the disabled button's tooltip.
   */
  const blocker = useMemo<string | null>(() => {
    if (readOnly) return "This is a starter template. Duplicate it to make changes.";
    if (name.trim().length < 2) return "Give the campaign a name of at least 2 characters.";
    if (goal.trim().length < GOAL_MIN_LENGTH) {
      return `The goal needs at least ${GOAL_MIN_LENGTH} characters — it has ${goal.trim().length}.`;
    }
    const badField = fields.find((f) => f.key.trim() && fieldKeyError(f.key));
    if (badField) return `The field “${badField.key}” has an invalid name.`;
    const emptyEnum = fields.find((f) => f.type === "enum" && f.options.length === 0);
    if (emptyEnum) {
      return `The choice field “${emptyEnum.key || "unnamed"}” needs at least one option.`;
    }
    return null;
  }, [readOnly, name, goal, fields]);

  function updateField(id: string, patch: Partial<EditorField>) {
    setFields((current) => current.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  }

  function addField() {
    setFields((current) => [...current, newEditorField(`field-${nextId}`)]);
    setNextId((n) => n + 1);
  }

  async function save() {
    if (blocker) return;
    setSaving(true);
    try {
      const created = await api.createCampaign({
        name: name.trim(),
        goal_template: goal,
        extra_fields: toWireFields(fields),
        region,
        language,
        escalate_on_negative: settings.escalateOnNegative,
      });
      saveLocalSettings(created.id, settings);
      toast({ tone: "success", title: "Campaign saved" });
      router.push("/app/campaigns");
    } catch (error) {
      toast({
        tone: "error",
        title: "That campaign wasn't saved",
        body: error instanceof Error ? error.message : "The service didn't respond.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[55fr_45fr]">
      {/* ================= Compose ====================================== */}
      <div className="flex min-w-0 flex-col gap-5">
        {readOnly ? (
          <Panel sunken className="flex flex-col gap-2 p-4">
            <Eyebrow>Read only</Eyebrow>
            <p className="text-small text-text-dim">
              This is a starter template. Duplicate it from the campaigns list to make a
              version you can change.
            </p>
          </Panel>
        ) : null}

        <Field label="Campaign name" required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Holiday enquiry follow-up"
            disabled={readOnly}
          />
        </Field>

        <div className="flex flex-col gap-2">
          <Field
            label="Goal"
            hint="Write it as instructions to a competent new colleague: what to say, what to ask, and what to do when they say yes or no."
            required
          >
            <Textarea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              rows={14}
              mono
              disabled={readOnly}
              placeholder={"You are calling {name} about…"}
            />
          </Field>

          <MinLengthCounter value={goal} min={GOAL_MIN_LENGTH} reason={GOAL_MIN_REASON} />

          {/* Variables the template actually references, so a typo in a context key is
              visible rather than silently rendering empty at call time. */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="eyebrow text-text-mute">Variables</span>
            {variables.length === 0 ? (
              <span className="text-small text-text-mute">
                none yet — try <code className="font-mono text-data">{"{name}"}</code>
              </span>
            ) : (
              variables.map((variable) => <Tag key={variable}>{variable}</Tag>)
            )}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Calling region">
            <Select
              value={region}
              onValueChange={setRegion}
              options={REGIONS}
              disabled={readOnly}
            />
          </Field>
          <Field label="Language">
            <Select
              value={language}
              onValueChange={setLanguage}
              options={LANGUAGES}
              disabled={readOnly}
            />
          </Field>
        </div>

        {/* ---- Calling window ------------------------------------------- */}
        <Panel className="flex flex-col gap-4 p-4">
          <div className="flex flex-col gap-1">
            <Eyebrow>Calling window</Eyebrow>
            <p className="text-small text-text-dim">
              The hours you intend to call within.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="From">
              <Input
                type="time"
                value={settings.window.start}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, window: { ...s.window, start: e.target.value } }))
                }
                disabled={readOnly}
                className="font-mono tabular-nums"
              />
            </Field>
            <Field label="Until">
              <Input
                type="time"
                value={settings.window.end}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, window: { ...s.window, end: e.target.value } }))
                }
                disabled={readOnly}
                className="font-mono tabular-nums"
              />
            </Field>
            <Field label="Timezone">
              <Select
                value={settings.window.timezone}
                onValueChange={(tz) =>
                  setSettings((s) => ({ ...s, window: { ...s.window, timezone: tz } }))
                }
                options={TIMEZONES}
                disabled={readOnly}
              />
            </Field>
          </div>

          <NotWiredNotice>
            Not enforced yet — this is saved locally for your own reference, but a run
            can still dial outside these hours.
          </NotWiredNotice>
        </Panel>

        {/* ---- Retry policy -------------------------------------------- */}
        <Panel className="flex flex-col gap-4 p-4">
          <div className="flex flex-col gap-1">
            <Eyebrow>Retry policy</Eyebrow>
            <p className="text-small text-text-dim">
              A bad time isn&apos;t a bad mood — unavailable contacts and bad-time calls
              are marked for retry rather than escalated.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Attempts after the first">
              <Select
                value={String(settings.retry.attempts)}
                onValueChange={(v) =>
                  setSettings((s) => ({ ...s, retry: { ...s.retry, attempts: Number(v) } }))
                }
                options={["0", "1", "2", "3"].map((n) => ({
                  value: n,
                  label: n === "0" ? "Don't retry" : `${n} more`,
                }))}
                disabled={readOnly}
                mono
              />
            </Field>
            <Field label="Wait between attempts">
              <Select
                value={String(settings.retry.spacingHours)}
                onValueChange={(v) =>
                  setSettings((s) => ({ ...s, retry: { ...s.retry, spacingHours: Number(v) } }))
                }
                options={[
                  { value: "4", label: "4 hours" },
                  { value: "24", label: "1 day" },
                  { value: "48", label: "2 days" },
                  { value: "168", label: "1 week" },
                ]}
                disabled={readOnly}
                mono
              />
            </Field>
          </div>

          <NotWiredNotice>
            The disposition is real — a bad-time call is genuinely marked for retry.
            Automatically acting on these attempt and spacing settings isn&apos;t built
            yet, so retrying today is a manual second run.
          </NotWiredNotice>

          <Switch
            checked={settings.escalateOnNegative}
            onCheckedChange={(v) => setSettings((s) => ({ ...s, escalateOnNegative: v }))}
            label="Escalate frustrated calls to a person"
            subLabel="Opt-outs and requests for a human always escalate regardless."
            disabled={readOnly}
          />
        </Panel>

        {/* ---- Extraction fields --------------------------------------- */}
        <Panel className="flex flex-col gap-4 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="flex flex-col gap-1">
              <Eyebrow>Fields to extract</Eyebrow>
              <p className="text-small text-text-dim">
                Every call returns outcome and sentiment. These are the fields on top of
                that.
              </p>
            </div>
            <Button variant="secondary" size="sm" onClick={addField} disabled={readOnly}>
              <PlusIcon aria-hidden className="size-4" />
              Add field
            </Button>
          </div>

          {fields.length === 0 ? (
            <p className="text-small text-text-mute">
              No extra fields yet. Outcome and sentiment come back on every call anyway.
            </p>
          ) : (
            <ul className="flex flex-col gap-4">
              {fields.map((field) => {
                const keyError = field.key.trim() ? fieldKeyError(field.key) : null;
                return (
                  <li
                    key={field.id}
                    className="flex flex-col gap-3 border-t border-rule pt-4 first:border-0 first:pt-0"
                  >
                    <div className="grid gap-3 sm:grid-cols-[1fr_140px_auto]">
                      <Field label="Field name" error={keyError} labelHidden>
                        <Input
                          value={field.key}
                          onChange={(e) => updateField(field.id, { key: e.target.value })}
                          placeholder="party_size"
                          disabled={readOnly}
                          className="font-mono text-data"
                          aria-label="Field name"
                        />
                      </Field>

                      <Select
                        value={field.type}
                        onValueChange={(v) =>
                          updateField(field.id, { type: v as EditorFieldType })
                        }
                        options={EDITOR_FIELD_TYPES}
                        disabled={readOnly}
                        ariaLabel={`Type for ${field.key || "the new field"}`}
                      />

                      <Button
                        variant="ghost"
                        size="md"
                        aria-label={`Remove ${field.key || "this field"}`}
                        disabled={readOnly}
                        onClick={() =>
                          setFields((current) => current.filter((f) => f.id !== field.id))
                        }
                      >
                        <TrashIcon aria-hidden className="size-4" />
                      </Button>
                    </div>

                    <Field
                      label="What to capture"
                      hint="This is the instruction the extraction reads. Write it as if explaining to someone filling the form in for you."
                      labelHidden
                    >
                      <Input
                        value={field.description}
                        onChange={(e) =>
                          updateField(field.id, { description: e.target.value })
                        }
                        placeholder="Number of people travelling, including children"
                        disabled={readOnly}
                        aria-label={`What to capture for ${field.key || "the new field"}`}
                      />
                    </Field>

                    {field.type === "enum" ? (
                      <Field
                        label="Options"
                        hint="Comma separated. The answer must be one of these."
                      >
                        <Input
                          value={field.options.join(", ")}
                          onChange={(e) =>
                            updateField(field.id, {
                              options: e.target.value
                                .split(",")
                                .map((o) => o.trim())
                                .filter(Boolean),
                            })
                          }
                          placeholder="onsite, hybrid, remote_only"
                          disabled={readOnly}
                          className="font-mono text-data"
                        />
                      </Field>
                    ) : null}

                    <Checkbox
                      checked={field.required}
                      onCheckedChange={(v) => updateField(field.id, { required: v })}
                      label="Required — the call isn't complete without it"
                      id={`required-${field.id}`}
                      disabled={readOnly}
                    />
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <div className="flex flex-wrap items-center gap-3">
          {/* A disabled control always says why, and the tooltip names the exact
              missing requirement rather than a generic complaint. */}
          {blocker ? (
            <Tooltip content={blocker} wrapTrigger>
              <Button disabled>Save campaign</Button>
            </Tooltip>
          ) : (
            <Button loading={saving} onClick={save}>
              Save campaign
            </Button>
          )}
          <Button variant="secondary" onClick={() => router.push("/app/campaigns")}>
            Cancel
          </Button>
        </div>
      </div>

      {/* ================= Live preview ================================= */}
      <div className="flex min-w-0 flex-col gap-4 lg:sticky lg:top-24 lg:self-start">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <Eyebrow>Live preview</Eyebrow>
          <div className="w-52">
            <Select
              value={String(previewIndex)}
              onValueChange={(v) => setPreviewIndex(Number(v))}
              options={PREVIEW_CONTACTS.map((contact, i) => ({
                value: String(i),
                label: contact.name,
              }))}
              ariaLabel="Preview with a different contact"
            />
          </div>
        </div>

        <Panel className="flex flex-col">
          <div className="flex flex-col gap-2 p-4">
            <Eyebrow>What {previewContact.name.split(" ")[0]} would hear</Eyebrow>
            <div
              className={cn(
                "min-h-40 overflow-x-auto whitespace-pre-wrap font-mono text-data",
                renderedGoal.trim() ? "text-text" : "text-text-mute",
              )}
            >
              {renderedGoal.trim() || "Start writing the goal and it will render here."}
            </div>
          </div>

          <div className="h-px bg-rule" />

          <div className="p-4">
            <CodeBlock
              label="What comes back"
              code={schema}
              maxHeight="max-h-80"
            />
          </div>
        </Panel>

        <p className="text-small text-text-mute">
          A missing context key renders empty rather than failing the run, so check this
          panel with a real contact selected before saving.
        </p>
      </div>
    </div>
  );
}

/** Turn a saved campaign's outcome fields into editor rows. */
function fieldsFrom(existing?: Campaign): EditorField[] {
  if (!existing) return [];
  return Object.entries(existing.outcome_fields).map(([key, description], i) => ({
    id: `existing-${i}`,
    key,
    type: "string" as EditorFieldType,
    description,
    options: [],
    required: false,
  }));
}
