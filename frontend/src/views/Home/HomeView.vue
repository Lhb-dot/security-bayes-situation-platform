<script setup lang="ts">
/**
 * HomeView.vue — 首页（全局态势），普通用户登录落地页（Task 007）
 *
 * 数据链路：HomeView → situationStore.fetchGlobalOverview() → mockApi.getGlobalOverview()
 * （mock 层已按当前用户数据范围聚合）。ADMIN 由路由 userOnly 守卫拦截（重定向 /scenarios）。
 * 视觉上区别于 OverviewView：大号数字卡 + 驾驶舱式双列图表 + 场景快捷入口。
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSituationStore } from '@/stores/situationStore';
import { useUserStore } from '@/stores/userStore';
import type { Scenario, TypeDistribution } from '@/types/security';
import PieChart from '@/components/charts/PieChart.vue';
import BarChart from '@/components/charts/BarChart.vue';
import LineChart from '@/components/charts/LineChart.vue';
import RiskLevelTag from '@/components/common/RiskLevelTag.vue';

const router = useRouter();
const situationStore = useSituationStore();
const userStore = useUserStore();

const loading = ref(true);
const error = ref('');

const overview = computed(() => situationStore.overview);

/** 仅接入（active）场景，用于分布/排行/快捷卡 */
const activeScenarios = computed<Scenario[]>(() =>
  overview.value?.scenarios.filter((s) => s.status === 'active') ?? []
);

/** 风险等级 → 指标卡色调（critical/high 归为 danger） */
const riskTone = (level: Scenario['risk_level'] | undefined): string => {
  if (level === 'critical' || level === 'high') return 'danger';
  if (level === 'medium') return 'warning';
  return 'success';
};

interface MetricCardInfo {
  label: string;
  value: number;
  unit: string;
  tone: 'primary' | 'danger' | 'warning' | 'success';
}

/** 四个大号指标卡（需求 7.0 全局驾驶舱数字卡） */
const metricCards = computed<MetricCardInfo[]>(() => {
  const data = overview.value;
  return [
    { label: '全局风险分', value: data?.global_risk_score ?? 0, unit: '分', tone: riskTone(data?.global_risk_level) as MetricCardInfo['tone'] },
    { label: '高风险事件', value: data?.high_risk_count ?? 0, unit: '条', tone: 'danger' },
    { label: '运行模型', value: data?.active_model_count ?? 0, unit: '个', tone: 'primary' },
    { label: '接入场景', value: data?.scenario_count ?? 0, unit: '个', tone: 'success' },
  ];
});

/** 各场景风险等级分布（risk_level 为小写；critical 归并高危），空数据返回 [] */
const riskDistribution = computed<TypeDistribution[]>(() => {
  const counts: Record<string, number> = { 高危: 0, 中危: 0, 低危: 0 };
  for (const s of activeScenarios.value) {
    if (s.risk_level === 'critical' || s.risk_level === 'high') counts['高危'] += 1;
    else if (s.risk_level === 'medium') counts['中危'] += 1;
    else counts['低危'] += 1;
  }
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  if (total === 0) return [];
  return [
    { label: '高危', value: counts['高危'], color: '#ff7b72' },
    { label: '中危', value: counts['中危'], color: '#ffd166' },
    { label: '低危', value: counts['低危'], color: '#9ad6ff' },
  ];
});

/** 场景健康度排行（按 risk_score 降序） */
const healthRanking = computed(() =>
  [...activeScenarios.value]
    .sort((a, b) => b.risk_score - a.risk_score)
    .map((s) => ({ name: s.name, score: s.risk_score }))
);

/** 近期告警趋势是否可渲染 */
const hasTrend = computed(() => (overview.value?.global_trend.length ?? 0) > 0);

const goScenarioDashboard = (scenarioId: Scenario['scenario_id']) => {
  router.push({ path: `/scenarios/${scenarioId}/dashboard` });
};

const loadData = async () => {
  loading.value = true;
  error.value = '';
  try {
    await situationStore.fetchGlobalOverview();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '首页数据加载失败';
  } finally {
    loading.value = false;
  }
};

onMounted(loadData);
</script>

