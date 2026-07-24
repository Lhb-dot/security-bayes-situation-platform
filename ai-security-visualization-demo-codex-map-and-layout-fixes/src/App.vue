<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';

// 路由实例
const router = useRouter();
const route = useRoute();

import AlertDetailView from './components/AlertDetailView.vue';
import AlertsView from './components/AlertsView.vue';
import DashboardView from './components/DashboardView.vue';
import MetricTrendModal from './components/MetricTrendModal.vue';
import WarRoomModal from './components/WarRoomModal.vue';
import { getAlertById, getAlerts, getDashboardSnapshot, refreshMockData } from './services/mockApi';
import type { AlertRecord, DashboardSnapshot, MetricHistory } from './types/security';

// 页面数据
const dashboard = ref<DashboardSnapshot | null>(null);
const alerts = ref<AlertRecord[]>([]);
const selectedAlert = ref<AlertRecord | null>(null);
const loading = ref(true);
const error = ref('');
const warRoomOpen = ref(false);
const activeMetric = ref<MetricHistory | null>(null);

// ===================== 路由跳转方法（全部改为标准router.push）=====================
/**
 * 顶部导航：跳转AI模型训练研判页面（无参数，手动训练数据集）
 */
const goAiTrainPage = () => {
  router.push({ path: '/risk' });
};

/**
 * 跳转首页大屏
 */
const goDashboard = () => {
  router.push({ path: '/dashboard' });
  // 切回首页重载图表数据，解决图表残留问题
  dashboard.value = null;
  loadData();
};

/**
 * 跳转告警列表页
 */
const goAlertsList = () => {
  router.push({ path: '/alerts' });
};

/**
 * 跳转单条告警详情
 */
const goAlertDetail = (id: string) => {
  router.push({ path: `/alerts/${id}` });
};

// ===================== 数据加载逻辑 =====================
const loadData = async () => {
  loading.value = true;
  error.value = '';
  try {
    const [snapshot, alertList] = await Promise.all([getDashboardSnapshot(), getAlerts()]);
    dashboard.value = snapshot;
    alerts.value = alertList;

    // 如果当前路由是告警详情，单独拉取详情数据
    if (route.path.startsWith('/alerts/')) {
      const alertId = route.params.id as string;
      selectedAlert.value = await getAlertById(alertId);
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据加载失败';
  } finally {
    loading.value = false;
  }
};

// 刷新Mock模拟数据
const reloadData = async () => {
  refreshMockData();
  await loadData();
};

// 作战大屏打开后跳转告警
const openAlertFromWarRoom = (id: string) => {
  warRoomOpen.value = false;
  goAlertDetail(id);
};

// 指标弹窗打开
const openMetric = (id: string) => {
  activeMetric.value = dashboard.value?.metricHistories.find((item) => item.id === id) ?? null;
};

// ===================== 页面标题计算属性 =====================
const pageTitle = computed(() => {
  if (route.path === '/risk') return 'AI模型训练与风险研判配置';
  if (route.path === '/alerts') return '告警详情总览';
  if (route.path.startsWith('/alerts/')) return '告警处置分析';
  return '态势感知与威胁可视化平台';
});

// ===================== 路由监听与生命周期 =====================
onMounted(async () => {
  await loadData();
  // 监听路由变化，重新加载数据/告警详情
  router.afterEach(() => {
    loadData();
  });
  // 默认进入首页
  if (route.path === '/') {
    goDashboard();
  }
});

onBeforeUnmount(() => {
  // 卸载销毁路由后置钩子，防止内存泄漏
  router.afterEach(() => {});
});

// ===================== 路由判断快捷变量（template用） =====================
const isDashboardPage = computed(() => route.path === '/dashboard');
const isAlertsListPage = computed(() => route.path === '/alerts');
const isAlertDetailPage = computed(() => route.path.startsWith('/alerts/'));
const isRiskPage = computed(() => route.path === '/risk');
</script>

<template>
  <div class="app-shell">
    <div class="app-shell__backdrop"></div>
    <header class="topbar">
      <div>
        <p class="eyebrow">AI Security Operations Center</p>
        <h1>{{ pageTitle }}</h1>
      </div>
      <div class="topbar__actions">
        <nav class="nav-tabs">
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isDashboardPage }"
            @click="goDashboard"
          >
            首页大屏
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isAlertsListPage || isAlertDetailPage }"
            @click="goAlertsList"
          >
            告警详情
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isRiskPage }"
            @click="goAiTrainPage"
          >
            AI模型训练预测
          </button>
        </nav>
        <button class="ghost-button" @click="reloadData">刷新模拟数据</button>
      </div>
    </header>

    <!-- 非AI研判页：渲染首页/告警列表/告警详情 -->
    <main v-if="!isRiskPage && !loading && !error && dashboard" class="page-container">
      <DashboardView
        v-if="isDashboardPage"
        :snapshot="dashboard"
        :alerts="alerts"
        @open-alert="goAlertDetail($event)"
        @open-war-room="warRoomOpen = true"
        @open-metric="openMetric"
      />
      <AlertsView
        v-else-if="isAlertsListPage"
        :alerts="alerts"
        @open-alert="goAlertDetail($event)"
      />
      <AlertDetailView v-else-if="isAlertDetailPage && selectedAlert" :alert="selectedAlert" @back="goAlertsList()" />
    </main>

    <!-- AI风险研判页面 单独路由视图渲染 -->
    <div v-if="isRiskPage" class="risk-page-wrap">
      <router-view />
    </div>

    <!-- 加载、错误状态 -->
    <section v-else-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在生成威胁感知数据与可视化面板...</p>
    </section>
    <section v-else class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadData">重试</button>
    </section>

    <!-- 弹窗组件不受路由影响 -->
    <WarRoomModal
      v-if="warRoomOpen && dashboard"
      :snapshot="dashboard"
      :alerts="alerts"
      @close="warRoomOpen = false"
      @open-alert="openAlertFromWarRoom"
    />
    <MetricTrendModal v-if="activeMetric" :metric="activeMetric" @close="activeMetric = null" />
  </div>
</template>

<style scoped>
.risk-page-wrap {
  padding: 24px;
  min-height: auto;
  box-sizing: border-box;
}
</style>


