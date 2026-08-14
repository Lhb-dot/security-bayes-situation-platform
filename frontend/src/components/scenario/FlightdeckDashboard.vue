<script setup lang="ts">
/**
 * FlightdeckDashboard.vue — 航母甲板运行态势看板（Task 009）
 *
 * 数据全部来自 props（事件 raw_features 含完整轨迹字段），聚合转换在 computed 中完成。
 * 对齐需求 7.4：KPI 卡（碰撞概率/最小间距/接近率/总航程，超阈值告警高亮）、
 * 甲板热点图（fault_position_x/y，占位底图）、间距变化折线、方向角对比雷达、碰撞事件列表。
 */
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { Dataset, RiskEvent, ScenarioDetail, SituationData, TrendPoint } from '@/types/security';
import ScenarioMetricCard from './ScenarioMetricCard.vue';
import LineChart from '@/components/charts/LineChart.vue';
import RadarChart from '@/components/charts/RadarChart.vue';
import DeckHeatMap from '@/components/Deck/DeckHeatMap.vue';
import { collisionRiskScore, trajectoryDeviationScore } from '@/utils/scenarioAlgorithms';

const props = defineProps<{
  detail: ScenarioDetail;
  situation: SituationData;
  datasets?: Dataset[];
}>();

const router = useRouter();

interface MetricCardItem {
  label: string;
  value: number;
  unit: string;
  tone: 'primary' | 'danger' | 'warning' | 'success';
  /** 超阈值告警高亮（需求 7.4：碰撞风险/最小间距联动） */
  alert?: boolean;
}

const events = computed<RiskEvent[]>(() => props.detail.recent_events);

/** 事件特征数值读取（防御非数值） */
const numOf = (ev: RiskEvent, key: string, fallback = 0): number => {
  const v = Number(ev.raw_features[key]);
  return Number.isFinite(v) ? v : fallback;
};

/** 取主轨迹事件（最近一条，含完整 278+ 字段） */
const primaryEvent = computed<RiskEvent | null>(() => events.value[0] ?? null);

/** 航迹指标：最小间距 / 接近率 / 碰撞风险 / 总航程 */
const metricCards = computed<MetricCardItem[]>(() => {
  const list = events.value;
  if (list.length === 0) {
    return [
      { label: '碰撞概率', value: 0, unit: '%', tone: 'primary' },
      { label: '最小间距', value: 0, unit: 'm', tone: 'primary' },
      { label: '接近率', value: 0, unit: '', tone: 'primary' },
      { label: '总航程', value: 0, unit: 'm', tone: 'primary' },
    ];
  }
  const minDist = Math.min(...list.map((e) => numOf(e, 'inter_dist_min', 999)));
  const closure = Math.max(...list.map((e) => Math.abs(numOf(e, 'dist_change_ratio'))));
  const collision = Math.max(...list.map((e) => Math.round(e.risk_score * 100)));
  const totalDist = Math.max(...list.map((e) => numOf(e, 'Plane1_total_distance')));
  return [
    { label: '碰撞概率', value: collision, unit: '%', tone: collision >= 70 ? 'danger' : 'warning', alert: collision >= 70 },
    { label: '最小间距', value: Number(minDist.toFixed(1)), unit: 'm', tone: minDist < 20 ? 'danger' : 'success', alert: minDist < 20 },
    { label: '接近率', value: Number(closure.toFixed(4)), unit: '', tone: 'warning' },
    { label: '总航程', value: Number(totalDist.toFixed(0)), unit: 'm', tone: 'primary' },
  ];
});

/** 按字段族提取序列（如 inter_distance_1..50 / relative_angle_deg_1..49） */
const seriesOf = (ev: RiskEvent | null, prefix: string, count: number): TrendPoint[] => {
  if (!ev) return [];
  const points: TrendPoint[] = [];
  for (let i = 1; i <= count; i++) {
    const v = Number(ev.raw_features[`${prefix}_${i}`]);
    if (!Number.isFinite(v)) continue;
    points.push({
      label: `T${i}`,
      value: v,
      blocked: 0,
      sources: 0,
      primaryType: 'FLIGHT_DECK_OPERATION_RISK',
    });
  }
  return points;
};

