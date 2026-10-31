import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import { rolesForPath } from './access';
import { roleLanding, setupRouterGuards } from './guards';

const routes = [
  {
    path: '/login',
    name: '登录',
    component: () => import('@/views/Login.vue'),
    meta: { title: '用户登录' },
  },
  {
    path: '/',
    // 具体规则只有一份实现（guards.ts 的 roleLanding），此处复用，避免两份副本各自漂移。
    redirect: () => {
      const user = useUserStore().currentUser;
      return user ? roleLanding(user) : '/login';
    },
    meta: { title: '首页' },
  },
  {
    path: '/alerts',
    name: '风险事件列表',
    component: () => import('@/views/Event/RiskEventListView.vue'),
    meta: { title: '风险事件列表' },
  },
  {
    path: '/risk',
    name: 'AI模型训练预测',
    component: () => import('@/views/Model/RiskAnalysis.vue'),
    meta: { title: 'AI模型训练预测', roles: rolesForPath('/risk') },
  },
  {
    path: '/overview',
    name: '管理员首页',
    component: () => import('@/views/Home/dashboard/DashboardHomeView.vue'),
    meta: { title: '平台运行总览', roles: rolesForPath('/overview') },
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
    meta: { title: '用户管理', roles: rolesForPath('/users') },
  },
  {
    path: '/events/:eventId',
    name: '风险事件详情',
    component: () => import('@/views/Event/RiskEventDetailView.vue'),
    meta: { title: '风险事件详情' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: '页面不存在',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
];

// 4 兜底页。装路由之前原地改写成 /reports，让已分享出去的链接继续可用。
// 位置很关键：createWebHistory() 在创建时就读取 window.location 并缓存当前位置，
// 所以这段必须跑在 createRouter() 之前。放在 main.ts 里已经晚了，router 模块
// 先执行完，路由拿到的仍是带 hash 的旧地址（实测会跳成 /login?redirect=/scenarios#/reports）。
// 用 replaceState 而不是赋值 location.pathname，后者会真的发起一次整页请求。
if (window.location.hash.startsWith('#/')) {
  window.history.replaceState(null, '', window.location.hash.slice(1));
}

const router = createRouter({
  // （nginx 的 try_files，以及后端 main.py 的 SPAStaticFiles）。
  history: createWebHistory(),
  routes,
});

// 角色化路由守卫
// 真正的鉴权在后端，前端守卫/隐藏仅为体验。
setupRouterGuards(router);

export default router;
