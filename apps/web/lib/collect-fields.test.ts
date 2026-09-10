import { describe, expect, it } from 'vitest';
import {
  describeForExtraction,
  fieldKeyError,
  GOAL_MIN_LENGTH,
  newEditorField,
  previewSchema,
  renderGoalPreview,
  templateVariables,
  toWireFields,
} from './collect-fields';
import type { EditorField } from './collect-fields';

function field(overrides: Partial<EditorField>): EditorField {
  return { ...newEditorField('1'), key: 'field_key', ...overrides };
}

describe('fieldKeyError', () => {
  it('requires a key', () => {
    expect(fieldKeyError('')).toBeTruthy();
  });

  it('rejects an uppercase or symbol-bearing key', () => {
    expect(fieldKeyError('Party Size')).toBeTruthy();
  });

  it('accepts lowercase letters, digits, and underscores', () => {
    expect(fieldKeyError('party_size_2')).toBeNull();
  });

  it('rejects a key over 40 characters', () => {
    expect(fieldKeyError('a'.repeat(41))).toBeTruthy();
  });
});

describe('toWireFields - the 5-to-4 type mapping', () => {
  it('maps date and enum onto string, the four types the service accepts', () => {
    const fields = [
      field({ key: 'a', type: 'string' }),
      field({ key: 'b', type: 'number' }),
      field({ key: 'c', type: 'boolean' }),
      field({ key: 'd', type: 'date' }),
      field({ key: 'e', type: 'enum' }),
    ];
    const wire = toWireFields(fields);
    expect(wire.map((f) => f.type)).toEqual([
      'string',
      'number',
      'boolean',
      'string',
      'string',
    ]);
  });

  it('drops a field with no key or an invalid key', () => {
    const fields = [field({ key: '' }), field({ key: 'Invalid Key' })];
    expect(toWireFields(fields)).toHaveLength(0);
  });
});

describe('describeForExtraction', () => {
  it('appends the date format instruction for a date field', () => {
    const desc = describeForExtraction(field({ type: 'date', description: 'When they can start' }));
    expect(desc).toContain('ISO date');
  });

  it('appends the allowed options for an enum field', () => {
    const desc = describeForExtraction(
      field({ type: 'enum', description: 'Work mode', options: ['onsite', 'remote'] }),
    );
    expect(desc).toContain('onsite, remote');
  });

  it('notes an optional field can be left null', () => {
    const desc = describeForExtraction(field({ required: false, description: 'Budget' }));
    expect(desc).toContain("didn't say");
  });

  it('does not add the null-allowed note for a required field', () => {
    const desc = describeForExtraction(field({ required: true, description: 'Budget' }));
    expect(desc).not.toContain("didn't say");
  });
});

describe('previewSchema', () => {
  it('always includes outcome and sentiment as required', () => {
    const schema = JSON.parse(previewSchema([]));
    expect(schema.required).toEqual(['outcome', 'sentiment']);
  });

  it('marks only required fields as required in the schema', () => {
    const fields = [field({ key: 'a', required: true }), field({ key: 'b', required: false })];
    const schema = JSON.parse(previewSchema(fields));
    expect(schema.required).toEqual(['outcome', 'sentiment', 'a']);
  });
});

describe('renderGoalPreview', () => {
  it('substitutes {name} and {context.key}', () => {
    const rendered = renderGoalPreview('Hi {name}, about your {context.destination} trip', {
      name: 'Aditi',
      context: { destination: 'Bali' },
    });
    expect(rendered).toBe('Hi Aditi, about your Bali trip');
  });

  it('renders a missing context key as empty rather than failing', () => {
    const rendered = renderGoalPreview('{context.missing}', { name: 'Aditi', context: {} });
    expect(rendered).toBe('');
  });
});

describe('templateVariables', () => {
  it('finds every referenced variable once each', () => {
    const vars = templateVariables('Hi {name}, {context.destination} and {context.destination} again');
    expect(vars).toEqual(['name', 'context.destination']);
  });
});

describe('GOAL_MIN_LENGTH', () => {
  it('is a real floor, not zero', () => {
    expect(GOAL_MIN_LENGTH).toBeGreaterThan(0);
  });
});
