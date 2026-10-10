// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';
import { createPollTimer, filterExpired, trimFinished } from './jobPollingCore';

afterEach(() => {
  vi.useRealTimers();
});

describe('createPollTimer', () => {
  it('starts once, ticks immediately, and stops idempotently', async () => {
    vi.useFakeTimers();
    let ticks = 0;
    const poll = createPollTimer(1000, () => { ticks += 1; });

    poll.start();
    poll.start();
    expect(poll.active).toBe(true);
    expect(ticks).toBe(1);

    await vi.advanceTimersByTimeAsync(1000);
    expect(ticks).toBe(2);

    poll.stop();
    poll.stop();
    expect(poll.active).toBe(false);
    await vi.advanceTimersByTimeAsync(1000);
    expect(ticks).toBe(2);
  });
});

describe('trimFinished', () => {
  type Job = { id: string; startedAt: number; status: 'RUNNING' | 'DONE' };
  const isTerminal = (job: Job) => job.status === 'DONE';

  it('drops only the oldest terminal jobs and preserves the order of the rest', () => {
    const jobs: Job[] = [
      { id: 'oldest', startedAt: 1, status: 'DONE' },
      { id: 'running', startedAt: 0, status: 'RUNNING' },
      { id: 'middle', startedAt: 2, status: 'DONE' },
      { id: 'newest', startedAt: 3, status: 'DONE' },
    ];

    const kept = trimFinished(jobs, isTerminal, (job) => job.id, (job) => job.startedAt, 2);
    expect(kept.map((job) => job.id)).toEqual(['running', 'middle', 'newest']);
  });

  it('returns the original array when the terminal count is within the limit', () => {
    const jobs: Job[] = [{ id: 'done', startedAt: 1, status: 'DONE' }];
    expect(trimFinished(jobs, isTerminal, (job) => job.id, (job) => job.startedAt, 1)).toBe(jobs);
  });
});

describe('filterExpired', () => {
  type Job = { id: string; startedAt: number; status: 'RUNNING' | 'DONE' };
  const isTerminal = (job: Job) => job.status === 'DONE';

  it('removes expired terminal jobs, keeps jobs at the cutoff, and keeps running jobs', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-10T12:00:00.000Z'));
    const now = Date.now();
    const jobs: Job[] = [
      { id: 'expired', startedAt: now - 86_400_001, status: 'DONE' },
      { id: 'cutoff', startedAt: now - 86_400_000, status: 'DONE' },
      { id: 'running', startedAt: now - 172_800_000, status: 'RUNNING' },
    ];

    const kept = filterExpired(jobs, isTerminal, (job) => job.startedAt, 86_400_000);
    expect(kept.map((job) => job.id)).toEqual(['cutoff', 'running']);
  });

  it('returns all jobs when none of the terminal jobs have expired', () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-10-10T12:00:00.000Z'));
    const jobs: Job[] = [{ id: 'recent', startedAt: Date.now(), status: 'DONE' }];
    expect(filterExpired(jobs, isTerminal, (job) => job.startedAt, 86_400_000)).toEqual(jobs);
  });
});
