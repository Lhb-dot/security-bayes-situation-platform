<script setup lang="ts">
/**
 * UserManagement - 用户管理（真实后端接口）
 *
 * - 登录态 / 列表 / 创建 / 重置密码 / 启停：全部走 /api/v1
 *   （本人改密已统一到设置页，此处只保留「重置他人密码」）
 * - SUPER_ADMIN：可看全部用户与场景管理员，可创建 SCENARIO_ADMIN / SCENARIO_USER 并绑定场景
 * - SCENARIO_ADMIN：仅管理本场景用户，只能创建 SCENARIO_USER
 */
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { keepScroll } from '@/utils/scrollAnchor';
import { useUserStore } from '@/stores/userStore';
import type { UserAccount, UserRole } from '@/types/security';
import { getScenarioList, type ApiScenario } from '@/api/scenarioApi';
import type { UserListParams } from '@/api/userApi';

const userStore = useUserStore();

const currentUser = computed(() => userStore.currentUser);
const users = computed(() => userStore.users);
const loading = computed(() => userStore.loading);
const keyword = ref('');
const filterRole = ref<'' | UserRole>('');
const filterStatus = ref<'' | 'ENABLED' | 'DISABLED'>('');
const filterScenarioId = ref<number | ''>('');

const PAGE_SIZE = 10;
const currentPage = ref(1);
const usersTotal = computed(() => userStore.usersTotal);
const totalPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / PAGE_SIZE)));

/** 页数多时收成 `1 2 … 末` */
const pageItems = computed<Array<{ gap: boolean; value: number }>>(() => {
  const total = totalPages.value;
  const cur = currentPage.value;
  const nums =
    total <= 7
      ? Array.from({ length: total }, (_, i) => i + 1)
      : [...new Set([1, total, cur - 1, cur, cur + 1])]
          .filter((p) => p >= 1 && p <= total)
          .sort((a, b) => a - b);
  const out: Array<{ gap: boolean; value: number }> = [];
  let prev = 0;
  for (const p of nums) {
    if (prev && p - prev > 1) out.push({ gap: true, value: 0 });
    out.push({ gap: false, value: p });
    prev = p;
  }
  return out;
});

const scenarioOptions = ref<ApiScenario[]>([]);
const scenarioNameByCode = ref<Record<string, string>>({});
const scenarioNameById = ref<Record<number, string>>({});

/** 管理级角色判断统一取自 userStore，不在页面内重复角色字符串 */
const isSuperAdmin = computed(() => userStore.isSuperAdmin);
const isManagement = computed(() => userStore.isManagement);

const roleLabel = (role: UserRole) => {
  if (role === 'SUPER_ADMIN') return '系统管理员';
  if (role === 'SCENARIO_ADMIN') return '场景管理员';
  return '场景用户';
};

/** 徽标配色：与「设置 → 账号与安全」保持一致（系统管理员=琥珀黄） */
const roleBadge = (role: UserRole) => {
  if (role === 'SUPER_ADMIN') return 'role-badge--super';
  if (role === 'SCENARIO_USER') return 'role-badge--user';
  return 'role-badge--admin';
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
  const options = await getScenarioList();
  scenarioOptions.value = options;
  scenarioNameByCode.value = Object.fromEntries(options.map((item) => [item.code, item.name]));
  scenarioNameById.value = Object.fromEntries(options.map((item) => [item.id, item.name]));
};

/** 当前筛选条件 —— 增删改后重拉列表也要带上，否则下拉还显示着筛选值、列表却跳回全量 */
const currentListParams = (): UserListParams => ({
  page: currentPage.value,
  page_size: PAGE_SIZE,
  keyword: keyword.value.trim() || undefined,
  role: filterRole.value || undefined,
  status: filterStatus.value || undefined,
  scenario_id: filterScenarioId.value === '' ? undefined : Number(filterScenarioId.value),
});

const loadUsers = async () => {
  await userStore.fetchUsers(currentListParams());
  // 增删改（尤其是禁用/删除后带筛选条件重拉）会让总数变小：当前页超出末页时回落到末页重拉，
  // 否则会出现「第 2 / 1 页 + 空表」的假空列表。
  if (currentPage.value > totalPages.value) {
    currentPage.value = totalPages.value;
    await userStore.fetchUsers(currentListParams());
  }
};

const tableWrapRef = ref<HTMLElement | null>(null);

/** 筛选条件变化 → 回到第 1 页；顺带清掉还压在防抖里的搜索 */
const applyFilter = async () => {
  if (keywordTimer) {
    clearTimeout(keywordTimer);
    keywordTimer = null;
  }
  currentPage.value = 1;
  await loadUsers();
};

