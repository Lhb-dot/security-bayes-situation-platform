// @vitest-environment jsdom
import { createApp, h, nextTick } from 'vue';
import { createPinia, disposePinia, setActivePinia } from 'pinia';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QuickLoginPanel from './QuickLoginPanel.vue';
import { DEV_QUICK_SCENARIOS, DEV_QUICK_SUPER_ADMINS } from './devAccounts.generated';
import { login } from '@/api/userApi';
import { user } from '@/test/queryFixtures';

const push = vi.fn();
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }));
vi.mock('@/api/userApi');

const flush = async (): Promise<void> => {
  // 登录链路本身还有几层 promise（store 的会话修订、finally 清理），多给几轮。
  for (let i = 0; i < 40; i += 1) await Promise.resolve();
  await nextTick();
  await new Promise((resolve) => setTimeout(resolve, 0));
};

// 清单由数据库生成，断言跟着清单走，避免把口令写死在用例里。
const accountsOf = (code: string, role: string): string[] => {
  const scenario = DEV_QUICK_SCENARIOS.find((item) => item.code === code);
  return (scenario?.accounts ?? []).filter((a) => a.role === role).map((a) => a.username);
};

let app: ReturnType<typeof createApp>;
let host: HTMLDivElement;
let pinia: ReturnType<typeof createPinia>;

const mount = (): void => {
  app = createApp({ render: () => h(QuickLoginPanel) });
  app.use(pinia);
  app.mount(host);
};

// 两个下拉按出现顺序取。
const selects = (): HTMLSelectElement[] => Array.from(host.querySelectorAll('select'));
const choose = async (el: HTMLSelectElement, value: string): Promise<void> => {
  el.value = value;
  el.dispatchEvent(new Event('change'));
  await flush();
};
// 下拉下方「符合要求的账号」列表（不含第一行的超级管理员）。
const listNames = (): string[] =>
  Array.from(host.querySelectorAll('.quick-login__accounts .quick-login__account-name')).map(
    (el) => el.textContent ?? '',
  );
const click = async (el: Element | null): Promise<void> => {
  if (!el) throw new Error('目标元素不存在');
  (el as HTMLElement).click();
  await flush();
};

beforeEach(() => {
  vi.resetAllMocks();
  pinia = createPinia();
  setActivePinia(pinia);
  host = document.createElement('div');
  document.body.append(host);
  vi.mocked(login).mockResolvedValue(user('admin'));
});

afterEach(() => {
  app.unmount();
  disposePinia(pinia);
  host.remove();
});

describe('开发快捷登录面板', () => {
  it('第一行是可直接点击的超级管理员，两个下拉未选完时不列账号', () => {
    mount();
    expect(host.querySelector('.quick-login__account--super .quick-login__account-name')?.textContent)
      .toBe('超级管理员');
    // 没有单独的「登录」按钮：整行就是登录入口
    expect(host.querySelector('.quick-login__btn')).toBeNull();
    expect(listNames()).toEqual([]);
    expect(host.querySelector('.quick-login__hint')?.textContent).toContain('选择场景与角色');
  });

  it('点超级管理员那一行，用清单里的账号口令直接登录', async () => {
    mount();
    const superAdmin = DEV_QUICK_SUPER_ADMINS[0];
    await click(host.querySelector('.quick-login__account--super'));
    expect(login).toHaveBeenCalledWith(superAdmin.username, superAdmin.password, expect.anything());
    expect(push).toHaveBeenCalledWith('/');
  });

  it('选完场景与角色后列出该场景下的全部账号，点击即登录', async () => {
    mount();
    const [scenario, role] = selects();
    await choose(scenario, 'network_security');
    expect(listNames()).toEqual([]);
    await choose(role, 'SCENARIO_ADMIN');
    expect(listNames()).toEqual(accountsOf('network_security', 'SCENARIO_ADMIN'));
    await choose(role, 'SCENARIO_USER');
    expect(listNames()).toEqual(accountsOf('network_security', 'SCENARIO_USER'));
    expect(listNames().length).toBeGreaterThan(1);

    const first = DEV_QUICK_SCENARIOS.find((item) => item.code === 'network_security')!
      .accounts.find((account) => account.role === 'SCENARIO_USER')!;
    await click(host.querySelector('.quick-login__accounts .quick-login__account'));
    expect(login).toHaveBeenCalledWith(first.username, first.password, expect.anything());
    expect(push).toHaveBeenCalledWith('/');
  });

  it('场景名与角色名都显示中文，不出现 sa / su 字样', () => {
    mount();
    const labels = Array.from(selects()[1].options).map((option) => option.textContent?.trim());
    expect(labels).toEqual(['请选择角色', '场景管理员', '场景用户']);
  });

  it('登录失败时给出提示且不跳转', async () => {
    mount();
    vi.mocked(login).mockRejectedValue(new Error('用户名或密码错误'));
    await click(host.querySelector('.quick-login__account--super'));
    expect(host.querySelector('.quick-login__message')?.textContent).toBe('用户名或密码错误');
    expect(push).not.toHaveBeenCalled();
  });
});
