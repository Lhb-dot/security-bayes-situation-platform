// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { keepScroll } from './scrollAnchor';
import { deferred } from '@/test/queryFixtures';

let anchor: HTMLDivElement;
let height: number;
beforeEach(() => {
  anchor = document.createElement('div');
  anchor.style.overflowY = 'auto';
  document.body.append(anchor);
  height = 1000;
  Object.defineProperties(anchor, { scrollHeight: { get: () => height }, clientHeight: { value: 500 } });
  anchor.scrollTop = 480;
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => { callback(0); return 1; });
});
afterEach(() => { anchor.remove(); vi.unstubAllGlobals(); });

describe('scroll anchoring with request validity', () => {
  it('preserves distance from the bottom for an active page', async () => {
    await keepScroll(() => { height = 1200; }, anchor);
    expect(anchor.scrollTop).toBe(680);
  });

  it('does not restore an obsolete page after navigation', async () => {
    const wait = deferred<void>();
    let current = true;
    const request = keepScroll(() => wait.promise, anchor, () => current);
    current = false;
    height = 1200;
    anchor.scrollTop = 100;
    wait.resolve();
    await request;
    expect(anchor.scrollTop).toBe(100);
  });

  it('checks validity again before restoring the final frame', async () => {
    let current = true;
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      current = false;
      anchor.scrollTop = 100;
      callback(0);
      return 1;
    });
    await keepScroll(() => { height = 1200; }, anchor, () => current);
    expect(anchor.scrollTop).toBe(100);
  });

  it('preserves action errors even if the page is no longer current', async () => {
    await expect(keepScroll(() => { throw new Error('failed'); }, anchor, () => false)).rejects.toThrow('failed');
  });
});
