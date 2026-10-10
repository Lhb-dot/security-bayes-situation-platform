import { defineStore } from 'pinia';
import * as userApi from '@/api/userApi';
import { invalidateSessionRequests, RequestError, setCsrfToken } from '@/utils/request';
import type { ScenarioId, UserAccount, UserRole } from '@/types/security';

const ALL_SCENARIO_IDS: ScenarioId[] = [
  'network_security',
  'power_system',
  'geological_risk',
  'flightdeck_operation',
];

interface SessionTask {
  controller: AbortController;
  promise: Promise<void>;
}
interface SessionRuntime {
  revision: number;
  restore: SessionTask | null;
  auth: (SessionTask & { kind: 'login' | 'logout' }) | null;
  usersSequence: number;
}
// 不把 Promise/AbortController 放入响应式状态；多个 Pinia 实例独立持有恢复请求。
const sessions = new WeakMap<object, SessionRuntime>();
const sessionFor = (store: object): SessionRuntime => {
  let session = sessions.get(store);
  if (!session) {
    session = { revision: 0, restore: null, auth: null, usersSequence: 0 };
    sessions.set(store, session);
  }
  return session;
};
const obsoleteLogin = () => new RequestError('登录请求已失效，请重新登录', { code: 'ERR_CANCELED' });

