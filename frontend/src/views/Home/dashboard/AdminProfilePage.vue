<script setup lang="ts">
/**
 * AdminProfilePage —— 场景数据画像（场景管理员首页）。
 * 按 scenario_key 分发到 4 个场景分区组件，字段口径见 docs/首页字段口径说明.md。
 * 数据来自 /dashboard/scenarios/{id}/profile（全量数据集实测，不受运行态影响）。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioProfile,
  type FlightdeckProfile,
  type GeologicalProfile,
  type NetworkProfile,
  type PowerProfile,
  type ScenarioProfile,
} from '@/api/dashboardApi';
import DashShell from '@/components/dashboard/DashShell.vue';
import ProfileNetwork from './sections/ProfileNetwork.vue';
import ProfilePower from './sections/ProfilePower.vue';
import ProfileFlightdeck from './sections/ProfileFlightdeck.vue';
import ProfileGeological from './sections/ProfileGeological.vue';
import { fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ scenarioRef: string }>();

const loading = ref(true);
const error = ref('');
const profile = ref<ScenarioProfile | null>(null);

/** 按 scenario_key 收窄类型，模板中据此渲染对应场景分区（TS 无法在模板里自动收窄联合类型） */
const networkData = computed<NetworkProfile | null>(() =>
  profile.value?.scenario_key === 'network' ? (profile.value as NetworkProfile) : null,
);
const powerData = computed<PowerProfile | null>(() =>
  profile.value?.scenario_key === 'power' ? (profile.value as PowerProfile) : null,
);
const flightdeckData = computed<FlightdeckProfile | null>(() =>
  profile.value?.scenario_key === 'flight_deck' ? (profile.value as FlightdeckProfile) : null,
);
const geologicalData = computed<GeologicalProfile | null>(() =>
  profile.value?.scenario_key === 'geological' ? (profile.value as GeologicalProfile) : null,
);

const subtitle = computed(() => {
  const data = profile.value;
  if (!data) return '以数据集字段为主线，全部为全量统计指标';
  return `数据集全量统计 · ${data.dataset_count} 个有效数据集 · ${fmtInt(data.sample_count)} 条样本 · 风险占比 ${fmtPercent(data.risk_rate)}`;
});

const load = async () => {
  loading.value = true;
  error.value = '';
  profile.value = null;
  try {
    profile.value = await getScenarioProfile(props.scenarioRef);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '场景画像加载失败';
  } finally {
    loading.value = false;
  }
};

watch(() => props.scenarioRef, load);
onMounted(load);
</script>

<template>
  <DashShell
    eyebrow="Admin · Data Profile"
    :title="profile ? `${profile.scenario_name} · 数据画像` : '场景数据画像'"
    :subtitle="subtitle"
    badge="实时数据"
    :loading="loading"
    :error="error"
    @retry="load"
  >
    <template v-if="profile">
      <ProfileNetwork v-if="networkData" :data="networkData" />
      <ProfilePower v-else-if="powerData" :data="powerData" />
      <ProfileFlightdeck v-else-if="flightdeckData" :data="flightdeckData" />
      <ProfileGeological v-else-if="geologicalData" :data="geologicalData" />
      <p v-else class="d-state">该场景暂未配置数据画像</p>
    </template>
  </DashShell>
</template>
