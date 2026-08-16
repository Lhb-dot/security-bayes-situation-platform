import { createRouter, createWebHashHistory } from 'vue-router';
import { getCurrentUser } from '@/services/mockApi';
import { setupRouterGuards } from './guards';

// 告警态势页面
import AlertsView from '@/views/Alert/AlertsView.vue';
import AlertDetailView from '@/views/Alert/AlertDetailView.vue';
// AI模型训练与风险预测
import RiskAnalysis from '@/views/Model/RiskAnalysis.vue';

const routes = [
  {
    path: '/login',
    name: '登录',
    component: () => import('@/views/Login.vue'),
    meta: { title: '用户登录' },
  },
  {
    path: '/home',
    name: '首页',
    component: () => import('@/views/Home/HomeView.vue'),
    meta: { title: '首页', userOnly: true },
  },
  {
    path: '/',
    // 按角色落地：SUPER_ADMIN → 全局总览；SCENARIO_ADMIN/USER → 自己场景详情；其余 → /home
    redirect: () => {
      const role = getCurrentUser()?.role;
      if (role === 'SUPER_ADMIN') return '/overview';
      const bound = getCurrentUser()?.scenario_ids?.[0];
      if (bound) return `/scenarios/${bound}/dashboard`;
      return '/home';
    },
    meta: { title: '首页' },
  },
  {
    path: '/alerts',
    name: '告警详情页',
    component: AlertsView,
    // 告警中心对所有登录用户开放；普通用户仅能看到本人风险事件（数据层已按用户过滤）
    meta: { title: '告警详情页' },
  },
  {
    path: '/alerts/:id',
    name: '告警详情',
    component: AlertDetailView,
    meta: { title: '告警详情' },
  },
  {
    path: '/risk',
    name: 'AI模型训练预测',
    component: RiskAnalysis,
    // 管理级角色（最外层 + 场景管理员）可训练；场景管理员由后端校验仅自己场景
    meta: { title: 'AI模型训练预测' },
  },
  // ===================== 多场景架构新增路由 =====================
  {
    path: '/overview',
    name: '管理员首页',
    component: () => import('@/views/Admin/AdminOverviewView.vue'),
    // 管理员首页（原全局总览）：全平台跨用户态势，仅管理员可访问；普通用户的首页是 /home
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
    // Task 009：场景看板容器（四场景动态分发）；旧 views/Model/ScenarioDashboard.vue 保留未使用
    component: () => import('@/views/Scenario/ScenarioDashboardView.vue'),
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
