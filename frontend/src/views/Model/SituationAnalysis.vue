<script setup lang="ts">
/**
 * SituationAnalysis - 态势分析页面
 *
 * 顶部：时间范围选择
 * 中部：风险趋势图、风险等级分布、事件数量统计
 * 底部：场景统计
 */
import { computed, onMounted, ref } from 'vue';
import type { SituationData, ScenarioId } from '@/types/security';
import { useScenarioStore } from '@/stores/scenarioStore';
import { getSituationData } from '@/services/mockApi';
import LineTrendChart from '@/components/LineTrendChart.vue';
import DonutChart from '@/components/DonutChart.vue';

const scenarioStore = useScenarioStore();

/** 场景列表：从 scenarioStore.activeScenarios 注入（Task 016，已按用户绑定过滤） */
const SCENARIOS = computed<{ id: ScenarioId; label: string }[]>(() =>
  scenarioStore.activeScenarios.map((s) => ({ id: s.scenario_id, label: s.name }))
);

/** 时间范围选项 */
const timeRanges = [
  { value: '24h', label: '最近24小时' },
  { value: '7d', label: '最近7天' },
  { value: '30d', label: '最近30天' },
];

const selectedRange = ref('7d');
const allData = ref<SituationData[]>([]);
const loading = ref(true);

/** 合并风险趋势点（取均值） */
const mergedTrend = computed(() => {
  if (!allData.value.length) return [];
  const first = allData.value[0];
  return first.risk_trend.map((_, i) => {
    const values = allData.value.map((d) => d.risk_trend[i]?.value ?? 0);
    const avg = Math.round(values.reduce((a, b) => a + b, 0) / values.length);
    return {
      label: first.risk_trend[i]?.label ?? '',
      value: avg,
      blocked: Math.round(avg * 0.4),
      sources: Math.round(avg * 0.15),
      primaryType: first.risk_trend[i]?.primaryType ?? '',
    };
  });
});

/** 合并事件分布 */
const mergedDistribution = computed(() => {
  if (!allData.value.length) return [];
  const allTypes = new Set<string>();
  allData.value.forEach((d) => d.event_distribution.forEach((e) => allTypes.add(e.label)));
  return Array.from(allTypes).map((label, i) => {
    const total = allData.value.reduce((sum, d) => {
      const found = d.event_distribution.find((e) => e.label === label);
      return sum + (found?.value ?? 0);
    }, 0);
    return {
      label,
      value: total,
      color: ['#5ba6ff', '#53e5c8', '#ffd166', '#ff7b72', '#a78bfa'][i % 5],
    };
  });
});

/** 事件总数统计 */
const eventStats = computed(() =>
  allData.value.map((d) => {
    const total = d.event_distribution.reduce((sum, e) => sum + e.value, 0);
    return {
      name: SCENARIOS.value.find((s) => s.id === d.scenario_id)?.label ?? d.scenario_id,
      score: total,
    };
  })
);

