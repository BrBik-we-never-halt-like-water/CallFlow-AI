/**
 * The extraction-field model used by the campaign editor.
 *
 * The editor offers five types; the service accepts four (`string`, `number`,
 * `integer`, `boolean`). `date` and `enum` are mapped onto `string` on the way out,
 * with their constraint folded into the description.
 *
 * That is not a fudge. The description *is* the extraction instruction   it is what
 * the engine reads to decide what belongs in a field   so "one of: onsite, hybrid,
 * remote_only" in the description constrains the answer in practice, while the
 * transport type stays something the service already validates. The alternative was
 * to drop two useful types from the editor.
 */

import type { CampaignField, FieldType as WireFieldType } from "./api";

export type EditorFieldType = "string" | "number" | "boolean" | "date" | "enum";

export const EDITOR_FIELD_TYPES: { value: EditorFieldType; label: string; hint: string }[] = [
  { value: "string", label: "Text", hint: "Anything in the contact's own words" },
  { value: "number", label: "Number", hint: "Counts, durations, amounts" },
  { value: "boolean", label: "Yes / no", hint: "A single true-or-false fact" },
  { value: "date", label: "Date", hint: "A specific day, returned as an ISO date" },
  { value: "enum", label: "Choice", hint: "One of a fixed set of options you list" },
];

export interface EditorField {
  /** Stable local id so rows can be reordered and removed without index bugs. */
  id: string;
  key: string;
  type: EditorFieldType;
  description: string;
  /** Only for `enum`. */
  options: string[];
  required: boolean;
}

export function newEditorField(id: string): EditorField {
  return { id, key: "", type: "string", description: "", options: [], required: false };
}

const KEY_PATTERN = /^[a-z][a-z0-9_]*$/;

export function fieldKeyError(key: string): string | null {
  if (!key.trim()) return "Give this field a name.";
  if (!KEY_PATTERN.test(key)) {
    return "Use lowercase letters, numbers, and underscores   like party_size.";
  }
  if (key.length > 40) return "Keep the name under 40 characters.";
  return null;
}

/** What the editor sends to the service. */
export function toWireFields(fields: EditorField[]): CampaignField[] {
  return fields
    .filter((field) => field.key.trim() && !fieldKeyError(field.key))
    .map((field) => ({
      key: field.key.trim(),
      type: toWireType(field.type),
      description: describeForExtraction(field),
    }));
}

function toWireType(type: EditorFieldType): WireFieldType {
  switch (type) {
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    // `date` and `enum` travel as text; their shape lives in the description.
    case "date":
    case "enum":
    case "string":
    default:
      return "string";
  }
}

/**
 * The description the engine actually reads. A field's constraint is appended so the
 * extraction is told the shape even where the wire type cannot express it.
 */
export function describeForExtraction(field: EditorField): string {
  const base =
    field.description.trim() ||
    `The contact's ${field.key.replace(/_/g, " ").trim() || "answer"}.`;

  const parts = [base];
  if (field.type === "date") {
    parts.push("Return it as an ISO date, YYYY-MM-DD.");
  }
  if (field.type === "enum" && field.options.length > 0) {
    parts.push(`Must be one of: ${field.options.join(", ")}.`);
  }
  if (!field.required) {
    parts.push("Leave it null if the contact didn't say.");
  }
  return parts.join(" ");
}

/** The JSON Schema preview shown beside the editor. */
export function previewSchema(fields: EditorField[]): string {
  const properties: Record<string, unknown> = {
    outcome: { type: "string", description: "How the call ended, in one or two words." },
    sentiment: {
      type: "string",
      enum: ["positive", "neutral", "negative"],
      description: "How the contact sounded.",
    },
  };

  const required = ["outcome", "sentiment"];

  for (const field of fields) {
    const key = field.key.trim();
    if (!key || fieldKeyError(key)) continue;

    const entry: Record<string, unknown> = { description: describeForExtraction(field) };

    switch (field.type) {
      case "number":
        entry.type = "number";
        break;
      case "boolean":
        entry.type = "boolean";
        break;
      case "date":
        entry.type = "string";
        entry.format = "date";
        break;
      case "enum":
        entry.type = "string";
        if (field.options.length > 0) entry.enum = field.options;
        break;
      default:
        entry.type = "string";
    }

    properties[key] = entry;
    if (field.required) required.push(key);
  }

  return JSON.stringify({ type: "object", properties, required }, null, 2);
}

/**
 * Substitute a sample contact into a goal template, the same way the service does  
 * a missing key renders empty rather than failing.
 */
export function renderGoalPreview(
  template: string,
  contact: { name: string; context: Record<string, string> },
): string {
  return template
    .replace(/\{name\}/g, contact.name)
    .replace(/\{context\[(\w+)\]\}/g, (_, key: string) => contact.context[key] ?? "")
    .replace(/\{context\.(\w+)\}/g, (_, key: string) => contact.context[key] ?? "");
}

/** The variables a template references, for the chip row above the textarea. */
export function templateVariables(template: string): string[] {
  const found = new Set<string>();
  if (/\{name\}/.test(template)) found.add("name");
  for (const match of template.matchAll(/\{context[[.](\w+)\]?\}/g)) {
    found.add(`context.${match[1]}`);
  }
  return [...found];
}

/** Minimum goal length the service enforces. A thin goal fails at call time. */
export const GOAL_MIN_LENGTH = 40;

export const GOAL_MIN_REASON =
  "A thin goal is rejected before it dials. Say what to ask, what to do if they say yes, and what to do if they say no.";
