import { describe, expect, it } from 'vitest';
import { formatE164, isE164, maskPhone, normalisePhone } from './phone';

describe('isE164', () => {
  it('accepts a well-formed E.164 number', () => {
    expect(isE164('+919876543210')).toBe(true);
  });

  it('rejects a number missing the leading +', () => {
    expect(isE164('919876543210')).toBe(false);
  });

  it('rejects a number starting with 0 after the +', () => {
    expect(isE164('+0987654321')).toBe(false);
  });
});

describe('normalisePhone', () => {
  it('assumes a bare 10-digit number is in the default country', () => {
    expect(normalisePhone('9876543210')).toBe('+919876543210');
  });

  it('respects an explicit default country code', () => {
    expect(normalisePhone('5551234567', '1')).toBe('+15551234567');
  });

  it('converts a 00-prefixed international number', () => {
    expect(normalisePhone('0091 98765 43210')).toBe('+919876543210');
  });

  it('strips separators from an already-prefixed number', () => {
    expect(normalisePhone('+91 98765-43210')).toBe('+919876543210');
  });

  it('leaves an unrecognisable string alone rather than guessing', () => {
    expect(normalisePhone('not a phone number')).toBe('notaphonenumber');
  });
});

describe('maskPhone', () => {
  it('masks a full E.164 number, keeping the prefix and last three digits', () => {
    const masked = maskPhone('+919876543210');
    expect(masked.startsWith('+91')).toBe(true);
    expect(masked.endsWith('210')).toBe(true);
    expect(masked).toContain('*');
    // The full number never survives unmasked in the middle.
    expect(masked).not.toContain('98765432');
  });

  it('masks a short string down to a fixed placeholder', () => {
    expect(maskPhone('12345')).toBe('***');
  });

  it('returns an empty string for empty input', () => {
    expect(maskPhone('')).toBe('');
    expect(maskPhone('   ')).toBe('');
  });
});

describe('formatE164', () => {
  it('groups the national number for readability', () => {
    expect(formatE164('+919876543210')).toBe('+91 9876 5432 10');
  });

  it('returns non-E.164 input unchanged rather than guessing a grouping', () => {
    expect(formatE164('not a number')).toBe('not a number');
  });
});
