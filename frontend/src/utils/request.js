import axios from 'axios';

const CSRF_STORAGE_KEY = 'bayes_csrf_token';

const service = axios.create({
  // Dev: empty baseURL + Vite /api proxy keeps cookies first-party.
  // Prod: set VITE_API_BASE_URL to the backend origin when not same-origin.
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 0,
  withCredentials: true,
  // 注意：不在此处写死 Content-Type。axios 会自动处理——
  // JSON 对象请求自动带 application/json，FormData 上传自动带 multipart/form-data(boundary)。
});

/**
 * 隐私模式 / 浏览器禁用存储时，访问 storage 会直接抛 SecurityError。
 * 这里存的都是可再生的缓存（CSRF 令牌有 cookie 兜底），所以统一降级成
 * 「读不到 / 写不进」，绝不让它打断认证与请求主流程 ——
 * 尤其 401 分支里的 `setCsrfToken(null)` 一旦抛出，后面的 unauthorizedHandler
 * 就不会执行，用户会被卡在「已登出但界面还以为在登录」的状态。
 */
const safeStorage = (run, fallback = undefined) => {
  try {
    return run();
  } catch {
    return fallback;
  }
};

const readCookie = (name) => {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split('; ')
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
};

export const setCsrfToken = (token) => {
  safeStorage(() => {
    if (token) {
      window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
    } else {
      window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
    }
  });
};

const currentCsrfToken = () =>
  readCookie(import.meta.env.VITE_CSRF_COOKIE_NAME || 'bayes_csrf') ||
  safeStorage(() => window.sessionStorage.getItem(CSRF_STORAGE_KEY), null);

export const getCsrfToken = () => currentCsrfToken();

/**
 * 401 的跳转由路由层接管（main.ts 在装好 router 后注册）。
 *
 * 这里不直接改 window.location：history 模式下 vue-router 只监听 popstate，
 * 改 hash 既不触发导航，还会把地址污染成 /reports#/login。
 * 会话恢复期间（handler 尚未注册）只清凭据，随后的路由守卫会把用户送去
 * /login?redirect=<原目标>。
 */
let unauthorizedHandler = null;

export const setUnauthorizedHandler = (handler) => {
  unauthorizedHandler = handler;
};

const extractErrorMessage = async (error) => {
  let data = error?.response?.data;
  // responseType: 'blob' 的请求失败时，服务端回的是 JSON，但被 axios 包成了 Blob，
  // 不解开就只能报「Request failed with status code 500」这种没用的话
  if (data instanceof Blob) {
    try {
      data = JSON.parse(await data.text());
    } catch {
      data = null;
    }
  }
  if (!data) return error?.message || '请求失败';
  if (typeof data.message === 'string' && data.message) return data.message;
  if (typeof data.detail === 'string' && data.detail) return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => item?.msg || item?.message || JSON.stringify(item))
      .join('; ');
  }
  if (data.detail && typeof data.detail === 'object' && data.detail.message) {
    return data.detail.message;
  }
  return error?.message || '请求失败';
};

service.interceptors.request.use((config) => {
  const method = (config.method || 'get').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrf = currentCsrfToken();
    if (csrf) {
      config.headers = config.headers || {};
      config.headers['X-CSRF-Token'] = csrf;
    }
  }
  return config;
});

service.interceptors.response.use(
  (response) => response.data,
  async (error) => {
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

export const unwrapData = (res) => {
  if (res && res.code === 0) return res.data;
  throw new Error(res?.message || '请求失败');
};

export default service;
