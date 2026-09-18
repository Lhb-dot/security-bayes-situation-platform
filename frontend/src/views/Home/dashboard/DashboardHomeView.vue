<script setup lang="ts">
/**
 * DashboardHomeView —— 角色化首页入口。
 *
 * 三种形态，由「当前角色」与「是否带场景上下文」共同决定：
 *
 * | 路由                              | SUPER_ADMIN      | SCENARIO_ADMIN | SCENARIO_USER |
 * |-----------------------------------|------------------|----------------|---------------|
 * | `/overview`                       | 平台运行总览     | （守卫拦截）   | （守卫拦截）  |
 * | `/scenarios/:scenarioId/dashboard`| 场景数据画像     | 场景数据画像   | 我的工作台    |
 *
 * 即：场景中心进入某个场景后，最外层管理员看到的就是场景管理员的那个首页（场景数据画像），
 * 只有 `/overview`（导航「首页」）才是平台运行总览。
 *
 * 数据全部来自后端真实数据库聚合接口 `/api/v1/dashboard/**`，页面不含任何静态示例数据。
 */
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import AdminOverviewPage from './AdminOverviewPage.vue';
import AdminProfilePage from './AdminProfilePage.vue';
import UserWorkspacePage from './UserWorkspacePage.vue';
import '@/components/dashboard/dash.css';

const route = useRoute();
const userStore = useUserStore();

const role = computed(() => userStore.currentUser?.role);
/** 是否带场景上下文（来自 /scenarios/:scenarioId/dashboard） */
const hasScenarioContext = computed(() => Boolean(route.params.scenarioId));
/** 场景标识：路由参数优先（前端传场景编码），其次取账号绑定场景 */
const scenarioRef = computed(() =>
  String(route.params.scenarioId || userStore.currentUser?.scenario_code || ''),
);

type HomeMode = 'overview' | 'profile' | 'workspace';

const mode = computed<HomeMode>(() => {
  // 场景用户：始终是本人的「我的工作台」
  if (role.value === 'SCENARIO_USER') return 'workspace';
  // 管理级角色 + 场景上下文：该场景的数据画像（= 场景管理员的首页）
  if (hasScenarioContext.value) return 'profile';
  // 无场景上下文：最外层管理员看平台总览，其余回落到场景画像
  return role.value === 'SUPER_ADMIN' ? 'overview' : 'profile';
});
</script>

<template>
  <AdminOverviewPage v-if="mode === 'overview'" />
  <AdminProfilePage v-else-if="mode === 'profile'" :scenario-ref="scenarioRef" />
  <UserWorkspacePage v-else :scenario-ref="scenarioRef" />
</template>
