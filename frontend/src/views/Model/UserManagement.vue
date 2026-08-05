<script setup lang="ts">
/**
 * UserManagement - 用户管理
 *
 * 需求 6.2（P0）：管理员创建普通用户账号，并可重置密码、启用或禁用账号；普通用户可修改本人密码。
 */
import { onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  getCurrentUser,
  getUserList,
  createUser,
  resetUserPassword,
  setUserStatus,
  changeOwnPassword,
} from '@/services/mockApi';
import type { UserAccount, UserRole } from '@/types/security';

const currentUser = ref<UserAccount | null>(null);
const users = ref<UserAccount[]>([]);
const loading = ref(false);

const isAdmin = () => currentUser.value?.role === 'ADMIN';

// ========== 创建用户弹窗 ==========
const createOpen = ref(false);
const createForm = ref({
  username: '',
  display_name: '',
  password: '',
  role: 'USER' as UserRole,
});

const openCreate = () => {
  createForm.value = { username: '', display_name: '', password: '', role: 'USER' };
  createOpen.value = true;
};

const submitCreate = async () => {
  try {
    await createUser({ ...createForm.value, role: createForm.value.role });
    ElMessage.success('账号创建成功');
    createOpen.value = false;
    await loadUsers();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '创建失败');
  }
};

// ========== 重置密码 ==========
const resetTarget = ref<UserAccount | null>(null);
const resetPwd = ref('');

const openReset = (user: UserAccount) => {
  resetTarget.value = user;
  resetPwd.value = '';
};

const submitReset = async () => {
  if (!resetTarget.value) return;
  try {
    await resetUserPassword(resetTarget.value.user_id, resetPwd.value);
    ElMessage.success(`已重置 ${resetTarget.value.username} 的密码`);
    resetTarget.value = null;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重置失败');
  }
};

// ========== 启用 / 禁用 ==========
const toggleStatus = async (user: UserAccount) => {
  const next = user.status === 'active' ? 'disabled' : 'active';
  try {
    await setUserStatus(user.user_id, next);
    ElMessage.success(next === 'active' ? '账号已启用' : '账号已禁用');
    await loadUsers();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败');
  }
};

// ========== 修改本人密码 ==========
const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' });

const submitChangePwd = async () => {
  if (!pwdForm.value.newPassword) {
    ElMessage.warning('请输入新密码');
    return;
  }
  if (pwdForm.value.newPassword !== pwdForm.value.confirmPassword) {
    ElMessage.warning('两次输入的新密码不一致');
    return;
  }
  try {
    await changeOwnPassword(pwdForm.value.oldPassword, pwdForm.value.newPassword);
    ElMessage.success('密码修改成功');
    pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' };
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '修改失败');
  }
};

const loadUsers = async () => {
  loading.value = true;
  try {
    users.value = await getUserList();
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  currentUser.value = getCurrentUser();
  if (isAdmin()) await loadUsers();
});
</script>

