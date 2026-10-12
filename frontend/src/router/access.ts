/**
 * access.ts — 前端页面级角色准入的**唯一来源**。
 *
 * 前端隐藏导航 / 路由守卫都只是体验（真正的数据鉴权在后端
 * `backend/app/security/policy.py`）。但「哪些角色能进哪个页面」不能有两份定义，
 * 否则就会出现「导航里隐藏了、手敲地址却进得去」这类漂移 —— 路由 meta.roles
 * 与 App.vue 顶部导航统一读本表。
 *
 * 新增页面只需在 PAGE_ROLES 里加一行；未列出的路径默认所有已登录角色可进。
 */
import type { UserRole } from '@/types/security';

export const ALL_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER'];
export const MGMT_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN'];
export const SUPER_ADMIN_ROLES: UserRole[] = ['SUPER_ADMIN'];

/** 页面路径 → 可访问角色。缺省（未列出的路径）= 所有已登录角色。 */
export const PAGE_ROLES: Record<string, UserRole[]> = {
  '/overview': SUPER_ADMIN_ROLES,
  '/risk': MGMT_ROLES,
  '/users': MGMT_ROLES,
};

/** 取某路径的可访问角色（缺省所有角色）。 */
export const rolesForPath = (path: string): UserRole[] => PAGE_ROLES[path] ?? ALL_ROLES;
