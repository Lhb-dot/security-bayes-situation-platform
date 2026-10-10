// @vitest-environment jsdom
import { AxiosError } from 'axios';
import { createApp, h, nextTick } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { createMemoryHistory, createRouter, RouterView } from 'vue-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getMe } from '@/api/userApi';
import { useUserStore } from '@/stores/userStore';
import { setupRouterGuards } from '@/router/guards';
import Login from '@/views/Login.vue';
import { deferred, user } from '@/test/queryFixtures';
import type { UserAccount } from '@/types/security';
import request, { getCsrfToken, RequestError, setCsrfToken, setUnauthorizedHandler } from './request';
import { startApplication } from './appStartup';

vi.mock('@/api/userApi');
let host: HTMLDivElement;
let pinia: ReturnType<typeof createPinia>;
let app: ReturnType<typeof createApp>;
let router: ReturnType<typeof createRouter>;
let store: ReturnType<typeof useUserStore>;
const flush = async () => { for (let i = 0; i < 30; i += 1) await Promise.resolve(); await nextTick(); };
beforeEach(() => {
  vi.resetAllMocks();
  window.sessionStorage.clear();
  window.localStorage.clear();
  host = document.createElement('div');
  host.id = 'app';
  document.body.append(host);
  pinia = createPinia();
  setActivePinia(pinia);
  store = useUserStore();
  const history = createMemoryHistory();
  history.push('/reports?scope=mine');
  router = createRouter({ history, routes: [
    { path: '/reports', component: { render: () => h('div', { 'data-page': 'reports' }, '模拟报告页') }, meta: { title: '报告中心' } },
    { path: '/login', component: Login, meta: { title: '登录' } },
  ] });
  setupRouterGuards(router);
  app = createApp({ render: () => h(RouterView) }).use(pinia);
});
afterEach(() => {
  if (Reflect.get(host, '__vue_app__')) app.unmount();
  store.expireSession();
  disposePinia(pinia);
  setUnauthorizedHandler(null);
  host.remove();
});

describe('application session initialization and routing', () => {
  it.each(['SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER'] as const)('waits for %s restoration before initial deep-link navigation', async (role) => {
    const wait = deferred<UserAccount>();
    vi.mocked(getMe).mockReturnValueOnce(wait.promise);
    const startup = startApplication(app, router, store);
    await flush();
    expect(host.children.length).toBe(0);
    expect(getMe).toHaveBeenCalledOnce();
    wait.resolve({ ...user(), role, scenario_id: role === 'SUPER_ADMIN' ? null : 1,
      scenario_code: role === 'SUPER_ADMIN' ? null : 'network_security' });
    await startup;
    await router.isReady();
    await flush();
    expect(router.currentRoute.value.fullPath).toBe('/reports?scope=mine');
    expect(host.querySelector('[data-page="reports"]')).not.toBeNull();
  });

  it.each(['401', 'timeout', 'network'])('mounts after %s and retains the original redirect', async (kind) => {
    vi.mocked(getMe).mockRejectedValueOnce(kind === '401' ? new RequestError('expired', { status: 401 })
      : new RequestError('transport error', { code: kind === 'timeout' ? 'ECONNABORTED' : 'ERR_NETWORK' }));
    await startApplication(app, router, store);
    await router.isReady();
    await flush();
    expect(router.currentRoute.value.path).toBe('/login');
    expect(router.currentRoute.value.query.redirect).toBe('/reports?scope=mine');
    expect(host.querySelector('.login-form')).not.toBeNull();
    if (kind === '401') expect(host.querySelector('.login-error')).toBeNull();
    else expect(host.querySelector('.login-error')?.textContent).toContain('重新登录或刷新重试');
  });

  it('expires authenticated state before routing a current 401 to login', async () => {
    vi.mocked(getMe).mockResolvedValueOnce(user());
    await startApplication(app, router, store);
    await router.isReady();
    store.users = [user()];
    const adapter = request.defaults.adapter;
    setCsrfToken('current');
    request.defaults.adapter = async (config) => {
      throw new AxiosError('expired', 'ERR_BAD_RESPONSE', config, undefined,
        { config, status: 401, statusText: 'Unauthorized', headers: {}, data: { detail: 'expired' } });
    };
    try { await expect(request.get('/mock401')).rejects.toThrow('expired'); }
    finally { request.defaults.adapter = adapter; }
    await flush();
    expect(store.currentUser).toBeNull();
    expect(store.users).toEqual([]);
    expect(getCsrfToken()).toBeNull();
    expect(router.currentRoute.value.path).toBe('/login');
    expect(router.currentRoute.value.query.redirect).toBe('/reports?scope=mine');
    expect(getMe).toHaveBeenCalledOnce();
  });
});
