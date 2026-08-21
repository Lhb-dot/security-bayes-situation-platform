<script setup lang="ts">
/**
 * UserManagement - 用户管理（真实后端接口）
 *
 * - 登录态 / 列表 / 创建 / 重置密码 / 启停 / 改密：全部走 /api/v1
 * - SUPER_ADMIN：可看全部用户与场景管理员，可创建 SCENARIO_ADMIN / SCENARIO_USER 并绑定场景
 * - SCENARIO_ADMIN：仅管理本场景用户，只能创建 SCENARIO_USER
 */
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import request, { unwrapData } from '@/utils/request';
import { useUserStore } from '@/stores/userStore';
import type { ScenarioId, UserAccount, UserRole } from '@/types/security';

interface ScenarioOption {
  id: number;
  code: ScenarioId;
  name: string;
  access_status?: string;
}

const userStore = useUserStore();

const currentUser = computed(() => userStore.currentUser);
const users = computed(() => userStore.users);
const loading = computed(() => userStore.loading);
const keyword = ref('');

const scenarioOptions = ref<ScenarioOption[]>([]);
const scenarioNameByCode = ref<Record<string, string>>({});
const scenarioNameById = ref<Record<number, string>>({});

const isSuperAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN');
const isManagement = computed(
  () =>
    currentUser.value?.role === 'SUPER_ADMIN' ||
    currentUser.value?.role === 'SCENARIO_ADMIN',
);

const roleLabel = (role: UserRole) => {
  if (role === 'SUPER_ADMIN') return '系统管理员';
  if (role === 'SCENARIO_ADMIN') return '场景管理员';
  return '普通用户';
};

const scenarioLabel = (user: UserAccount) => {
  if (user.scenario_code && scenarioNameByCode.value[user.scenario_code]) {
    return scenarioNameByCode.value[user.scenario_code];
  }
  if (user.scenario_id != null && scenarioNameById.value[user.scenario_id]) {
    return scenarioNameById.value[user.scenario_id];
  }
  if (user.scenario_code) return user.scenario_code;
  return '—';
};

const loadScenarios = async () => {
  const rows = (await unwrapData(await request.get('/api/v1/scenarios'))) as Array<{
    id: number;
    code: string;
    name: string;
    access_status?: string;
  }>;
  const options = (rows ?? []).map((row) => ({
    id: row.id,
    code: row.code as ScenarioId,
    name: row.name,
    access_status: row.access_status,
  }));
  scenarioOptions.value = options;
  scenarioNameByCode.value = Object.fromEntries(options.map((item) => [item.code, item.name]));
  scenarioNameById.value = Object.fromEntries(options.map((item) => [item.id, item.name]));
};

const loadUsers = async () => {
  await userStore.fetchUsers({
    page: 1,
    page_size: 200,
    keyword: keyword.value.trim() || undefined,
  });
};

// ========== 创建用户 ==========
const createOpen = ref(false);
const createSubmitting = ref(false);
const createForm = ref<{
  username: string;
  password: string;
  role: UserRole;
  scenario_id: number | null;
}>({
  username: '',
  password: '',
  role: 'SCENARIO_USER',
  scenario_id: null,
});

const openCreate = () => {
  const defaultRole: UserRole = isSuperAdmin.value ? 'SCENARIO_ADMIN' : 'SCENARIO_USER';
  const defaultScenarioId = isSuperAdmin.value
    ? scenarioOptions.value[0]?.id ?? null
    : currentUser.value?.scenario_id ?? null;
  createForm.value = {
    username: '',
    password: '',
    role: defaultRole,
    scenario_id: defaultScenarioId,
  };
  createOpen.value = true;
};

const submitCreate = async () => {
  if (!createForm.value.username.trim()) {
    ElMessage.warning('请输入用户名');
    return;
  }
  if (!createForm.value.password || createForm.value.password.length < 6) {
    ElMessage.warning('初始密码至少 6 位');
    return;
  }
  if (createForm.value.scenario_id == null) {
    ElMessage.warning('请选择绑定场景');
    return;
  }
  createSubmitting.value = true;
  try {
    await userStore.createUser({
      username: createForm.value.username.trim(),
      password: createForm.value.password,
      role: createForm.value.role,
      scenario_id: Number(createForm.value.scenario_id),
    });
    ElMessage.success('账号创建成功');
    createOpen.value = false;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '创建失败');
  } finally {
    createSubmitting.value = false;
  }
};

// ========== 重置密码 ==========
const resetTarget = ref<UserAccount | null>(null);
const resetPwd = ref('');
const resetSubmitting = ref(false);