/** 搜索框实时响应：连续输入合并成一次请求 */
let keywordTimer: ReturnType<typeof setTimeout> | null = null;
watch(keyword, () => {
  if (keywordTimer) clearTimeout(keywordTimer);
  keywordTimer = setTimeout(() => {
    keywordTimer = null;
    void applyFilter();
  }, 300);
});

const goPage = async (p: number) => {
  if (p < 1 || p > totalPages.value || p === currentPage.value) return;
  currentPage.value = p;
  // 包一层滚动锚定：换页后视口停在原处（见 utils/scrollAnchor.ts）
  await keepScroll(() => loadUsers(), tableWrapRef.value);
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
    await userStore.createUser(
      {
        username: createForm.value.username.trim(),
        password: createForm.value.password,
        role: createForm.value.role,
        scenario_id: Number(createForm.value.scenario_id),
      },
      currentListParams(),
    );
    ElMessage.success('用户创建成功');
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
    ElMessage.warning('不能禁用当前登录用户');
    return;
  }
  const next = user.status === 'active' ? 'disabled' : 'active';
  try {
    await userStore.setUserStatus(user.user_id, next, currentListParams());
    ElMessage.success(next === 'active' ? '用户已启用' : '用户已禁用');
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
    await userStore.updateUserScenario(
      bindTarget.value.user_id,
      Number(bindScenarioId.value),
      currentListParams(),
    );
    ElMessage.success('场景绑定已更新');
    bindTarget.value = null;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '绑定失败');
  } finally {
    bindSubmitting.value = false;
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
        <p class="users-page__desc">用户、角色与场景绑定管理</p>
      </div>
      <button v-if="isManagement" class="users-btn users-btn--primary" @click="openCreate">
        创建用户
      </button>
    </div>

    <section v-if="isManagement" class="card users-section">
      <div class="section-heading">
        <div class="users-filters">
          <select v-model="filterRole" class="pwd-form__input users-filter" @change="applyFilter">
            <option value="">全部角色</option>
            <option v-if="isSuperAdmin" value="SUPER_ADMIN">系统管理员</option>
            <option value="SCENARIO_ADMIN">场景管理员</option>
            <option value="SCENARIO_USER">场景用户</option>
          </select>
          <select
            v-if="isSuperAdmin"
            v-model="filterScenarioId"
            class="pwd-form__input users-filter"
            @change="applyFilter"
          >
            <option value="">全部场景</option>
            <option v-for="sc in scenarioOptions" :key="sc.id" :value="sc.id">
              {{ sc.name }}
            </option>
          </select>
          <select v-model="filterStatus" class="pwd-form__input users-filter" @change="applyFilter">
            <option value="">全部状态</option>
            <option value="ENABLED">启用</option>
            <option value="DISABLED">禁用</option>
          </select>
        </div>
        <div class="users-toolbar">
          <input
            v-model.trim="keyword"
            class="pwd-form__input users-search"
            placeholder="按用户名搜索"
            @keyup.enter="applyFilter"
          />
        </div>
      </div>

      <div ref="tableWrapRef" class="users-table-wrap">
        <div v-if="loading" class="pane-loading"><div class="loader"></div></div>
        <table v-if="users.length" class="users-table">
          <!-- 列宽合计 100%（见下方 .col-* 规则）。配合 table-layout: fixed，
               空表和满表共用同一套列宽 —— 否则加载时按表头分、数据到了按内容重排，
               整张表会「从宽变窄」跳一下。 -->
          <colgroup>
            <col class="col-id" />
            <col class="col-name" />
            <col class="col-role" />
            <col class="col-status" />
            <col class="col-scenario" />
            <col class="col-created" />
            <col class="col-ops" />
          </colgroup>
          <thead>
            <tr>
              <th>用户ID</th>
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
                  :class="roleBadge(user.role)"
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
      </div>

      <div v-if="usersTotal > 0" class="users-pager">
        <span class="users-pager__info">
          第 {{ currentPage }} / {{ totalPages }} 页 · 共 {{ usersTotal }} 条
        </span>
        <div class="users-pager__btns">
          <button class="users-pager__btn" :disabled="currentPage === 1" @click="goPage(1)">
            首页
          </button>
          <button
            class="users-pager__btn"
            :disabled="currentPage === 1"
            @click="goPage(currentPage - 1)"
          >
            上一页
          </button>
          <template v-for="item in pageItems" :key="item.gap ? 'gap' : item.value">
            <span v-if="item.gap" class="users-pager__gap">…</span>
            <button
              v-else
              class="users-pager__btn users-pager__btn--num"
              :class="{ 'is-active': item.value === currentPage }"
              @click="goPage(item.value)"
            >
              {{ item.value }}
            </button>
          </template>
          <button
            class="users-pager__btn"
            :disabled="currentPage === totalPages"
            @click="goPage(currentPage + 1)"
          >
            下一页
          </button>
          <button
            class="users-pager__btn"
            :disabled="currentPage === totalPages"
            @click="goPage(totalPages)"
          >
            末页
          </button>
        </div>
      </div>
    </section>

    <el-dialog
      v-model="createOpen"
      :title="isSuperAdmin ? '创建用户并绑定场景' : '创建本场景用户'"
      class="users-create-dialog"
      width="480px"
      align-center
      append-to-body
      lock-scroll
      :close-on-click-modal="false"
    >
      <div class="pwd-form">
        <div class="pwd-form__field">
          <label class="pwd-form__label">用户名</label>
          <input
            v-model.trim="createForm.username"
            class="pwd-form__input"
            placeholder="如 zhangsan"
          />
        </div>
        <div class="pwd-form__field">
          <label class="pwd-form__label">初始密码</label>
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
            <option value="SCENARIO_USER">场景用户</option>
          </select>
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
            <label class="pwd-form__label">新密码</label>
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
  color: #c8deff;
}

