<script setup lang="ts">
import type { AlertRecord, DashboardSnapshot } from '../../types/security';
import DonutChart from '../../components/DonutChart.vue';
import LineTrendChart from '../../components/LineTrendChart.vue';
import RankingList from '../../components/RankingList.vue';
import ThreatMap from '../../components/ThreatMap.vue';
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { getBayesStatData } from '@/api/modelApi';

const router = useRouter();

defineProps<{
  snapshot: DashboardSnapshot;
  alerts: AlertRecord[];
}>();

defineEmits<{
  openAlert: [id: string];
  openWarRoom: [];
  openMetric: [id: string];
}>();

const metricIcons = ['TH', 'HI', 'AI', 'RT'];

/**
 * 告警条目携带流量特征跳转到AI研判页，自动回填参数做风险推理
 */
const jumpBayesPage = (e: MouseEvent, alertItem: AlertRecord) => {
  e.stopPropagation();
  e.preventDefault();
  router.push({
    path: '/risk',
    query: {
      fl: alertItem.flowLength,
      du: alertItem.duration,
      af: alertItem.accessFreq,
    },
  });
};

const bayesSnapshot = ref<Partial<DashboardSnapshot>>({});

onMounted(async () => {
  try {
    const res = await getBayesStatData();
    bayesSnapshot.value = {
      attackTrend: res.data.trend_data,
      attackTypes: res.data.attack_type,
      sourceMap: res.data.map_points,
      topSourceIps: res.data.top_ip_rank,
      model_metric: res.data.model_metric,
    };
  } catch (err) {
    console.error('获取贝叶斯态势数据失败，使用默认模拟数据', err);
  }
});
</script>

<template>
  <div class="dashboard-grid">
    <section class="hero-panel card">
      <div class="hero-panel__content">
        <div>
          <p class="eyebrow">Transformer Threat Insight Engine</p>
          <h2>面向攻防研判的态势感知中枢</h2>
          <p class="hero-panel__desc">
            聚合网络日志、行为链路与 AI 推理结果，形成清晰、动态、可接后端扩展的威胁监测视图。
          </p>
          <div class="hero-panel__actions">
            <button class="hero-button" @click="$emit('openWarRoom')">进入作战大屏</button>
            <span class="hero-chip">地图支持中国 / 世界切换</span>
          </div>
        </div>
        <div class="hero-panel__pulse">
          <div class="pulse-ring"></div>
          <div class="pulse-ring pulse-ring--delay"></div>
          <div class="pulse-core"></div>
        </div>
      </div>
    </section>

    <section class="metrics-row">
      <button
        v-for="(metric, index) in snapshot.metrics"
        :key="metric.label"
        class="metric-card card metric-card--button"
        @click="$emit('openMetric', metric.id)"
      >
        <div class="metric-card__icon">{{ metricIcons[index] }}</div>
        <div>
          <p class="metric-card__label">{{ metric.label }}</p>
          <h3>{{ metric.value }}</h3>
          <p class="metric-card__delta" :class="{ danger: metric.trend < 0, safe: metric.trend > 0 }">
            {{ metric.trend > 0 ? '+' : '' }}{{ metric.trend }}% 较昨日
          </p>
          <span class="metric-card__hint">点击查看近 30 天趋势</span>
        </div>
      </button>
    </section>

    <section class="card chart-card chart-card--wide">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Trend</p>
          <h3>攻击趋势折线图</h3>
        </div>
        <span class="section-tag">24h</span>
      </div>
      <LineTrendChart :points="bayesSnapshot.attackTrend ?? snapshot.attackTrend" />
    </section>

    <!-- 右侧图表统一父容器，实现上下均分 -->
    <div class="right-chart-group">
      <section class="card chart-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Types</p>
            <h3>攻击类型分布图</h3>
          </div>
        </div>
        <DonutChart :items="bayesSnapshot.attackTypes ?? snapshot.attackTypes" />
      </section>

      <section class="card chart-card">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Map</p>
            <h3>攻击源分布图</h3>
          </div>
          <span class="section-tag">导弹轨迹动画</span>
        </div>
        <ThreatMap :maps="bayesSnapshot.sourceMap ?? snapshot.sourceMap" />
      </section>
    </div>

    <section class="card dashboard-span-4">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Top Sources</p>
          <h3>Top 攻击源 IP</h3>
        </div>
      </div>
      <RankingList :items="bayesSnapshot.topSourceIps ?? snapshot.topSourceIps" accent="danger" />
    </section>

    <section class="card dashboard-span-4">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Top Targets</p>
          <h3>Top 受攻击主机</h3>
        </div>
      </div>
      <RankingList :items="snapshot.topTargetHosts" accent="safe" />
    </section>

    <section class="card dashboard-span-4">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Protocol</p>
          <h3>攻击协议分布</h3>
        </div>
      </div>
      <DonutChart :items="snapshot.protocolDistribution" />
    </section>

    <section class="card dashboard-span-4">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Response</p>
          <h3>防护联动效率</h3>
        </div>
      </div>
      <RankingList :items="snapshot.responseActions" accent="safe" />
    </section>

    <section class="card alert-feed">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Realtime</p>
          <h3>实时告警流</h3>
        </div>
      </div>
      <div class="alert-feed__list">
        <div v-for="alert in alerts.slice(0, 6)" :key="alert.id" class="alert-row-item">
          <div>
            <strong>{{ alert.title }}</strong>
            <p>{{ alert.sourceIp }} -> {{ alert.targetHost }}</p>
          </div>
          <div class="alert-feed__meta">
            <span :class="['risk-badge', `risk-${alert.riskLevel}`]">{{ alert.riskLevel }}</span>
            <time>{{ alert.timestamp }}</time>
          </div>
          <!-- 新增AI研判跳转按钮，@click.stop阻止上层弹窗事件冲突 -->
          <button class="jump-ai-btn" @click.prevent.stop="jumpBayesPage($event, alert)">AI风险溯源研判</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* 全局网格布局，加宽右侧栏（新增） */
.dashboard-grid {
  display: grid;
  grid-template-columns: 1.6fr 1.4fr;
  grid-auto-rows: auto;
  gap: 20px;
  width: 100%;
}

/* 右侧图表分组父容器 */
.right-chart-group {
  grid-row: span 3;
  display: flex;
  flex-direction: column;
  gap: 24px;
  height: 100%;
  width: 100%;
}
/* 组内两个卡片自动平分全部高度，各占50% */
.right-chart-group .chart-card {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px 12px;
  box-sizing: border-box;
}
/* 图表组件自适应剩余高度，减去标题区域 */
.right-chart-group .chart-card > *:last-child {
  flex: 1;
  min-height: 0;
}

.alert-row-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 8px;
  margin-bottom: 12px;
  background: rgba(13, 133, 231, 0.05);
  border-radius: 6px;
}
.alert-feed__meta {
  display: flex;
  gap: 16px;
  align-items: center;
}

.jump-ai-btn {
  width: fit-content;
  background: #407acc !important;
  color: #fff !important;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  margin-top: 8px;
  cursor: pointer;
  opacity: 1 !important;
  transition: background 0.2s;
}
/* 鼠标悬浮变亮，区分可点击状态 */
.jump-ai-btn:hover {
  background: #5494e8 !important;
}
</style>
