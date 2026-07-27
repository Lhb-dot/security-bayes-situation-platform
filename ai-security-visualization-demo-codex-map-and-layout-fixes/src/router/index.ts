import { createRouter, createWebHashHistory } from 'vue-router';
// 大屏、告警页面都在components文件夹
import DashboardView from '@/components/DashboardView.vue';
import AlertsView from '@/components/AlertsView.vue';
// AI页面在views文件夹
import RiskAnalysis from '@/views/RiskAnalysis.vue';

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
  // 告警页面路由
  {
    path: '/alerts',
    name: '告警详情页',
    component: AlertsView,
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
    component: () => import('@/views/OverviewView.vue'),
  },
  {
    path: '/scenarios',
    name: '场景中心',
    component: () => import('@/views/ScenarioCenter.vue'),
  },
  {
    path: '/scenarios/:scenarioId/dashboard',
    name: '场景大屏',
    component: () => import('@/views/ScenarioDashboard.vue'),
  },
  {
    path: '/datasets',
    name: '数据集中心',
    component: () => import('@/views/DatasetCenter.vue'),
  },
  {
    path: '/models',
    name: 'ModelCenter',
    component: () => import('@/views/ModelCenter.vue'),
  },
  {
    path: '/inference',
    name: 'RiskInference',
    component: () => import('@/views/RiskInference.vue'),
  },
  {
    path: '/situation',
    name: 'SituationAnalysis',
    component: () => import('@/views/SituationAnalysis.vue'),
  },
  {
    path: '/reports',
    name: 'ReportCenter',
    component: () => import('@/views/ReportCenter.vue'),
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/Settings.vue'),
  },
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
