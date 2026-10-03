import { createRouter, createWebHistory } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import type { UserRole } from '@/types/security';
import { roleLanding, setupRouterGuards } from './guards';

// 角色白名单常量。写成 UserRole[] 而不是内联数组字面量：
// routes 的类型是独立推断的，内联字面量会退化成 string[]，传给 createRouter 时报类型错。
const MGMT_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN'];
const SUPER_ADMIN_ROLES: UserRole[] = ['SUPER_ADMIN'];

const routes = [
  {
    path: '/login',
    name: '登录',
    component: () => import('@/views/Login.vue'),
    meta: { title: '用户登录' },
  },
  {
    path: '/',
    // 按角色落地：SUPER_ADMIN → 全局总览；SCENARIO_ADMIN/USER → 自己场景详情；异常无场景账号 → 场景中心。
    // 具体规则只有一份实现（guards.ts 的 roleLanding），此处复用，避免两份副本各自漂移。
    // 未登录时同样先落到场景中心，再由守卫改写成 /login?redirect=...
    redirect: () => {
      const user = useUserStore().currentUser;
      return user ? roleLanding(user) : '/scenarios';
    },
    meta: { title: '首页' },
  },
  {
    // path 保留 /alerts 属历史遗留（改名会打断已分享的链接）；页面本身是风险事件列表。
    path: '/alerts',
    name: '风险事件列表',
    component: () => import('@/views/Event/RiskEventListView.vue'),
    meta: { title: '风险事件列表' },
  },
  {
    path: '/risk',
    name: 'AI模型训练预测',
    // 懒加载：此前是唯一一个静态 import 的路由，会把整个训练预测页打进入口 chunk，
    // 拖慢首屏（首页 / 场景中心）的加载。
    component: () => import('@/views/Model/RiskAnalysis.vue'),
    // 管理级角色（最外层 + 场景管理员）可训练；场景管理员由后端校验仅自己场景
    meta: { title: 'AI模型训练预测', roles: MGMT_ROLES },
  },
  // ===================== 多场景架构新增路由 =====================
  {
    path: '/overview',
    name: '管理员首页',
    component: () => import('@/views/Home/dashboard/DashboardHomeView.vue'),
    // 首页按角色分发：最外层管理员=平台总览；场景管理员=数据画像；场景用户=我的工作台
    meta: { title: '平台运行总览', roles: SUPER_ADMIN_ROLES },
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
    meta: { title: '用户管理', roles: MGMT_ROLES },
  },
  {
    path: '/events/:eventId',
    name: '风险事件详情',
    component: () => import('@/views/Event/RiskEventDetailView.vue'),
    meta: { title: '风险事件详情' },
  },
  {
    // 兜底：history 模式下用户可以直接手敲任意地址，未匹配时必须给出页面。
    // 此前没有这条，未知地址会渲染出「顶栏在、内容区空白」。必须放在最后，按顺序匹配。
    path: '/:pathMatch(.*)*',
    name: '页面不存在',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
];

// 旧 hash 链接迁移：此前地址形如 /#/reports，切到 history 模式后这类地址会落到
// 404 兜底页。装路由之前原地改写成 /reports，让已分享出去的链接继续可用。
//
// 位置很关键：createWebHistory() 在**创建时**就读取 window.location 并缓存当前位置，
// 所以这段必须跑在 createRouter() 之前。放在 main.ts 里已经晚了 —— router 模块
// 先执行完，路由拿到的仍是带 hash 的旧地址（实测会跳成 /login?redirect=/scenarios#/reports）。
// 用 replaceState 而不是赋值 location.pathname —— 后者会真的发起一次整页请求。
if (window.location.hash.startsWith('#/')) {
  window.history.replaceState(null, '', window.location.hash.slice(1));
}

const router = createRouter({
  // history 模式：地址里不再有 #。深链由服务端兜底到 index.html
  // （nginx 的 try_files，以及后端 main.py 的 SPAStaticFiles）。
  history: createWebHistory(),
  routes,
});

// ===================== 角色化路由守卫（Task 005，逻辑见 guards.ts） =====================
// 需求 6.5.2 末段：真正的鉴权在后端，前端守卫/隐藏仅为体验。
setupRouterGuards(router);

export default router;
