import { defineStore } from 'pinia';
import * as userApi from '@/api/userApi';
import type { ScenarioId, UserAccount, UserRole } from '@/types/security';

const ALL_SCENARIO_IDS: ScenarioId[] = [
  'network_security',
  'power_system',
  'geological_risk',
  'flightdeck_operation',
];

export const useUserStore = defineStore('user', {
  state: () => ({
    currentUser: null as UserAccount | null,
    users: [] as UserAccount[],
    loading: false,
    initialized: false,
  }),
  getters: {
    isAdmin: (state): boolean => state.currentUser?.role === 'SUPER_ADMIN',
    isSuperAdmin: (state): boolean => state.currentUser?.role === 'SUPER_ADMIN',
    isScenarioAdmin: (state): boolean => state.currentUser?.role === 'SCENARIO_ADMIN',
    isManagement: (state): boolean =>
      state.currentUser?.role === 'SUPER_ADMIN' || state.currentUser?.role === 'SCENARIO_ADMIN',
    visibleScenarioIds: (state): ScenarioId[] =>
      state.currentUser?.role === 'SUPER_ADMIN'
        ? [...ALL_SCENARIO_IDS]
        : state.currentUser?.scenario_code ? [state.currentUser.scenario_code] : [],
    boundScenarioId: (state): ScenarioId | null => state.currentUser?.scenario_code ?? null,
  },
  actions: {
    async bootstrap(): Promise<void> {
      if (this.initialized) return;
      this.loading = true;
      try {
        this.currentUser = await userApi.getMe();
      } catch {
        this.currentUser = null;
      } finally {
        this.initialized = true;
        this.loading = false;
      }
    },
    async login(username: string, password: string): Promise<void> {
      this.loading = true;
      try {
        this.currentUser = await userApi.login(username, password);
        this.initialized = true;
      } finally {
        this.loading = false;
      }
    },
    async logout(): Promise<void> {
      try {
        await userApi.logout();
      } finally {
        this.currentUser = null;
        this.users = [];
        this.initialized = true;
      }
    },
    async changePassword(oldPassword: string, newPassword: string): Promise<void> {
      if (!this.currentUser) throw new Error('未登录，请先登录系统');
      await userApi.changePassword(this.currentUser.user_id, {
        old_password: oldPassword,
        new_password: newPassword,
      });
    },
    async fetchUsers(): Promise<void> {
      this.loading = true;
      try {
        this.users = await userApi.getUserList();
      } finally {
        this.loading = false;
      }
    },
    async createUser(params: {
      username: string;
      display_name: string;
      password: string;
      role: UserRole;
      scenario_id?: number | null;
    }): Promise<void> {
      await userApi.createUser({
        username: params.username,
        password: params.password,
        role: params.role,
        scenario_id: params.scenario_id,
      });
      await this.fetchUsers();
    },
    async resetUserPassword(userId: string, newPassword: string): Promise<void> {
      await userApi.resetPassword(userId, newPassword);
    },
    async setUserStatus(userId: string, status: 'active' | 'disabled'): Promise<void> {
      await userApi.setUserStatus(userId, status);
      await this.fetchUsers();
    },
  },
});
