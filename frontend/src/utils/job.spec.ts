import { describe, expect, it } from 'vitest';
import { createIsTerminal, keepUnexpiredJobs, messageOf, trimFinishedJobs } from './job';

interface Job {
  id: string;
  status: string;
  startedAt: number;
}

const isTerminal = createIsTerminal<Job>(['DONE', 'FAILED']);
const keyOf = (job: Job) => job.id;

describe('finished task retention', () => {
  it('drops the oldest finished tasks without changing running tasks or display order', () => {
    const jobs: Job[] = [
      { id: 'new', status: 'DONE', startedAt: 30 },
      { id: 'running', status: 'RUNNING', startedAt: 0 },
      { id: 'old', status: 'FAILED', startedAt: 10 },
      { id: 'middle', status: 'DONE', startedAt: 20 },
    ];
    const kept = trimFinishedJobs(jobs, isTerminal, keyOf, 2);
    expect(kept.map(keyOf)).toEqual(['new', 'running', 'middle']);
    expect(kept[1]).toBe(jobs[1]);
    expect(jobs.map(keyOf)).toEqual(['new', 'running', 'old', 'middle']);
  });

  it('keeps the original array when it is within the finished-task limit', () => {
    const jobs: Job[] = [{ id: 'one', status: 'DONE', startedAt: 10 }];
    expect(trimFinishedJobs(jobs, isTerminal, keyOf, 1)).toBe(jobs);
  });

  it('keeps the cutoff boundary and old running tasks while dropping expired finished tasks', () => {
    const jobs: Job[] = [
      { id: 'old', status: 'DONE', startedAt: 9 },
      { id: 'boundary', status: 'FAILED', startedAt: 10 },
      { id: 'running', status: 'RUNNING', startedAt: 1 },
      { id: 'unknown', status: 'PUBLISHED', startedAt: 1 },
    ];
    expect(keepUnexpiredJobs(jobs, isTerminal, 10).map(keyOf)).toEqual(['boundary', 'running', 'unknown']);
  });

  it('does not apply the batch terminal statuses to training tasks', () => {
    const isTrainingTerminal = createIsTerminal<Job>(['DRAFT', 'FAILED']);
    expect(isTrainingTerminal({ id: 'trained', status: 'DRAFT', startedAt: 0 })).toBe(true);
    expect(isTerminal({ id: 'trained', status: 'DRAFT', startedAt: 0 })).toBe(false);
  });
});

describe('task error messages', () => {
  it('preserves an error message and falls back for missing or non-Error values', () => {
    expect(messageOf(new Error('状态查询失败'), 'fallback')).toBe('状态查询失败');
    expect(messageOf(new Error(''), 'fallback')).toBe('fallback');
    expect(messageOf({ message: 'untrusted' }, 'fallback')).toBe('fallback');
  });
});
