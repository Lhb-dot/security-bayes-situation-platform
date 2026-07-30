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
    redirect: '/dashboard',
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
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
