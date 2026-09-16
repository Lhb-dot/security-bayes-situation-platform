<script setup lang="ts">
/**
 * UserWorkspacePage —— 我的工作台（场景用户首页）。
 * 按 scenario_key 分发到 4 个场景分区组件，字段口径见 docs/首页字段口径说明.md。
 * 数据来自 /dashboard/scenarios/{id}/workspace，范围严格限定当前登录用户本人。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type FlightdeckWorkspace,
  type GeologicalWorkspace,
  type NetworkWorkspace,
  type PowerWorkspace,
  type ScenarioWorkspace,
} from '@/api/dashboardApi';
import DashShell from '@/components/dashboard/DashShell.vue';
import WorkspaceNetwork from './sections/WorkspaceNetwork.vue';
import WorkspacePower from './sections/WorkspacePower.vue';
import WorkspaceFlightdeck from './sections/WorkspaceFlightdeck.vue';
import WorkspaceGeological from './sections/WorkspaceGeological.vue';
import { fmtInt } from '@/components/dashboard/dashFormat';

const props = defineProps<{ scenarioRef: string }>();

const loading = ref(true);
const error = ref('');
const workspace = ref<ScenarioWorkspace | null>(null);

/** 按 scenario_key 收窄类型，模板中据此渲染对应场景分区 */
const networkData = computed<NetworkWorkspace | null>(() =>
  workspace.value?.scenario_key === 'network' ? (workspace.value as NetworkWorkspace) : null,
);
const powerData = computed<PowerWorkspace | null>(() =>
  workspace.value?.scenario_key === 'power' ? (workspace.value as PowerWorkspace) : null,
);
const flightdeckData = computed<FlightdeckWorkspace | null>(() =>
  workspace.value?.scenario_key === 'flight_deck' ? (workspace.value as FlightdeckWorkspace) : null,
);
const geologicalData = computed<GeologicalWorkspace | null>(() =>
  workspace.value?.scenario_key === 'geological' ? (workspace.value as GeologicalWorkspace) : null,
);

const subtitle = computed(() => {
  const data = workspace.value;
  if (!data) return '仅统计当前登录用户本人的风险事件';
  if (!data.summary.total) return '仅统计当前登录用户本人 · 当前暂无风险事件';
  return `仅统计当前登录用户本人 · 共 ${fmtInt(data.summary.total)} 条风险事件 · 待处置 ${fmtInt(data.summary.pending)} 条`;
});

const load = async () => {
  loading.value = true;
  error.value = '';
  workspace.value = null;
  try {
    workspace.value = await getScenarioWorkspace(props.scenarioRef);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '工作台数据加载失败';
  } finally {
    loading.value = false;
  }
};

watch(() => props.scenarioRef, load);
onMounted(load);
</script>

<template>
  <DashShell
    eyebrow="User Console · My Workspace"
    :title="workspace ? `${workspace.scenario_name.replace('态势', '')} · 我的工作台` : '我的工作台'"
    :subtitle="subtitle"
    badge="实时数据"
    badge-tone="info"
    :loading="loading"
    :error="error"
    @retry="load"
  >
    <template v-if="workspace">
      <WorkspaceNetwork v-if="networkData" :data="networkData" />
      <WorkspacePower v-else-if="powerData" :data="powerData" />
      <WorkspaceFlightdeck v-else-if="flightdeckData" :data="flightdeckData" />
      <WorkspaceGeological v-else-if="geologicalData" :data="geologicalData" />
      <p v-else class="d-state">该场景暂未配置工作台数据</p>
    </template>
  </DashShell>
</template>