export const useUserStore = defineStore('user', {
  state: () => ({
    currentUser: null as UserAccount | null,
    users: [] as UserAccount[],
    usersTotal: 0,
    restoringSession: false,
    authenticating: false,
    loadingUsers: false,
    initialized: false,
    bootstrapError: '',
  }),
  getters: {
    loading: (state): boolean => state.restoringSession || state.authenticating || state.loadingUsers,
    isSuperAdmin: (state): boolean => state.currentUser?.role === 'SUPER_ADMIN',
    isScenarioAdmin: (state): boolean => state.currentUser?.role === 'SCENARIO_ADMIN',
    isManagement: (state): boolean =>
      state.currentUser?.role === 'SUPER_ADMIN' || state.currentUser?.role === 'SCENARIO_ADMIN',
    visibleScenarioIds: (state): ScenarioId[] =>
      state.currentUser?.role === 'SUPER_ADMIN'
        ? [...ALL_SCENARIO_IDS]
        : state.currentUser?.scenario_code
          ? [state.currentUser.scenario_code]
          : [],
    boundScenarioId: (state): ScenarioId | null => state.currentUser?.scenario_code ?? null,
  },
  actions: {
    bootstrap(): Promise<void> {
      const session = sessionFor(this);
      // 登录/退出意图优先于恢复；复用其完成信号，不发新的 getMe。
      if (session.auth) return session.auth.promise.catch(() => {});
      if (session.restore) return session.restore.promise;
      if (this.initialized && !this.bootstrapError) return Promise.resolve();
      const revision = session.revision;
      const controller = new AbortController();
      const isCurrent = () => revision === session.revision && !controller.signal.aborted;
      this.restoringSession = true;
      this.bootstrapError = '';
      const task = Promise.resolve().then(async () => {
        if (!isCurrent()) return;
        try {
          const user = await userApi.getMe({ signal: controller.signal });
          if (isCurrent()) this.currentUser = user;
        } catch (error) {
          if (!isCurrent()) return;
          this.currentUser = null;
          if (!(error instanceof RequestError && error.status === 401)) {
            this.bootstrapError = error instanceof RequestError && error.kind === 'timeout'
              ? '会话恢复超时，请检查网络后重新登录或刷新重试'
              : '暂时无法恢复会话，请检查网络后重新登录或刷新重试';
          }
        } finally {
          if (isCurrent()) {
            this.initialized = true;
            this.restoringSession = false;
          }
        }
      }).finally(() => {
        if (session.restore?.promise === task) session.restore = null;
      });
      session.restore = { controller, promise: task };
      return task;
    },

    /** 仅清前端会话；401 使用此动作，不向后端额外发送退出请求。 */
    expireSession(options?: { clearCredentials?: boolean }): void {
      const session = sessionFor(this);
      session.revision += 1;
      session.restore?.controller.abort();
      session.auth?.controller.abort();
      session.restore = null;
      session.auth = null;
      session.usersSequence += 1;
      invalidateSessionRequests();
      // 退出 POST 仍需当前 CSRF；该请求结束时再由 userApi 清理。
      if (options?.clearCredentials !== false) setCsrfToken(null);
      this.currentUser = null;
      this.users = [];
      this.usersTotal = 0;
      this.initialized = true;
      this.bootstrapError = '';
      this.restoringSession = false;
      this.authenticating = false;
      this.loadingUsers = false;
    },

    login(username: string, password: string): Promise<void> {
      this.expireSession();
      const session = sessionFor(this);
      const revision = session.revision;
      const controller = new AbortController();
      const isCurrent = () => revision === session.revision && !controller.signal.aborted;
      this.authenticating = true;
      const task = Promise.resolve().then(async () => {
        if (!isCurrent()) throw obsoleteLogin();
        try {
          const user = await userApi.login(username, password, { signal: controller.signal, isCurrent });
          if (!isCurrent()) throw obsoleteLogin();
          invalidateSessionRequests();
          this.currentUser = user;
        } catch (error) {
          if (!isCurrent()) throw obsoleteLogin();
          throw error;
        } finally {
          if (isCurrent()) this.authenticating = false;
        }
      }).finally(() => {
        if (session.auth?.promise === task) session.auth = null;
      });
      session.auth = { controller, promise: task, kind: 'login' };
      return task;
    },

    logout(): Promise<void> {
      const session = sessionFor(this);
      if (session.auth?.kind === 'logout') return session.auth.promise;
      // 立即失效，旧恢复/查询不能在退出请求等待期间回填用户和列表。
      this.expireSession({ clearCredentials: false });
      const revision = session.revision;
      const controller = new AbortController();
      const isCurrent = () => revision === session.revision && !controller.signal.aborted;
      this.authenticating = true;
      const task = Promise.resolve().then(async () => {
        if (!isCurrent()) return;
        try {
          await userApi.logout({ signal: controller.signal, isCurrent });
        } catch (error) {
          if (isCurrent()) throw error;
        } finally {
          if (isCurrent()) this.authenticating = false;
        }
      }).finally(() => {
        if (session.auth?.promise === task) session.auth = null;
      });
      session.auth = { controller, promise: task, kind: 'logout' };
      return task;
    },
    async changePassword(oldPassword: string, newPassword: string): Promise<void> {
      if (!this.currentUser) throw new Error('未登录，请先登录系统');
      await userApi.changePassword(this.currentUser.user_id, {
        old_password: oldPassword,
        new_password: newPassword,
      });
    },
    async fetchUsers(params?: userApi.UserListParams): Promise<void> {
      const owner = this.currentUser?.user_id;
      if (!owner) return;
      const session = sessionFor(this);
      const revision = session.revision;
      const sequence = ++session.usersSequence;
      const isCurrent = () => revision === session.revision && sequence === session.usersSequence
        && owner === this.currentUser?.user_id;
      this.loadingUsers = true;
      try {
        const result = await userApi.getUserList(params);
        if (!isCurrent()) return;
        this.users = result.items;
        this.usersTotal = result.total;
      } catch (error) {
        if (isCurrent()) throw error;
      } finally {
        if (revision === session.revision && sequence === session.usersSequence) this.loadingUsers = false;
      }
    },
    async createUser(
      params: {
        username: string;
        password: string;
        role: UserRole;
        scenario_id?: number | null;
      },
      listParams?: userApi.UserListParams,
    ): Promise<UserAccount> {
      const created = await userApi.createUser(params);
      await this.fetchUsers(listParams);
      return created;
    },
    async updateUserScenario(
      userId: string,
      scenarioId: number,
      listParams?: userApi.UserListParams,
    ): Promise<void> {
      await userApi.updateUserScenario(userId, scenarioId);
      await this.fetchUsers(listParams);
    },
    async resetUserPassword(userId: string, newPassword: string): Promise<void> {
      await userApi.resetPassword(userId, newPassword);
    },
    async setUserStatus(
      userId: string,
      status: 'active' | 'disabled',
      listParams?: userApi.UserListParams,
    ): Promise<void> {
      await userApi.setUserStatus(userId, status);
      await this.fetchUsers(listParams);
    },
  },
});