/** 间距变化趋势（inter_distance_1..50） */
const distanceTrend = computed<TrendPoint[]>(() => seriesOf(primaryEvent.value, 'inter_distance', 50));

/** 方向角对比雷达（需求 7.4：1 号机 vs 2 号机方向角统计量 均值/最大/最小/标准差） */
const radarCompare = computed<{
  indicators: { name: string; max: number }[];
  series: { name: string; values: number[] }[];
}>(() => {
  const ev = primaryEvent.value;
  if (!ev) return { indicators: [], series: [] };
  const stat = (key: string) => numOf(ev, key);
  const labels = ['均值', '最大', '最小', '标准差'] as const;
  const plane1 = { 均值: stat('Plane1_dir_mean_deg'), 最大: stat('Plane1_dir_max_deg'), 最小: stat('Plane1_dir_min_deg'), 标准差: stat('Plane1_dir_std_deg') };
  const plane2 = { 均值: stat('Plane2_dir_mean_deg'), 最大: stat('Plane2_dir_max_deg'), 最小: stat('Plane2_dir_min_deg'), 标准差: stat('Plane2_dir_std_deg') };
  const maxVal = Math.max(180, ...labels.map((l) => plane1[l]), ...labels.map((l) => plane2[l]));
  return {
    indicators: labels.map((name) => ({ name, max: Math.ceil(maxVal / 10) * 10 })),
    series: [
      { name: '1 号机', values: labels.map((l) => plane1[l]) },
      { name: '2 号机', values: labels.map((l) => plane2[l]) },
    ],
  };
});

/** 碰撞风险评估（需求 8.4 轻量算法：最小间距 + 接近率 → 0-100 风险分） */
const collisionRisk = computed(() => {
  const ev = primaryEvent.value;
  if (!ev) return null;
  const minDist = numOf(ev, 'inter_dist_min', 999);
  const closure = Math.abs(numOf(ev, 'dist_change_ratio'));
  return collisionRiskScore(minDist, closure);
});

/** 轨迹偏差检测（需求 8.4：方向角 / 相对角 / 间距标准差相对基线偏差评分） */
const trajectoryDeviation = computed(() => {
  const ev = primaryEvent.value;
  if (!ev) return null;
  return trajectoryDeviationScore(ev);
});

const riskLabel = (level: RiskEvent['risk_level']): string => {
  if (level === 'HIGH') return '高危';
  if (level === 'MEDIUM') return '中危';
  return '低危';
};

