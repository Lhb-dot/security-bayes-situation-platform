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

const readCookie = (name) => {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split('; ')
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
};

export const setCsrfToken = (token) => {
  if (token) {
    window.sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  } else {
    window.sessionStorage.removeItem(CSRF_STORAGE_KEY);
  }
};

const currentCsrfToken = () =>
  readCookie(import.meta.env.VITE_CSRF_COOKIE_NAME || 'bayes_csrf') ||
  window.sessionStorage.getItem(CSRF_STORAGE_KEY);

const extractErrorMessage = (error) => {
  const data = error?.response?.data;
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
  (error) => {
    if (error.response?.status === 401) {
      setCsrfToken(null);
      window.localStorage.removeItem('bayes_session_user_id');
      if (window.location.hash !== '#/login') {
        window.location.hash = '#/login';
      }
    }
    return Promise.reject(new Error(extractErrorMessage(error)));
  },
);

export const unwrapData = (res) => {
  if (res && res.code === 0) return res.data;
  throw new Error(res?.message || '请求失败');
};

export default service;