onMounted(async () => {
  loading.value = true;
  try {
    await scenarioStore.fetchScenarioList();
    const results = await Promise.all(
      SCENARIOS.value.map((s) => getSituationData(s.id))
    );
    allData.value = results;
  } catch {
    // ignore
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="situation-page">
    <div class="situation-page__header">
      <div>
        <p class="eyebrow">Situation Analysis</p>
        <h2>态势分析</h2>
        <p class="situation-page__desc">四场景风险趋势分析</p>
      </div>
    </div>

    <!-- 顶部：时间范围选择 -->
    <section class="card situation-toolbar">
      <div class="situation-toolbar__tabs">
        <button
          v-for="range in timeRanges"
          :key="range.value"
          class="situation-toolbar__tab"
          :class="{ 'is-active': selectedRange === range.value }"
          @click="selectedRange = range.value"
        >
          {{ range.label }}
        </button>
      </div>
    </section>

    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载态势数据...</p>
    </section>

    <template v-else>
      <!-- 中部：图表区域 -->
      <div class="situation-charts">
        <section class="card chart-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Trend</p>
              <h3>风险趋势图</h3>
            </div>
            <span class="section-tag">{{ selectedRange === '24h' ? '24h' : selectedRange === '7d' ? '7天' : '30天' }}</span>
          </div>
          <LineTrendChart :points="mergedTrend" />
        </section>

        <section class="card chart-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Distribution</p>
              <h3>风险等级分布</h3>
            </div>
          </div>
          <DonutChart :items="mergedDistribution" title="风险分布" />
        </section>
      </div>

      <!-- 底部：事件统计 + 场景统计 -->
      <div class="situation-bottom">
        <section class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Events</p>
              <h3>事件数量统计</h3>
            </div>
          </div>
          <div class="situation-events">
            <div
              v-for="event in eventStats"
              :key="event.name"
              class="situation-events__item"
            >
              <span class="situation-events__name">{{ event.name }}</span>
              <span class="situation-events__bar">
                <span
                  class="situation-events__bar-fill"
                  :style="{ width: Math.min(100, (event.score / Math.max(...eventStats.map(e => e.score))) * 100) + '%' }"
                ></span>
              </span>
              <span class="situation-events__value">{{ event.score }}</span>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Scenario</p>
              <h3>场景统计</h3>
            </div>
          </div>
          <div class="situation-scenarios">
            <div
              v-for="s in SCENARIOS"
              :key="s.id"
              class="situation-scenarios__item"
            >
              <h4 class="situation-scenarios__name">{{ s.label }}</h4>
              <div class="situation-scenarios__metrics">
                <div
                  v-for="m in (allData.find(d => d.scenario_id === s.id)?.metrics ?? [])"
                  :key="m.id"
                  class="situation-scenarios__metric"
                >
                  <span class="situation-scenarios__metric-label">{{ m.label }}</span>
                  <span
                    class="situation-scenarios__metric-value"
                    :class="{ 'is-up': m.trend > 0, 'is-down': m.trend < 0 }"
                  >
                    {{ m.value }}
                    <small>{{ m.trend > 0 ? '+' : '' }}{{ m.trend }}%</small>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.situation-page {
  position: relative;
  z-index: 1;
}

.situation-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.situation-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.situation-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

/* 工具栏 */
.situation-toolbar {
  margin-bottom: 20px;
}

.situation-toolbar__tabs {
  display: inline-flex;
  padding: 4px;
  border: 1px solid rgba(125, 201, 255, 0.18);
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.7);
  gap: 2px;
}

.situation-toolbar__tab {
  border: 0;
  padding: 8px 18px;
  border-radius: 999px;
  color: #d9e8ff;
  background: transparent;
  font-size: 0.88rem;
  cursor: pointer;
  transition: background 0.25s;
  white-space: nowrap;
}

.situation-toolbar__tab:hover {
  background: rgba(91, 166, 255, 0.12);
}

.situation-toolbar__tab.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}

/* 图表区域 */
.situation-charts {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 18px;
  margin-bottom: 18px;
}

.situation-charts .chart-card {
  min-height: 340px;
}

/* 底部 */
.situation-bottom {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

/* 事件统计 */
.situation-events {
  display: grid;
  gap: 14px;
}

.situation-events__item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.situation-events__name {
  width: 80px;
  font-size: 0.9rem;
  color: #d9e8ff;
  flex-shrink: 0;
}

.situation-events__bar {
  flex: 1;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

.situation-events__bar-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #5ba6ff, #407acc);
  transition: width 0.5s ease;
}

.situation-events__value {
  width: 40px;
  text-align: right;
  font-size: 0.95rem;
  font-weight: 600;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

/* 场景统计 */
.situation-scenarios {
  display: grid;
  gap: 18px;
}

.situation-scenarios__item {
  padding: 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.situation-scenarios__name {
  margin: 0 0 12px;
  font-size: 0.95rem;
  color: #e8f1ff;
}

.situation-scenarios__metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.situation-scenarios__metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.situation-scenarios__metric-label {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
}

.situation-scenarios__metric-value {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e8f1ff;
  font-variant-numeric: tabular-nums;
}

.situation-scenarios__metric-value small {
  font-size: 0.78rem;
  font-weight: 400;
  margin-left: 4px;
}

.situation-scenarios__metric-value.is-up small {
  color: #ff8c84;
}

.situation-scenarios__metric-value.is-down small {
  color: #53e5c8;
}

@media (max-width: 768px) {
  .situation-charts,
  .situation-bottom {
    grid-template-columns: 1fr;
  }
}
</style>
