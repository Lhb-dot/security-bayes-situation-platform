import axios from 'axios';
import type {
  AxiosError,
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';

/** 后端统一响应结构。响应拦截器已剥掉 axios 外层，所以拿到的是响应体本身。 */
export interface ApiEnvelope<T = unknown> {
  code: number;
  message?: string;
  data?: T;
}

/** Axios 默认类型无法表达响应拦截器解包后的返回值。 */
interface RequestInstance extends Omit<AxiosInstance, 'get' | 'post' | 'put' | 'patch' | 'delete' | 'request'> {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  put<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  patch<T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T>;
  request<T = unknown>(config: AxiosRequestConfig): Promise<T>;
}

const CSRF_STORAGE_KEY = 'bayes_csrf_token';

const service = axios.create({
  // Dev: empty baseURL + Vite /api proxy keeps cookies first-party.
  // Prod: set VITE_API_BASE_URL to the backend origin when not same-origin.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 0,
  withCredentials: true,
  // 注意：不在此处写死 Content-Type。axios 会自动处理——
  // JSON 对象请求自动带 application/json，FormData 上传自动带 multipart/form-data(boundary)。
}) as unknown as RequestInstance;

/**
 * 隐私模式 / 浏览器禁用存储时，访问 storage 会直接抛 SecurityError。
 * 这里存的都是可再生的缓存（CSRF 令牌有 cookie 兜底），所以统一降级成
 * 「读不到 / 写不进」，绝不让它打断认证与请求主流程 ——
 * 尤其 401 分支里的 `setCsrfToken(null)` 一旦抛出，后面的 unauthorizedHandler
 * 就不会执行，用户会被卡在「已登出但界面还以为在登录」的状态。
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

/**
 * 401 的跳转由路由层接管（main.ts 在装好 router 后注册）。
 *
 * 这里不直接改 window.location：history 模式下 vue-router 只监听 popstate，
 * 改 hash 既不触发导航，还会把地址污染成 /reports#/login。
 * 会话恢复期间（handler 尚未注册）只清凭据，随后的路由守卫会把用户送去
 * /login?redirect=<原目标>。
 */
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
    // Error 构造器原本也会转为字符串；保留 truthy 判断，避免把未知值伪装成 string。
    if (message) return String(message);
  }
  return err?.message || '请求失败';
};

service.interceptors.request.use((config: InternalAxiosRequestConfig) => {
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
    if (error.response?.status === 401) {
      setCsrfToken(null);
      // 老版本把当前用户 id 写在 localStorage 里，现在已无写入方；这里只是清残留，
      // 清不掉（隐私模式）也不影响流程。
      safeStorage(() => window.localStorage.removeItem('bayes_session_user_id'));
      if (unauthorizedHandler) unauthorizedHandler();
    }
    return Promise.reject(new Error(await extractErrorMessage(error)));
  },
);

export const unwrapData = <T = unknown>(res: unknown): T => {
  const body = res as ApiEnvelope<T> | null | undefined;
  if (body && body.code === 0) return body.data as T;
  throw new Error(body?.message || '请求失败');
};

export default service;
