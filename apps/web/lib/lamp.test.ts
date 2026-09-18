import { describe, expect, it } from 'vitest';
import {
  countLamps,
  describeStrip,
  lampForDisposition,
  lampForOutcome,
  lampForRunStatus,
  stripForRun,
} from './lamp';
import type { Outcome } from './api';

function outcome(disposition: Outcome['disposition']): Outcome {
  return { disposition } as Outcome;
}

describe('lampForDisposition', () => {
  it('gives a distinct lamp to every disposition, none of them collapsing', () => {
    const dispositions: Outcome['disposition'][] = [
      'in_flight',
      'auto_closed',
      'escalated',
      'retry',
      'unreachable',
      'skipped',
    ];
    const seen = dispositions.map((d) => lampForDisposition(d).state);
    // Delighted (auto_closed) and furious (escalated) must never share a lamp -
    // that distinction is the whole point of this mapping.
    expect(lampForDisposition('auto_closed').state).not.toBe(
      lampForDisposition('escalated').state,
    );
    expect(seen).toHaveLength(dispositions.length);
  });

  it('pulses a retry but not a settled outcome', () => {
    expect(lampForDisposition('retry').pulse).toBe(true);
    expect(lampForDisposition('auto_closed').pulse).toBeUndefined();
  });

  it('falls back to the queued lamp for an unrecognised disposition', () => {
    // @ts-expect-error - deliberately an out-of-union value
    expect(lampForDisposition('something_new').state).toBe('off');
  });
});

describe('lampForOutcome', () => {
  it('reads the disposition off the outcome', () => {
    expect(lampForOutcome(outcome('escalated')).state).toBe('flare');
  });
});

describe('lampForRunStatus', () => {
  it('shows stopping as brass and pulsing, not a fifth colour', () => {
    const lamp = lampForRunStatus('running', true);
    expect(lamp.state).toBe('brass');
    expect(lamp.pulse).toBe(true);
    expect(lamp.label).toBe('Stopping');
  });

  it('never shows a stopped run as the clean-outcome colour', () => {
    expect(lampForRunStatus('stopped').state).not.toBe('jade');
  });

  it('never shows a stopped run as the failure colour either', () => {
    expect(lampForRunStatus('stopped').state).not.toBe('flare');
  });

  it('maps completed to the clean-outcome colour', () => {
    expect(lampForRunStatus('completed').state).toBe('jade');
  });
});

describe('stripForRun', () => {
  it('pads the strip with queued lamps for contacts not yet dialled', () => {
    const strip = stripForRun([outcome('auto_closed')], 3);
    expect(strip).toHaveLength(3);
    expect(strip[0].state).toBe('jade');
    expect(strip[1].state).toBe('off');
    expect(strip[2].state).toBe('off');
  });

  it('never pads a negative amount when outcomes exceed the total', () => {
    const strip = stripForRun([outcome('auto_closed'), outcome('escalated')], 1);
    expect(strip).toHaveLength(2);
  });
});

describe('countLamps', () => {
  it('separates closed, retry, needs-a-person, and queued', () => {
    const lamps = [
      lampForDisposition('auto_closed'),
      lampForDisposition('escalated'),
      lampForDisposition('retry'),
      { state: 'off' as const, label: 'Queued' },
    ];
    const counts = countLamps(lamps);
    expect(counts).toEqual({
      closed: 1,
      retry: 1,
      needsPerson: 1,
      queued: 1,
      settled: 3,
      total: 4,
    });
  });
});

describe('describeStrip', () => {
  it('summarises a strip with nothing in a countable bucket without a colon', () => {
    // in_flight (brass, no pulse) falls outside every countLamps bucket, so a
    // strip of only in-conversation calls has no parts to join.
    expect(describeStrip([lampForDisposition('in_flight')])).toBe('1 call');
  });

  it('names a queued lamp as "not yet dialled"', () => {
    expect(describeStrip([{ state: 'off', label: 'Queued' }])).toBe(
      '1 call: 1 not yet dialled',
    );
  });

  it('names each bucket present, comma separated', () => {
    const lamps = [lampForDisposition('auto_closed'), lampForDisposition('escalated')];
    expect(describeStrip(lamps)).toBe('2 calls: 1 closed, 1 need a person');
  });
});
