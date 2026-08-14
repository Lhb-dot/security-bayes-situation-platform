<script setup lang="ts">
/**
 * GeologicalDashboard.vue — 地质风险态势看板（Task 009）
 *
 * 数据全部来自 props，聚合转换在 computed 中完成；无 any / ts-ignore。
 * 对齐需求 7.3：区域风险统计卡（高/中/低）、数据集风险占比堆叠柱（点击联动）、
 * 关键因子贡献条形、风险事件时间线（标注触发因素），支持按触发因素筛选。
 */
import { computed, ref } from 'vue';
import type { Dataset, RankingItem, RiskEvent, ScenarioDetail, SituationData } from '@/types/security';
import ScenarioMetricCard from './ScenarioMetricCard.vue';
import BarChart from '@/components/charts/BarChart.vue';
import EventTimeline from './EventTimeline.vue';
import { geoRegionRanking } from '@/utils/scenarioAlgorithms';

const props = defineProps<{
  detail: ScenarioDetail;
  situation: SituationData;
  datasets: Dataset[];
}>();

interface MetricCardItem {
  label: string;
  value: number;
  unit: string;
  tone: 'primary' | 'danger' | 'warning' | 'success';
}

const events = computed<RiskEvent[]>(() => props.detail.recent_events);

/** 区域风险统计卡（需求 7.3）：高 / 中 / 低风险区域数量 */
const riskCounts = computed(() => {
  const counts: Record<RiskEvent['risk_level'], number> = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  for (const e of events.value) counts[e.risk_level] += 1;
  return counts;
});

const metricCards = computed<MetricCardItem[]>(() => {
  return [
    { label: '高风险区域', value: riskCounts.value.HIGH, unit: '个', tone: 'danger' },
    { label: '中风险区域', value: riskCounts.value.MEDIUM, unit: '个', tone: 'warning' },
    { label: '低风险区域', value: riskCounts.value.LOW, unit: '个', tone: 'success' },
    { label: '事件总数', value: events.value.length, unit: '起', tone: 'primary' },
  ];
});

/**
 * 数据集风险占比（需求 7.3：五个数据集样本数与风险占比堆叠柱状图）。
 * 风险占比取需求文档 2.1 的正式标签分布（非虚构）；dis_global_catalog 为编目数据，不参与。
 */
const GEO_RISK_SHARE: Record<string, number> = {
  dis_raw_data: 873 / 5000,
  dis_landslides: 2594 / 5185,
  dis_causative_factors: 28 / 5000,
  dis_guaruja_random: 99 / 200,
};

const geoDatasets = computed<Dataset[]>(() =>
  props.datasets.filter((d) => d.scenario_id === 'geological_risk')
);

const datasetStack = computed<{
  categories: string[];
  series: Array<{ name: string; data: number[] }>;
}>(() => {
  const list = geoDatasets.value;
  const share = (datasetId: string) => GEO_RISK_SHARE[datasetId] ?? 0;
  return {
    categories: list.map((d) => d.name),
    series: [
      { name: '正常样本', data: list.map((d) => Math.round(d.record_count * (1 - share(d.dataset_id)))) },
      { name: '风险样本', data: list.map((d) => Math.round(d.record_count * share(d.dataset_id))) },
    ],
  };
});

const datasetIdByName = computed(() => new Map(geoDatasets.value.map((d) => [d.name, d.dataset_id])));
const datasetFilter = ref<string | null>(null);

/** 点击数据集柱 → 联动筛选该数据集的事件（需求 7.3 交互） */
const onDatasetClick = (name: string) => {
  datasetFilter.value = datasetIdByName.value.get(name) ?? null;
};

/** 按触发因素筛选（需求 7.3：landslide_trigger；mock 事件暂无该字段时仅"全部"） */
const triggerFilter = ref('all');
const triggerOptions = computed(() => {
  const set = new Set<string>();
  for (const e of events.value) {
    const v = e.raw_features.landslide_trigger;
    if (v !== undefined && v !== null && v !== '') set.add(String(v));
  }
  return [...set];
});

const visibleEvents = computed<RiskEvent[]>(() =>
  events.value.filter((e) => {
    if (datasetFilter.value && e.dataset_id !== datasetFilter.value) return false;
    if (triggerFilter.value !== 'all' && String(e.raw_features.landslide_trigger ?? '') !== triggerFilter.value) return false;
    return true;
  })
);

/** 风险因素贡献（Slope / TWI / Dis2fault 均值；兼容大小写字段变体） */
const factorContribution = computed<RankingItem[]>(() => {
  const factors: Array<{ name: string; primary: string; fallback: string }> = [
    { name: '坡度', primary: 'Slope', fallback: 'slope' },
    { name: 'TWI', primary: 'TWI', fallback: 'twi' },
    { name: '距断层', primary: 'Dis2fault', fallback: 'Dis2roads' },
  ];
  const result: RankingItem[] = [];
  for (const f of factors) {
    const values: number[] = [];
    for (const ev of events.value) {
      const v = Number(ev.raw_features[f.primary] ?? ev.raw_features[f.fallback]);
      if (Number.isFinite(v)) values.push(v);
    }
    if (values.length === 0) continue;
    result.push({
      name: f.name,
      score: Number((values.reduce((sum, v) => sum + v, 0) / values.length).toFixed(1)),
    });
  }
  return result.sort((a, b) => b.score - a.score);
});

