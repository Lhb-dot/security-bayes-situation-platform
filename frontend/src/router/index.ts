import { createRouter, createWebHashHistory } from 'vue-router';
import { getCurrentUser } from '@/services/mockApi';
import { setupRouterGuards } from './guards';

// 仪表盘大屏
import DashboardView from '@/views/Dashboard/DashboardView.vue';
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
    name: '首页（全局态势）',
    component: () => import('@/views/Home/HomeView.vue'),
    meta: { title: '首页（全局态势）', userOnly: true },
  },
  {
    path: '/',
    // Task 007：按角色落地（ADMIN → 场景中心；USER → 首页 /home）
    redirect: () => (getCurrentUser()?.role === 'ADMIN' ? '/scenarios' : '/home'),
    meta: { title: '首页' },
  },
  {
    path: '/dashboard',
    name: '态势监控大屏',
    component: DashboardView,
    meta: { title: '态势监控大屏', requiresAdmin: true, hiddenForUser: true },
  },
  {
    path: '/alerts',
    name: '告警详情页',
    component: AlertsView,
    meta: { title: '告警详情页', requiresAdmin: true, hiddenForUser: true },
  },
  {
    path: '/alerts/:id',
    name: '告警详情',
    component: AlertDetailView,
    meta: { title: '告警详情', requiresAdmin: true, hiddenForUser: true },
  },
  {
    path: '/risk',
    name: 'AI模型训练预测',
    component: RiskAnalysis,
    meta: { title: 'AI模型训练预测', requiresAdmin: true, hiddenForUser: true },
  },
  // ===================== 多场景架构新增路由 =====================
  {
    path: '/overview',
    name: '全局总览',
    component: () => import('@/views/Model/OverviewView.vue'),
    // 需求 6.5.2：全局总览为全平台跨用户态势，仅管理员可访问；普通用户的全局视图是 /home
    meta: { title: '全局总览', requiresAdmin: true, hiddenForUser: true },
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
    path: '/situation',
    name: 'SituationAnalysis',
    component: () => import('@/views/Model/SituationAnalysis.vue'),
    meta: { title: '态势分析' },
  },
  {
    path: '/reports',
    name: 'ReportCenter',
    component: () => import('@/views/Model/ReportCenter.vue'),
    meta: { title: '报告中心' },
  },
  {
    path: '/users',
    name: '用户管理',
    component: () => import('@/views/Model/UserManagement.vue'),
    meta: { title: '用户管理', requiresAdmin: true, hiddenForUser: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Model/Settings.vue'),
    meta: { title: '系统设置' },
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
