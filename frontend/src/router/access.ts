/**
 * 前端页面级角色准入的唯一来源：路由 meta.roles 与顶部导航都读本表。
 * 前端隐藏导航与路由守卫只是体验，真正的数据鉴权在后端。
 */
import type { UserRole } from '@/types/security';

export const ALL_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER'];
export const MGMT_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN'];
export const SUPER_ADMIN_ROLES: UserRole[] = ['SUPER_ADMIN'];

export const PAGE_ROLES: Record<string, UserRole[]> = {
  '/overview': SUPER_ADMIN_ROLES,
  '/risk': MGMT_ROLES,
  '/users': MGMT_ROLES,
};

export const rolesForPath = (path: string): UserRole[] => PAGE_ROLES[path] ?? ALL_ROLES;
