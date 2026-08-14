<script setup lang="ts">
/**
 * ScenarioDashboardView.vue — 场景看板容器（Task 009）
 *
 * 职责：获取 route.params.scenarioId → 调用 store 校验/加载 → 按场景分发子看板。
 * 数据链路：页面 → scenarioStore / situationStore → mockApi（页面不直接调用 mockApi）。
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useSituationStore } from '@/stores/situationStore';
import { useDatasetStore } from '@/stores/datasetStore';
import { useUserStore } from '@/stores/userStore';
import type { ScenarioDetail, ScenarioId, SituationData } from '@/types/security';
import RiskLevelTag from '@/components/common/RiskLevelTag.vue';
import ScenariosQuickNav from '@/components/scenario/ScenariosQuickNav.vue';
import NetworkDashboard from '@/components/scenario/NetworkDashboard.vue';
import PowerDashboard from '@/components/scenario/PowerDashboard.vue';
import GeologicalDashboard from '@/components/scenario/GeologicalDashboard.vue';
import FlightdeckDashboard from '@/components/scenario/FlightdeckDashboard.vue';

const route = useRoute();
const scenarioStore = useScenarioStore();
const situationStore = useSituationStore();
const datasetStore = useDatasetStore();
const userStore = useUserStore();

const loading = ref(true);
const error = ref('');
const notFound = ref(false);
const denied = ref(false);

const scenarioId = computed(() => String(route.params.scenarioId ?? ''));
const detail = computed<ScenarioDetail | null>(() => scenarioStore.detail);
const situation = computed<SituationData | null>(() => situationStore.situation);

const loadData = async () => {
  loading.value = true;
  error.value = '';
  notFound.value = false;
  denied.value = false;
  try {
    await scenarioStore.fetchScenarioList();
    // 通过 store 校验场景存在性（不硬编码场景数组）
    const id = scenarioId.value as ScenarioId;
    if (!scenarioStore.scenarioById(id)) {
      notFound.value = true;
      // 需求 6.5：普通用户访问未绑定场景 → 无权访问；其余视为未知场景
      denied.value = userStore.currentUser?.role === 'USER' && !userStore.visibleScenarioIds.includes(id);
      return;
    }
    await Promise.all([
      scenarioStore.fetchScenarioDetail(id),
      situationStore.fetchSituationData(id),
      datasetStore.fetchDatasets(id),
    ]);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '看板数据加载失败';
  } finally {
    loading.value = false;
  }
};

onMounted(loadData);
</script>

<template>
  <div class="scenario-dashboard">
    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载场景态势数据...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadData">重试</button>
    </section>

<!-- 未知场景 / 无权访问 -->
<section v-else-if="notFound" class="state-card">
<p v-if="denied">无权访问该场景</p>
<p v-else>未知场景：{{ scenarioId }}</p>
</section>

    <template v-else-if="detail && situation">
      <!-- 场景头 -->
      <section class="card scenario-head">
        <div>
          <p class="eyebrow">Scenario Dashboard</p>
          <h2>{{ detail.scenario.name }}</h2>
          <p class="scenario-head__desc">{{ detail.scenario.description }}</p>
        </div>
        <RiskLevelTag :level="detail.scenario.risk_level" size="large" />
      </section>

      <!-- 业务场景概览快捷入口（需求 7.0 第三入口） -->
      <ScenariosQuickNav :scenarios="scenarioStore.activeScenarios" :current-id="scenarioId" />

      <!-- 按场景分发 -->
      <NetworkDashboard
        v-if="scenarioId === 'network_security'"
        :detail="detail"
        :situation="situation"
        :datasets="datasetStore.datasets"
      />
      <PowerDashboard
        v-else-if="scenarioId === 'power_system'"
        :detail="detail"
        :situation="situation"
        :datasets="datasetStore.datasets"
      />
      <GeologicalDashboard
        v-else-if="scenarioId === 'geological_risk'"
        :detail="detail"
        :situation="situation"
        :datasets="datasetStore.datasets"
      />
      <FlightdeckDashboard
        v-else-if="scenarioId === 'flightdeck_operation'"
        :detail="detail"
        :situation="situation"
        :datasets="datasetStore.datasets"
      />
    </template>
  </div>
</template>

<style>
/* ========== 场景看板共享样式（scenario-* 命名空间，Task 009） ========== */
.scenario-dashboard {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 20px;
}

