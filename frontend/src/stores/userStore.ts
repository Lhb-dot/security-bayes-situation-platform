/**
 * userStore.ts — 全局会话与用户管理（Task 004）
 *
 * 职责边界：仅 state / action（调用数据源）/ getter（派生数据），
 * 不含权限拦截、页面业务逻辑与 UI 逻辑。
 *
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/userApi.*
 * （login/logout 后端无路由，持续走 mock）。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { ScenarioId, UserAccount, UserRole } from '@/types/security';

/** 四场景全集（管理员可见范围；普通用户以 currentUser.scenario_ids 为准） */
const ALL_SCENARIO_IDS = [
  'network_security',
  'power_system',
  'geological_risk',
  'flightdeck_operation',
] as const;

export const useUserStore = defineStore('user', {
  state: () => ({
    currentUser: mockApi.getCurrentUser() as UserAccount | null,
    users: [] as UserAccount[],
    loading: false,
  }),
  getters: {
    isAdmin: (state): boolean => state.currentUser?.role === 'ADMIN',
    /** 可见场景范围：管理员全部场景；普通用户仅绑定场景（Task 006 用于入口过滤） */
    visibleScenarioIds: (state): ScenarioId[] =>
      state.currentUser?.role === 'ADMIN'
        ? [...ALL_SCENARIO_IDS]
        : (state.currentUser?.scenario_ids ?? []),
  },
  actions: {
    async login(username: string, password: string): Promise<void> {
      this.loading = true;
      try {
        this.currentUser = await mockApi.login(username, password);
      } finally {
        this.loading = false;
      }
    },
    async logout(): Promise<void> {
      await mockApi.logout();
      this.currentUser = null;
      this.users = [];
    },
    async changePassword(oldPassword: string, newPassword: string): Promise<void> {
      await mockApi.changeOwnPassword(oldPassword, newPassword);
    },
    async fetchUsers(): Promise<void> {
      this.loading = true;
      try {
        this.users = await mockApi.getUserList();
      } finally {
        this.loading = false;
      }
    },
    async createUser(params: {
      username: string;
      display_name: string;
      password: string;
      role: UserRole;
    }): Promise<void> {
      await mockApi.createUser(params);
      await this.fetchUsers();
    },
    async resetUserPassword(userId: string, newPassword: string): Promise<void> {
      await mockApi.resetUserPassword(userId, newPassword);
    },
    async setUserStatus(userId: string, status: 'active' | 'disabled'): Promise<void> {
      await mockApi.setUserStatus(userId, status);
      await this.fetchUsers();
    },
    /** 管理员设置用户绑定场景（需求 1.1.6 / 6.5），保存后刷新用户列表 */
    async updateUserScenarios(userId: string, scenarioIds: ScenarioId[]): Promise<void> {
      await mockApi.setUserScenarioIds(userId, scenarioIds);
      await this.fetchUsers();
    },
  },
});
