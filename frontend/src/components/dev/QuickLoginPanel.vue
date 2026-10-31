<template>
  <aside v-if="QUICK_LOGIN_ENABLED" class="quick-login">
    <header class="quick-login__head">
      <p class="quick-login__title">快捷登录</p>
      <p class="quick-login__tag">仅开发阶段使用</p>
    </header>

    <p v-if="!scenarios.length" class="quick-login__hint">
      账号清单为空，请先运行 scripts/gen_quick_login_accounts.py
    </p>

    <template v-else>
      <button
        v-for="account in superAdmins"
        :key="account.username"
        class="quick-login__account quick-login__account--super"
        type="button"
        :disabled="busy"
        @click="signIn(account)"
      >
        <span class="quick-login__account-name">超级管理员</span>
        <span class="quick-login__account-meta">{{ account.username }} · 全部场景</span>
      </button>

      <label class="quick-login__field">
        <span class="quick-login__field-label">场景</span>
        <select v-model="scenarioCode" class="quick-login__select" :disabled="busy">
          <option value="" disabled>请选择场景</option>
          <option v-for="scenario in scenarios" :key="scenario.code" :value="scenario.code">
            {{ scenario.name }}
          </option>
        </select>
      </label>

      <label class="quick-login__field">
        <span class="quick-login__field-label">角色</span>
        <select v-model="roleCode" class="quick-login__select" :disabled="busy">
          <option value="" disabled>请选择角色</option>
          <option v-for="option in ROLE_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <ul v-if="scenarioCode && roleCode" class="quick-login__accounts">
        <li v-for="account in matchedAccounts" :key="account.username">
          <button
            class="quick-login__account"
            type="button"
            :disabled="busy"
            @click="signIn(account)"
          >
            <span class="quick-login__account-name">{{ account.username }}</span>
            <span class="quick-login__account-meta">
              {{ roleLabel(account.role) }} · {{ scenarioName(scenarioCode) }}
            </span>
          </button>
        </li>
        <li v-if="!matchedAccounts.length" class="quick-login__empty">该场景暂无对应账号</li>
      </ul>
      <p v-else class="quick-login__hint">选择场景与角色后显示可用账号</p>
    </template>

    <p v-if="message" class="quick-login__message">{{ message }}</p>
  </aside>
</template>
<script setup lang="ts">
/**
 * QuickLoginPanel，开发阶段「快捷登录」面板（完全独立、可整块删除）。
 * 用途：开发/联调时不用手输账号密码，点一下就能切到某个测试账号。
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import type { UserRole } from '@/types/security';
import {
  DEV_QUICK_SCENARIOS,
  DEV_QUICK_SUPER_ADMINS,
  type DevQuickAccount,
} from './devAccounts.generated';

// 代码层开关：false = 本面板整块不渲染（登录页与线上完全一致）。
const QUICK_LOGIN_ENABLED = true;

// 第二个下拉框：界面上一律显示中文角色名。
const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'SCENARIO_ADMIN', label: '场景管理员' },
  { value: 'SCENARIO_USER', label: '场景用户' },
];

const router = useRouter();
const userStore = useUserStore();

const scenarioCode = ref('');
const roleCode = ref<UserRole | ''>('');
const busy = ref(false);
const message = ref('');

const superAdmins = DEV_QUICK_SUPER_ADMINS;
const scenarios = DEV_QUICK_SCENARIOS;

// 两个下拉都选完之后，才列出该场景下符合角色的全部账号。
const matchedAccounts = computed<DevQuickAccount[]>(() => {
  if (!scenarioCode.value || !roleCode.value) return [];
  const scenario = scenarios.find((item) => item.code === scenarioCode.value);
  return scenario ? scenario.accounts.filter((account) => account.role === roleCode.value) : [];
});

const scenarioName = (code: string): string =>
  scenarios.find((item) => item.code === code)?.name ?? code;

const roleLabel = (role: UserRole): string =>
  ROLE_OPTIONS.find((option) => option.value === role)?.label ?? role;

// 走和正常登录完全相同的通道；成功后就交给既有路由逻辑按角色落地。
const signIn = async (account: DevQuickAccount): Promise<void> => {
  if (busy.value) return;
  busy.value = true;
  message.value = '';
  try {
    await userStore.login(account.username, account.password);
    // 落地与正常登录同源：推 '/' 交给 router 的 redirect + 守卫按角色跳转。
    await router.push('/');
  } catch (error) {
    message.value = error instanceof Error ? error.message : '登录失败';
  } finally {
    busy.value = false;
  }
};
</script>
<style scoped>
/* 绝对定位在登录卡右侧：不占布局位置，登录卡保持原来的居中 */
.quick-login {
  position: absolute;
  top: 50%;
  right: 4vw;
  transform: translateY(-50%);
  z-index: 1;
  width: 320px;
  max-width: 100%;
  /* 面板整体不超出视口；账号多的时候只让下面的列表滚 */
  max-height: calc(100vh - 48px);
  padding: 22px 22px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  border-radius: 18px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.92), rgba(8, 17, 31, 0.96));
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.5), 0 0 40px rgba(91, 166, 255, 0.08);
  backdrop-filter: blur(10px);
}