<template>
  <div class="home-view">
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

    <!-- 空状态：overview 为 null -->
    <section v-else-if="!overview" class="state-card">
      <p>暂无全局态势数据</p>
    </section>

    <template v-else>
      <!-- ==================== 顶部欢迎区 ==================== -->
      <section class="card home-welcome">
        <div>
          <p class="eyebrow">Home · Global Situation</p>
          <h2>欢迎回来，{{ userStore.currentUser?.display_name || '用户' }}</h2>
          <p class="home-welcome__sub">
            {{ userStore.currentUser?.role === 'ADMIN' ? '管理员' : '普通用户' }}
            · 以下是您数据范围内的全局态势概览
          </p>
        </div>
        <span class="home-welcome__badge">全局驾驶舱</span>
      </section>

      <!-- ==================== 大号数字指标卡 ==================== -->
      <section class="home-metrics">
        <div
          v-for="card in metricCards"
          :key="card.label"
          class="home-metric"
          :class="`home-metric--${card.tone}`"
        >
          <span class="home-metric__value">
            {{ card.value }}<em v-if="card.unit">{{ card.unit }}</em>
          </span>
          <span class="home-metric__label">{{ card.label }}</span>
        </div>
      </section>

      <!-- ==================== 图表区域 ==================== -->
      <div class="home-charts">
        <div class="home-charts__col">
          <section class="card home-chart-card">
            <h3 class="home-chart-card__title">各场景风险等级分布</h3>
            <PieChart v-if="riskDistribution.length" :items="riskDistribution" donut height="260px" />
            <p v-else class="home-empty">暂无分布数据</p>
          </section>
          <section class="card home-chart-card">
            <h3 class="home-chart-card__title">场景健康度排行</h3>
            <BarChart v-if="healthRanking.length" :data="healthRanking" horizontal height="260px" />
            <p v-else class="home-empty">暂无排行数据</p>
          </section>
        </div>
        <section class="card home-chart-card home-chart-card--trend">
          <h3 class="home-chart-card__title">近期告警趋势</h3>
          <LineChart v-if="hasTrend" :points="overview.global_trend" area height="300px" />
          <p v-else class="home-empty">暂无趋势数据</p>
        </section>
      </div>

      <!-- ==================== 场景快捷入口 ==================== -->
      <section class="card home-scenarios">
        <h3 class="home-chart-card__title">业务场景快捷入口</h3>
        <div v-if="activeScenarios.length" class="home-scenarios__grid">
          <button
            v-for="scenario in activeScenarios"
            :key="scenario.scenario_id"
            class="home-scenario-card"
            @click="goScenarioDashboard(scenario.scenario_id)"
          >
            <div class="home-scenario-card__head">
              <strong>{{ scenario.name }}</strong>
              <RiskLevelTag :level="scenario.risk_level" size="small" />
            </div>
            <p class="home-scenario-card__desc">{{ scenario.description }}</p>
            <div class="home-scenario-card__meta">
              <span>风险分 {{ scenario.risk_score }}</span>
              <span>事件 {{ scenario.event_count }} 条</span>
            </div>
          </button>
        </div>
        <p v-else class="home-empty">暂无已接入场景</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.home-view {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 20px;
}

/* ===== 顶部欢迎区 ===== */
.home-welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
}

.home-welcome h2 {
  margin: 8px 0 6px;
  font-size: 1.5rem;
}

.home-welcome__sub {
  margin: 0;
  color: rgba(220, 234, 255, 0.65);
  font-size: 0.9rem;
}

.home-welcome__badge {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(83, 229, 200, 0.35);
  background: rgba(83, 229, 200, 0.1);
  color: #53e5c8;
  font-size: 0.8rem;
  letter-spacing: 1px;
}

/* ===== 大号数字指标卡 ===== */
.home-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.home-metric {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 22px 24px;
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.85), rgba(8, 17, 31, 0.9));
}

.home-metric::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}

.home-metric--primary::before { background: #5ba6ff; }
.home-metric--danger::before { background: #ff7b72; }
.home-metric--warning::before { background: #ffd166; }
.home-metric--success::before { background: #53e5c8; }

.home-metric--primary .home-metric__value { color: #7dc9ff; }
.home-metric--danger .home-metric__value { color: #ff8c84; }
.home-metric--warning .home-metric__value { color: #ffd166; }
.home-metric--success .home-metric__value { color: #53e5c8; }

.home-metric__value {
  font-size: 2.3rem;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.home-metric__value em {
  font-style: normal;
  font-size: 0.95rem;
  font-weight: 600;
  margin-left: 4px;
  opacity: 0.75;
}

.home-metric__label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}

/* ===== 图表区域 ===== */
.home-charts {
  display: grid;
  grid-template-columns: 1fr 1.35fr;
  gap: 18px;
}

.home-charts__col {
  display: grid;
  gap: 18px;
}

.home-chart-card {
  min-height: 320px;
  padding: 18px;
}

.home-chart-card--trend {
  min-height: 100%;
}

.home-chart-card__title {
  margin: 0 0 14px;
  font-size: 0.98rem;
  color: #e8f1ff;
}

/* ===== 场景快捷入口 ===== */
.home-scenarios {
  padding: 18px;
}

.home-scenarios__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.home-scenario-card {
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: rgba(255, 255, 255, 0.03);
  color: #eaf3ff;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;
}

.home-scenario-card:hover {
  background: rgba(91, 166, 255, 0.07);
  border-color: rgba(125, 201, 255, 0.28);
  transform: translateY(-2px);
}

.home-scenario-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.home-scenario-card__head strong {
  font-size: 0.98rem;
}

.home-scenario-card__desc {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.6);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.home-scenario-card__meta {
  display: flex;
  gap: 12px;
  font-size: 0.78rem;
  color: rgba(154, 214, 255, 0.72);
}

.home-empty {
  margin: 0;
  padding: 42px 0;
  text-align: center;
  color: rgba(220, 234, 255, 0.45);
  font-size: 0.88rem;
}

/* ===== 响应式降级 ===== */
@media (max-width: 1100px) {
  .home-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .home-charts {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .home-metrics {
    grid-template-columns: 1fr;
  }
  .home-welcome {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