/**
 * 区域易发性评分（需求 8.3 轻量算法）：对事件区域按地形因子叠加的 0-100 易发性指数排序，
 * 作为"哪里最需要优先核查"的辅助判断。
 */
const regionRanking = computed<RankingItem[]>(() =>
  geoRegionRanking(events.value)
    .slice(0, 8)
    .map((r) => ({ name: r.eventId, score: r.score }))
);

</script>

<template>
  <div class="scenario-dashboard">
    <!-- 指标卡 -->
    <section class="scenario-metrics">
      <ScenarioMetricCard
        v-for="card in metricCards"
        :key="card.label"
        :label="card.label"
        :value="card.value"
        :unit="card.unit"
        :tone="card.tone"
      />
    </section>

    <!-- 图表区 -->
    <div class="scenario-grid">
      <section class="scenario-card">
        <h3 class="scenario-card__title">数据集风险占比（点击联动）</h3>
        <BarChart
          v-if="datasetStack.categories.length"
          :data="[]"
          :categories="datasetStack.categories"
          :series="datasetStack.series"
          stacked
          height="240px"
          @bar-click="onDatasetClick"
        />
        <p v-else class="scenario-empty">暂无数据</p>
        <p v-if="datasetFilter" class="scenario-filter-tip">
          已筛选数据集：{{ datasetFilter }}
          <button class="scenario-filter-clear" @click="datasetFilter = null">清除筛选</button>
        </p>
      </section>
      <section class="scenario-card">
        <h3 class="scenario-card__title">关键因子贡献排行</h3>
        <BarChart v-if="factorContribution.length" :data="factorContribution" horizontal height="240px" />
        <p v-else class="scenario-empty">暂无数据</p>
      </section>
    </div>

    <!-- 区域易发性评分（需求 8.3 轻量算法：地形因子标准化叠加 → 0-100） -->
    <section class="scenario-card scenario-card--wide">
      <h3 class="scenario-card__title">区域易发性评分 TOP（轻量算法）</h3>
      <div v-if="regionRanking.length" class="scenario-algo">
        <div class="scenario-algo__chart">
          <BarChart :data="regionRanking" horizontal height="240px" />
        </div>
        <div class="scenario-algo__side">
          <p class="scenario-algo__note">
            易发性指数 0-100 由坡度、TWI、SPI、高程与距断层 / 河流 / 道路距离
            标准化叠加计算（需求 8.3）。评分越高表示该区域越需要优先核查与布防。
          </p>
          <div class="scenario-algo__tags">
            <span
              class="scenario-algo__tag"
              :class="regionRanking[0]?.score >= 70 ? 'scenario-algo__tag--danger' : regionRanking[0]?.score >= 40 ? 'scenario-algo__tag--warning' : ''"
            >
              最高易发性：{{ regionRanking[0]?.score ?? 0 }} / 100
            </span>
            <span class="scenario-algo__tag">共评估 {{ regionRanking.length }} 个区域</span>
          </div>
        </div>
      </div>
      <p v-else class="scenario-empty">暂无数据</p>
    </section>

    <!-- 风险事件时间线（需求 7.3：标注风险等级与触发因素） -->
    <section class="scenario-card">
      <h3 class="scenario-card__title">风险事件时间线</h3>
      <div class="scenario-timeline-toolbar">
        <span class="scenario-timeline-toolbar__label">触发因素</span>
        <select v-model="triggerFilter" class="scenario-select">
          <option value="all">全部</option>
          <option v-for="t in triggerOptions" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <EventTimeline v-if="visibleEvents.length" :events="visibleEvents" :meta-keys="['landslide_trigger', 'Slope']" />
      <p v-else class="scenario-empty">暂无风险事件</p>
    </section>
  </div>
</template>

<style scoped>
.scenario-filter-tip {
  margin: 10px 0 0;
  font-size: 0.8rem;
  color: rgba(255, 209, 102, 0.85);
}

.scenario-filter-clear {
  margin-left: 8px;
  padding: 2px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 209, 102, 0.4);
  background: transparent;
  color: rgba(255, 209, 102, 0.9);
  font-size: 0.76rem;
  cursor: pointer;
}

.scenario-timeline-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.scenario-timeline-toolbar__label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}

.scenario-select {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: rgba(8, 17, 31, 0.7);
  color: #e8f1ff;
  font-size: 0.84rem;
  outline: none;
}

.scenario-select option {
  background: #0b1628;
  color: #e8f1ff;
}
</style>
