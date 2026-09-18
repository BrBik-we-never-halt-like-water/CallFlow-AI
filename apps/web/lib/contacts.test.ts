import { describe, expect, it } from 'vitest';
import {
  contextColumns,
  parseSheet,
  toContactInputs,
  toContextKey,
  validateRow,
} from './contacts';

describe('validateRow', () => {
  it('rejects a row with no name', () => {
    const result = validateRow('', '+919876543210');
    expect(result.valid).toBe(false);
    expect(result.errorField).toBe('name');
  });

  it('rejects a row with no phone', () => {
    const result = validateRow('Aditi', '');
    expect(result.valid).toBe(false);
    expect(result.errorField).toBe('phone');
  });

  it('rejects a phone that does not normalise to E.164', () => {
    const result = validateRow('Aditi', 'not a number');
    expect(result.valid).toBe(false);
    expect(result.errorField).toBe('phone');
  });

  it('accepts a valid name and phone', () => {
    expect(validateRow('Aditi', '9876543210')).toEqual({ valid: true });
  });
});

describe('toContextKey', () => {
  it('lowercases and underscores a header', () => {
    expect(toContextKey('Trip Type')).toBe('trip_type');
  });

  it('treats a dash the same as a space', () => {
    expect(toContextKey('trip-type')).toBe('trip_type');
  });

  it('truncates an unreasonably long header', () => {
    expect(toContextKey('a'.repeat(60)).length).toBe(40);
  });
});

describe('parseSheet', () => {
  it('parses a headerless CSV positionally', () => {
    const rows = parseSheet('Aditi Sharma,9876543210,asked about a holiday');
    expect(rows).toHaveLength(1);
    expect(rows[0].name).toBe('Aditi Sharma');
    expect(rows[0].phone).toBe('+919876543210');
    expect(rows[0].valid).toBe(true);
  });

  it('reads named columns as per-contact context, dropping reserved ones', () => {
    const csv = [
      'name,phone,note,destination,goal',
      'Rahul,9876543210,honeymoon enquiry,Malaysia,ignore me',
    ].join('\n');
    const rows = parseSheet(csv);
    expect(rows[0].context).toEqual({ destination: 'Malaysia' });
  });

  it('flags an invalid row instead of silently dropping it', () => {
    const csv = ['name,phone,note', ',9876543210,no name here'].join('\n');
    const rows = parseSheet(csv);
    expect(rows).toHaveLength(1);
    expect(rows[0].valid).toBe(false);
    expect(rows[0].errorField).toBe('name');
  });

  it('splits tab-separated input pasted from a spreadsheet', () => {
    const rows = parseSheet('Aditi\t9876543210\tasked about a holiday');
    expect(rows[0].name).toBe('Aditi');
    expect(rows[0].phone).toBe('+919876543210');
  });

  it('returns nothing for empty input', () => {
    expect(parseSheet('')).toEqual([]);
    expect(parseSheet('   \n  \n')).toEqual([]);
  });
});

describe('toContactInputs', () => {
  it('drops invalid rows and folds note into detail and note', () => {
    const rows = parseSheet(
      ['name,phone,note', 'Aditi,9876543210,wants a beach holiday', ',,'].join('\n'),
    );
    const inputs = toContactInputs(rows);
    expect(inputs).toHaveLength(1);
    expect(inputs[0]!.context!.detail).toBe('wants a beach holiday');
    expect(inputs[0]!.context!.note).toBe('wants a beach holiday');
  });
});

describe('contextColumns', () => {
  it('collects the union of context keys across rows, sorted', () => {
    const rows = parseSheet(
      [
        'name,phone,note,destination,travel_month',
        'Aditi,9876543210,x,Bali,December',
        'Rahul,9876543211,y,Malaysia,',
      ].join('\n'),
    );
    expect(contextColumns(rows)).toEqual(['destination', 'travel_month']);
  });
});
