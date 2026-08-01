import { createRouter, createWebHashHistory } from 'vue-router';

// 仪表盘大屏
import DashboardView from '@/views/Dashboard/DashboardView.vue';
// 告警态势页面
import AlertsView from '@/views/Alert/AlertsView.vue';
import AlertDetailView from '@/views/Alert/AlertDetailView.vue';
// AI模型训练与风险预测
import RiskAnalysis from '@/views/Model/RiskAnalysis.vue';

const routes = [
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
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Model/Settings.vue'),
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