.users-page__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

.users-section {
  padding: 20px 24px;
  margin-bottom: 18px;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.users-filters {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.users-filter {
  min-width: 132px;
  cursor: pointer;
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
  position: relative; /* 翻页遮罩（.pane-loading）的定位上下文 */
  overflow-x: auto;
}

.users-table {
  width: 100%;
  /* 固定布局：列宽完全由下方 .col-* 决定，不随内容重排 */
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.88rem;
}

/* 列宽按「有数据时」的观感定（合计 100%），空表和满表共用一套 */
.col-id { width: 8%; }
.col-name { width: 12%; }
.col-role { width: 13%; }
.col-status { width: 8%; }
.col-scenario { width: 13%; }
.col-created { width: 18%; }
.col-ops { width: 28%; }

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

.users-table__muted {
  color: rgba(220, 234, 255, 0.4);
}

.users-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(125, 201, 255, 0.1);
}

.users-pager__info {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}

.users-pager__btns {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.users-pager__btn {
  min-width: 34px;
  padding: 5px 10px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  border-radius: 6px;
  background: rgba(91, 166, 255, 0.08);
  color: rgba(200, 224, 255, 0.85);
  font-size: 0.8rem;
  cursor: pointer;
}

.users-pager__btn:hover:not(:disabled) {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.45);
  color: #fff;
}

.users-pager__btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.users-pager__btn--num {
  padding: 5px 0;
}

.users-pager__btn.is-active {
  background: rgba(91, 166, 255, 0.24);
  border-color: rgba(91, 166, 255, 0.6);
  color: #fff;
  font-weight: 600;
}

.users-pager__gap {
  padding: 0 2px;
  color: rgba(220, 234, 255, 0.4);
  font-size: 0.8rem;
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

.role-badge--super {
  background: rgba(255, 183, 77, 0.16);
  color: #ffc37d;
  border: 1px solid rgba(255, 183, 77, 0.3);
}

.role-badge--admin {
  background: rgba(167, 139, 250, 0.18);
  color: #c4b5fd;
  border: 1px solid rgba(167, 139, 250, 0.28);
}

.role-badge--user {
  background: rgba(91, 166, 255, 0.16);
  color: #9ad6ff;
  border: 1px solid rgba(91, 166, 255, 0.28);
}

.status-badge--on {
  background: rgba(14, 99, 76, 0.62);
  color: #6ef0c4;
  border: 1px solid rgba(83, 229, 200, 0.36);
}

.status-badge--off {
  background: rgba(112, 32, 30, 0.55);
  color: #ff9a92;
  border: 1px solid rgba(255, 123, 114, 0.34);
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
  border: 1px solid rgba(125, 201, 255, 0.35);
  border-radius: 10px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, color 0.2s;
  width: fit-content;
}

.users-btn:hover {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.5);
  color: #fff;
}

.users-btn--primary {
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  border: 1px solid rgba(125, 201, 255, 0.35);
  font-weight: 600;
}

.users-btn--primary:hover {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.5);
  color: #fff;
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

<style>
/* 创建用户弹窗 append-to-body 后挂到 body，scoped 样式不生效；
   且 style.css 的 .el-button 暗色覆盖与 Element Plus 同权重、EP 在后，实际不生效
   （实测渲染成白底 / EP 默认蓝），故此处用 !important 兜住。 */
.users-create-dialog .el-button {
  background: rgba(91, 166, 255, 0.1) !important;
  border-color: rgba(125, 201, 255, 0.35) !important;
  color: #9ad6ff !important;
}

.users-create-dialog .el-button:hover {
  background: rgba(91, 166, 255, 0.18) !important;
  border-color: rgba(91, 166, 255, 0.5) !important;
  color: #fff !important;
}

.users-create-dialog .el-button--primary {
  font-weight: 600 !important;
}
</style>
