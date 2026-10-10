import { describe, expect, it } from 'vitest';
import {
  fmtDate,
  fmtInt,
  fmtNum,
  fmtPercent,
  fmtPercentValue,
  tagClass,
  tagText,
} from './dashFormat';

describe('numeric formatters', () => {
  it('formats invalid integers as an em dash', () => {
    expect(fmtInt('abc')).toBe('—');
    expect(fmtInt(undefined)).toBe('—');
    expect(fmtInt(Number.NaN)).toBe('—');
  });

  it('rounds integers and adds a thousands separator', () => {
    expect(fmtInt(1234.6)).toBe('1,235');
  });

  it('formats numbers with two decimal places and thousands separators by default', () => {
    expect(fmtNum(1234.5)).toBe('1,234.50');
  });

  it('uses the requested number of decimal places', () => {
    expect(fmtNum(12.345, 1)).toBe('12.3');
  });

  it('formats invalid numbers as an em dash and preserves null as numeric zero', () => {
    expect(fmtNum('abc')).toBe('—');
    expect(fmtNum(Number.NaN)).toBe('—');
    // Number(null) is 0; this test records the current formatter behavior.
    expect(fmtNum(null)).toBe('0.00');
    expect(fmtInt(null)).toBe('0');
  });
});

describe('percentage formatters', () => {
  it('converts a 0-1 ratio to a percentage', () => {
    expect(fmtPercent(0.123)).toBe('12.3%');
  });

  it('formats an existing 0-100 percentage value without scaling', () => {
    expect(fmtPercentValue(12.3)).toBe('12.3%');
  });

  it('keeps the ratio and percentage-value functions semantically distinct', () => {
    expect(fmtPercent(12.3)).not.toBe('12.3%');
    expect(fmtPercentValue(0.123)).not.toBe('12.3%');
  });

  it('formats a ratio of one as one hundred percent', () => {
    expect(fmtPercent(1)).toBe('100.0%');
  });
});

describe('date and status formatters', () => {
  it('formats a date as MM-DD and returns an empty string for an empty value', () => {
    expect(fmtDate('2026-10-10')).toBe('10-10');
    expect(fmtDate('')).toBe('');
  });

  it('maps all known statuses to tag classes and uses the default for unknown values', () => {
    expect(tagClass('HIGH')).toBe('d-tag--pending');
    expect(tagClass('MEDIUM')).toBe('d-tag--processing');
    expect(tagClass('LOW')).toBe('d-tag--low');
    expect(tagClass('PENDING')).toBe('d-tag--pending');
    expect(tagClass('PROCESSING')).toBe('d-tag--processing');
    expect(tagClass('RESOLVED')).toBe('d-tag--resolved');
    expect(tagClass('OTHER')).toBe('d-tag--ok');
  });

  it('maps known statuses to Chinese text and preserves unknown values', () => {
    expect(tagText('HIGH')).toBe('高危');
    expect(tagText('MEDIUM')).toBe('中危');
    expect(tagText('LOW')).toBe('低危');
    expect(tagText('PENDING')).toBe('待处置');
    expect(tagText('PROCESSING')).toBe('处理中');
    expect(tagText('RESOLVED')).toBe('已处置');
    expect(tagText('OTHER')).toBe('OTHER');
    expect(tagText(null)).toBe('—');
    expect(tagText('')).toBe('');
  });

  it('handles lowercase status values', () => {
    expect(tagClass('high')).toBe('d-tag--pending');
    expect(tagText('resolved')).toBe('已处置');
  });
});