.scenario-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
}

.scenario-head h2 {
  margin: 8px 0 6px;
  font-size: 1.45rem;
}

.scenario-head__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.6);
  font-size: 0.88rem;
  line-height: 1.5;
}

.scenario-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.scenario-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.scenario-card {
  min-height: 300px;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.85), rgba(8, 17, 31, 0.9));
}

.scenario-card--wide {
  grid-column: 1 / -1;
  min-height: 260px;
}

.scenario-card__title {
  margin: 0 0 14px;
  font-size: 0.98rem;
  color: #e8f1ff;
}

.scenario-empty {
  margin: 0;
  padding: 44px 0;
  text-align: center;
  color: rgba(220, 234, 255, 0.45);
  font-size: 0.88rem;
}

.scenario-events {
  display: grid;
  gap: 10px;
}

.scenario-event {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 13px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.1);
}

.scenario-event__badge {
  flex-shrink: 0;
  min-width: 52px;
  padding: 3px 8px;
  border-radius: 999px;
  text-align: center;
  font-size: 0.72rem;
  font-weight: 600;
}

.scenario-event__badge--high {
  background: rgba(255, 123, 114, 0.16);
  color: #ff8c84;
  border: 1px solid rgba(255, 123, 114, 0.3);
}

.scenario-event__badge--medium {
  background: rgba(255, 209, 102, 0.14);
  color: #ffd166;
  border: 1px solid rgba(255, 209, 102, 0.28);
}

.scenario-event__badge--low {
  background: rgba(83, 229, 200, 0.14);
  color: #53e5c8;
  border: 1px solid rgba(83, 229, 200, 0.28);
}

.scenario-event__body {
  min-width: 0;
}

.scenario-event__body strong {
  display: block;
  font-size: 0.88rem;
  color: #e8f1ff;
  line-height: 1.45;
}

.scenario-event__meta {
  display: block;
  margin-top: 4px;
  font-size: 0.76rem;
  color: rgba(220, 234, 255, 0.5);
}

.scenario-info {
  display: grid;
  gap: 10px;
}

.scenario-info__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.scenario-info__row span {
  color: rgba(220, 234, 255, 0.62);
  font-size: 0.84rem;
}

.scenario-info__row strong {
  color: #9ad6ff;
  font-size: 0.92rem;
  font-variant-numeric: tabular-nums;
}

/* ========== 轻量算法面板（需求 8.x，四看板通用） ========== */
.scenario-algo {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
  gap: 18px;
  align-items: stretch;
}

.scenario-algo__chart {
  min-height: 0;
}

.scenario-algo__side {
  display: flex;
  flex-direction: column;
  gap: 12px;
  justify-content: center;
}

.scenario-algo__note {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.7;
  color: rgba(220, 234, 255, 0.68);
}

.scenario-algo__note--mt {
  margin-top: 10px;
}

.scenario-algo__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.scenario-algo__tag {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: rgba(91, 166, 255, 0.08);
  color: rgba(154, 214, 255, 0.9);
  font-size: 0.78rem;
}

.scenario-algo__tag--danger {
  border-color: rgba(255, 123, 114, 0.4);
  background: rgba(255, 123, 114, 0.12);
  color: #ff8c84;
}

.scenario-algo__tag--warning {
  border-color: rgba(255, 209, 102, 0.4);
  background: rgba(255, 209, 102, 0.1);
  color: #ffd166;
}

.scenario-algo__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
}

.scenario-algo__item {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.1);
}

.scenario-algo__item-label {
  display: block;
  font-size: 0.72rem;
  color: rgba(220, 234, 255, 0.55);
  margin-bottom: 4px;
}

.scenario-algo__item-value {
  display: block;
  font-size: 1.05rem;
  font-weight: 700;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1100px) {
  .scenario-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .scenario-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .scenario-algo {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .scenario-metrics {
    grid-template-columns: 1fr;
  }
  .scenario-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
