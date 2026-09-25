/**
 * guards.ts — 角色化路由守卫（Task 005）
 *
 * 权限边界（需求 6.5.2 末段）：真正的鉴权在后端，前端守卫/隐藏仅为体验。
 * 登录态统一读取 userStore，不在路由层复制 session 逻辑。
 */
import type { Router } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import type { UserAccount, UserRole } from '@/types/security';

// vue-router RouteMeta 类型增强：路由 meta 字段（Task 005）
declare module 'vue-router' {
  interface RouteMeta {
    /** 页面标题 */
    title: string;
    /**
     * 可访问角色白名单。缺省 = 所有已登录角色可进。
     * 此前只有一个布尔 requiresAdmin，表达不了「管理级两个角色可进」这种规则，
     * 导致 /risk 的注释与守卫行为不一致（导航隐藏但手敲地址能进）。
     */
    roles?: UserRole[];
    /** 普通用户隐藏导航入口（仅入口隐藏，不影响路由注册） */
    hiddenForUser?: boolean;
  }
}

/** 角色落地页：
 * - SUPER_ADMIN（最外层）→ 全局总览 /overview（监控所有场景）
 * - SCENARIO_ADMIN（场景管理员）→ 自己场景详情页
 * - SCENARIO_USER（场景用户）→ 自己场景详情页
 */
const roleLanding = (user: UserAccount): string => {
  if (user.role === 'SUPER_ADMIN') return '/overview';
  const bound = user.scenario_code;
  if (bound) return `/scenarios/${bound}/dashboard`;
  return '/scenarios';
};

/** 注册角色化路由守卫（由 router/index.ts 调用） */
export const setupRouterGuards = (router: Router): void => {
  router.beforeEach((to) => {
    const userStore = useUserStore();
    const user = userStore.currentUser;

    // 已登录访问登录页 → 按角色回落地页；未登录 → 放行登录页
    if (to.path === '/login') {
      return user ? roleLanding(user) : true;
    }
    // 未登录访问业务路由 → 跳登录页并记录原路径（需求 1.1.1）
    if (!user) {
      return { path: '/login', query: { redirect: to.fullPath } };
    }
    // 角色白名单：声明了 meta.roles 的路由只有名单内角色可进（越权 → 落地页）。
    // 与 App.vue 的 navItems.roles 同源，避免「导航里隐藏了、手敲地址却进得去」。
    const allowed = to.meta.roles;
    if (allowed && !allowed.includes(user.role)) {
      return roleLanding(user);
    }
    // 根路径按角色落地（路由配置中也有函数式 redirect，此处双保险）
    if (to.path === '/') {
      return roleLanding(user);
    }
    return true;
  });
};
