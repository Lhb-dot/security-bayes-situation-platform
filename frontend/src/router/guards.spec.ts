// @vitest-environment jsdom
import { createMemoryHistory, createRouter } from 'vue-router';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useUserStore } from '@/stores/userStore';
import { user } from '@/test/queryFixtures';
import { setupRouterGuards } from './guards';

let pinia: ReturnType<typeof createPinia>;
beforeEach(() => { pinia = createPinia(); setActivePinia(pinia); });
afterEach(() => disposePinia(pinia));
const routerForTest = () => {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    '/login', '/overview', '/scenarios', '/scenarios/:scenarioId/dashboard',
  ].map((path) => ({ path, component: { render: () => null }, meta: { title: path } })) });
  setupRouterGuards(router);
  return router;
};
describe('管理员场景中心融入首页后的路由兼容', () => {
  it('系统管理员打开旧场景中心地址回到首页，仍能直接进入四个场景', async () => {
    useUserStore().currentUser = user();
    const router = routerForTest();
    await router.push('/scenarios');
    expect(router.currentRoute.value.path).toBe('/overview');
    for (const code of ['network_security', 'power_system', 'flightdeck_operation', 'geological_risk']) {
      await router.push(`/scenarios/${code}/dashboard`);
      expect(router.currentRoute.value.path).toBe(`/scenarios/${code}/dashboard`);
    }
  });
  it.each(['SCENARIO_ADMIN', 'SCENARIO_USER'] as const)('%s 保留场景入口和自己的登录落地页', async (role) => {
    useUserStore().currentUser = { ...user(), role, scenario_code: 'network_security' };
    const router = routerForTest();
    await router.push('/scenarios');
    expect(router.currentRoute.value.path).toBe('/scenarios');
    await router.push('/login');
    expect(router.currentRoute.value.path).toBe('/scenarios/network_security/dashboard');
  });
  it('未登录打开旧地址仍需要登录', async () => {
    const router = routerForTest();
    await router.push('/scenarios');
    expect(router.currentRoute.value.path).toBe('/login');
  });
});
