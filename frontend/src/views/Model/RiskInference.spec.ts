// @vitest-environment jsdom
import { createApp, nextTick } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import RiskInference from './RiskInference.vue';
import { getScenarioList } from '@/api/scenarioApi';
import { getDatasetFields, getDatasetList, getDatasetPreview } from '@/api/datasetApi';
import { getModelVersionList } from '@/api/modelVersionApi';
import { useDatasetStore } from '@/stores/datasetStore';
import { useUserStore } from '@/stores/userStore';
import { keepScroll } from '@/utils/scrollAnchor';
import { dataset, deferred, field, model, preview, user } from '@/test/queryFixtures';
import type { DataPreview, Dataset, DatasetField } from '@/types/security';
import type { BackendModelVersion } from '@/api/modelVersionApi';
import type { ApiScenario } from '@/api/scenarioApi';

vi.mock('vue-router', () => ({ useRoute: () => ({ query: { port: '443' } }), useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/api/scenarioApi');
vi.mock('@/api/datasetApi');
vi.mock('@/api/modelVersionApi');
vi.mock('@/api/inferenceRecordApi');
vi.mock('@/stores/batchJobStore', () => ({ useBatchJobStore: () => ({ activeJob: null, lastResult: null }) }));
vi.mock('@/utils/scrollAnchor', () => ({ keepScroll: vi.fn(async (action: () => unknown) => { await action(); }) }));
const flush = async () => { for (let i = 0; i < 20; i += 1) await Promise.resolve(); await nextTick(); };
const scenes: ApiScenario[] = [
  { id: 1, code: 'network_security', name: '网络安全', description: null, access_status: 'ACTUAL' },
  { id: 2, code: 'power_system', name: '电力系统', description: null, access_status: 'ACTUAL' },
];
let app: ReturnType<typeof createApp>;
let pinia: ReturnType<typeof createPinia>;
let host: HTMLDivElement;
beforeEach(() => {
  vi.resetAllMocks();
  pinia = createPinia();
  setActivePinia(pinia);
  useUserStore().currentUser = user();
  vi.mocked(getScenarioList).mockResolvedValue(scenes);
  vi.mocked(getDatasetList).mockImplementation(async (params) => params?.scenario_id === 'power_system'
    ? [dataset('3', 'power_system')] : [dataset('1'), dataset('2')]);
  vi.mocked(getModelVersionList).mockImplementation(async (params) => {
    const id = Number(params?.dataset_id);
    return [model(id * 10 + 1, id, { is_default: true }), model(id * 10 + 2, id, { dataset_version: 2 })];
  });
  vi.mocked(getDatasetFields).mockResolvedValue([field()]);
  vi.mocked(getDatasetPreview).mockImplementation(async (_, params) => preview(params.page));
  host = document.createElement('div');
  document.body.append(host);
  app = createApp(RiskInference).use(pinia);
});
afterEach(() => { app.unmount(); disposePinia(pinia); host.remove(); });
const selects = () => host.querySelectorAll<HTMLSelectElement>('.scope-bar select');
const choose = async (select: HTMLSelectElement, value: string) => {
  select.value = value;
  select.dispatchEvent(new Event('change', { bubbles: true }));
  await flush();
};
const mount = async () => { app.mount(host); await flush(); };
const chooseDataset = (id = '1') => choose(selects()[0], id);
const chooseModel = (id: string) => choose(selects()[1], id);

describe('risk inference selection and pagination races', () => {
  it.each(['success', 'failure'])('ignores old-scene %s and preserves new-scene loading', async (outcome) => {
    const old = deferred<Dataset[]>();
    const fresh = deferred<Dataset[]>();
    vi.mocked(getDatasetList).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    await mount();
    host.querySelectorAll<HTMLButtonElement>('.scenario-tab')[1].click();
    await flush();
    if (outcome === 'success') old.resolve([dataset()]);
    else old.reject(new Error('old scene'));
    await flush();
    expect(selects()[0].disabled).toBe(true);
    fresh.resolve([dataset('3', 'power_system')]);
    await flush();
    expect(selects()[0].disabled).toBe(false);
    expect(selects()[0].textContent).toContain('数据集3');
    expect(selects()[0].textContent).not.toContain('数据集1');
  });

  it.each(['success', 'failure'])('ignores old-dataset model %s while the new models load', async (outcome) => {
    const old = deferred<BackendModelVersion[]>();
    const fresh = deferred<BackendModelVersion[]>();
    vi.mocked(getModelVersionList).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    await mount();
    await chooseDataset('1');
    await chooseDataset('2');
    if (outcome === 'success') old.resolve([model(11, 1, { is_default: true })]);
    else old.reject(new Error('old models'));
    await flush();
    expect(selects()[1].textContent).toContain('加载中');
    expect(getDatasetFields).not.toHaveBeenCalled();
    fresh.resolve([model(21, 2, { is_default: true })]);
    await flush();
    expect(selects()[1].value).toBe('21');
    expect(selects()[1].textContent).not.toContain('算法11');
    expect(getDatasetFields).toHaveBeenCalledWith('2', '1');
  });

  it('invalidates model requests on A → B → empty selection', async () => {
    const old = deferred<BackendModelVersion[]>();
    const fresh = deferred<BackendModelVersion[]>();
    vi.mocked(getModelVersionList).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    await mount();
    await chooseDataset('1');
    await chooseDataset('2');
    await chooseDataset('');
    fresh.resolve([model(21, 2, { is_default: true })]);
    old.resolve([model(11, 1, { is_default: true })]);
    await flush();
    expect(selects()[1].value).toBe('');
    expect(selects()[1].textContent).toContain('暂无已发布模型');
    expect(host.querySelector('.source-card')).toBeNull();
    expect(getDatasetFields).not.toHaveBeenCalled();
  });

  it.each(['success', 'failure'])('ignores old-model field %s and keeps new input defaults', async (outcome) => {
    const old = deferred<DatasetField[]>();
    const fresh = deferred<DatasetField[]>();
    vi.mocked(getDatasetFields).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    await mount();
    await chooseDataset();
    await chooseModel('12');
    fresh.resolve([field(), { ...field('protocol'), field_type: 'string', sample_value: 'TCP', enum_values: ['TCP', 'UDP'] },
      { ...field('label'), field_role: '分类标签' }]);
    await flush();
    if (outcome === 'success') old.resolve([field('old_field')]);
    else old.reject(new Error('old fields'));
    await flush();
    host.querySelectorAll<HTMLButtonElement>('.source-tab')[1].click();
    await flush();
    expect(host.querySelector<HTMLInputElement>('.field-group-body input')?.value).toBe('443');
    expect(host.querySelector<HTMLSelectElement>('.field-group-body select')?.value).toBe('TCP');
    expect(host.textContent).toContain('共 2 个输入特征');
    expect(host.textContent).not.toContain('old_field');
    expect(getDatasetPreview).toHaveBeenCalledTimes(1);
  });

  it('uses returned fields when another query replaces the shared fields before the continuation', async () => {
    const wait = deferred<DatasetField[]>();
    vi.mocked(getDatasetFields).mockReturnValueOnce(wait.promise);
    await mount();
    await chooseDataset();
    wait.resolve([field('own_field')]);
    await useDatasetStore().fetchFields('other');
    await flush();
    expect(host.querySelector('thead')?.textContent).toContain('own_field');
    expect(host.querySelector('thead')?.textContent).not.toContain('L4_DST_PORT');
  });

  it.each(['success', 'failure'])('ignores old-model sample %s and preserves the new loading flag', async (outcome) => {
    const old = deferred<DataPreview>();
    const fresh = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    await mount();
    await chooseDataset();
    await chooseModel('12');
    if (outcome === 'success') old.resolve(preview(1, 999));
    else old.reject(new Error('old sample'));
    await flush();
    expect(host.textContent).toContain('正在读取样本');
    fresh.resolve(preview(1, 222));
    await flush();
    expect(host.querySelector('tbody')?.textContent).toContain('222');
    expect(host.querySelector('tbody')?.textContent).not.toContain('999');
    expect(host.querySelector('.loader')).toBeNull();
  });

  it.each(['success', 'failure'])('ignores an obsolete page %s when the next page has finished', async (outcome) => {
    await mount();
    await chooseDataset();
    const old = deferred<DataPreview>();
    const fresh = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(old.promise).mockReturnValueOnce(fresh.promise);
    // 程序触发两个分页事件，模拟禁用属性写回 DOM 前的重复事件。
    const next = host.querySelectorAll<HTMLButtonElement>('.sample-pager button')[1];
    next.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    next.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await flush();
    fresh.resolve(preview(2, 222));
    await flush();
    if (outcome === 'success') old.resolve(preview(2, 999));
    else old.reject(new Error('old page'));
    await flush();
    expect(host.querySelector('tbody')?.textContent).toContain('222');
    expect(host.querySelector('tbody')?.textContent).not.toContain('999');
    expect(host.querySelector('.sample-pager__info')?.textContent).toBe('2 / 3');
    expect(host.querySelector('.loader')).toBeNull();
    expect(keepScroll).toHaveBeenCalledTimes(2);
  });

  it('keeps page 3 when independent page 2 and page 3 requests return out of order', async () => {
    await mount();
    await chooseDataset();
    const second = deferred<DataPreview>();
    const third = deferred<DataPreview>();
    vi.mocked(getDatasetPreview).mockReturnValueOnce(second.promise).mockReturnValueOnce(third.promise);
    // 直接驱动组件已有分页动作，覆盖多入口触发不同页码；不为测试增加生产 expose。
    const changePage: (page: number) => Promise<void> = Reflect.get(Reflect.get(app._instance!, 'setupState'), 'changeSamplePage');
    const old = changePage(2);
    const fresh = changePage(3);
    third.resolve(preview(3));
    await fresh;
    await flush();
    second.resolve(preview(2));
    await old;
    await flush();
    expect(host.querySelector('.sample-pager__info')?.textContent).toBe('3 / 3');
    expect(host.querySelector('tbody')?.textContent).toContain('300');
    expect(host.querySelector('tbody')?.textContent).not.toContain('200');
  });

  it('discards pending fields when the model is cleared', async () => {
    const wait = deferred<DatasetField[]>();
    vi.mocked(getDatasetFields).mockReturnValueOnce(wait.promise);
    await mount();
    await chooseDataset();
    await chooseModel('');
    wait.resolve([field()]);
    await flush();
    expect(host.querySelector('.source-card')).toBeNull();
    expect(getDatasetPreview).not.toHaveBeenCalled();
  });

  it('does not auto-select a draft model marked as default', async () => {
    vi.mocked(getModelVersionList).mockResolvedValueOnce([
      model(11, 1, { status: 'DRAFT', is_default: true }), model(12, 1),
    ]);
    await mount();
    await chooseDataset();
    expect(selects()[1].value).toBe('');
    expect(selects()[1].textContent).not.toContain('算法11');
    expect(getDatasetFields).not.toHaveBeenCalled();
  });

  it('keeps current sample failure empty and recovers after changing models', async () => {
    vi.mocked(getDatasetPreview).mockRejectedValueOnce(new Error('offline'));
    await mount();
    await chooseDataset();
    expect(host.textContent).toContain('没有可读取的样本');
    expect(host.querySelector('.loader')).toBeNull();
    await chooseModel('12');
    expect(host.querySelector('tbody')?.textContent).toContain('100');
  });

  it('stops a pending initial scene query from continuing after unmount', async () => {
    const wait = deferred<ApiScenario[]>();
    vi.mocked(getScenarioList).mockReturnValueOnce(wait.promise);
    await mount();
    app.unmount();
    wait.resolve(scenes);
    await flush();
    expect(getDatasetList).not.toHaveBeenCalled();
  });

  it('stops a pending field query from starting sample loading after unmount', async () => {
    const wait = deferred<DatasetField[]>();
    vi.mocked(getDatasetFields).mockReturnValueOnce(wait.promise);
    await mount();
    await chooseDataset();
    app.unmount();
    wait.resolve([field()]);
    await flush();
    expect(getDatasetPreview).not.toHaveBeenCalled();
    expect(useDatasetStore().fields).toEqual([]);
  });

  it('invalidates previous account requests on logout and same-account relogin', async () => {
    const wait = deferred<BackendModelVersion[]>();
    vi.mocked(getModelVersionList).mockReturnValueOnce(wait.promise);
    await mount();
    await chooseDataset();
    useUserStore().currentUser = null;
    useUserStore().currentUser = user();
    await flush();
    wait.resolve([model(11, 1, { is_default: true })]);
    await flush();
    expect(selects()[0].value).toBe('');
    expect(selects()[1].value).toBe('');
    expect(host.querySelector('.source-card')).toBeNull();
    expect(getDatasetFields).not.toHaveBeenCalled();
  });

  it('leaves current model failures empty and recovers on another dataset', async () => {
    vi.mocked(getModelVersionList).mockRejectedValueOnce(new Error('offline'));
    await mount();
    await chooseDataset();
    expect(selects()[1].textContent).toContain('暂无已发布模型');
    await chooseDataset('2');
    expect(selects()[1].value).toBe('21');
    expect(host.querySelector('tbody')?.textContent).toContain('100');
  });
});
