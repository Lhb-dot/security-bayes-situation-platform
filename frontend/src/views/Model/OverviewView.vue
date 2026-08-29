<script setup lang="ts">
/**
 * OverviewView - 全局总览页面
 *
 * 展示三大场景整体运行态势
 * 包含：全局风险指标、场景卡片、总体风险趋势、高风险事件列表
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import type { GlobalOverview, RiskEvent, TypeDistribution } from '@/types/security';
import { useSituationStore } from '@/stores/situationStore';
import { getRiskEventList } from '@/api/riskEventApi';
import { mapRiskEvent } from '@/api/situationApi';
import ScenarioCard from '@/components/common/ScenarioCard.vue';
import LineTrendChart from '@/components/LineTrendChart.vue';
import DonutChart from '@/components/DonutChart.vue';
import RiskLevelTag from '@/components/common/RiskLevelTag.vue';

const router = useRouter();
const situationStore = useSituationStore();

/** 概览数据 */
const overview = ref<GlobalOverview | null>(null);
/** 高风险事件列表 */
const highRiskEvents = ref<RiskEvent[]>([]);
/** 全部风险事件（用于分布统计） */
const allEvents = ref<RiskEvent[]>([]);
/** 加载状态 */
const loading = ref(true);
/** 错误信息 */
const error = ref('');

/** 风险等级分布（用于DonutChart） */
const riskDistribution = computed<TypeDistribution[]>(() => {
  const counts: Record<string, number> = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  allEvents.value.forEach((e) => {
    if (counts[e.risk_level] !== undefined) counts[e.risk_level]++;
  });
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  if (total === 0) return [];
  return [
    { label: '高危', value: Math.round((counts.HIGH / total) * 100), color: '#ff7b72' },
    { label: '中危', value: Math.round((counts.MEDIUM / total) * 100), color: '#ffd166' },
    { label: '低危', value: Math.round((counts.LOW / total) * 100), color: '#9ad6ff' },
  ];
});

/** 加载数据 */
const loadData = async () => {
  loading.value = true;
  error.value = '';
  try {
    await situationStore.fetchGlobalOverview();
    overview.value = situationStore.overview;
    const raw = (await getRiskEventList({ page_size: 200 })) as unknown as Array<Record<string, unknown>>;
    allEvents.value = raw.map(mapRiskEvent);
    // 筛选高风险事件，最多取 5 条
    highRiskEvents.value = allEvents.value
      .filter((e) => e.risk_level === 'HIGH')
      .slice(0, 5);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '全局数据加载失败';
  } finally {
    loading.value = false;
  }
};

/** 点击场景卡片 -> 跳转场景大屏 */
const goScenarioDashboard = (scenarioId: string) => {
  router.push({ path: `/scenarios/${scenarioId}/dashboard` });
};

/** 点击事件行 → 风险事件详情（Task 012） */
const goEventDetail = (eventId: string) => {
  router.push({ path: `/events/${eventId}` });
};

/** 场景名称映射 */
const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '航母甲板',
};

