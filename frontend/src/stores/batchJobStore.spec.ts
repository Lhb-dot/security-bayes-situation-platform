import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getInferenceBatchJob, listInferenceBatchJobs } from '@/api/inferenceRecordApi';
import type { BatchInferenceJob } from '@/api/inferenceRecordApi';
import { ElNotification } from 'element-plus';
import { useBatchJobStore } from './batchJobStore';

const account = vi.hoisted(() => ({ id: 'a' as string | null }));
vi.mock('./jobHelpers', () => ({ currentUid: () => account.id }));
vi.mock('@/utils/jobSeen', () => ({ readSeenIds: () => new Set(), markSeenIds: () => new Set() }));
vi.mock('element-plus', () => ({ ElNotification: vi.fn() }));
vi.mock('@/api/inferenceRecordApi', () => ({ getInferenceBatchJob: vi.fn(), listInferenceBatchJobs: vi.fn() }));
const deferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};
const query = vi.mocked(getInferenceBatchJob);
const list = vi.mocked(listInferenceBatchJobs);
const view = (status: BatchInferenceJob['status'] = 'RUNNING'): BatchInferenceJob => ({
  job_id: 'batch', model_version_id: 7, status, total: 10, processed: 4,
  succeeded: 4, failed: 0, risk_count: 2, error: null, created_at: Date.now() / 1000,
  truncated: false, result: status === 'DONE'
    ? { total: 10, succeeded: 8, failed: 2, risk_count: 3, items: [] } : null,
});
let store: ReturnType<typeof useBatchJobStore>;
beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  account.id = 'a';
  setActivePinia(createPinia());
  store = useBatchJobStore();
  query.mockResolvedValue(view());
  list.mockResolvedValue([]);
});
afterEach(() => { store.reset(); vi.useRealTimers(); });

describe('batch polling integration', () => {
  it('keeps progress and result available across page changes, notifying completion once', async () => {
    store.track('batch', 7, '批量任务', 10);
    await store._tick();
    expect(store.activeJob?.processed).toBe(4);
    query.mockResolvedValue(view('DONE'));
    await vi.advanceTimersByTimeAsync(1000);
    expect(store.lastResult?.result.succeeded).toBe(8);
    expect(store.completedTick).toBe(1);
    expect(store.finishedJobs).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(3000);
    expect(ElNotification).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(['success', 'failure'])('does not restore old results or errors after reset (%s)', async (outcome) => {
    const old = deferred<BatchInferenceJob>();
    const fresh = deferred<BatchInferenceJob>();
    query.mockReturnValueOnce(old.promise).mockReturnValue(fresh.promise);
    store.track('old', 7, '旧批量', 10);
    await vi.advanceTimersByTimeAsync(0);
    const tick = store._tick();
    account.id = 'b';
    store.reset();
    store.track('new', 8, '新批量', 10);
    await vi.advanceTimersByTimeAsync(0);
    if (outcome === 'success') old.resolve(view('DONE'));
    else old.reject(new Error('old error'));
    await tick;
    await vi.advanceTimersByTimeAsync(2000);
    expect(query).toHaveBeenCalledTimes(2);
    expect(store.lastResult).toBeNull();
    expect(store.completedTick).toBe(0);
    expect(ElNotification).not.toHaveBeenCalled();
    fresh.resolve({ ...view('DONE'), job_id: 'new' });
    await store._tick();
    expect(store.lastResult?.jobId).toBe('new');
    expect(store.completedTick).toBe(1);
  });

  it('discards restoration arriving after logout and resets prior result state', async () => {
    const wait = deferred<Awaited<ReturnType<typeof listInferenceBatchJobs>>>();
    list.mockReturnValue(wait.promise);
    const restore = store.resumePending();
    account.id = null;
    store.reset();
    wait.resolve([view()]);
    await restore;
    expect(store.jobs).toEqual([]);
    expect(store.lastResult).toBeNull();
    expect(query).not.toHaveBeenCalled();
  });

  it('recovers after a query failure and preserves failure notification semantics', async () => {
    query.mockRejectedValueOnce(new Error('offline'));
    store.track('batch', 7, '失败批量', 10);
    await store._tick();
    expect(store.running).toBe(true);
    expect(store.activeJob?.error).toBe('offline');
    expect(ElNotification).not.toHaveBeenCalled();
    query.mockResolvedValue({ ...view('FAILED'), error: 'invalid sample' });
    await vi.advanceTimersByTimeAsync(1000);
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'error', duration: 0 }));
    expect(store.completedTick).toBe(0);
  });

  it('restores elapsed time and still uses a 40 minute warning timeout', async () => {
    list.mockResolvedValue([{ ...view(), created_at: (Date.now() - 40 * 60 * 1000) / 1000 }]);
    await store.resumePending();
    await store._tick();
    expect(store.jobs).toEqual([]);
    expect(query).not.toHaveBeenCalled();
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'warning' }));
  });
});
