// @vitest-environment jsdom
import { AxiosError } from 'axios';
import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import request, { getCsrfToken, setCsrfToken, setUnauthorizedHandler, unwrapData } from './request';

const originalAdapter = request.defaults.adapter;
const response = (config: InternalAxiosRequestConfig, data: unknown, status = 200) => ({
  data,
  status,
  statusText: String(status),
  headers: {},
  config,
});

const rejectWith = (data: unknown, status = 500) => {
  request.defaults.adapter = async (config) => {
    throw new AxiosError('transport failure', 'ERR_BAD_RESPONSE', config, undefined, response(config, data, status));
  };
};

beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  document.cookie = 'bayes_csrf=; Max-Age=0; Path=/';
  setUnauthorizedHandler(null);
});

afterEach(() => {
  request.defaults.adapter = originalAdapter;
  setUnauthorizedHandler(null);
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('response interceptor contract', () => {
  it('returns the response body, rather than an AxiosResponse wrapper', async () => {
    const body = { code: 0, data: { id: 7 } };
    request.defaults.adapter = async (config) => response(config, body);
    expect(await request.get('/test')).toBe(body);
    expect(unwrapData<{ id: number }>(body)).toEqual({ id: 7 });
  });

  it('keeps a download as a Blob without trying to unwrap an API envelope', async () => {
    const blob = new Blob(['download'], { type: 'application/octet-stream' });
    request.defaults.adapter = async (config) => response(config, blob);
    const downloaded = await request.get<Blob>('/test', { responseType: 'blob' });
    expect(downloaded).toBe(blob);
    expect(downloaded.size).toBe(8);
  });

  it('rejects nonzero and missing business envelopes with the existing messages', () => {
    expect(() => unwrapData({ code: 1, message: '权限不足' })).toThrow('权限不足');
    expect(() => unwrapData(null)).toThrow('请求失败');
    expect(unwrapData({ code: 0, data: null })).toBeNull();
  });

  it('keeps business errors, FastAPI validation details and transport errors readable', async () => {
    rejectWith({ message: '训练参数错误', detail: 'unused' });
    await expect(request.get('/test')).rejects.toThrow('训练参数错误');
    rejectWith({ detail: [{ msg: '缺少字段' }, { message: '类型错误' }] }, 422);
    await expect(request.get('/test')).rejects.toThrow('缺少字段; 类型错误');
    rejectWith({ detail: { message: 123 } });
    await expect(request.get('/test')).rejects.toThrow('123');
    rejectWith(null);
    await expect(request.get('/test')).rejects.toThrow('transport failure');
  });

  it('decodes a JSON error returned by a Blob download request', async () => {
    const payload = JSON.stringify({ detail: '导出失败' });
    const blob = new Blob([payload], { type: 'application/json' });
    // jsdom 的 Blob 尚未实现 text()；补上浏览器提供的同名读取接口。
    Object.defineProperty(blob, 'text', { value: async () => payload });
    rejectWith(blob);
    await expect(request.get('/test', { responseType: 'blob' })).rejects.toThrow('导出失败');
  });
});

describe('CSRF and unauthorized handling', () => {
  it('uses the cookie token first and attaches it only to mutating methods', async () => {
    setCsrfToken('session-token');
    document.cookie = 'bayes_csrf=cookie-token; Path=/';
    request.defaults.adapter = async (config) => response(config, config.headers.get('X-CSRF-Token'));
    expect(getCsrfToken()).toBe('cookie-token');
    expect(await request.get('/test')).toBeUndefined();
    for (const method of ['post', 'put', 'patch', 'delete']) {
      expect(await request.request({ url: '/test', method })).toBe('cookie-token');
    }
  });

  it('uses the session fallback when there is no cookie', async () => {
    setCsrfToken('session-token');
    request.defaults.adapter = async (config) => response(config, config.headers.get('X-CSRF-Token'));
    expect(await request.post('/test')).toBe('session-token');
  });

  it('clears old credentials and calls the unauthorized handler on a 401', async () => {
    setCsrfToken('session-token');
    window.localStorage.setItem('bayes_session_user_id', 'previous');
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    rejectWith({ detail: '会话失效' }, 401);
    await expect(request.get('/test')).rejects.toThrow('会话失效');
    expect(getCsrfToken()).toBeNull();
    expect(window.localStorage.getItem('bayes_session_user_id')).toBeNull();
    expect(handler).toHaveBeenCalledOnce();
  });

  it('still handles a 401 when the browser refuses storage access', async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('storage blocked'); });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => { throw new Error('storage blocked'); });
    rejectWith({ detail: '会话失效' }, 401);
    expect(getCsrfToken()).toBeNull();
    await expect(request.get('/test')).rejects.toThrow('会话失效');
    expect(handler).toHaveBeenCalledOnce();
  });
});
