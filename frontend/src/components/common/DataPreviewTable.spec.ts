// @vitest-environment jsdom
import { createApp, h, nextTick, reactive } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import DataPreviewTable from './DataPreviewTable.vue';
import { getDatasetPreview } from '@/api/datasetApi';
import { useDatasetStore } from '@/stores/datasetStore';
import { useUserStore } from '@/stores/userStore';
import { keepScroll } from '@/utils/scrollAnchor';
import { deferred, preview, user } from '@/test/queryFixtures';
import type { DataPreview } from '@/types/security';

vi.mock('@/api/datasetApi');
vi.mock('@/utils/scrollChain', () => ({ attachOuterFirstWheel: () => vi.fn() }));
vi.mock('@/utils/scrollAnchor', () => ({ keepScroll: vi.fn(async (action: () => unknown) => { await action(); }) }));
const flush = async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); await nextTick(); };
let pinia: ReturnType<typeof createPinia>;
let app: ReturnType<typeof createApp>;
let host: HTMLDivElement;
let props: { id: string; pageSize: number };
beforeEach(() => {
  vi.resetAllMocks();
  pinia = createPinia();
  setActivePinia(pinia);
  useUserStore().currentUser = user();
  props = reactive({ id: '1', pageSize: 50 });
  host = document.createElement('div');
  document.body.append(host);
  vi.mocked(getDatasetPreview).mockImplementation(async (_, params) => preview(params.page));
  app = createApp({ render: () => h(DataPreviewTable, { datasetId: props.id, pageSize: props.pageSize, labelField: '' }) });
  app.use(pinia);
});
afterEach(() => { app.unmount(); disposePinia(pinia); host.remove(); });

describe('dataset preview request ownership', () => {
  it.each(['success', 'failure'])('ignores old-dataset %s without ending the new request', async (outcome) => {
    const old = deferred<DataPreview>();
    const fresh = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    app.mount(host);
    props.id = '2';
    await flush();
    if (outcome === 'success') old.resolve(preview(1, 999));
    else old.reject(new Error('old failure'));
    await flush();
    expect(host.textContent).toContain('正在加载');
    expect(host.textContent).not.toContain('old failure');
    fresh.resolve(preview(1, 222));
    await flush();
    expect(host.textContent).toContain('222');
    expect(host.textContent).not.toContain('999');
    expect(host.querySelector('.loader')).toBeNull();
  });

  it('keeps its own rows when another consumer changes shared preview', async () => {
    app.mount(host);
    await flush();
    vi.mocked(getDatasetPreview).mockResolvedValueOnce(preview(1, 999));
    await useDatasetStore().fetchPreview('other', { page: 1, page_size: 50 });
    await flush();
    expect(host.textContent).toContain('100');
    expect(host.textContent).not.toContain('999');
  });

  it('accepts only the last pagination response and retains scroll anchoring', async () => {
    app.mount(host);
    await flush();
    const second = deferred<DataPreview>();
    const third = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(second.promise).mockReturnValueOnce(third.promise);
    const pages = host.querySelectorAll<HTMLElement>('.el-pager li.number');
    pages[1].click();
    await flush();
    pages[2].click();
    await flush();
    third.resolve(preview(3));
    await flush();
    second.resolve(preview(2));
    await flush();
    expect(host.textContent).toContain('300');
    expect(host.textContent).not.toContain('200');
    expect(host.querySelector('.el-pager li.is-active')?.textContent).toBe('3');
    expect(keepScroll).toHaveBeenCalledTimes(2);
  });

  it('offers retry for a current failure and uses the requested page', async () => {
    vi.mocked(getDatasetPreview).mockRejectedValueOnce(new Error('offline'));
    app.mount(host);
    await flush();
    expect(host.textContent).toContain('offline');
    host.querySelector<HTMLButtonElement>('.data-preview__state--error button')!.click();
    await flush();
    expect(host.textContent).toContain('100');
    expect(getDatasetPreview).toHaveBeenLastCalledWith('1', { page: 1, page_size: 50 });
  });

  it('discards a response after unmount without changing shared preview', async () => {
    const wait = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(wait.promise);
    app.mount(host);
    app.unmount();
    wait.resolve(preview());
    await flush();
    expect(useDatasetStore().preview).toBeNull();
  });

  it('reloads after account changes and rejects the previous account response', async () => {
    const old = deferred<DataPreview>();
    const fresh = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    app.mount(host);
    useUserStore().currentUser = null;
    useUserStore().currentUser = user('b');
    await flush();
    fresh.resolve(preview(1, 222));
    await flush();
    old.resolve(preview(1, 999));
    await flush();
    expect(host.textContent).toContain('222');
    expect(host.textContent).not.toContain('999');
  });
});
