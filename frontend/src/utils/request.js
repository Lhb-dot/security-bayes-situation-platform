import axios from 'axios';

// 创建Axios实例，统一后端基础地址、超时、请求头
const service = axios.create({
  baseURL: 'http://127.0.0.1:12312', // 后端本地服务地址
  timeout: 0, // 不设超时上限
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：统一携带登录凭证（需求 1.1.1 未登录用户不得访问业务接口）
// 会话 key 与 mockApi 保持一致（SESSION_KEY = 'bayes_session_user_id'）
service.interceptors.request.use((config) => {
  const userId = window.localStorage.getItem('bayes_session_user_id');
  if (userId) {
    config.headers['X-User-Id'] = userId;
  }
  return config;
});

// 响应拦截器：统一剥离外层axios包装，直接拿到后端真正data
service.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('后端接口请求异常：', error);
    return Promise.reject(error);
  }
);

export default service;