const openReset = (user: UserAccount) => {
  resetTarget.value = user;
  resetPwd.value = '';
};

const submitReset = async () => {
  if (!resetTarget.value) return;
  if (!resetPwd.value || resetPwd.value.length < 6) {
    ElMessage.warning('新密码至少 6 位');
    return;
  }
  resetSubmitting.value = true;
  try {
    await userStore.resetUserPassword(resetTarget.value.user_id, resetPwd.value);
    ElMessage.success(`已重置 ${resetTarget.value.username} 的密码`);
    resetTarget.value = null;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重置失败');
  } finally {
    resetSubmitting.value = false;
  }
};

// ========== 启用 / 禁用 ==========
const toggleStatus = async (user: UserAccount) => {
  if (user.id === currentUser.value?.id) {
    ElMessage.warning('不能禁用当前登录账号');
    return;
  }
  const next = user.status === 'active' ? 'disabled' : 'active';
  try {
    await userStore.setUserStatus(user.user_id, next);
    ElMessage.success(next === 'active' ? '账号已启用' : '账号已禁用');
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败');
  }
};

// ========== 修改绑定场景（仅系统管理员） ==========
const bindTarget = ref<UserAccount | null>(null);
const bindScenarioId = ref<number | null>(null);
const bindSubmitting = ref(false);

const openBind = (user: UserAccount) => {
  if (user.role === 'SUPER_ADMIN') {
    ElMessage.warning('系统管理员不绑定场景');
    return;
  }
  bindTarget.value = user;
  bindScenarioId.value = user.scenario_id;
};

const submitBind = async () => {
  if (!bindTarget.value || bindScenarioId.value == null) {
    ElMessage.warning('请选择绑定场景');
    return;
  }
  bindSubmitting.value = true;
  try {
    await userStore.updateUserScenario(bindTarget.value.user_id, Number(bindScenarioId.value));
    ElMessage.success('场景绑定已更新');
    bindTarget.value = null;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '绑定失败');
  } finally {
    bindSubmitting.value = false;
  }
};

// ========== 修改本人密码 ==========
const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' });
const pwdSubmitting = ref(false);

const submitChangePwd = async () => {
  if (!pwdForm.value.oldPassword) {
    ElMessage.warning('请输入原密码');
    return;
  }
  if (!pwdForm.value.newPassword || pwdForm.value.newPassword.length < 6) {
    ElMessage.warning('新密码至少 6 位');
    return;
  }
  if (pwdForm.value.newPassword !== pwdForm.value.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致');
    return;
  }
  pwdSubmitting.value = true;
  try {
    await userStore.changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword);
    ElMessage.success('密码修改成功');
    pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' };
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '修改失败');
  } finally {
    pwdSubmitting.value = false;
  }
};

onMounted(async () => {
  try {
    await loadScenarios();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '场景列表加载失败');
  }
  if (isManagement.value) {
    try {
      await loadUsers();
    } catch (err) {
      ElMessage.error(err instanceof Error ? err.message : '用户列表加载失败');
    }
  }
});
</script>

