import axios from 'axios';

// 创建Axios实例，统一后端基础地址、超时、请求头
const service = axios.create({
  baseURL: 'http://127.0.0.1:12312', // 后端本地服务地址
  timeout: 0, // 不设超时上限
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：可后续统一加token、请求头
service.interceptors.request.use((config) => {
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