/** 点击事件行 → 风险事件详情（Task 012） */
const goEventDetail = (eventId: string) => {
  router.push({ path: `/events/${eventId}` });
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

    <!-- 热点图状态说明（需求 7.4.1：占位底图，美工替换后仅更换背景） -->
    <section class="scenario-card scenario-note">
      <p class="scenario-note__text">
        甲板热点图已接入（需求 7.4.1）：当前使用占位底图（坐标基准 1000px），
        红点按 fault_position_x/y 定位，悬停显示评分/碰撞概率/时间，点击跳事件详情；美工底图替换后仅更换背景。
      </p>
    </section>

    <!-- 图表区 -->
    <div class="scenario-grid">
      <section class="scenario-card">
        <h3 class="scenario-card__title">甲板热点图</h3>
        <DeckHeatMap :events="events" />
      </section>
      <div class="scenario-stack">
        <section class="scenario-card">
        <h3 class="scenario-card__title">间距变化趋势</h3>
        <LineChart v-if="distanceTrend.length" :points="distanceTrend" area height="240px" />
        <p v-else class="scenario-empty">暂无数据</p>
        </section>
        <section class="scenario-card">
          <h3 class="scenario-card__title">方向角对比雷达</h3>
          <RadarChart v-if="radarCompare.indicators.length" :indicators="radarCompare.indicators" :series="radarCompare.series" height="240px" />
          <p v-else class="scenario-empty">暂无数据</p>
        </section>
      </div>
    </div>

    <!-- 碰撞风险评估 + 轨迹偏差检测（需求 8.4 轻量算法） -->
    <section v-if="collisionRisk" class="scenario-card scenario-card--wide">
      <h3 class="scenario-card__title">碰撞风险评估（轻量算法）</h3>
      <div class="scenario-algo">
        <div class="scenario-algo__side">
          <p class="scenario-algo__note">
            碰撞风险评分由最小间距（60%）与接近率（40%）加权得到 0-100 分；
            轨迹偏差评分基于双机方向角 / 相对角 / 间距标准差相对经验基线的偏差，
            作为二分类结果的辅助解释层（需求 8.4）。
          </p>
          <div class="scenario-algo__tags">
            <span
              class="scenario-algo__tag"
              :class="collisionRisk.score >= 70 ? 'scenario-algo__tag--danger' : collisionRisk.score >= 40 ? 'scenario-algo__tag--warning' : ''"
            >
              碰撞风险：{{ collisionRisk.score }} / 100
            </span>
            <span
              class="scenario-algo__tag"
              :class="(trajectoryDeviation?.score ?? 0) >= 70 ? 'scenario-algo__tag--danger' : ''"
            >
              轨迹偏差：{{ trajectoryDeviation?.score ?? 0 }} / 100
            </span>
          </div>
        </div>
        <div class="scenario-algo__grid">
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">最小间距</span>
            <span class="scenario-algo__item-value">{{ collisionRisk.minDistance.toFixed(1) }} m</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">接近率</span>
            <span class="scenario-algo__item-value">{{ collisionRisk.closureRate.toFixed(3) }}</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">1 号机方向角标准差</span>
            <span class="scenario-algo__item-value">{{ trajectoryDeviation?.plane1Std.toFixed(1) ?? '-' }}°</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">2 号机方向角标准差</span>
            <span class="scenario-algo__item-value">{{ trajectoryDeviation?.plane2Std.toFixed(1) ?? '-' }}°</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">相对角标准差</span>
            <span class="scenario-algo__item-value">{{ trajectoryDeviation?.relativeStd.toFixed(1) ?? '-' }}°</span>
          </div>
          <div class="scenario-algo__item">
            <span class="scenario-algo__item-label">间距标准差</span>
            <span class="scenario-algo__item-value">{{ trajectoryDeviation?.distStd.toFixed(1) ?? '-' }} m</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 碰撞事件列表 -->
    <section class="scenario-card">
      <h3 class="scenario-card__title">最近碰撞事件</h3>
        <div v-if="events.length" class="scenario-events">
          <div v-for="ev in events" :key="ev.event_id" class="scenario-event" @click="goEventDetail(ev.event_id)">
            <span class="scenario-event__badge" :class="`scenario-event__badge--${ev.risk_level.toLowerCase()}`">
              {{ riskLabel(ev.risk_level) }}
            </span>
            <div class="scenario-event__body">
              <strong>{{ ev.description }}</strong>
              <span class="scenario-event__meta">{{ ev.event_id }} · 碰撞概率 {{ Math.round(ev.risk_score * 100) }}% · {{ ev.occurred_at }}</span>
            </div>
          </div>
        </div>
        <p v-else class="scenario-empty">暂无碰撞事件</p>
    </section>
  </div>
</template>

<style scoped>
.scenario-event {
  cursor: pointer;
}

.scenario-note {
  min-height: auto;
  padding: 12px 18px;
  border-style: dashed;
  border-color: rgba(255, 209, 102, 0.3);
  background: rgba(255, 209, 102, 0.05);
}

.scenario-note__text {
  margin: 0;
  font-size: 0.82rem;
  color: rgba(255, 209, 102, 0.85);
  line-height: 1.6;
}

.scenario-stack {
  display: grid;
  gap: 18px;
}
</style>