<template>
  <div class="users-page">
    <div class="users-page__header">
      <div>
        <p class="eyebrow">Account Management</p>
        <h2>用户管理</h2>
        <p class="users-page__desc">
          当前登录：{{ currentUser?.username }}（{{ roleLabel(currentUser?.role || 'SCENARIO_USER') }}）
          <template v-if="isSuperAdmin"> · 可查看全部用户与场景管理员，并创建账号绑定场景</template>
          <template v-else-if="isManagement"> · 仅管理本场景用户</template>
        </p>
      </div>
      <button v-if="isManagement" class="users-btn users-btn--primary" @click="openCreate">
        {{ isSuperAdmin ? '创建账号' : '创建用户' }}
      </button>
    </div>

    <section v-if="isManagement" class="card users-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">User Directory</p>
          <h3>{{ isSuperAdmin ? '全部用户 / 场景管理员' : '本场景用户' }}</h3>
        </div>
        <div class="users-toolbar">
          <input
            v-model.trim="keyword"
            class="pwd-form__input users-search"
            placeholder="按用户名搜索"
            @keyup.enter="loadUsers"
          />
          <button class="users-btn" :disabled="loading" @click="loadUsers">查询</button>
        </div>
      </div>

      <div class="users-table-wrap">
        <table class="users-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>用户名</th>
              <th>角色</th>
              <th>状态</th>
              <th>绑定场景</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.user_id">
              <td>{{ user.id }}</td>
              <td>{{ user.username }}</td>
              <td>
                <span
                  class="role-badge"
                  :class="user.role === 'SCENARIO_USER' ? 'role-badge--user' : 'role-badge--admin'"
                >
                  {{ roleLabel(user.role) }}
                </span>
              </td>
              <td>
                <span
                  class="status-badge"
                  :class="user.status === 'active' ? 'status-badge--on' : 'status-badge--off'"
                >
                  {{ user.status === 'active' ? '启用' : '禁用' }}
                </span>
              </td>
              <td>
                <span v-if="user.scenario_id != null || user.scenario_code" class="scenario-tag">
                  {{ scenarioLabel(user) }}
                </span>
                <span v-else class="users-table__muted">—</span>
              </td>
              <td>{{ user.created_at }}</td>
              <td class="users-table__ops">
                <button class="op-btn" @click="openReset(user)">重置密码</button>
                <button
                  v-if="isSuperAdmin && user.role !== 'SUPER_ADMIN'"
                  class="op-btn"
                  @click="openBind(user)"
                >
                  绑定场景
                </button>
                <button
                  class="op-btn"
                  :class="user.status === 'active' ? 'op-btn--danger' : 'op-btn--ok'"
                  :disabled="user.id === currentUser?.id"
                  @click="toggleStatus(user)"
                >
                  {{ user.status === 'active' ? '禁用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="loading" class="users-table__empty">加载中...</p>
        <p v-else-if="!users.length" class="users-table__empty">暂无用户数据</p>
      </div>
    </section>

    <section class="card users-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">My Password</p>
          <h3>修改本人密码</h3>
        </div>
      </div>
      <div class="pwd-form">
        <div class="pwd-form__field">
          <label class="pwd-form__label">原密码</label>
          <input
            v-model="pwdForm.oldPassword"
            type="password"
            class="pwd-form__input"
            placeholder="请输入原密码"
          />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">新密码</label>
          <input
            v-model="pwdForm.newPassword"
            type="password"
            class="pwd-form__input"
            placeholder="至少 6 位"
          />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">确认新密码</label>
          <input
            v-model="pwdForm.confirmPassword"
            type="password"
            class="pwd-form__input"
            placeholder="再次输入新密码"
          />
        </div>
        <button class="users-btn users-btn--primary" :disabled="pwdSubmitting" @click="submitChangePwd">
          {{ pwdSubmitting ? '保存中...' : '保存新密码' }}
        </button>
      </div>
    </section>

    <el-dialog
      v-model="createOpen"
      :title="isSuperAdmin ? '创建账号并绑定场景' : '创建本场景用户'"
      width="480px"
      align-center
      append-to-body
      lock-scroll
      :close-on-click-modal="false"
    >
      <div class="pwd-form" style="display: grid; gap: 14px">
        <div class="pwd-form__field">
          <label class="pwd-form__label">用户名（登录账号）</label>
          <input
            v-model.trim="createForm.username"
            class="pwd-form__input"
            placeholder="如 zhangsan"
          />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">初始密码（至少 6 位）</label>
          <input
            v-model="createForm.password"
            type="password"
            class="pwd-form__input"
            placeholder="初始密码"
          />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">角色</label>
          <select
            v-model="createForm.role"
            class="pwd-form__input"
            :disabled="!isSuperAdmin"
          >
            <option v-if="isSuperAdmin" value="SCENARIO_ADMIN">场景管理员</option>
            <option value="SCENARIO_USER">普通用户</option>
          </select>
          <p v-if="isSuperAdmin" class="bind-tip">系统管理员可创建场景管理员或普通用户</p>
          <p v-else class="bind-tip">场景管理员只能创建本场景普通用户</p>
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">绑定场景</label>
          <select
            v-model="createForm.scenario_id"
            class="pwd-form__input"
            :disabled="!isSuperAdmin"
          >
            <option
              v-for="sc in scenarioOptions"
              :key="sc.id"
              :value="sc.id"
            >
              {{ sc.name }}
            </option>
          </select>
          <p v-if="!isSuperAdmin" class="bind-tip">固定绑定当前场景，不可更改</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="createOpen = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <div v-if="resetTarget" class="modal-mask" @click.self="resetTarget = null">
      <div class="modal-card">
        <div class="modal-card__head">
          <h3>重置密码 — {{ resetTarget.username }}</h3>
          <button class="modal-close" @click="resetTarget = null">✕</button>
        </div>
        <div class="modal-card__body">
          <div class="pwd-form__field">
            <label class="pwd-form__label">新密码（至少 6 位）</label>
            <input
              v-model="resetPwd"
              type="password"
              class="pwd-form__input"
              placeholder="请输入新密码"
            />
          </div>
        </div>
        <div class="modal-card__foot">
          <button class="users-btn" @click="resetTarget = null">取消</button>
          <button class="users-btn users-btn--primary" :disabled="resetSubmitting" @click="submitReset">
            {{ resetSubmitting ? '提交中...' : '确认重置' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="bindTarget" class="modal-mask" @click.self="bindTarget = null">
      <div class="modal-card">
        <div class="modal-card__head">
          <h3>绑定场景 — {{ bindTarget.username }}</h3>
          <button class="modal-close" @click="bindTarget = null">✕</button>
        </div>
        <div class="modal-card__body">
          <div class="pwd-form__field">
            <label class="pwd-form__label">选择场景</label>
            <select v-model="bindScenarioId" class="pwd-form__input">
              <option
                v-for="sc in scenarioOptions"
                :key="sc.id"
                :value="sc.id"
              >
                {{ sc.name }}
              </option>
            </select>
          </div>
        </div>
        <div class="modal-card__foot">
          <button class="users-btn" @click="bindTarget = null">取消</button>
          <button class="users-btn users-btn--primary" :disabled="bindSubmitting" @click="submitBind">
            {{ bindSubmitting ? '保存中...' : '确认绑定' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.users-page {
  position: relative;
  z-index: 1;
}

.users-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.users-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.users-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.users-section {
  padding: 20px 24px;
  margin-bottom: 18px;
}

.section-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.section-heading h3 {
  margin: 0;
}

.users-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
}

.users-search {
  min-width: 180px;
}

.users-table-wrap {
  overflow-x: auto;
}

.users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}

.users-table th {
  text-align: left;
  padding: 12px 14px;
  color: rgba(154, 214, 255, 0.8);
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.15);
  white-space: nowrap;
}

.users-table td {
  padding: 12px 14px;
  color: rgba(217, 232, 255, 0.9);
  border-bottom: 1px solid rgba(125, 201, 255, 0.07);
}

.users-table tbody tr:hover {
  background: rgba(20, 44, 72, 0.5);
}

.users-table__ops {
  display: flex;
  gap: 8px;
  white-space: nowrap;
}

.users-table__empty {
  padding: 20px;
  text-align: center;
  color: rgba(220, 234, 255, 0.5);
}

.users-table__muted {
  color: rgba(220, 234, 255, 0.4);
}

.scenario-tag {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
  font-size: 0.76rem;
  white-space: nowrap;
}

.bind-tip {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.55);
}

.op-btn {
  padding: 5px 12px;
  border: 1px solid rgba(125, 201, 255, 0.28);
  border-radius: 6px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.8rem;
  cursor: pointer;
}

.op-btn:hover:not(:disabled) {
  background: rgba(91, 166, 255, 0.2);
}

.op-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.op-btn--danger {
  color: #ff7b72;
  border-color: rgba(255, 123, 114, 0.3);
}

.op-btn--ok {
  color: #53e5c8;
  border-color: rgba(83, 229, 200, 0.3);
}

.role-badge,
.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.78rem;
}

.role-badge--admin {
  background: rgba(167, 139, 250, 0.18);
  color: #c4b5fd;
}

.role-badge--user {
  background: rgba(91, 166, 255, 0.16);
  color: #9ad6ff;
}

.status-badge--on {
  background: rgba(83, 229, 200, 0.14);
  color: #53e5c8;
}

.status-badge--off {
  background: rgba(255, 123, 114, 0.14);
  color: #ff7b72;
}

.pwd-form {
  display: grid;
  gap: 14px;
  max-width: 460px;
}

.pwd-form__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pwd-form__label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.pwd-form__input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
}

.pwd-form__input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

select.pwd-form__input option {
  background: #0b1628;
  color: #e8f1ff;
}

.users-btn {
  padding: 10px 20px;
  border: 1px solid rgba(125, 201, 255, 0.25);
  border-radius: 10px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s;
  width: fit-content;
}

.users-btn:hover {
  background: rgba(91, 166, 255, 0.2);
}

.users-btn--primary {
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  border: none;
  font-weight: 600;
}

.users-btn--primary:hover {
  opacity: 0.9;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(3, 8, 16, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-card {
  width: 440px;
  max-width: calc(100vw - 40px);
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.96), rgba(8, 17, 31, 0.98));
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.1);
}

.modal-card__head h3 {
  margin: 0;
  font-size: 1.05rem;
}

.modal-close {
  border: none;
  background: transparent;
  color: rgba(220, 234, 255, 0.6);
  font-size: 1rem;
  cursor: pointer;
}

.modal-card__body {
  padding: 20px;
  display: grid;
  gap: 14px;
}

.modal-card__foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid rgba(125, 201, 255, 0.1);
}
</style>
