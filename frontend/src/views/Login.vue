<script setup lang="ts">
/**
 * Login - 用户登录页
 *
 * 需求 6.2（P0）：管理员和普通用户必须登录后使用系统；未登录用户不得访问业务页面和接口。
 */
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useUserStore } from '@/stores/userStore';

const router = useRouter();
const userStore = useUserStore();

const username = ref('');
const password = ref('');
const loading = ref(false);
const errorMsg = ref('');

const handleLogin = async () => {
  if (!username.value.trim() || !password.value) {
    errorMsg.value = '请输入用户名和密码';
    return;
  }
  loading.value = true;
  errorMsg.value = '';
  try {
    // 登录态统一走 Pinia userStore，与路由守卫同源，避免登录后仍被当作未登录而重定向回登录页
    await userStore.login(username.value.trim(), password.value);
    const user = userStore.currentUser;
    if (!user) throw new Error('登录失败');
    const roleText =
      user.role === 'SUPER_ADMIN' ? '系统管理员' : user.role === 'SCENARIO_ADMIN' ? '管理员' : '用户';
    ElMessage.success(`欢迎回来，${user.display_name}（${roleText}）`);
    // 按角色落地：SUPER_ADMIN → 全局总览；场景管理员/用户 → 自己场景详情
    if (user.role === 'SUPER_ADMIN') {
      router.push('/overview');
    } else if (user.scenario_ids?.[0]) {
      router.push(`/scenarios/${user.scenario_ids[0]}/dashboard`);
    } else {
      router.push('/home');
    }
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '登录失败';
  } finally {
    loading.value = false;
  }
};

const quickLogin = async (uname: string, pwd: string) => {
  username.value = uname;
  password.value = pwd;
  await handleLogin();
};
</script>

<template>
  <div class="login-page">
    <div class="login-backdrop"></div>
    <div class="login-card">
      <div class="login-card__head">
        <p class="eyebrow">Bayes Situation Awareness Platform</p>
        <h1>多场景贝叶斯分类态势感知系统</h1>
        <p class="login-card__sub">网络 · 电力 · 地质 · 航母甲板保障作业</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <div class="login-field">
          <label class="login-field__label">用户名</label>
          <input
            v-model.trim="username"
            class="login-field__input"
            type="text"
            placeholder="请输入用户名"
            autocomplete="username"
          />
        </div>
        <div class="login-field">
          <label class="login-field__label">密码</label>
          <input
            v-model="password"
            class="login-field__input"
            type="password"
            placeholder="请输入密码"
            autocomplete="current-password"
            @keyup.enter="handleLogin"
          />
        </div>
        <p v-if="errorMsg" class="login-error">{{ errorMsg }}</p>
        <button class="login-btn" type="submit" :disabled="loading">
          <span v-if="loading" class="login-btn__spinner"></span>
          {{ loading ? '正在登录...' : '登 录' }}
        </button>
      </form>

      <div class="login-demo">
        <p class="login-demo__title">演示账号（密码均为 123456）</p>
        <div class="login-demo__btns">
          <button class="login-demo__btn" @click="quickLogin('admin', '123456')">
            系统管理员 admin
          </button>
          <button class="login-demo__btn" @click="quickLogin('net_admin', '123456')">
            管理员 net_admin
          </button>
          <button class="login-demo__btn" @click="quickLogin('alice', '123456')">
            用户 alice
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: auto;
  background: #050b16;
  padding: 24px;
}

.login-backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 20% 10%, rgba(91, 166, 255, 0.18), transparent 55%),
    radial-gradient(ellipse at 85% 90%, rgba(83, 229, 200, 0.12), transparent 50%),
    radial-gradient(ellipse at 70% 20%, rgba(167, 139, 250, 0.1), transparent 45%);
  pointer-events: none;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  max-width: 100%;
  padding: 40px 36px 28px;
  border-radius: 18px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.92), rgba(8, 17, 31, 0.96));
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.5), 0 0 40px rgba(91, 166, 255, 0.08);
  backdrop-filter: blur(10px);
}

.login-card__head {
  text-align: center;
  margin-bottom: 28px;
}

.login-card__head h1 {
  margin: 10px 0 6px;
  font-size: 1.35rem;
  color: #eaf3ff;
  letter-spacing: 0.5px;
}

.login-card__sub {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(154, 214, 255, 0.75);
  letter-spacing: 2px;
}

.login-form {
  display: grid;
  gap: 18px;
}

.login-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.login-field__label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.75);
}

.login-field__input {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.25);
  background: rgba(8, 17, 31, 0.7);
  color: #e8f1ff;
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.login-field__input:focus {
  border-color: rgba(91, 166, 255, 0.65);
  box-shadow: 0 0 0 3px rgba(91, 166, 255, 0.12);
}

.login-field__input::placeholder {
  color: rgba(220, 234, 255, 0.35);
}

.login-error {
  margin: -6px 0 0;
  color: #ff7b72;
  font-size: 0.85rem;
}

.login-btn {
  margin-top: 4px;
  padding: 12px 0;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 4px;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.1s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.login-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.login-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-btn__spinner {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.login-demo {
  margin-top: 26px;
  padding-top: 18px;
  border-top: 1px solid rgba(125, 201, 255, 0.1);
}

.login-demo__title {
  margin: 0 0 10px;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.5);
  text-align: center;
}

.login-demo__btns {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.login-demo__btn {
  padding: 8px 18px;
  border: 1px solid rgba(125, 201, 255, 0.28);
  border-radius: 8px;
  background: rgba(91, 166, 255, 0.08);
  color: #9ad6ff;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s;
}

.login-demo__btn:hover {
  background: rgba(91, 166, 255, 0.18);
}
</style>
