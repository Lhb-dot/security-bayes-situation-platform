<script setup lang="ts">
/**
 * ScenarioDashboard - 场景大屏页面
 *
 * 展示单个场景的专属态势看板
 * 包含：场景风险指标、风险趋势图、风险类型分布、风险事件排行、最近风险事件
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import type { ScenarioDetail, RankingItem, ScenarioId } from '@/types/security';
import { getScenarioDetail } from '@/services/mockApi';
import DonutChart from '@/components/DonutChart.vue';
import LineTrendChart from '@/components/LineTrendChart.vue';
import RankingList from '@/components/RankingList.vue';
import RiskLevelTag from '@/components/common/RiskLevelTag.vue';

const route = useRoute();

/** 从路由参数获取场景 ID */
const scenarioId = computed(() => route.params.scenarioId as string);

/** 场景详情数据 */
const detail = ref<ScenarioDetail | null>(null);
const loading = ref(true);
const error = ref('');

/** 将 recent_events 转为 RankingItem[]（按风险概率排序） */
const eventRanking = computed<RankingItem[]>(() => {
  if (!detail.value) return [];
  return detail.value.recent_events
    .map((ev) => ({
      name: ev.title ?? ev.event_type ?? '未知事件',
      score: Math.round((ev.risk_probability ?? 0.5) * 100),
    }))
    .sort((a, b) => b.score - a.score);
});

/** 加载场景详情 */
const loadDetail = async () => {
  loading.value = true;
  error.value = '';
  try {
    detail.value = await getScenarioDetail(scenarioId.value as ScenarioId);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '场景数据加载失败';
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadDetail();
});
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
      <button class="ghost-button" @click="loadDetail">重试</button>
    </section>

    <template v-else-if="detail">
      <!-- ==================== 顶部：场景概览 ==================== -->
      <section class="sd-hero card">
        <div class="sd-hero__content">
          <div>
            <p class="eyebrow">Scenario Dashboard</p>
            <div class="sd-hero__title-row">
              <h2>{{ detail.scenario.name }}</h2>
              <RiskLevelTag :level="detail.scenario.risk_level" size="large" />
            </div>
            <p class="sd-hero__desc">{{ detail.scenario.description }}</p>
          </div>
          <div class="sd-hero__score">
            <div class="sd-hero__score-value" :class="`sd-score--${detail.scenario.risk_level}`">
              {{ detail.scenario.risk_score }}
            </div>
            <span class="sd-hero__score-label">风险评分</span>
          </div>
        </div>
      </section>

      <!-- ==================== 指标行 ==================== -->
      <section class="sd-metrics">
        <div
          v-for="metric in detail.metrics"
          :key="metric.id"
          class="sd-metric card"
        >
          <p class="sd-metric__label">{{ metric.label }}</p>
          <strong class="sd-metric__value">{{ metric.value }}</strong>
          <p
            class="sd-metric__trend"
            :class="{ 'sd-trend--up': metric.trend > 0, 'sd-trend--down': metric.trend < 0 }"
          >
            {{ metric.trend > 0 ? '+' : '' }}{{ metric.trend }}%
          </p>
        </div>
      </section>

      <!-- ==================== 中部：图表区域 ==================== -->
      <div class="sd-charts">
        <section class="card chart-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Trend</p>
              <h3>风险趋势图</h3>
            </div>
            <span class="section-tag">24h</span>
          </div>
          <LineTrendChart :points="detail.trend_data" />
        </section>

        <section class="card chart-card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Distribution</p>
              <h3>风险类型分布</h3>
            </div>
          </div>
          <DonutChart :items="detail.risk_distribution" title="风险类型" />
        </section>
      </div>

      <!-- ==================== 底部：排行 + 事件列表 ==================== -->
      <div class="sd-bottom">
        <section class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Ranking</p>
              <h3>风险事件排行</h3>
            </div>
          </div>
          <RankingList :items="eventRanking" accent="danger" />
        </section>

        <section class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Recent Events</p>
              <h3>最近风险事件</h3>
            </div>
            <span class="section-tag">{{ detail.recent_events.length }} 条</span>
          </div>
          <div class="sd-events">
            <div
              v-for="ev in detail.recent_events"
              :key="ev.event_id"
              class="sd-events__item"
            >
              <div class="sd-events__left">
                <RiskLevelTag :level="ev.risk_level" size="small" />
                <div>
                  <strong>{{ ev.title ?? ev.event_type }}</strong>
                  <p>{{ ev.description ?? '' }}</p>
                </div>
              </div>
              <div class="sd-events__right">
                <span class="sd-events__prob">
                  风险概率：{{ Math.round((ev.risk_probability ?? 0) * 100) }}%
                </span>
                <span class="sd-events__time">{{ ev.timestamp ?? '' }}</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.scenario-dashboard {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 18px;
}

/* ===== 顶部概览 ===== */
.sd-hero__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.sd-hero__title-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 8px;
}

.sd-hero__title-row h2 {
  margin: 0;
  font-size: 1.6rem;
}

.sd-hero__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.68);
  font-size: 0.92rem;
  max-width: 600px;
}

.sd-hero__score {
  display: grid;
  place-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.sd-hero__score-value {
  font-size: 3rem;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.sd-score--critical { color: #ff8c84; }
.sd-score--high { color: #ffc37d; }
.sd-score--medium { color: #9ad6ff; }
.sd-score--low { color: #53e5c8; }

.sd-hero__score-label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.55);
}

/* ===== 指标行 ===== */
.sd-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.sd-metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sd-metric__label {
  margin: 0;
  font-size: 0.84rem;
  color: rgba(220, 234, 255, 0.65);
}

.sd-metric__value {
  font-size: 1.6rem;
  font-weight: 700;
  color: #e8f1ff;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.sd-metric__trend {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 500;
}

.sd-trend--up { color: #ff8c84; }
.sd-trend--down { color: #53e5c8; }

/* ===== 图表区域（两列） ===== */
.sd-charts {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 18px;
}

.sd-charts .chart-card {
  min-height: 340px;
}

/* ===== 底部（两列） ===== */
.sd-bottom {
  display: grid;
  grid-template-columns: 1fr 1.4fr;
  gap: 18px;
}

/* 风险事件列表 */
.sd-events {
  display: grid;
  gap: 10px;
}

.sd-events__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.1);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.sd-events__item:hover {
  background: rgba(91, 166, 255, 0.06);
  border-color: rgba(125, 201, 255, 0.2);
}

.sd-events__left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.sd-events__left strong {
  display: block;
  font-size: 0.9rem;
  color: #e8f1ff;
}

.sd-events__left p {
  margin: 4px 0 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.58);
}

.sd-events__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.sd-events__prob {
  font-size: 0.82rem;
  color: #ffc37d;
  font-weight: 500;
}

.sd-events__time {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.5);
}

/* ===== 响应式降级 ===== */
@media (max-width: 1200px) {
  .sd-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .sd-charts,
  .sd-bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .sd-metrics {
    grid-template-columns: 1fr;
  }
  .sd-hero__content {
    flex-direction: column;
    align-items: stretch;
  }
  .sd-hero__score {
    flex-direction: row;
    gap: 12px;
  }
  .sd-events__item {
    flex-direction: column;
    align-items: flex-start;
  }
  .sd-events__right {
    flex-direction: row;
    gap: 12px;
    align-items: center;
  }
}
</style>
