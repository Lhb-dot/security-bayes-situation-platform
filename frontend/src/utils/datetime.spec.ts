import { describe, expect, it } from 'vitest';
import {
  formatBeijingDateTime,
  formatBeijingShort,
  parseBeijingNaive,
  parseInstant,
  toBeijingParts,
} from './datetime';

describe('datetime utilities', () => {
  it('interprets a Beijing-naive timestamp as UTC+8', () => {
    expect(parseBeijingNaive('2026-10-10 09:00:00')).toBe(Date.UTC(2026, 9, 10, 1, 0, 0));
  });

  it('respects an existing timezone marker without adding another Beijing offset', () => {
    expect(parseBeijingNaive('2026-10-10T09:00:00+09:00')).toBe(Date.UTC(2026, 9, 10, 0, 0, 0));
  });

  it('returns null for empty and invalid Beijing-naive values', () => {
    expect(parseBeijingNaive('')).toBeNull();
    expect(parseBeijingNaive('not-a-date')).toBeNull();
  });

  it('parses an ISO instant with a timezone and fractional seconds', () => {
    expect(parseInstant('2026-09-14T09:09:08.949249+00:00')).toBe(Date.UTC(2026, 8, 14, 9, 9, 8, 949));
  });

  it('interprets an instant without a timezone marker as UTC', () => {
    expect(parseInstant('2026-09-14T09:09:08.949')).toBe(Date.UTC(2026, 8, 14, 9, 9, 8, 949));
  });

  it('formats epoch milliseconds as a Beijing datetime', () => {
    expect(formatBeijingDateTime(Date.UTC(2026, 9, 10, 1, 0, 0))).toBe('2026-10-10 09:00:00');
  });

  it('formats epoch milliseconds as a short Beijing datetime', () => {
    expect(formatBeijingShort(Date.UTC(2026, 9, 10, 1, 5, 0))).toBe('10-10 09:05');
  });

  it('handles the UTC-to-Beijing cross-day boundary', () => {
    expect(toBeijingParts(Date.UTC(2026, 9, 9, 16, 30, 0))).toEqual({
      year: 2026,
      month: 10,
      day: 10,
      hour: 0,
      minute: 30,
      second: 0,
    });
  });
});
