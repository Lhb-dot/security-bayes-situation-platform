// @vitest-environment jsdom
import { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import request, { getCsrfToken, RequestError, setCsrfToken } from '@/utils/request';
import { deferred } from '@/test/queryFixtures';
import { getMe, getUserList, login, logout, SESSION_QUERY_TIMEOUT_MS, USER_LIST_QUERY_TIMEOUT_MS } from './userApi';

const originalAdapter = request.defaults.adapter;
const rawUser = { id: 7, username: 'tester', role: 'SCENARIO_ADMIN', status: 'ENABLED',
  scenario_id: 1, scenario_code: 'network_security', created_at: '2026-10-11 00:00:00', updated_at: '2026-10-11 00:00:00' };
const response = (config: InternalAxiosRequestConfig, data: unknown) => ({
  config, status: 200, statusText: 'OK', headers: {}, data: { code: 0, data },
});
beforeEach(() => { window.sessionStorage.clear(); document.cookie = 'bayes_csrf=; Max-Age=0; Path=/'; });
afterEach(() => { request.defaults.adapter = originalAdapter; setCsrfToken(null); });

describe('bounded account reads and authentication context', () => {
  it('bounds getMe and forwards cancellation without changing user mapping', async () => {
    const controller = new AbortController();
    let captured: InternalAxiosRequestConfig | undefined;
    request.defaults.adapter = async (config) => { captured = config; return response(config, rawUser); };
    expect(await getMe({ signal: controller.signal })).toMatchObject({ user_id: '7', role: 'SCENARIO_ADMIN', scenario_code: 'network_security' });
    expect(captured?.url).toBe('/api/v1/auth/me');
    expect(captured?.timeout).toBe(SESSION_QUERY_TIMEOUT_MS);
    expect(captured?.signal).toBe(controller.signal);
  });

  it('bounds only the selected user list query, preserving its parameters', async () => {
    let captured: InternalAxiosRequestConfig | undefined;
    request.defaults.adapter = async (config) => { captured = config; return response(config, { items: [rawUser], total: 1, page: 2, page_size: 5 }); };
    expect(await getUserList({ page: 2, page_size: 5, keyword: 'test' })).toMatchObject({ total: 1, page: 2 });
    expect(captured?.timeout).toBe(USER_LIST_QUERY_TIMEOUT_MS);
    expect(captured?.params).toMatchObject({ page: 2, page_size: 5, keyword: 'test' });
    expect(request.defaults.timeout).toBe(0);
  });

  it('preserves the session timeout message and does not retry', async () => {
    let attempts = 0;
    request.defaults.adapter = async (config) => { attempts += 1; throw new AxiosError(config.timeoutErrorMessage, 'ECONNABORTED', config); };
    await expect(getMe()).rejects.toMatchObject({ kind: 'timeout', message: '会话恢复超时，请检查网络后重新登录或刷新重试' });
    expect(attempts).toBe(1);
  });

  it('does not apply a short read timeout to authentication writes', async () => {
    const timeouts: number[] = [];
    request.defaults.adapter = async (config) => { timeouts.push(config.timeout ?? -1); return response(config, { user: rawUser, csrf_token: 'new' }); };
    await login('tester', 'password');
    await logout();
    expect(timeouts).toEqual([0, 0]);
  });

  it('rejects an aborted getMe with cancellation metadata', async () => {
    const wait = deferred<void>();
    let started!: () => void;
    const ready = new Promise<void>((resolve) => { started = resolve; });
    request.defaults.adapter = async (config) => { started(); await wait.promise; return response(config, rawUser); };
    const controller = new AbortController();
    const query = getMe({ signal: controller.signal });
    const failed = expect(query).rejects.toMatchObject({ code: 'ERR_CANCELED', kind: 'canceled' });
    await ready;
    controller.abort();
    wait.resolve();
    await failed;
  });

  it('does not install an obsolete login token', async () => {
    setCsrfToken('current');
    request.defaults.adapter = async (config) => response(config, { user: rawUser, csrf_token: 'obsolete' });
    await login('tester', 'password', { signal: new AbortController().signal, isCurrent: () => false });
    expect(getCsrfToken()).toBe('current');
  });

  it.each(['success', 'failure'])('does not clear new CSRF after old logout %s', async (outcome) => {
    const wait = deferred<void>();
    let active = true;
    let started!: () => void;
    const ready = new Promise<void>((resolve) => { started = resolve; });
    request.defaults.adapter = async (config) => { started(); await wait.promise; return response(config, null); };
    const pending = logout({ signal: new AbortController().signal, isCurrent: () => active });
    const handled = pending.catch(() => {});
    await ready;
    active = false;
    setCsrfToken('new');
    if (outcome === 'success') wait.resolve();
    else wait.reject(new RequestError('old network failure'));
    await handled;
    expect(getCsrfToken()).toBe('new');
  });

  it('sends the existing logout CSRF and clears it after the request', async () => {
    setCsrfToken('existing');
    let csrf: unknown;
    request.defaults.adapter = async (config) => { csrf = config.headers.get('X-CSRF-Token'); return response(config, null); };
    await logout();
    expect(csrf).toBe('existing');
    expect(getCsrfToken()).toBeNull();
  });
});
