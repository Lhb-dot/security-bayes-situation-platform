// @vitest-environment jsdom
import { createApp, defineComponent, h, nextTick, reactive } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getScenarioProfile, getScenarioWorkspace, type ScenarioProfile } from '@/api/dashboardApi';
import { getScenarioList, resolveScenarioId } from '@/api/scenarioApi';
import { getUserList } from '@/api/userApi';
import { useUserStore } from '@/stores/userStore';
import { deferred, user } from '@/test/queryFixtures';
import { geologicalProfile, networkProfile, powerProfile, scenarioList, workspaceFixture } from '@/test/scenarioProfileFixtures';
import AdminProfilePage from './AdminProfilePage.vue';

const routing = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('vue-router', () => ({ useRouter: () => routing }));
vi.mock('@/api/dashboardApi');
vi.mock('@/api/scenarioApi');
vi.mock('@/api/userApi');
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), warning: vi.fn() } }));
vi.mock('@/components/charts/EChartBase.vue', () => ({ default: defineComponent({ props: ['option'], setup: props => () => h('div', { class: 'test-chart', 'data-option': JSON.stringify(props.option) }) }) }));
const flush = async () => { for (let i = 0; i < 30; i++) await Promise.resolve(); await nextTick(); };
let app: ReturnType<typeof createApp> | undefined;
let pinia: ReturnType<typeof createPinia>;
let host: HTMLDivElement;
let props: { scenarioRef: string };
const mount = async (wait = true) => {
  props = reactive({ scenarioRef: 'network_security' });
  app = createApp({ setup: () => () => h(AdminProfilePage, props) });
  app.use(pinia); app.mount(host);
  if (wait) await flush();
};
const clickText = (text: string) => [...host.querySelectorAll('button')].find(item => item.textContent?.trim() === text)!.click();
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks();
  pinia = createPinia(); setActivePinia(pinia);
  useUserStore().currentUser = { ...user('scene-admin'), role: 'SCENARIO_ADMIN', scenario_id: 1, scenario_code: 'network_security' };
  host = document.createElement('div'); document.body.append(host);
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  vi.mocked(resolveScenarioId).mockImplementation(async value => value === 'power_system' ? 2 : 1);
  vi.mocked(getScenarioProfile).mockResolvedValue(networkProfile());
  vi.mocked(getScenarioWorkspace).mockResolvedValue(workspaceFixture());
  vi.mocked(getScenarioList).mockResolvedValue(scenarioList().slice(0, 1));
  vi.mocked(getUserList).mockImplementation(async params => ({ items: [], total: params?.status === 'ENABLED' ? 6 : params?.status === 'DISABLED' ? 2 : 8, page: 1, page_size: 1 }));
});
afterEach(() => { app?.unmount(); app = undefined; disposePinia(pinia); host.remove(); vi.useRealTimers(); vi.restoreAllMocks(); });

