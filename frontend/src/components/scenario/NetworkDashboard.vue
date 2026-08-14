<script setup lang="ts">
/**
 * NetworkDashboard.vue — 网络安全态势看板（Task 009）
 *
 * 数据全部来自 props（ScenarioDetail / SituationData，由容器经 store 获取），
 * 所有聚合转换在 computed 中完成；无 any / ts-ignore。
 * 对齐需求 7.1：总连接数/异常数/风险率/今日告警指标卡、TOP 端口、流量分布、按等级筛选事件列表；
 * 点击端口 → 预填风险研判表单（/inference?port=）。
 */
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import type { Dataset, RankingItem, RiskEvent, ScenarioDetail, SituationData, TypeDistribution } from '@/types/security';
import ScenarioMetricCard from './ScenarioMetricCard.vue';
import BarChart from '@/components/charts/BarChart.vue';
import PieChart from '@/components/charts/PieChart.vue';
import { networkPortDeviation, zScoreAnomaly } from '@/utils/scenarioAlgorithms';

const props = defineProps<{
  detail: ScenarioDetail;
  situation: SituationData;
  datasets?: Dataset[];
}>();

const router = useRouter();

/** 今日日期（YYYY-MM-DD），用于"今日告警数" */
const todayStr = (): string => {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

/** 详情指标取值（统一转 number） */
const metricValue = (id: string): number => {
  const item = props.detail.metrics.find((m) => m.id === id);
  return item ? Number(item.value) : 0;
};

interface MetricCardItem {
  label: string;
  value: number;
  unit: string;
  tone: 'primary' | 'danger' | 'warning' | 'success';
}

const PIE_COLORS = ['#5ba6ff', '#53e5c8', '#ff7b72', '#ffd166', '#a78bfa', '#ffb26b'];

const events = computed<RiskEvent[]>(() => props.detail.recent_events);

/** 指标卡（需求 7.1）：总连接数 / 异常数 / 风险率 / 今日告警数 */
const metricCards = computed<MetricCardItem[]>(() => {
  const s = props.detail.scenario;
  const totalConnections = metricValue('model-accuracy');
  const abnormal = s.event_count;
  const riskRate = totalConnections > 0 ? Math.round((abnormal / totalConnections) * 100) : 0;
  const todayAlerts = events.value.filter((e) => e.occurred_at.startsWith(todayStr())).length;
  return [
    { label: '总连接数', value: totalConnections, unit: '条', tone: 'primary' },
    { label: '异常数', value: abnormal, unit: '起', tone: 'danger' },
    { label: '风险率', value: riskRate, unit: '%', tone: 'warning' },
    { label: '今日告警', value: todayAlerts, unit: '起', tone: 'danger' },
  ];
});

/** TOP 端口排行（raw_features.L4_DST_PORT 聚合计数） */
const topPorts = computed<RankingItem[]>(() => {
  const counts = new Map<string, number>();
  for (const ev of events.value) {
    const port = ev.raw_features.L4_DST_PORT;
    if (port === undefined || port === null || port === '') continue;
    const key = String(port);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, score]) => ({ name, score }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 8);
});

/**
 * 端口偏离度预判（需求 8.1 轻量算法）：端口出现次数相对均匀基线的偏离度评分 0-100。
 * 与 topPorts（纯计数）并存：计数排行看"量"，偏离度排行看"异常程度"。
 */
const portDeviation = computed(() => networkPortDeviation(events.value).slice(0, 8));

/** 偏离度评分排行（供 BarChart 展示） */
const deviationRanking = computed<RankingItem[]>(() =>
  portDeviation.value.map((p) => ({ name: p.port, score: p.score }))
);

/** 异常端口数（偏离倍数 >= 2） */
const anomalyPortCount = computed(() => portDeviation.value.filter((p) => p.anomaly).length);

/**
 * Z-score 突变检测摘要（需求 8.1）：按事件发生时间（分钟级窗口）聚合计数，
 * 对窗口序列做留一法 Z-score 检测，标记突变窗口。
 */
const zScoreWindows = computed(() => {
  const sorted = [...events.value].sort((a, b) => a.occurred_at.localeCompare(b.occurred_at));
  const counts = new Map<string, number>();
  for (const ev of sorted) {
    const key = ev.occurred_at.slice(0, 16);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const labels = [...counts.keys()];
  const values = labels.map((label) => counts.get(label) ?? 0);
  return zScoreAnomaly(values).map((r, i) => ({ window: labels[i], ...r }));
});

/** 突变窗口数 */
const anomalyWindowCount = computed(() => zScoreWindows.value.filter((w) => w.anomaly).length);

/** 流量分布（需求 7.1）：优先包长区间五段，回退 TCP_FLAGS，再回退协议 */
const flowDistribution = computed<TypeDistribution[]>(() => {
  const bucketKeys = [
    'NUM_PKTS_UP_TO_128_BYTES',
    'NUM_PKTS_128_TO_256_BYTES',
    'NUM_PKTS_256_TO_512_BYTES',
    'NUM_PKTS_512_TO_1024_BYTES',
    'NUM_PKTS_1024_TO_1514_BYTES',
  ];
  const bucketLabels = ['≤128B', '128-256B', '256-512B', '512-1024B', '1024-1514B'];
  const bucketCounts = bucketKeys.map((key) =>
    events.value.reduce((sum, e) => sum + (Number(e.raw_features[key]) || 0), 0)
  );
  if (bucketCounts.some((v) => v > 0)) {
    return bucketCounts
      .map((value, index) => ({ label: bucketLabels[index], value, color: PIE_COLORS[index % PIE_COLORS.length] }))
      .filter((item) => item.value > 0);
  }
  const tcpCounts = new Map<string, number>();
  for (const ev of events.value) {
    const flags = ev.raw_features.TCP_FLAGS;
    if (flags === undefined || flags === null || flags === '') continue;
    const key = String(flags);
    tcpCounts.set(key, (tcpCounts.get(key) ?? 0) + 1);
  }
  if (tcpCounts.size > 0) {
    return [...tcpCounts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([label, value], index) => ({ label: `TCP_FLAGS ${label}`, value, color: PIE_COLORS[index % PIE_COLORS.length] }));
  }
  const counts = new Map<string, number>();
  for (const ev of events.value) {
    const proto = ev.raw_features.PROTOCOL ?? ev.raw_features.protocol_type;
    const key = proto === undefined || proto === null || proto === '' ? '未知' : String(proto);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([label, value], index) => ({ label, value, color: PIE_COLORS[index % PIE_COLORS.length] }));
});

/** 等级筛选（需求 7.1：事件列表支持按等级筛选） */
const levelFilter = ref<'all' | RiskEvent['risk_level']>('all');
const filteredEvents = computed<RiskEvent[]>(() =>
  levelFilter.value === 'all' ? events.value : events.value.filter((e) => e.risk_level === levelFilter.value)
);

const levelFilterOptions: Array<{ value: 'all' | RiskEvent['risk_level']; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'HIGH', label: '高危' },
  { value: 'MEDIUM', label: '中危' },
  { value: 'LOW', label: '低危' },
];

