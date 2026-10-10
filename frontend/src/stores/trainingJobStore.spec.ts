import { createPinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getModelVersionDetail, listTrainingJobs } from '@/api/trainingApi';
import { ElNotification } from 'element-plus';
import { useTrainingJobStore } from './trainingJobStore';

const account = vi.hoisted(() => ({ id: 'a' as string | null }));
vi.mock('./jobHelpers', () => ({ currentUid: () => account.id }));
vi.mock('@/utils/jobSeen', () => ({ readSeenIds: () => new Set(), markSeenIds: () => new Set() }));
vi.mock('element-plus', () => ({ ElNotification: vi.fn() }));
vi.mock('@/api/trainingApi', () => ({ getModelVersionDetail: vi.fn(), listTrainingJobs: vi.fn() }));

const deferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};
const detail = vi.mocked(getModelVersionDetail);
const list = vi.mocked(listTrainingJobs);
let store: ReturnType<typeof useTrainingJobStore>;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date('2026-10-10T16:00:00Z'));
  vi.resetAllMocks();
  account.id = 'a';
  setActivePinia(createPinia());
  store = useTrainingJobStore();
  detail.mockResolvedValue({ id: 1, status: 'TRAINING' });
  list.mockResolvedValue([]);
});
afterEach(() => { store.reset(); vi.useRealTimers(); });

describe('training polling integration', () => {
  it('queries only once while slow, then stops and notifies once when complete', async () => {
    const wait = deferred<Awaited<ReturnType<typeof getModelVersionDetail>>>();
    detail.mockReturnValue(wait.promise);
    store.track(1, '网络训练');
    store.startPolling();
    await vi.advanceTimersByTimeAsync(5000);
    expect(detail).toHaveBeenCalledTimes(1);
    wait.resolve({ id: 1, status: 'DRAFT' });
    await store._tick();
    expect(store.finishedJobs[0]?.status).toBe('DRAFT');
    expect(ElNotification).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(5000);
    expect(detail).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each(['success', 'failure'])('ignores an old %s after reset and preserves the new polling lock', async (outcome) => {
    const old = deferred<Awaited<ReturnType<typeof getModelVersionDetail>>>();
    const fresh = deferred<Awaited<ReturnType<typeof getModelVersionDetail>>>();
    detail.mockReturnValueOnce(old.promise).mockReturnValue(fresh.promise);
    store.track(1, '旧账号');
    await vi.advanceTimersByTimeAsync(0);
    const oldTick = store._tick();
    account.id = 'b';
    store.reset();
    store.track(2, '新账号');
    await vi.advanceTimersByTimeAsync(0);
    if (outcome === 'success') old.resolve({ id: 1, status: 'DRAFT' });
    else old.reject(new Error('old failure'));
    await oldTick;
    await vi.advanceTimersByTimeAsync(3000);
    expect(detail).toHaveBeenCalledTimes(2);
    expect(store.jobs.map((job) => job.modelVersionId)).toEqual([2]);
    expect(store.jobs[0]?.error).toBeNull();
    expect(ElNotification).not.toHaveBeenCalled();
    fresh.resolve({ id: 2, status: 'DRAFT' });
    await store._tick();
    expect(ElNotification).toHaveBeenCalledTimes(1);
  });

  it('ignores restoration that returns after a newer restoration', async () => {
    const old = deferred<Awaited<ReturnType<typeof listTrainingJobs>>>();
    list.mockReturnValueOnce(old.promise).mockResolvedValueOnce([{ id: 2, status: 'DRAFT' }]);
    const first = store.resumePending();
    await store.resumePending();
    old.resolve([{ id: 1, status: 'TRAINING' }]);
    await first;
    expect(store.jobs.map((job) => job.modelVersionId)).toEqual([2]);
    expect(detail).not.toHaveBeenCalled();
  });

  it('resumes polling with server time after refresh, preserving unseen completed jobs', async () => {
    list.mockResolvedValue([
      { id: 1, status: 'TRAINING', trained_at: '2026-10-10 23:58:00' },
      { id: 2, status: 'DRAFT', trained_at: '2026-10-10 23:57:00' },
    ]);
    await store.resumePending();
    await store._tick();
    expect(store.activeJob?.elapsed).toBe(120);
    expect(store.unseenJobs.map((job) => job.modelVersionId)).toEqual([2]);
    expect(ElNotification).not.toHaveBeenCalled();
    detail.mockResolvedValue({ id: 1, status: 'DRAFT' });
    await vi.advanceTimersByTimeAsync(1000);
    expect(store.running).toBe(false);
    expect(store.unseenJobs).toHaveLength(2);
    expect(ElNotification).toHaveBeenCalledTimes(1);
  });

  it('suppresses an account-changed response even before the UI resets its Store', async () => {
    const wait = deferred<Awaited<ReturnType<typeof getModelVersionDetail>>>();
    detail.mockReturnValue(wait.promise);
    store.track(1, '旧账号');
    await vi.advanceTimersByTimeAsync(0);
    const tick = store._tick();
    account.id = null;
    wait.resolve({ id: 1, status: 'FAILED', evaluation_metrics: { error: 'failed' } });
    await tick;
    expect(store.jobs[0]?.status).toBe('TRAINING');
    expect(ElNotification).not.toHaveBeenCalled();
  });

  it('retains training terminal policies, one-time notification and the 65 minute timeout', async () => {
    detail.mockResolvedValue({ id: 1, status: 'PUBLISHED' });
    store.track(1, '已发布');
    await vi.advanceTimersByTimeAsync(3000);
    expect(store.running).toBe(true);
    expect(ElNotification).toHaveBeenCalledTimes(1);
    store.reset();
    vi.mocked(ElNotification).mockClear();
    detail.mockClear();
    store.track(2, '超时', 'TRAINING', Date.now() - 65 * 60 * 1000);
    await store._tick();
    expect(store.jobs).toEqual([]);
    expect(detail).not.toHaveBeenCalled();
    expect(ElNotification).toHaveBeenCalledWith(expect.objectContaining({ type: 'warning' }));
  });
});