/** 告警等级 -> Tag 文案 */
const riskLevelLabel: Record<string, string> = {
  HIGH: '高危',
  MEDIUM: '中危',
  LOW: '低危',
};

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="overview-view">
    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载全局态势数据...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadData">重试</button>
    </section>

    <template v-else-if="overview">
      <!-- ==================== 顶部：全局风险指标 ==================== -->
      <section class="ov-hero card">
        <div class="ov-hero__content">
          <div>
            <p class="eyebrow">Home</p>
            <h2>首页</h2>
            <p class="ov-hero__desc">全平台安全态势统一监控（管理员首页）</p>
          </div>
          <div class="ov-hero__metrics">
            <div class="ov-hero__main-score">
              <div
                class="ov-hero__score-value"
                :class="`ov-score--${overview.global_risk_level}`"
              >
                {{ overview.global_risk_score }}
              </div>
              <RiskLevelTag :level="overview.global_risk_level" size="large" />
            </div>
            <div class="ov-hero__sub-metrics">
              <div class="ov-hero__sub-item">
                <span class="ov-hero__sub-value">{{ overview.scenario_count }}</span>
                <span class="ov-hero__sub-label">场景总数</span>
              </div>
              <div class="ov-hero__sub-divider"></div>
              <div class="ov-hero__sub-item">
                <span class="ov-hero__sub-value ov-hero__sub-value--danger">{{ overview.high_risk_count }}</span>
                <span class="ov-hero__sub-label">高风险事件</span>
              </div>
              <div class="ov-hero__sub-divider"></div>
              <div class="ov-hero__sub-item">
                <span class="ov-hero__sub-value">{{ overview.active_model_count }}</span>
                <span class="ov-hero__sub-label">运行模型</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ==================== 中部：场景卡片 + 风险趋势 ==================== -->
      <div class="ov-mid">
        <section class="ov-scenarios">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Scenarios</p>
              <h3>业务场景概览</h3>
            </div>
          </div>
          <div class="ov-scenarios__grid">
            <ScenarioCard
              v-for="scenario in overview.scenarios"
              :key="scenario.scenario_id"
              :scenario="scenario"
              @click="goScenarioDashboard"
            />
          </div>
        </section>

        <section class="card chart-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Trend</p>
              <h3>总体风险趋势</h3>
            </div>
            <span class="section-tag">24h</span>
          </div>
          <LineTrendChart :points="overview.global_trend" />
        </section>
      </div>

      <!-- ==================== 底部：分布统计 + 事件列表 ==================== -->
      <div class="ov-bottom">
        <section class="card chart-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Distribution</p>
              <h3>高危事件分布统计</h3>
            </div>
          </div>
          <DonutChart :items="riskDistribution" title="事件分布" />
        </section>

        <section class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">High Risk Events</p>
              <h3>最近高风险事件</h3>
            </div>
            <span class="section-tag">{{ highRiskEvents.length }} 条</span>
          </div>
          <div class="ov-events">
            <div
              v-for="ev in highRiskEvents"
              :key="ev.event_id"
              class="ov-events__item"
              @click="goEventDetail(ev.event_id)"
            >
              <div class="ov-events__left">
                <span
                  class="risk-badge"
                  :class="`risk-${ev.risk_level.toLowerCase()}`"
                >
                  {{ riskLevelLabel[ev.risk_level] ?? ev.risk_level }}
                </span>
                <div>
                  <strong>{{ ev.description || ev.risk_type }}</strong>
                  <p>{{ scenarioLabel[ev.scenario_id] ?? ev.scenario_id }} · {{ ev.event_id }}</p>
                </div>
              </div>
              <div class="ov-events__right">
                <span class="ov-events__type">{{ ev.risk_type }}</span>
                <span class="ov-events__time">{{ ev.occurred_at }}</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.overview-view {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 22px;
}

/* ===== 顶部：全局风险指标 ===== */
.ov-hero__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.ov-hero__content h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.ov-hero__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.68);
  font-size: 0.92rem;
}

.ov-hero__metrics {
  display: flex;
  align-items: center;
  gap: 28px;
  flex-shrink: 0;
}

.ov-hero__main-score {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ov-hero__score-value {
  font-size: 3.2rem;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.ov-score--critical { color: #ff8c84; }
.ov-score--high { color: #ffc37d; }
.ov-score--medium { color: #9ad6ff; }
.ov-score--low { color: #53e5c8; }

.ov-hero__sub-metrics {
  display: flex;
  align-items: center;
  gap: 20px;
}

.ov-hero__sub-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.ov-hero__sub-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #e8f1ff;
  line-height: 1;
}

.ov-hero__sub-value--danger {
  color: #ff8c84;
}

.ov-hero__sub-label {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
  white-space: nowrap;
}

.ov-hero__sub-divider {
  width: 1px;
  height: 36px;
  background: rgba(125, 201, 255, 0.12);
}

/* ===== 场景卡片区域 ===== */
.ov-scenarios {
  display: grid;
  gap: 16px;
}

.ov-scenarios__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

/* ===== 中部：场景 + 趋势 ===== */
.ov-mid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 18px;
}

.ov-mid .chart-card {
  min-height: 360px;
}

/* ===== 底部：两列布局 ===== */
.ov-bottom {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 18px;
}

/* 高风险事件列表 */
.ov-events {
  display: grid;
  gap: 10px;
}

.ov-events__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.1);
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.ov-events__item:hover {
  background: rgba(91, 166, 255, 0.06);
  border-color: rgba(125, 201, 255, 0.2);
}

.ov-events__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.ov-events__left strong {
  display: block;
  font-size: 0.9rem;
  color: #e8f1ff;
}

.ov-events__left p {
  margin: 4px 0 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.58);
}

.ov-events__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.ov-events__type {
  font-size: 0.82rem;
  color: #9ad6ff;
  font-weight: 500;
}

.ov-events__time {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.5);
}

/* ===== 响应式降级 ===== */
@media (max-width: 1200px) {
  .ov-scenarios__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .ov-mid {
    grid-template-columns: 1fr;
  }
  .ov-bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .ov-hero__content {
    flex-direction: column;
    align-items: stretch;
  }
  .ov-hero__metrics {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
  }
  .ov-hero__sub-metrics {
    justify-content: space-around;
  }
  .ov-scenarios__grid {
    grid-template-columns: 1fr;
  }
  .ov-events__item {
    flex-direction: column;
    align-items: flex-start;
  }
  .ov-events__right {
    flex-direction: row;
    gap: 12px;
    align-items: center;
  }
}
</style>
