<script setup lang="ts">
/**
 * ScenarioStatusCard.vue — 系统管理员大屏·场景运行状态卡
 *
 * 职责：单场景"是否正常运行"的可视化卡片（状态灯 + 风险分 + 指标 + 迷你趋势）。
 * 状态判定：
 *   danger：存在高危事件，或风险分 >= 该场景 high 阈值；
 *   warn  ：存在中危事件，或风险分 >= medium 阈值；
 *   ok    ：其余（正常运行）。
 * 数据全部来自 props，纯展示组件；点击整卡跳转对应场景大屏。
 */
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { RiskEvent, Scenario, ThresholdConfig } from '@/types/security';

const props = defineProps<{
  scenario: Scenario;
  events: RiskEvent[];
  threshold?: ThresholdConfig;
}>();

const router = useRouter();

type StatusTone = 'ok' | 'warn' | 'danger';

const statusTone = computed<StatusTone>(() => {
  const riskScore = Number(props.scenario.risk_score) || 0;
  const highThreshold = props.threshold ? Number(props.threshold.high_threshold) * 100 : 80;
  const mediumThreshold = props.threshold ? Number(props.threshold.medium_threshold) * 100 : 45;
  const highCount = props.events.filter((e) => e.risk_level === 'HIGH').length;
  const mediumCount = props.events.filter((e) => e.risk_level === 'MEDIUM').length;
  if (highCount > 0 || riskScore >= highThreshold) return 'danger';
  if (mediumCount > 0 || riskScore >= mediumThreshold) return 'warn';
  return 'ok';
});

const statusLabel = computed(() =>
  statusTone.value === 'danger' ? '异常' : statusTone.value === 'warn' ? '关注' : '正常'
);

const scoreTone = computed<'danger' | 'warning' | 'success'>(() => {
  const s = Number(props.scenario.risk_score) || 0;
  if (s >= 75) return 'danger';
  if (s >= 45) return 'warning';
  return 'success';
});

const highCount = computed(() => props.events.filter((e) => e.risk_level === 'HIGH').length);

/**
 * 迷你趋势（最近 12 个 2 小时窗口的事件数，右侧为最新）。
 * 纯 SVG 绘制，避免大屏上挂多个 ECharts 实例。
 */
const spark = computed<{ line: string; area: string }>(() => {
  const buckets = new Array<number>(12).fill(0);
  const now = Date.now();
  for (const ev of props.events) {
    const t = new Date(ev.occurred_at.replace(' ', 'T')).getTime();
    if (Number.isNaN(t)) continue;
    const diffH = (now - t) / 3_600_000;
    if (diffH >= 0 && diffH < 24) {
      const idx = Math.min(11, Math.floor(diffH / 2));
      buckets[11 - idx] += 1;
    }
  }
  const max = Math.max(1, ...buckets);
  const w = 132;
  const h = 38;
  const pad = 3;
  const step = w / (buckets.length - 1);
  const points = buckets.map((v, i) => {
    const x = i * step;
    const y = h - pad - (v / max) * (h - pad * 2);
    return [x, y] as const;
  });
  const line = points
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ');
  const lastX = points[points.length - 1]?.[0] ?? w;
  const area = `${line} L${lastX.toFixed(1)},${h} L0,${h} Z`;
  return { line, area };
});

const goDashboard = (): void => {
  router.push({ path: `/scenarios/${props.scenario.scenario_id}/dashboard` });
};
</script>

<template>
  <button
    type="button"
    class="admin-scenario-card"
    :class="`admin-scenario-card--${statusTone}`"
    @click="goDashboard"
  >
    <div class="admin-scenario-card__head">
      <div class="admin-scenario-card__title">
        <span
          class="admin-scenario-card__dot"
          :class="`admin-scenario-card__dot--${statusTone}`"
          :title="`状态：${statusLabel}`"
        ></span>
        <strong>{{ scenario.name }}</strong>
        <em class="admin-scenario-card__code">{{ scenario.scenario_id }}</em>
      </div>
      <span
        class="admin-scenario-card__status"
        :class="`admin-scenario-card__status--${statusTone}`"
      >
        {{ statusLabel }}
      </span>
    </div>

    <div class="admin-scenario-card__body">
      <div class="admin-scenario-card__score">
        <span class="admin-scenario-card__score-value" :class="`admin-score--${scoreTone}`">
          {{ Number(scenario.risk_score) || 0 }}
        </span>
        <span class="admin-scenario-card__score-label">风险分</span>
      </div>

      <div class="admin-scenario-card__metrics">
        <div class="admin-scenario-card__metric">
          <span class="admin-scenario-card__metric-value">{{ scenario.event_count ?? 0 }}</span>
          <span class="admin-scenario-card__metric-label">事件</span>
        </div>
        <div class="admin-scenario-card__metric">
          <span class="admin-scenario-card__metric-value admin-metric--danger">{{ highCount }}</span>
          <span class="admin-scenario-card__metric-label">高危</span>
        </div>
        <div class="admin-scenario-card__metric">
          <span class="admin-scenario-card__metric-value">{{ scenario.model_count ?? 0 }}</span>
          <span class="admin-scenario-card__metric-label">模型</span>
        </div>
        <div class="admin-scenario-card__metric">
          <span class="admin-scenario-card__metric-value">{{ scenario.dataset_count ?? 0 }}</span>
          <span class="admin-scenario-card__metric-label">数据集</span>
        </div>
      </div>
    </div>

    <div class="admin-scenario-card__spark">
      <svg
        class="admin-scenario-card__spark-svg"
        viewBox="0 0 132 38"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient :id="`spark-${scenario.scenario_id}`" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#7dc9ff" stop-opacity="0.35" />
            <stop offset="100%" stop-color="#7dc9ff" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path :d="spark.area" :fill="`url(#spark-${scenario.scenario_id})`" />
        <path :d="spark.line" fill="none" stroke="#7dc9ff" stroke-width="1.6" stroke-linecap="round" />
      </svg>
      <span class="admin-scenario-card__spark-label">近24h事件趋势</span>
    </div>
  </button>