describe('正式场景大屏', () => {
  it('从接口加载四卡和图表，保留预览版指标说明与图标，用户计数使用分页 total', async () => {
    await mount();
    expect(host.querySelectorAll('.sp-metrics article')).toHaveLength(4);
    expect(host.querySelectorAll('.sp-metrics article p')).toHaveLength(4);
    expect(host.querySelector('.sp-metrics article p')?.textContent).toContain('按内容指纹去重');
    expect(host.querySelectorAll('.sp-command nav svg')).toHaveLength(4);
    expect(host.querySelector('.sp-metrics strong')?.textContent).toBe('1');
    expect(host.querySelector('.sp-members')?.textContent).toContain('注册 8');
    expect(host.querySelector('.sp-members')?.textContent).toContain('启用 6');
    expect(host.querySelector('.sp-members')?.textContent).toContain('停用 2');
    expect(host.textContent).not.toContain('演示');
    expect(host.querySelector('tbody')?.textContent).toContain('公司');
    expect(document.documentElement.classList.contains('scenario-screen-mode')).toBe(true);
    clickText('test_sourceV2');
    expect(routing.push).toHaveBeenCalledWith('/datasets/91');
    clickText('模型训练');
    expect(routing.push).toHaveBeenCalledWith('/risk');
    expect(host.querySelectorAll('.sp-switcher button')).toHaveLength(1);
  });
  it('加载期间不伪造零值，失败可以重试', async () => {
    const pending = deferred<ScenarioProfile>();
    vi.mocked(getScenarioProfile).mockReturnValueOnce(pending.promise);
    await mount(false); await flush();
    expect(host.textContent).toContain('正在读取场景数据');
    expect(host.querySelectorAll('.sp-metrics article')).toHaveLength(0);
    pending.reject(new Error('读取超时')); await flush();
    expect(host.textContent).toContain('读取超时');
    clickText('重新加载'); await flush();
    expect(host.querySelectorAll('.sp-metrics article')).toHaveLength(4);
  });
  it('运行接口独立失败不影响画像，显式提示错误并可恢复', async () => {
    vi.mocked(getScenarioWorkspace).mockRejectedValueOnce(new Error('运行接口失败'));
    await mount();
    expect(host.querySelectorAll('.sp-metrics article')).toHaveLength(4);
    expect(host.querySelectorAll('.sp-chart-error')).toHaveLength(2);
    expect(host.querySelector('.sp-status')?.textContent).toContain('更新失败');
    host.querySelector<HTMLButtonElement>('.sp-status')!.click(); await flush();
    expect(host.querySelectorAll('.sp-chart-error')).toHaveLength(0);
  });
  it('系统管理员不查询受限的场景用户列表，运行统计标明本人范围', async () => {
    useUserStore().currentUser = user('super-admin');
    vi.mocked(getScenarioWorkspace).mockResolvedValue(workspaceFixture(false));
    await mount();
    expect(getUserList).not.toHaveBeenCalled();
    expect(host.textContent).toContain('本人范围');
    expect(host.textContent).toContain('当前账号在本场景');
  });
  it('切换场景会中止旧请求，迟到的结果不能覆盖新场景', async () => {
    const pending = deferred<ScenarioProfile>();
    vi.mocked(getScenarioProfile).mockReturnValueOnce(pending.promise).mockResolvedValueOnce(powerProfile());
    await mount(false); await flush();
    const signal = vi.mocked(getScenarioProfile).mock.calls[0]![1]?.signal;
    props.scenarioRef = 'power_system'; await flush();
    expect(signal?.aborted).toBe(true);
    pending.resolve(networkProfile()); await flush();
    expect(host.querySelector('h2')?.textContent).toContain(powerProfile().scenario_name);
    expect(host.textContent).toContain('电参量基线');
  });
  it('滑坡页按附件使用覆盖矩阵和数据职责，分箱冲突来自接口', async () => {
    const data = geologicalProfile();
    data.factor_coverage[0] = { factor: 'Slope', datasets: ['test_source', 'another_source'], consistent_binning: false };
    data.roles = [{ logical_id: 'test_source', name: '测试因子集', role: '因子表', attribute_count: 4, label_field: 'Label', label_kind: 'binary', participates_in_training: true, produces_risk_events: true, record_count: 28, risk_rate: .25 }];
    vi.mocked(getScenarioProfile).mockResolvedValue(data);
    await mount();
    expect(host.querySelector('.sp-grid')).not.toBeNull();
    expect(host.querySelectorAll('.geo-leaf-node')).toHaveLength(0);
    expect(host.textContent).not.toContain('类型 × 规模');
    expect(host.querySelector('[aria-label="数据集与地形因子的字段覆盖热力矩阵"]')).not.toBeNull();
    expect(host.querySelector('.sp-governance')?.textContent).toContain('数据职责与风险口径');
    expect(host.querySelector('.sp-governance')?.textContent).toContain('因子表 · Label');
    expect(host.querySelector('.sp-governance-note')?.textContent).toContain('分箱不一致：Slope');
    expect(host.querySelector('.sp-governance-note')?.textContent).not.toContain('工频');
  });
  it('刷新失败保留已读取画像，离开页面清理轮询、取消请求和全屏样式', async () => {
    await mount();
    vi.mocked(getScenarioProfile).mockRejectedValueOnce(new Error('刷新失败'));
    await vi.advanceTimersByTimeAsync(30_000); await flush();
    expect(host.querySelectorAll('.sp-metrics article')).toHaveLength(4);
    expect(host.querySelector('.sp-status')?.getAttribute('title')).toContain('上次成功读取');
    const count = vi.mocked(getScenarioProfile).mock.calls.length;
    app!.unmount(); app = undefined;
    expect(document.documentElement.classList.contains('scenario-screen-mode')).toBe(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getScenarioProfile).toHaveBeenCalledTimes(count);
  });
  it('后台页面暂停自动刷新', async () => {
    await mount();
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getScenarioProfile).toHaveBeenCalledTimes(1);
  });
});
