import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '@/api/datasetApi';
import { useUserStore } from './userStore';
import { useDatasetStore } from './datasetStore';
import { dataset, deferred, field, preview, user } from '@/test/queryFixtures';
import type { DatasetVersion } from '@/types/security';

vi.mock('@/api/datasetApi');
let pinia: ReturnType<typeof createPinia>;
let store: ReturnType<typeof useDatasetStore>;
let users: ReturnType<typeof useUserStore>;
beforeEach(() => {
  vi.resetAllMocks();
  pinia = createPinia();
  setActivePinia(pinia);
  users = useUserStore();
  users.currentUser = user();
  store = useDatasetStore();
});
afterEach(() => disposePinia(pinia));

const queryCase = <T>(run: () => Promise<T>, install: (wait: Promise<T>) => void, value: T, stale: T) => {
  const old = deferred<T>();
  const fresh = deferred<T>();
  install(old.promise);
  install(fresh.promise);
  return { run, old: { resolve: () => old.resolve(stale), reject: old.reject },
    fresh: { resolve: () => fresh.resolve(value) }, value, stale };
};
const cases = {
  datasets: () => queryCase(() => store.fetchDatasets('network_security'),
    (wait) => vi.mocked(api.getDatasetList).mockReturnValueOnce(wait), [dataset()], []),
  fields: () => queryCase(() => store.fetchFields('1', 'v1'),
    (wait) => vi.mocked(api.getDatasetFields).mockReturnValueOnce(wait), [field()], [field('old')]),
  preview: () => queryCase(() => store.fetchPreview('1', { page: 1, page_size: 50 }),
    (wait) => vi.mocked(api.getDatasetPreview).mockReturnValueOnce(wait), preview(), preview(2)),
  versions: () => queryCase(() => store.fetchVersions('1'),
    (wait) => vi.mocked(api.getDatasetVersions).mockReturnValueOnce(wait),
    [{ ...dataset(), dataset_version_id: '1-v1', file_path: 'mock.csv' }] as DatasetVersion[], []),
};
const resources = ['datasets', 'fields', 'preview', 'versions'] as const;

describe('dataset query isolation', () => {
  it.each(resources)('%s: returns its own payload and keeps the latest response', async (resource) => {
    const test = cases[resource]();
    const oldRequest = test.run();
    const newRequest = test.run();
    test.fresh.resolve();
    expect(await newRequest).toEqual(test.value);
    const latest = store[resource];
    test.old.resolve();
    expect(await oldRequest).toEqual(test.stale);
    expect(store[resource]).toEqual(latest);
    expect(store.loading).toBe(false);
  });

  it.each(resources)('%s: an obsolete failure cannot end the latest loading', async (resource) => {
    const test = cases[resource]();
    const oldRequest = test.run();
    const failed = expect(oldRequest).rejects.toThrow('old failure');
    const newRequest = test.run();
    test.old.reject(new Error('old failure'));
    await failed;
    expect(store.queries[resource].loading).toBe(true);
    test.fresh.resolve();
    await newRequest;
    expect(store.loading).toBe(false);
  });

  it('keeps loading independent across list, fields, preview and versions', async () => {
    const tests = resources.map((resource) => cases[resource]());
    const requests = tests.map((test) => test.run());
    for (let i = 0; i < tests.length; i += 1) {
      tests[i].old.resolve();
      await requests[i];
      expect(store.queries[resources[i]].loading).toBe(false);
      expect(store.loading).toBe(i < tests.length - 1);
    }
  });

  it('clears a previous resource when dataset/version/page context changes', async () => {
    vi.mocked(api.getDatasetFields).mockResolvedValueOnce([field('old')]);
    await store.fetchFields('1', 'v1');
    const wait = deferred<ReturnType<typeof field>[]>();
    vi.mocked(api.getDatasetFields).mockReturnValueOnce(wait.promise);
    const request = store.fetchFields('2', 'v2');
    expect(store.fields).toEqual([]);
    expect(store.queries.fields.key).toBe(JSON.stringify(['2', 'v2']));
    wait.resolve([field('new')]);
    await request;
    expect(store.fields[0].field_name).toBe('new');
  });

  it('does not write shared results when the requesting page has gone away', async () => {
    const wait = deferred<ReturnType<typeof field>[]>();
    vi.mocked(api.getDatasetFields).mockReturnValueOnce(wait.promise);
    let active = true;
    const request = store.fetchFields('1', 'v1', { isCurrent: () => active });
    active = false;
    wait.resolve([field()]);
    expect(await request).toEqual([field()]);
    expect(store.fields).toEqual([]);
    expect(store.loading).toBe(false);
  });

  it.each(['success', 'failure'])('discards old-session %s after logout and relogin to the same account', async (outcome) => {
    const old = deferred<ReturnType<typeof field>[]>();
    const fresh = deferred<ReturnType<typeof field>[]>();
    vi.mocked(api.getDatasetFields).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    const pending = store.fetchFields('1');
    const handled = pending.catch(() => []);
    users.currentUser = null;
    expect(store.fields).toEqual([]);
    expect(store.loading).toBe(false);
    users.currentUser = user();
    const current = store.fetchFields('1');
    if (outcome === 'success') old.resolve([field('old')]);
    else old.reject(new Error('old session'));
    await handled;
    expect(store.fields).toEqual([]);
    expect(store.queries.fields.loading).toBe(true);
    fresh.resolve([field('new')]);
    await current;
    expect(store.fields[0].field_name).toBe('new');
  });

  it('can recover after a current request fails', async () => {
    vi.mocked(api.getDatasetList).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce([dataset()]);
    await expect(store.fetchDatasets()).rejects.toThrow('offline');
    expect(store.loading).toBe(false);
    await store.fetchDatasets();
    expect(store.datasetsByScenario('network_security')).toEqual([dataset()]);
  });

  it('keeps requests independent between Pinia instances', async () => {
    const old = deferred<ReturnType<typeof field>[]>();
    vi.mocked(api.getDatasetFields).mockReturnValueOnce(old.promise).mockResolvedValueOnce([field('other')]);
    const first = store.fetchFields('1');
    const otherPinia = createPinia();
    const other = useDatasetStore(otherPinia);
    await other.fetchFields('2');
    old.resolve([field('first')]);
    await first;
    expect(store.fields[0].field_name).toBe('first');
    expect(other.fields[0].field_name).toBe('other');
    disposePinia(otherPinia);
  });
});
