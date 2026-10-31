<script setup lang="ts">
/**
 * DashboardHomeView，角色化首页入口。
 * 三种形态，由「当前角色」与「是否带场景上下文」共同决定：
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
const hasScenarioContext = computed(() => Boolean(route.params.scenarioId));
const scenarioRef = computed(() =>
  String(route.params.scenarioId || userStore.currentUser?.scenario_code || ''),
);

type HomeMode = 'overview' | 'profile' | 'workspace';

const mode = computed<HomeMode>(() => {
  if (role.value === 'SCENARIO_USER') return 'workspace';
  if (hasScenarioContext.value) return 'profile';
  return role.value === 'SUPER_ADMIN' ? 'overview' : 'profile';
});
</script>

<template>
  <AdminOverviewPage v-if="mode === 'overview'" />
  <AdminProfilePage v-else-if="mode === 'profile'" :scenario-ref="scenarioRef" />
  <UserWorkspacePage v-else :scenario-ref="scenarioRef" />
</template>
