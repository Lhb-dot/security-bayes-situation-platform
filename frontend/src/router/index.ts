import { createRouter, createWebHashHistory } from 'vue-router';
import { getCurrentUser } from '@/services/mockApi';

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
  },
  {
    path: '/',
    redirect: '/overview',
  },
  {
    path: '/dashboard',
    name: '态势监控大屏',
    component: DashboardView,
  },
  {
    path: '/alerts',
    name: '告警详情页',
    component: AlertsView,
  },
  {
    path: '/alerts/:id',
    name: '告警详情',
    component: AlertDetailView,
  },
  {
    path: '/risk',
    name: 'AI模型训练预测',
    component: RiskAnalysis,
  },
  // ===================== 多场景架构新增路由 =====================
  {
    path: '/overview',
    name: '全局总览',
    component: () => import('@/views/Model/OverviewView.vue'),
  },
  {
    path: '/scenarios',
    name: '场景中心',
    component: () => import('@/views/Model/ScenarioCenter.vue'),
  },
  {
    path: '/scenarios/:scenarioId/dashboard',
    name: '场景大屏',
    component: () => import('@/views/Model/ScenarioDashboard.vue'),
  },
  {
    path: '/datasets',
    name: '数据集中心',
    component: () => import('@/views/Model/DatasetCenter.vue'),
  },
  {
    path: '/models',
    name: 'ModelCenter',
    component: () => import('@/views/Model/ModelCenter.vue'),
  },
  {
    path: '/inference',
    name: 'RiskInference',
    component: () => import('@/views/Model/RiskInference.vue'),
  },
  {
    path: '/inference-records',
    name: '推理记录',
    component: () => import('@/views/Model/InferenceRecords.vue'),
  },
  {
    path: '/situation',
    name: 'SituationAnalysis',
    component: () => import('@/views/Model/SituationAnalysis.vue'),
  },
  {
    path: '/reports',
    name: 'ReportCenter',
    component: () => import('@/views/Model/ReportCenter.vue'),
  },
  {
    path: '/users',
    name: '用户管理',
    component: () => import('@/views/Model/UserManagement.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Model/Settings.vue'),
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

// ===================== 登录守卫（需求 1.1.1：未登录不得访问业务页面） =====================
router.beforeEach((to) => {
  const user = getCurrentUser();
  if (to.path === '/login') {
    // 已登录访问登录页 → 直接进入全局总览
    return user ? '/overview' : true;
  }
  if (!user) {
    return { path: '/login', query: { redirect: to.fullPath } };
  }
  // 旧版大屏/告警使用的是全平台演示数据，普通用户应使用 v2 页面查看本人数据。
  if (user.role === 'USER' && (to.path === '/dashboard' || to.path === '/alerts' || to.path.startsWith('/alerts/'))) {
    return '/overview';
  }
  return true;
});

export default router;
