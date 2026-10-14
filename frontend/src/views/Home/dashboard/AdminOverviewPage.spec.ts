// @vitest-environment jsdom
import { createApp, nextTick } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ElMessage } from 'element-plus';
import { getAdminDashboard, type DashboardOverview } from '@/api/dashboardApi';
import { useUserStore } from '@/stores/userStore';
import { adminOverviewPayload } from '@/test/adminOverviewFixtures';
import { deferred, user } from '@/test/queryFixtures';
import AdminOverviewPage from './AdminOverviewPage.vue';

const routing = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('vue-router', () => ({ useRouter: () => routing }));
vi.mock('@/api/dashboardApi');
vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn(), warning: vi.fn() } }));
const flush = async () => { for (let i = 0; i < 20; i += 1) await Promise.resolve(); await nextTick(); };
let app: ReturnType<typeof createApp> | undefined;
let pinia: ReturnType<typeof createPinia>;
let host: HTMLDivElement;
const mount = async (wait = true) => {
  app = createApp(AdminOverviewPage);
  app.use(pinia);
  app.mount(host);
  if (wait) await flush();
};
const click = (selector: string) => host.querySelector<HTMLButtonElement>(selector)!.click();
const valueFor = (label: string) => [...host.querySelectorAll('.model-stat-grid a')].find((item) => item.textContent?.includes(label))?.querySelector('strong')?.textContent;
beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  routing.push.mockResolvedValue(undefined);
  routing.replace.mockResolvedValue(undefined);
  pinia = createPinia();
  setActivePinia(pinia);
  useUserStore().currentUser = user('admin');
  host = document.createElement('div');
  document.body.append(host);
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  vi.mocked(getAdminDashboard).mockResolvedValue(adminOverviewPayload());
});
afterEach(() => {
  app?.unmount();
  app = undefined;
  disposePinia(pinia);
  host.remove();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('正式管理员首页', () => {
  it('首次请求中显示加载状态，没有演示指标或伪造的零值', async () => {
    const pending = deferred<DashboardOverview>();
    vi.mocked(getAdminDashboard).mockReturnValueOnce(pending.promise);
    await mount(false);
    expect(host.textContent).toContain('正在读取平台实时数据');
    expect(host.querySelectorAll('.metric-card')).toHaveLength(0);
    expect(host.querySelectorAll('.scene-card')).toHaveLength(0);
    pending.resolve(adminOverviewPayload());
    await flush();
    expect(host.querySelectorAll('.panel')).toHaveLength(6);
    expect(valueFor('推理记录')).toBe('42');
    expect(host.querySelector('.metric-card:nth-child(3) strong')?.textContent).toBe('4,000');
    expect(host.textContent).not.toContain('设计预览');
    expect(document.documentElement.classList.contains('admin-overview-mode')).toBe(true);
  });

  it('接口失败时允许重试，成功后恢复看板', async () => {
    vi.mocked(getAdminDashboard).mockRejectedValueOnce(new Error('服务连接失败'));
    await mount();
    expect(host.textContent).toContain('平台数据暂不可用');
    expect(host.querySelectorAll('.metric-card')).toHaveLength(0);
    click('.overview-state button');
    await flush();
    expect(host.querySelector('.overview-state')).toBeNull();
    expect(valueFor('训练完成模型')).toBe('17');
  });

  it('刷新失败保留最后成功数据，明确提示后可手动恢复', async () => {
    await mount();
    vi.mocked(getAdminDashboard).mockRejectedValueOnce(new Error('刷新超时'));
    await vi.advanceTimersByTimeAsync(15_000);
    await flush();
    expect(valueFor('推理记录')).toBe('42');
    expect(host.querySelector('.runtime-badge')?.textContent).toBe('更新失败');
    expect(host.querySelector('.runtime-badge')?.getAttribute('title')).toContain('上次成功读取的数据');
    const fresh = adminOverviewPayload();
    fresh.runtime.inference_count = 99;
    vi.mocked(getAdminDashboard).mockResolvedValueOnce(fresh);
    click('.runtime-badge');
    await flush();
    expect(valueFor('推理记录')).toBe('99');
    expect(host.querySelector('.runtime-badge')?.textContent).toBe('实时数据');
  });

  it('请求仍在进行时不会叠加轮询请求，后台页也不轮询', async () => {
    const pending = deferred<DashboardOverview>();
    vi.mocked(getAdminDashboard).mockReturnValueOnce(pending.promise);
    await mount(false);
    await vi.advanceTimersByTimeAsync(45_000);
    expect(getAdminDashboard).toHaveBeenCalledTimes(1);
    pending.resolve(adminOverviewPayload());
    await flush();
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getAdminDashboard).toHaveBeenCalledTimes(1);
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    document.dispatchEvent(new Event('visibilitychange'));
    await flush();
    expect(getAdminDashboard).toHaveBeenCalledTimes(2);
  });

  it('离开页面中止请求并恢复滚动样式，迟到响应不能回填', async () => {
    const pending = deferred<DashboardOverview>();
    vi.mocked(getAdminDashboard).mockReturnValueOnce(pending.promise);
    await mount(false);
    const signal = vi.mocked(getAdminDashboard).mock.calls[0][0]?.signal;
    app!.unmount();
    app = undefined;
    expect(signal?.aborted).toBe(true);
    expect(document.documentElement.classList.contains('admin-overview-mode')).toBe(false);
    pending.resolve(adminOverviewPayload());
    await flush();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(getAdminDashboard).toHaveBeenCalledTimes(1);
    expect(host.textContent).toBe('');
  });

  it('账号切换后忽略上一账号的迟到结果', async () => {
    const old = deferred<DashboardOverview>();
    const fresh = adminOverviewPayload();
    fresh.runtime.inference_count = 77;
    vi.mocked(getAdminDashboard).mockReturnValueOnce(old.promise).mockResolvedValueOnce(fresh);
    await mount(false);
    useUserStore().currentUser = user('another-admin');
    await flush();
    old.resolve(adminOverviewPayload());
    await flush();
    expect(valueFor('推理记录')).toBe('77');
  });

  it('非系统管理员不会查询管理员总览', async () => {
    useUserStore().currentUser = { ...user('scenario-user'), role: 'SCENARIO_USER' };
    await mount();
    expect(getAdminDashboard).not.toHaveBeenCalled();
  });

  it('零数据和可选字段缺失没有 NaN，也不隐藏指标卡片', async () => {
    const payload = adminOverviewPayload();
    Object.keys(payload.totals).forEach((key) => { (payload.totals as unknown as Record<string, number>)[key] = 0; });
    Object.keys(payload.runtime).forEach((key) => { (payload.runtime as unknown as Record<string, number>)[key] = 0; });
    delete payload.runtime.trained_model_count;
    delete payload.runtime.report_count;
    delete payload.runtime.served_user_count;
    payload.scenarios = [];
    vi.mocked(getAdminDashboard).mockResolvedValueOnce(payload);
    await mount();
    expect(host.querySelectorAll('.panel')).toHaveLength(6);
    expect(host.querySelectorAll('.model-stat-grid a')).toHaveLength(4);
    expect(valueFor('训练完成模型')).toBe('—');
    expect(valueFor('已生成报告')).toBe('—');
    expect(host.querySelector('.resolution strong')?.textContent).toBe('—');
    expect(host.querySelector('.user-coverage strong')?.textContent).toBe('—');
    expect(host.textContent).toContain('暂无场景成员');
    expect(host.textContent).not.toMatch(/NaN|Infinity|undefined/);
    expect([...host.querySelectorAll('[style]')].map((e) => e.getAttribute('style')).join('')).not.toMatch(/NaN|Infinity/);
  });

  it('普通链接由路由处理，Ctrl 点击保留浏览器的新标签行为', async () => {
    await mount();
    const link = host.querySelector<HTMLAnchorElement>('.metric-card:nth-child(2)')!;
    const normal = new MouseEvent('click', { bubbles: true, cancelable: true, button: 0 });
    link.dispatchEvent(normal);
    await flush();
    expect(normal.defaultPrevented).toBe(true);
    expect(routing.push).toHaveBeenCalledWith('/datasets');
    routing.push.mockClear();
    const modified = new MouseEvent('click', { bubbles: true, cancelable: true, ctrlKey: true });
    link.dispatchEvent(modified);
    expect(modified.defaultPrevented).toBe(false);
    expect(routing.push).not.toHaveBeenCalled();
    modified.preventDefault();
  });

  it('场景菜单直接进入接口编码对应的数据画像，卡片显式展示两项统计', async () => {
    const payload = adminOverviewPayload();
    payload.scenarios[0].code = 'network/自定义';
    vi.mocked(getAdminDashboard).mockResolvedValueOnce(payload);
    await mount();
    click('[data-category="scene"]');
    await flush();
    const links = [...host.querySelectorAll<HTMLAnchorElement>('#category-panel > a')];
    expect(links.map((link) => link.querySelector('strong')?.textContent)).toEqual(['网络安全', '电力系统', '舰面调度', '地质风险']);
    expect(links[0].getAttribute('href')).toBe('/scenarios/network%2F%E8%87%AA%E5%AE%9A%E4%B9%89/dashboard');
    links[0].click();
    await flush();
    expect(routing.push).toHaveBeenCalledWith('/scenarios/network%2F%E8%87%AA%E5%AE%9A%E4%B9%89/dashboard');
    expect(host.querySelector('#category-panel')).toBeNull();
    const card = host.querySelector('.scene-card--network')!;
    expect(card.querySelector('.scene-stat--samples strong')?.textContent).toBe('1,000');
    expect(card.querySelector('.scene-stat--datasets strong')?.textContent).toBe('2');
    expect(card.textContent).toContain('数据集数量');
    expect(host.querySelector('a[href="/scenarios"]')).toBeNull();
  });

  it('首页的场景概览和能力链路打开场景菜单，不刷新或改变路由', async () => {
    await mount();
    click('.metric-card');
    await flush();
    expect(host.querySelectorAll('#category-panel > a')).toHaveLength(4);
    click('.pipeline a');
    await flush();
    expect(host.querySelector('#category-panel')).toBeNull();
    click('.pipeline a');
    await flush();
    expect(host.querySelectorAll('#category-panel > a')).toHaveLength(4);
    expect(routing.push).not.toHaveBeenCalled();
  });

  it('场景数据缺失时不生成虚假的场景链接，加载成功后菜单自动更新', async () => {
    const pending = deferred<DashboardOverview>();
    vi.mocked(getAdminDashboard).mockReturnValueOnce(pending.promise);
    await mount(false);
    click('[data-category="scene"]');
    await flush();
    expect(host.querySelectorAll('#category-panel > a')).toHaveLength(0);
    expect(host.querySelector('.category-empty')?.textContent).toBe('正在读取场景…');
    const payload = adminOverviewPayload();
    payload.scenarios = [];
    pending.resolve(payload);
    await flush();
    expect(host.querySelector('.category-empty')?.textContent).toBe('暂无已接入场景');
    click('.runtime-badge');
    await flush();
    expect(host.querySelectorAll('#category-panel > a')).toHaveLength(4);
  });

  it('分类菜单支持再次点击、切换、外部点击和 Esc 关闭', async () => {
    await mount();
    click('[data-category="prediction"]');
    await flush();
    expect(host.querySelectorAll('#category-panel > a')).toHaveLength(4);
    click('[data-category="prediction"]');
    await flush();
    expect(host.querySelector('#category-panel')).toBeNull();
    click('[data-category="prediction"]');
    click('[data-category="model"]');
    await flush();
    expect(host.querySelectorAll('#category-panel > a')).toHaveLength(2);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await flush();
    expect(host.querySelector('#category-panel')).toBeNull();
    expect(document.activeElement).toBe(host.querySelector('[data-category="model"]'));
    click('[data-category="settings"]');
    await flush();
    host.querySelector('.command-title')!.dispatchEvent(new Event('pointerdown', { bubbles: true }));
    await flush();
    expect(host.querySelector('#category-panel')).toBeNull();
  });

  it('登录页加载失败时给出反馈，不留下未处理的异步异常', async () => {
    await mount();
    vi.spyOn(useUserStore(), 'logout').mockResolvedValueOnce(undefined);
    routing.replace.mockRejectedValueOnce(new Error('登录页加载失败'));
    click('.logout-button');
    await flush();
    expect(ElMessage.error).toHaveBeenCalledWith('登录页加载失败，请刷新页面重试');
    expect(host.querySelector<HTMLButtonElement>('.logout-button')!.disabled).toBe(false);
  });

  it.each(['success', 'failure'])('退出登录 %s 都结束管理员页面，且不重复提交', async (outcome) => {
    await mount();
    const pending = deferred<void>();
    const logout = vi.spyOn(useUserStore(), 'logout').mockReturnValueOnce(pending.promise);
    click('.logout-button');
    await flush();
    expect(host.querySelector<HTMLButtonElement>('.logout-button')!.disabled).toBe(true);
    click('.logout-button');
    expect(logout).toHaveBeenCalledTimes(1);
    if (outcome === 'success') pending.resolve();
    else pending.reject(new Error('网络中断'));
    await flush();
    expect(routing.replace).toHaveBeenCalledWith('/login');
    if (outcome === 'failure') expect(ElMessage.warning).toHaveBeenCalled();
  });
});