/* 窄屏时登录卡本身已接近满宽，面板改贴右下角，避免压在卡片上 */
@media (max-width: 1120px) {
  .quick-login {
    top: auto;
    bottom: 20px;
    right: 20px;
    transform: none;
  }
}

.quick-login__head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.quick-login__title {
  margin: 0;
  color: #eaf3ff;
  font-size: 0.98rem;
  font-weight: 600;
  letter-spacing: 1px;
}

.quick-login__tag {
  margin: 0;
  color: rgba(154, 214, 255, 0.6);
  font-size: 0.72rem;
}

.quick-login__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quick-login__field-label {
  color: rgba(220, 234, 255, 0.75);
  font-size: 0.82rem;
}

.quick-login__select {
  padding: 9px 10px;
  border-radius: 9px;
  border: 1px solid rgba(125, 201, 255, 0.25);
  background: rgba(8, 17, 31, 0.7);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
}

.quick-login__select:focus {
  border-color: rgba(91, 166, 255, 0.65);
  box-shadow: 0 0 0 3px rgba(91, 166, 255, 0.12);
}

.quick-login__select option {
  background: #0d1a2e;
  color: #e8f1ff;
}

.quick-login__accounts {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
  /* 账号多的时候出现滚动条：占满面板剩余高度但不超过 300px，绝不把面板顶出屏幕 */
  flex: 1 1 auto;
  min-height: 0;
  max-height: 300px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(125, 201, 255, 0.4) transparent;
}

.quick-login__accounts::-webkit-scrollbar {
  width: 6px;
}

.quick-login__accounts::-webkit-scrollbar-thumb {
  border-radius: 3px;
  background: rgba(125, 201, 255, 0.35);
}

.quick-login__accounts::-webkit-scrollbar-track {
  background: transparent;
}

.quick-login__account {
  width: 100%;
  padding: 9px 12px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: rgba(91, 166, 255, 0.08);
  text-align: left;
  cursor: pointer;
  transition: background 0.18s, border-color 0.18s;
}

.quick-login__account--super {
  background: rgba(91, 166, 255, 0.14);
  border-color: rgba(91, 166, 255, 0.35);
}

.quick-login__account:hover:not(:disabled) {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.5);
}

.quick-login__account:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.quick-login__account-name {
  color: #eaf3ff;
  font-size: 0.9rem;
  font-weight: 600;
}

.quick-login__account-meta {
  color: rgba(154, 214, 255, 0.65);
  font-size: 0.72rem;
}

.quick-login__empty,
.quick-login__hint {
  margin: 0;
  color: rgba(154, 214, 255, 0.5);
  font-size: 0.8rem;
  text-align: center;
}

.quick-login__empty {
  padding: 8px 0;
}

.quick-login__message {
  margin: 0;
  color: #ff7b72;
  font-size: 0.8rem;
}
</style>
