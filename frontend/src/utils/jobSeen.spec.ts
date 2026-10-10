// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from 'vitest';
import { markSeenIds, onSeenIdsChange, readSeenIds } from './jobSeen';

const STORAGE_KEY = 'bayes_seen_job_ids';

beforeEach(() => {
  window.localStorage.clear();
});

describe('jobSeen local storage', () => {
  it('returns an empty set for an account that has not been marked', () => {
    expect(readSeenIds('account-1')).toEqual(new Set());
  });

  it('reads ids after marking them for the same account', () => {
    markSeenIds('account-1', ['job-a', 'job-b']);
    expect(readSeenIds('account-1')).toEqual(new Set(['job-a', 'job-b']));
  });

  it('does not add duplicate ids when the same ids are marked again', () => {
    markSeenIds('account-1', ['job-a', 'job-b']);
    markSeenIds('account-1', ['job-a', 'job-b']);
    expect(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}')['account-1']).toEqual(['job-a', 'job-b']);
  });

  it('keeps account buckets isolated', () => {
    markSeenIds('account-a', ['job-a']);
    expect(readSeenIds('account-b')).toEqual(new Set());
    expect(readSeenIds('account-a')).toEqual(new Set(['job-a']));
  });

  it('stores a null uid in the anonymous bucket, separate from real accounts', () => {
    markSeenIds(null, ['anonymous-job']);
    markSeenIds('account-1', ['account-job']);
    expect(readSeenIds(null)).toEqual(new Set(['anonymous-job']));
    expect(readSeenIds('account-1')).toEqual(new Set(['account-job']));
  });

  it('keeps only the newest 400 ids for an account', () => {
    const ids = Array.from({ length: 401 }, (_, index) => `job-${index + 1}`);
    markSeenIds('account-1', ids);
    const seen = readSeenIds('account-1');
    expect(seen.size).toBe(400);
    expect(seen.has('job-1')).toBe(false);
    expect(seen.has('job-2')).toBe(true);
    expect(seen.has('job-401')).toBe(true);
  });

  it('keeps at most eight account buckets and retains the most recently used account', () => {
    for (let index = 1; index <= 9; index += 1) {
      markSeenIds(`account-${index}`, [`job-${index}`]);
    }
    const buckets = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}') as Record<string, string[]>;
    expect(Object.keys(buckets)).toHaveLength(8);
    expect(buckets['account-1']).toBeUndefined();
    expect(buckets['account-9']).toEqual(['job-9']);
    expect(Object.keys(buckets).at(-1)).toBe('account-9');
  });

  it('reads the legacy single-account structure', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ uid: '1', ids: ['a', 'b'] }));
    expect(readSeenIds('1')).toEqual(new Set(['a', 'b']));
  });

  it('discards a legacy structure with an empty or non-string uid', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ uid: '', ids: ['a'] }));
    expect(readSeenIds(null)).toEqual(new Set());
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ uid: 1, ids: ['a'] }));
    expect(readSeenIds('1')).toEqual(new Set());
  });

  it('returns an empty set for invalid JSON without throwing', () => {
    window.localStorage.setItem(STORAGE_KEY, '{');
    expect(() => readSeenIds('account-1')).not.toThrow();
    expect(readSeenIds('account-1')).toEqual(new Set());
  });

  it('filters malformed buckets and non-string ids', () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ 'account-1': ['valid', 2, null, ''], 'account-2': 'invalid' }));
    expect(readSeenIds('account-1')).toEqual(new Set(['valid']));
    expect(readSeenIds('account-2')).toEqual(new Set());
  });

  it('notifies subscribers after ids are marked', () => {
    let calls = 0;
    const unsubscribe = onSeenIdsChange(() => { calls += 1; });
    markSeenIds('account-1', ['job-a']);
    unsubscribe();
    expect(calls).toBe(1);
  });

  it('does not notify a subscriber after it has unsubscribed', () => {
    let calls = 0;
    const unsubscribe = onSeenIdsChange(() => { calls += 1; });
    unsubscribe();
    markSeenIds('account-1', ['job-a']);
    expect(calls).toBe(0);
  });
});
