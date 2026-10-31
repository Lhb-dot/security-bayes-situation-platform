/**
 * 角色化路由守卫
 * 权限边界真正的鉴权在后端，前端守卫/隐藏仅为体验。
 * 登录态统一读取 userStore，不在路由层复制 session 逻辑。
 */
import type { Router } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import type { UserAccount, UserRole } from '@/types/security';

declare module 'vue-router' {
  interface RouteMeta {
    title: string;
    roles?: UserRole[];
  }
}

export const roleLanding = (user: UserAccount): string => {
  if (user.role === 'SUPER_ADMIN') return '/overview';
  const bound = user.scenario_code;
  if (bound) return `/scenarios/${bound}/dashboard`;
  return '/scenarios';
};

export const setupRouterGuards = (router: Router): void => {
  router.beforeEach((to) => {
    const userStore = useUserStore();
    const user = userStore.currentUser;

    if (to.path === '/login') {
      return user ? roleLanding(user) : true;
    }
    if (!user) {
      return '/login';
    }
    if (to.path === '/scenarios' && user.role === 'SUPER_ADMIN') {
      return '/overview';
    }
    const allowed = to.meta.roles;
    if (allowed && !allowed.includes(user.role)) {
      return roleLanding(user);
    }
    if (to.path === '/') {
      return roleLanding(user);
    }
    return true;
  });
};
