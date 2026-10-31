import axios from 'axios';
import type {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';

export interface ApiEnvelope<T = unknown> {
  code: number;
  message?: string;
  data?: T;
}

interface RequestInstance extends Omit<AxiosInstance, 'get' | 'post' | 'put' | 'patch' | 'delete' | 'request'> {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>;
  request<T = unknown>(config: AxiosRequestConfig): Promise<T>;
}

const CSRF_STORAGE_KEY = 'bayes_csrf_token';

export type RequestErrorKind = 'unauthorized' | 'timeout' | 'canceled' | 'network' | 'http';

export class RequestError extends Error {
  readonly status: number | undefined;
  readonly code: string | undefined;
  readonly kind: RequestErrorKind;

  constructor(message: string, details: { status?: number; code?: string } = {}) {
    super(message);
    this.name = 'RequestError';
    this.status = details.status;
    this.code = details.code;
    this.kind = details.status === 401 ? 'unauthorized'
      : details.code === 'ERR_CANCELED' ? 'canceled'
        : ['ECONNABORTED', 'ETIMEDOUT'].includes(details.code ?? '') ? 'timeout'
          : details.status ? 'http' : 'network';
  }
}

let sessionRevision = 0;
const requestSessions = new WeakMap<object, number>();
export const invalidateSessionRequests = (): void => { sessionRevision += 1; };

const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 0,
  withCredentials: true,
  // JSON 对象请求自动带 application/json，FormData 上传自动带 multipart/form-data(boundary)。
}) as unknown as RequestInstance;

/**
 * 隐私模式 / 浏览器禁用存储时访问 storage 会抛 SecurityError。这里存的都是可再生缓存
 * （CSRF 令牌有 cookie 兜底），统一降级成「读不到 / 写不进」，不打断请求主流程。
 */
const safeStorage = <T>(run: () => T, fallback?: T): T | undefined => {
  try {
    return run();
  } catch {
    return fallback;
  }
};

const readCookie = (name: string): string | null => {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split('; ')
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
};

export const setCsrfToken = (token: string | null): void => {
  safeStorage(() => {
    if (token) {
      window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
    }
  });
};

const currentCsrfToken = (): string | null => {
  const fromCookie = readCookie(import.meta.env.VITE_CSRF_COOKIE_NAME || 'bayes_csrf');
  if (fromCookie) return fromCookie;
  return safeStorage(() => window.sessionStorage.getItem(CSRF_STORAGE_KEY), null) ?? null;
};

export const getCsrfToken = (): string | null => currentCsrfToken();

// 1 的跳转由路由层接管（main.ts 在装好 router 后注册）。
let unauthorizedHandler: (() => void) | null = null;

export const setUnauthorizedHandler = (handler: (() => void) | null): void => {
  unauthorizedHandler = handler;
};

const extractErrorMessage = async (error: unknown): Promise<string> => {
  const err = error as AxiosError<unknown> | undefined;
  let data: unknown = err?.response?.data;
  // responseType: 'blob' 的请求失败时，服务端回的是 JSON，但被 axios 包成了 Blob，
  // 不解开就只能报「Request failed with status code 500」这种没用的话
  if (data instanceof Blob) {
    try {
      data = JSON.parse(await data.text());
    } catch {
      data = null;
    }
  }
  if (!data) return err?.message || '请求失败';
  if (typeof data !== 'object' && typeof data !== 'function') return err?.message || '请求失败';
  const body = data as Record<string, unknown>;
  if (typeof body.message === 'string' && body.message) return body.message;
  if (typeof body.detail === 'string' && body.detail) return body.detail;
  if (Array.isArray(body.detail)) {
    const rows = body.detail as unknown[];
    return rows
      .map((item) => {
        const row = item as Record<string, unknown> | null;
        return row?.msg || row?.message || JSON.stringify(item);
      })
      .join('; ');
  }
  const detail = body.detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message;
    if (message) return String(message);
  }
  return err?.message || '请求失败';
};

service.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  requestSessions.set(config, sessionRevision);
  const method = (config.method || 'get').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = currentCsrfToken();
    if (csrf) {
      config.headers['X-CSRF-Token'] = csrf;
    }
  }
  return config;
});

service.interceptors.response.use(
  (response: AxiosResponse) => response.data,
  async (error: AxiosError) => {
    const currentSession = error.config && requestSessions.get(error.config) === sessionRevision
      && !error.config.signal?.aborted;
    if (error.response?.status === 401 && currentSession) {
      setCsrfToken(null);
      safeStorage(() => window.localStorage.removeItem('bayes_session_user_id'));
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return Promise.reject(new RequestError(await extractErrorMessage(error), {
      status: error.response?.status,
      code: error.code,
    }));
  },
);

export const unwrapData = <T = unknown>(res: unknown): T => {
  const body = res as ApiEnvelope<T> | null | undefined;
  if (body && body.code === 0) return body.data as T;
  throw new Error(body?.message || '请求失败');
};

export default service;