<template>
  <div class="users-page">
    <div class="users-page__header">
      <div>
        <p class="eyebrow">Account Management</p>
        <h2>用户管理</h2>
        <p class="users-page__desc">
          当前登录：{{ currentUser?.display_name }}（{{ currentUser?.role === 'ADMIN' ? '管理员' : '普通用户' }}）
        </p>
      </div>
      <button v-if="isAdmin()" class="users-btn users-btn--primary" @click="openCreate">+ 创建用户</button>
    </div>

    <!-- 普通用户无权查看用户列表，仅可修改本人密码 -->
    <section v-if="isAdmin()" class="card users-section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Accounts</p>
          <h3>账号列表</h3>
        </div>
      </div>
      <div class="users-table-wrap">
        <table class="users-table">
          <thead>
            <tr>
              <th>用户ID</th>
              <th>用户名</th>
              <th>显示名</th>
              <th>角色</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>最后登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.user_id">
              <td>{{ user.user_id }}</td>
              <td>{{ user.username }}</td>
              <td>{{ user.display_name }}</td>
              <td>
                <span class="role-badge" :class="user.role === 'ADMIN' ? 'role-badge--admin' : 'role-badge--user'">
                  {{ user.role === 'ADMIN' ? '管理员' : '普通用户' }}
                </span>
              </td>
              <td>
                <span class="status-badge" :class="user.status === 'active' ? 'status-badge--on' : 'status-badge--off'">
                  {{ user.status === 'active' ? '启用' : '禁用' }}
                </span>
              </td>
              <td>{{ user.created_at }}</td>
              <td>{{ user.last_login_at ?? '—' }}</td>
              <td class="users-table__ops">
                <button
                  class="op-btn"
                  :disabled="!isAdmin()"
                  @click="openReset(user)"
                >
                  重置密码
                </button>
                <button
                  class="op-btn"
                  :class="user.status === 'active' ? 'op-btn--danger' : 'op-btn--ok'"
                  :disabled="!isAdmin()"
                  @click="toggleStatus(user)"
                >
                  {{ user.status === 'active' ? '禁用' : '启用' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="loading" class="users-table__empty">加载中...</p>
      </div>
    </section>

    <!-- 修改本人密码（所有角色可用，需求 6.2） -->
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
          <input v-model="pwdForm.oldPassword" type="password" class="pwd-form__input" placeholder="请输入原密码" />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">新密码</label>
          <input v-model="pwdForm.newPassword" type="password" class="pwd-form__input" placeholder="至少 6 位" />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">确认新密码</label>
          <input v-model="pwdForm.confirmPassword" type="password" class="pwd-form__input" placeholder="再次输入新密码" />
        </div>
        <button class="users-btn users-btn--primary" @click="submitChangePwd">保存新密码</button>
      </div>
    </section>

    <!-- 创建用户弹窗 -->
    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <div class="modal-card">
        <div class="modal-card__head">
          <h3>创建普通用户账号</h3>
          <button class="modal-close" @click="createOpen = false">✕</button>
        </div>
        <div class="modal-card__body">
          <div class="pwd-form__field">
            <label class="pwd-form__label">用户名（登录账号）</label>
            <input v-model.trim="createForm.username" class="pwd-form__input" placeholder="如 zhangsan" />
          </div>
          <div class="pwd-form__field">
            <label class="pwd-form__label">显示名</label>
            <input v-model.trim="createForm.display_name" class="pwd-form__input" placeholder="如 张三" />
          </div>
          <div class="pwd-form__field">
            <label class="pwd-form__label">初始密码（至少 6 位）</label>
            <input v-model="createForm.password" type="password" class="pwd-form__input" placeholder="初始密码" />
          </div>
          <div class="pwd-form__field">
            <label class="pwd-form__label">角色</label>
            <select v-model="createForm.role" class="pwd-form__input">
              <option value="USER">普通用户</option>
              <option value="ADMIN">管理员</option>
            </select>
          </div>
        </div>
        <div class="modal-card__foot">
          <button class="users-btn" @click="createOpen = false">取消</button>
          <button class="users-btn users-btn--primary" @click="submitCreate">创建</button>
        </div>
      </div>
    </div>

    <!-- 重置密码弹窗 -->
    <div v-if="resetTarget" class="modal-mask" @click.self="resetTarget = null">
      <div class="modal-card">
        <div class="modal-card__head">
          <h3>重置密码 — {{ resetTarget.username }}</h3>
          <button class="modal-close" @click="resetTarget = null">✕</button>
        </div>
        <div class="modal-card__body">
          <div class="pwd-form__field">
            <label class="pwd-form__label">新密码（至少 6 位）</label>
            <input v-model="resetPwd" type="password" class="pwd-form__input" placeholder="请输入新密码" />
          </div>
        </div>
        <div class="modal-card__foot">
          <button class="users-btn" @click="resetTarget = null">取消</button>
          <button class="users-btn users-btn--primary" @click="submitReset">确认重置</button>
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
