<script setup lang="ts">
/**
 * PowerDashboard.vue — 电力系统态势看板（Task 009）
 *
 * 数据全部来自 props，聚合转换在 computed 中完成；无 any / ts-ignore。
 * 对齐需求 7.2：电参量指标卡（电压/电流/温度/频率）、设备健康度、IssueType 分布、
 * 风险事件时间线（标注 IssueType 与设备）；点击设备条目筛选。
 */
import { computed, ref } from 'vue';
import type { Dataset, RankingItem, RiskEvent, ScenarioDetail, SituationData, TypeDistribution } from '@/types/security';
import ScenarioMetricCard from './ScenarioMetricCard.vue';
import BarChart from '@/components/charts/BarChart.vue';
import PieChart from '@/components/charts/PieChart.vue';
import EventTimeline from './EventTimeline.vue';
import { powerDeviceHealth, powerRiskScore } from '@/utils/scenarioAlgorithms';

const props = defineProps<{
  detail: ScenarioDetail;
  situation: SituationData;
  datasets?: Dataset[];
}>();

interface MetricCardItem {
  label: string;
  value: number;
  unit: string;
  tone: 'primary' | 'danger' | 'warning' | 'success';
}

const PIE_COLORS = ['#5ba6ff', '#53e5c8', '#ff7b72', '#ffd166', '#a78bfa', '#ffb26b'];

const events = computed<RiskEvent[]>(() => props.detail.recent_events);

/** 特征均值（电参量指标卡数据源） */
const avgFeature = (key: string): number => {
  const values = events.value
    .map((e) => Number(e.raw_features[key]))
    .filter((v) => Number.isFinite(v));
  if (values.length === 0) return 0;
  return Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(2));
};

/** 电参量指标卡（需求 7.2）：电压 / 电流 / 温度 / 频率 */
const metricCards = computed<MetricCardItem[]>(() => {
  return [
    { label: '电压', value: avgFeature('VoltageLevel_kV'), unit: 'kV', tone: 'primary' },
    { label: '电流', value: avgFeature('CurrentAmp'), unit: 'A', tone: 'warning' },
    { label: '温度', value: avgFeature('Temperature_C'), unit: '℃', tone: 'success' },
    { label: '频率', value: avgFeature('PowerFrequencyHz'), unit: 'Hz', tone: 'primary' },
  ];
});

/**
 * 设备健康度评估（需求 8.2 轻量算法）：0-100 健康分，
 * 由该设备越限率（风险事件占比）与平均风险评分加权计算，越高越健康。
 */
const deviceHealth = computed(() => powerDeviceHealth(events.value));

/** 健康分排行（供 BarChart 展示） */
const deviceRanking = computed<RankingItem[]>(() =>
  deviceHealth.value.map((d) => ({ name: d.component, score: d.healthScore }))
);

/** 最新事件的风险评分模型摘要（需求 8.2：包丢失 + 电参量偏差加权） */
const latestPowerRisk = computed(() => {
  const ev = events.value[0];
  if (!ev) return null;
  return powerRiskScore(ev, events.value);
});

/** IssueType 分布 */
const issueTypeDistribution = computed<TypeDistribution[]>(() => {
  const counts = new Map<string, number>();
  for (const ev of events.value) {
    const issue = ev.raw_features.IssueType;
    if (issue === undefined || issue === null || issue === '') continue;
    const key = String(issue);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, value], index) => ({ label, value, color: PIE_COLORS[index % PIE_COLORS.length] }));
});

/** 设备筛选（需求 7.2：点击设备条目筛选该设备的事件） */
const componentFilter = ref<string | null>(null);
const filteredEvents = computed<RiskEvent[]>(() =>
  componentFilter.value
    ? events.value.filter((e) => String(e.raw_features.Component ?? '') === componentFilter.value)
    : events.value
);

const setComponentFilter = (name: string) => {
  componentFilter.value = name;
};

const clearComponentFilter = () => {
  componentFilter.value = null;
};

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
        <h3 class="scenario-card__title">设备健康度评分（0-100）</h3>
        <BarChart v-if="deviceRanking.length" :data="deviceRanking" horizontal height="240px" @bar-click="setComponentFilter" />
        <p v-else class="scenario-empty">暂无数据</p>
        <p class="scenario-algo__note scenario-algo__note--mt">
          健康分由设备越限率（事件占比）与平均风险评分加权计算（需求 8.2）；点击柱条筛选该设备事件。
        </p>
        <p v-if="componentFilter" class="scenario-filter-tip">
          已筛选设备：{{ componentFilter }}
          <button class="scenario-filter-clear" @click="clearComponentFilter">清除筛选</button>
        </p>
      </section>
      <section class="scenario-card">
        <h3 class="scenario-card__title">IssueType 分布</h3>
        <PieChart v-if="issueTypeDistribution.length" :items="issueTypeDistribution" donut height="240px" />
        <p v-else class="scenario-empty">暂无数据</p>
      </section>
    </div>

    <!-- 风险评分模型（需求 8.2 轻量算法：Sensor_Packet_Loss_% + 电参量偏差加权） -->
    <section v-if="latestPowerRisk" class="scenario-card scenario-card--wide">
      <h3 class="scenario-card__title">风险评分模型（轻量算法）</h3>
      <div class="scenario-algo">
        <div class="scenario-algo__side">
          <p class="scenario-algo__note">
            对最近一条风险事件做加权风险评分：遥测包丢失 30% + 电压偏差 25% + 电流偏差 20%
            + 温度偏差 15% + 频率偏差 10%，输出 0-100 分，作为二分类结果的业务上下文解释。
          </p>
          <div class="scenario-algo__tags">
            <span
              class="scenario-algo__tag"
              :class="latestPowerRisk.score >= 70 ? 'scenario-algo__tag--danger' : latestPowerRisk.score >= 40 ? 'scenario-algo__tag--warning' : ''"
            >
              综合风险评分：{{ latestPowerRisk.score }} / 100
            </span>
            <span class="scenario-algo__tag">遥测包丢失：{{ latestPowerRisk.packetLoss.toFixed(1) }}%</span>
          </div>
        </div>
        <div class="scenario-algo__grid">
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">电压偏差</span>
            <span class="scenario-algo__item-value">{{ latestPowerRisk.voltageDeviation }}%</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">电流偏差</span>
            <span class="scenario-algo__item-value">{{ latestPowerRisk.currentDeviation }}%</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">温度偏差</span>
            <span class="scenario-algo__item-value">{{ latestPowerRisk.temperatureDeviation }}%</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">频率偏差</span>
            <span class="scenario-algo__item-value">{{ latestPowerRisk.frequencyDeviation }}%</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 风险事件时间线（需求 7.2：标注 IssueType 与受影响设备） -->
    <section class="scenario-card">
      <h3 class="scenario-card__title">风险事件时间线</h3>
      <EventTimeline v-if="filteredEvents.length" :events="filteredEvents" :meta-keys="['IssueType', 'Component']" />
      <p v-else class="scenario-empty">暂无风险事件</p>
    </section>
  </div>
</template>

<style scoped>
.scenario-event {
  cursor: pointer;
}

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
</style>
