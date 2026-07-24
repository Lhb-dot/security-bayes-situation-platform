import { createRouter, createWebHashHistory } from 'vue-router';
// 大屏、告警页面都在components文件夹
import DashboardView from '@/components/DashboardView.vue';
import AlertsView from '@/components/AlertsView.vue';
// AI页面在views文件夹
import RiskAnalysis from '@/views/RiskAnalysis.vue';

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
];

const router = createRouter({
  history: createWebHashHistory(),
  routes,
});

export default router;