const riskLabel = (level: RiskEvent['risk_level']): string => {
  if (level === 'HIGH') return '高危';
  if (level === 'MEDIUM') return '中危';
  return '低危';
};

/** 点击事件行 → 风险事件详情（Task 012） */
const goEventDetail = (eventId: string) => {
  router.push({ path: `/events/${eventId}` });
};

/** 点击端口 → 预填风险研判表单（需求 7.1 交互） */
const goInferenceWithPort = (port: string) => {
  router.push({ path: '/inference', query: { port } });
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
        <h3 class="scenario-card__title">TOP 端口排行</h3>
        <BarChart v-if="topPorts.length" :data="topPorts" horizontal height="240px" @bar-click="goInferenceWithPort" />
        <p v-else class="scenario-empty">暂无数据</p>
      </section>
      <section class="scenario-card">
        <h3 class="scenario-card__title">流量分布</h3>
        <PieChart v-if="flowDistribution.length" :items="flowDistribution" donut height="240px" />
        <p v-else class="scenario-empty">暂无数据</p>
      </section>
    </div>

    <!-- 轻量算法预判（需求 8.1：端口偏离度评分 + Z-score 突变检测） -->
    <section class="scenario-card scenario-card--wide">
      <h3 class="scenario-card__title">流量偏离度预判（轻量算法）</h3>
      <div v-if="portDeviation.length" class="scenario-algo">
        <div class="scenario-algo__chart">
          <BarChart
            :data="deviationRanking"
            horizontal
            height="240px"
            @bar-click="goInferenceWithPort"
          />
        </div>
        <div class="scenario-algo__side">
          <p class="scenario-algo__note">
            端口偏离度评分（0-100）由端口出现次数相对均匀基线的偏离倍数计算；
            偏离 ≥ 2 倍标记为异常端口。点击柱条可带该端口跳转风险研判预填表单。
          </p>
          <div class="scenario-algo__tags">
            <span
              class="scenario-algo__tag"
              :class="{ 'scenario-algo__tag--danger': anomalyPortCount > 0 }"
            >
              {{ anomalyPortCount > 0 ? `${anomalyPortCount} 个异常端口` : '未发现明显异常端口' }}
            </span>
            <span class="scenario-algo__tag">
              Z-score 突变窗口：{{ anomalyWindowCount }} 个
            </span>
          </div>
        </div>
      </div>
      <p v-else class="scenario-empty">暂无数据</p>
    </section>

    <!-- 风险事件列表（按等级筛选） -->
    <section class="scenario-card">
      <h3 class="scenario-card__title">风险事件列表</h3>
      <div class="scenario-filter-row">
        <button
          v-for="opt in levelFilterOptions"
          :key="opt.value"
          class="scenario-filter-btn"
          :class="{ 'is-active': levelFilter === opt.value }"
          @click="levelFilter = opt.value"
        >
          {{ opt.label }}
        </button>
      </div>
      <div v-if="filteredEvents.length" class="scenario-events">
        <div v-for="ev in filteredEvents" :key="ev.event_id" class="scenario-event" @click="goEventDetail(ev.event_id)">
          <span class="scenario-event__badge" :class="`scenario-event__badge--${ev.risk_level.toLowerCase()}`">
            {{ riskLabel(ev.risk_level) }}
          </span>
          <div class="scenario-event__body">
            <strong>{{ ev.description }}</strong>
            <span class="scenario-event__meta">{{ ev.event_id }} · {{ ev.occurred_at }}</span>
          </div>
        </div>
      </div>
      <p v-else class="scenario-empty">暂无事件</p>
    </section>
  </div>
</template>

<style scoped>
.scenario-event {
  cursor: pointer;
}

.scenario-filter-row {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.scenario-filter-btn {
  padding: 4px 14px;
  border-radius: 999px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: transparent;
  color: rgba(220, 234, 255, 0.65);
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.scenario-filter-btn:hover {
  background: rgba(91, 166, 255, 0.1);
}

.scenario-filter-btn.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  border-color: rgba(91, 166, 255, 0.5);
}
</style>