</template>

<style scoped>
.admin-scenario-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  height: 100%;
  padding: 18px 18px 14px;
  text-align: left;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.16);
  background:
    linear-gradient(160deg, rgba(16, 34, 62, 0.92), rgba(8, 17, 31, 0.94)),
    radial-gradient(circle at 100% 0%, rgba(91, 166, 255, 0.14), transparent 55%);
  color: #e8f1ff;
  cursor: pointer;
  transition: transform 0.18s, border-color 0.18s, box-shadow 0.18s;
  overflow: hidden;
}

.admin-scenario-card::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 100% 0%, rgba(91, 166, 255, 0.16), transparent 58%);
  pointer-events: none;
}

.admin-scenario-card:hover {
  transform: translateY(-2px);
  border-color: rgba(125, 201, 255, 0.42);
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.45), 0 0 24px rgba(91, 166, 255, 0.12);
}

.admin-scenario-card--danger {
  border-color: rgba(255, 123, 114, 0.42);
  box-shadow: inset 0 0 40px rgba(255, 123, 114, 0.06);
}

.admin-scenario-card--warn {
  border-color: rgba(255, 209, 102, 0.36);
}

.admin-scenario-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.admin-scenario-card__title {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.admin-scenario-card__title strong {
  font-size: 1.02rem;
  color: #eaf3ff;
  white-space: nowrap;
}

.admin-scenario-card__code {
  font-style: normal;
  font-size: 0.68rem;
  color: rgba(154, 214, 255, 0.55);
  border: 1px solid rgba(125, 201, 255, 0.16);
  border-radius: 999px;
  padding: 2px 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.admin-scenario-card__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.admin-scenario-card__dot--ok {
  background: #53e5c8;
  box-shadow: 0 0 10px rgba(83, 229, 200, 0.9);
  animation: admin-pulse-ok 2s ease-in-out infinite;
}

.admin-scenario-card__dot--warn {
  background: #ffd166;
  box-shadow: 0 0 10px rgba(255, 209, 102, 0.9);
  animation: admin-pulse-warn 2s ease-in-out infinite;
}

.admin-scenario-card__dot--danger {
  background: #ff7b72;
  box-shadow: 0 0 12px rgba(255, 123, 114, 1);
  animation: admin-pulse-danger 1.2s ease-in-out infinite;
}

@keyframes admin-pulse-ok {
  0%, 100% { box-shadow: 0 0 6px rgba(83, 229, 200, 0.7); }
  50% { box-shadow: 0 0 14px rgba(83, 229, 200, 1); }
}

@keyframes admin-pulse-warn {
  0%, 100% { box-shadow: 0 0 6px rgba(255, 209, 102, 0.7); }
  50% { box-shadow: 0 0 14px rgba(255, 209, 102, 1); }
}

@keyframes admin-pulse-danger {
  0%, 100% { box-shadow: 0 0 8px rgba(255, 123, 114, 0.8); }
  50% { box-shadow: 0 0 20px rgba(255, 123, 114, 1); }
}

.admin-scenario-card__status {
  flex-shrink: 0;
  padding: 3px 12px;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 600;
}

.admin-scenario-card__status--ok {
  background: rgba(83, 229, 200, 0.14);
  color: #53e5c8;
  border: 1px solid rgba(83, 229, 200, 0.3);
}

.admin-scenario-card__status--warn {
  background: rgba(255, 209, 102, 0.13);
  color: #ffd166;
  border: 1px solid rgba(255, 209, 102, 0.3);
}

.admin-scenario-card__status--danger {
  background: rgba(255, 123, 114, 0.15);
  color: #ff8c84;
  border: 1px solid rgba(255, 123, 114, 0.36);
}

.admin-scenario-card__body {
  flex: 1;
  display: flex;
  align-items: stretch;
  gap: 16px;
}

.admin-scenario-card__score {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 74px;
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.035);
  border: 1px solid rgba(125, 201, 255, 0.1);
}

.admin-scenario-card__score-value {
  font-size: 1.8rem;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.admin-scenario-card__score-label {
  margin-top: 5px;
  font-size: 0.7rem;
  color: rgba(220, 234, 255, 0.55);
}

.admin-score--success { color: #53e5c8; }
.admin-score--warning { color: #ffd166; }
.admin-score--danger { color: #ff8c84; }

.admin-scenario-card__metrics {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.admin-scenario-card__metric {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 4px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
}

.admin-scenario-card__metric-value {
  font-size: 1.05rem;
  font-weight: 700;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

.admin-metric--danger {
  color: #ff8c84;
}

.admin-scenario-card__metric-label {
  font-size: 0.68rem;
  color: rgba(220, 234, 255, 0.5);
}

.admin-scenario-card__spark {
  position: relative;
  flex: 1;
  min-height: 46px;
  border-radius: 10px;
  background: rgba(8, 17, 31, 0.55);
  border: 1px solid rgba(125, 201, 255, 0.08);
  overflow: hidden;
}

.admin-scenario-card__spark-svg {
  position: absolute;
  inset: 4px 6px;
  width: calc(100% - 12px);
  height: calc(100% - 20px);
}

.admin-scenario-card__spark-label {
  position: absolute;
  left: 8px;
  bottom: 5px;
  font-size: 0.62rem;
  color: rgba(220, 234, 255, 0.42);
}
</style>
