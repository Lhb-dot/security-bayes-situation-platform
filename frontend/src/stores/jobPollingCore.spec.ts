import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createJobPoller } from './jobPollingCore';
import type { PollContext } from './jobPollingCore';

const deferred = () => {
  let resolve!: () => void;
  const promise = new Promise<void>((done) => { resolve = done; });
  return { promise, resolve };
};

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('job polling lifecycle', () => {
  it('starts immediately once and skips interval ticks while a request is slow', async () => {
    const wait = deferred();
    const query = vi.fn(() => wait.promise);
    const poll = createJobPoller(1000, query, () => 'a');
    poll.start();
    poll.start();
    await vi.advanceTimersByTimeAsync(5000);
    expect(query).toHaveBeenCalledTimes(1);
    wait.resolve();
    await poll.tick();
    await vi.advanceTimersByTimeAsync(1000);
    expect(query).toHaveBeenCalledTimes(2);
    poll.stop();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('allows a restart before an old request ends without unlocking the new request', async () => {
    const old = deferred();
    const fresh = deferred();
    const contexts: PollContext[] = [];
    const query = vi.fn((context: PollContext) => {
      contexts.push(context);
      return contexts.length === 1 ? old.promise : fresh.promise;
    });
    const poll = createJobPoller(1000, query, () => 'a');
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    const oldTick = poll.tick();
    poll.stop();
    expect(contexts[0]!.isCurrent()).toBe(false);
    poll.start();
    await vi.advanceTimersByTimeAsync(0);
    old.resolve();
    await oldTick;
    await vi.advanceTimersByTimeAsync(4000);
    expect(query).toHaveBeenCalledTimes(2);
    expect(contexts[1]!.isCurrent()).toBe(true);
    fresh.resolve();
    await poll.tick();
    poll.stop();
  });

  it('keeps session work valid when idle polling stops, but invalidates it on reset or owner change', () => {
    let owner: string | null = 'a';
    const poll = createJobPoller(1000, async () => {}, () => owner);
    const download = poll.capture();
    poll.stop();
    expect(download.isCurrent()).toBe(true);
    owner = 'b';
    expect(download.isCurrent()).toBe(false);
    const restore = poll.capture();
    poll.reset();
    expect(restore.isCurrent()).toBe(false);
  });

  it('releases the lock after a failed tick so later polling can recover', async () => {
    const query = vi.fn().mockRejectedValueOnce(new Error('unexpected')).mockResolvedValue(undefined);
    const poll = createJobPoller(1000, query, () => 'a');
    await expect(poll.tick()).rejects.toThrow('unexpected');
    await poll.tick();
    expect(query).toHaveBeenCalledTimes(2);
  });
});
