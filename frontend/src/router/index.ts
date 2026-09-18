import { createRouter, createWebHashHistory } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import { setupRouterGuards } from './guards';

const routes = [
  {
    path: '/login',
    name: '登录',
    component: () => import('@/views/Login.vue'),
    meta: { title: '用户登录' },
  },
  {
    path: '/',
    // 按角色落地：SUPER_ADMIN → 全局总览；SCENARIO_ADMIN/USER → 自己场景详情；异常无场景账号 → 场景中心
    redirect: () => {
      const user = useUserStore().currentUser;
      const role = user?.role;
      if (role === 'SUPER_ADMIN') return '/overview';
      const bound = user?.scenario_code;
      if (bound) return `/scenarios/${bound}/dashboard`;
      return '/scenarios';
    },
    meta: { title: '首页' },
  },
  {
    path: '/alerts',
    name: '风险事件列表',
    component: () => import('@/views/Alert/AlertsView.vue'),
    meta: { title: '风险事件列表' },
  },
  {
    path: '/risk',
    name: 'AI模型训练预测',
    // 懒加载：此前是唯一一个静态 import 的路由，会把整个训练预测页打进入口 chunk，
    // 拖慢首屏（首页 / 场景中心）的加载。
    component: () => import('@/views/Model/RiskAnalysis.vue'),
    // 管理级角色（最外层 + 场景管理员）可训练；场景管理员由后端校验仅自己场景
    meta: { title: 'AI模型训练预测' },
  },
  // ===================== 多场景架构新增路由 =====================
  {
    path: '/overview',
    name: '管理员首页',
    component: () => import('@/views/Home/dashboard/DashboardHomeView.vue'),
    // 首页按角色分发：最外层管理员=平台总览；场景管理员=数据画像；场景用户=我的工作台
    meta: { title: '平台运行总览', requiresAdmin: true, hiddenForUser: true },
  },
  {
    path: '/scenarios',
    name: '场景中心',
    component: () => import('@/views/Model/ScenarioCenter.vue'),
    meta: { title: '场景中心' },
  },
  {
    path: '/scenarios/:scenarioId/dashboard',
    name: '场景大屏',
    // 角色化场景首页：场景管理员显示数据画像，场景用户显示我的工作台
    component: () => import('@/views/Home/dashboard/DashboardHomeView.vue'),
    meta: { title: '场景大屏' },
  },
  {
    path: '/datasets',
    name: '数据集中心',
    component: () => import('@/views/Model/DatasetCenter.vue'),
    meta: { title: '数据集中心' },
  },
  {
    path: '/datasets/:datasetId',
    name: '数据集详情',
    component: () => import('@/views/Dataset/DatasetDetailView.vue'),
    meta: { title: '数据集详情' },
  },
  {
    path: '/models',
    name: 'ModelCenter',
    component: () => import('@/views/Model/ModelCenter.vue'),
    meta: { title: '模型中心' },
  },
  {
    path: '/inference',
    name: 'RiskInference',
    component: () => import('@/views/Model/RiskInference.vue'),
    meta: { title: '风险研判' },
  },
  {
    path: '/inference-records',
    name: '推理记录',
    component: () => import('@/views/Model/InferenceRecords.vue'),
    meta: { title: '推理记录' },
  },
  {
    path: '/reports',
    name: 'ReportCenter',
    component: () => import('@/views/Model/ReportCenter.vue'),
    meta: { title: '报告中心' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Model/Settings.vue'),
    meta: { title: '系统设置' },
  },
  {
    path: '/users',
    name: '用户管理',
    component: () => import('@/views/Model/UserManagement.vue'),
    // 管理级角色（最外层管场景管理员/用户；场景管理员管自己场景用户）；权限由后端校验
    meta: { title: '用户管理' },
  },
  {
    path: '/events/:eventId',
    name: '风险事件详情',
    component: () => import('@/views/Event/RiskEventDetailView.vue'),
    meta: { title: '风险事件详情' },
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

// ===================== 角色化路由守卫（Task 005，逻辑见 guards.ts） =====================
// 需求 6.5.2 末段：真正的鉴权在后端，前端守卫/隐藏仅为体验。
setupRouterGuards(router);

export default router;
