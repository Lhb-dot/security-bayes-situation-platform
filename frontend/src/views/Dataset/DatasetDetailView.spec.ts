// @vitest-environment jsdom
import { createApp, nextTick, reactive } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DatasetDetailView from './DatasetDetailView.vue';
import { getDatasetFields, getDatasetList, getDatasetPreview } from '@/api/datasetApi';
import { useDatasetStore } from '@/stores/datasetStore';
import { useUserStore } from '@/stores/userStore';
import { dataset, deferred, field, preview, user } from '@/test/queryFixtures';
import type { DatasetField } from '@/types/security';

const mocks = vi.hoisted(() => ({ route: { params: { datasetId: '1' }, query: {} } }));
vi.mock('vue-router', () => ({ useRoute: () => mocks.route, useRouter: () => ({ back: vi.fn() }) }));
vi.mock('@/stores/scenarioStore', () => ({ useScenarioStore: () => ({
  fetchScenarioList: vi.fn(async () => {}), scenarioById: () => ({ name: '网络安全' }),
}) }));
vi.mock('@/api/datasetApi');
vi.mock('@/utils/scrollChain', () => ({ attachOuterFirstWheel: () => vi.fn() }));
const flush = async () => { for (let i = 0; i < 16; i += 1) await Promise.resolve(); await nextTick(); };
let app: ReturnType<typeof createApp>;
let pinia: ReturnType<typeof createPinia>;
let host: HTMLDivElement;
beforeEach(() => {
  vi.resetAllMocks();
  mocks.route = reactive({ params: { datasetId: '1' }, query: {} });
  pinia = createPinia();
  setActivePinia(pinia);
  useUserStore().currentUser = user();
  vi.mocked(getDatasetList).mockResolvedValue([dataset('1'), dataset('2')]);
  vi.mocked(getDatasetFields).mockResolvedValue([field('current_field')]);
  vi.mocked(getDatasetPreview).mockResolvedValue(preview());
  host = document.createElement('div');
  document.body.append(host);
  app = createApp(DatasetDetailView).use(pinia);
});
afterEach(() => { app.unmount(); disposePinia(pinia); host.remove(); });

describe('dataset detail ownership', () => {
  it.each(['success', 'failure'])('ignores old-route field %s while a new detail loads', async (outcome) => {
    const old = deferred<DatasetField[]>();
    const fresh = deferred<DatasetField[]>();
    vi.mocked(getDatasetFields).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    app.mount(host);
    await flush();
    mocks.route.params.datasetId = '2';
    await flush();
    if (outcome === 'success') old.resolve([field('old_field')]);
    else old.reject(new Error('old failure'));
    await flush();
    expect(host.textContent).toContain('正在加载数据集信息');
    expect(host.textContent).not.toContain('old failure');
    fresh.resolve([field('current_field')]);
    await flush();
    expect(host.querySelector('h2')?.textContent).toBe('数据集2');
    expect(host.textContent).toContain('current_field');
    expect(host.textContent).not.toContain('old_field');
  });

  it('keeps fields from its own request when another view writes the store', async () => {
    app.mount(host);
    await flush();
    vi.mocked(getDatasetFields).mockResolvedValueOnce([field('foreign_field')]);
    await useDatasetStore().fetchFields('other');
    await flush();
    expect(host.textContent).toContain('current_field');
    expect(host.textContent).not.toContain('foreign_field');
  });

  it('does not start fields loading after an obsolete list resolves on an unmounted page', async () => {
    const wait = deferred<ReturnType<typeof dataset>[]>();
    vi.mocked(getDatasetList).mockReturnValueOnce(wait.promise);
    app.mount(host);
    app.unmount();
    wait.resolve([dataset()]);
    await flush();
    expect(getDatasetFields).not.toHaveBeenCalled();
    expect(useDatasetStore().datasets).toEqual([]);
  });
});
