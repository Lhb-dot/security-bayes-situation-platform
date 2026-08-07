<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter, useRoute } from 'vue-router';

// 路由实例
const router = useRouter();
const route = useRoute();

import AlertDetailView from './views/Alert/AlertDetailView.vue';
import AlertsView from './views/Alert/AlertsView.vue';
import DashboardView from './views/Dashboard/DashboardView.vue';
import MetricTrendModal from './components/MetricTrendModal.vue';
import WarRoomModal from './components/WarRoomModal.vue';
import { getAlertById, getAlerts, getDashboardSnapshot, refreshMockData, getCurrentUser, logout } from './api/index';
import type { AlertRecord, DashboardSnapshot, MetricHistory, UserAccount } from './types/security';

// 页面数据
const dashboard = ref<DashboardSnapshot | null>(null);
const alerts = ref<AlertRecord[]>([]);
const selectedAlert = ref<AlertRecord | null>(null);
const loading = ref(true);
const error = ref('');
const warRoomOpen = ref(false);
const activeMetric = ref<MetricHistory | null>(null);

// ===================== v2.0 当前登录用户 =====================
const currentUser = ref<UserAccount | null>(getCurrentUser());
const isAdmin = computed(() => currentUser.value?.role === 'ADMIN');

const handleLogout = async () => {
  await logout();
  currentUser.value = null;
  router.push('/login');
};

// ===================== 路由跳转方法（全部改为标准router.push）=====================
/**
 * 顶部导航：跳转AI模型训练研判页面（无参数，手动训练数据集）
 */
const goAiTrainPage = () => {
  router.push({ path: '/risk' });
};

/**
 * 跳转全局总览
 */
const goOverview = () => {
  router.push({ path: '/overview' });
};

/**
 * 跳转场景中心
 */
const goScenarioCenter = () => {
  router.push({ path: '/scenarios' });
};

/**
 * 跳转数据集中心
 */
const goDatasetCenter = () => {
  router.push({ path: '/datasets' });
};

/**
 * 跳转模型中心
 */
const goModelCenter = () => {
  router.push({ path: '/models' });
};

/**
 * 跳转风险研判
 */
const goRiskInference = () => {
  router.push({ path: '/inference' });
};

/**
 * 跳转态势分析
 */
const goSituation = () => {
  router.push({ path: '/situation' });
};

/**
 * 跳转报告中心
 */
const goReportCenter = () => {
  router.push({ path: '/reports' });
};

/**
 * 跳转系统设置
 */
const goSettings = () => {
  router.push({ path: '/settings' });
};

/**
 * 跳转推理记录
 */
const goInferenceRecords = () => {
  router.push({ path: '/inference-records' });
};

/**
 * 跳转用户管理
 */
const goUsers = () => {
  router.push({ path: '/users' });
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
  if (route.path === '/login') return '用户登录';
  if (route.path === '/risk') return 'AI模型训练与风险研判配置';
  if (route.path === '/alerts') return '告警详情总览';
  if (route.path.startsWith('/alerts/')) return '告警处置分析';
  if (route.path === '/overview') return '全局总览';
  if (route.path === '/scenarios') return '场景中心';
  if (route.path.startsWith('/scenarios/')) return '场景大屏';
  if (route.path === '/datasets') return '数据集中心';
  if (route.path === '/models') return '模型中心';
  if (route.path === '/inference') return '风险研判';
  if (route.path === '/inference-records') return '推理记录';
  if (route.path === '/situation') return '态势分析';
  if (route.path === '/reports') return '报告中心';
  if (route.path === '/users') return '用户管理';
  if (route.path === '/settings') return '系统设置';
  return '态势感知与威胁可视化平台';
});

// ===================== 路由监听与生命周期 =====================
// 注册路由后置钩子，页面切换时重新加载数据（保存返回的取消注册函数）
const unregisterAfterEach = router.afterEach(() => {
  loadData();
});

onMounted(async () => {
  await loadData();
  // 默认进入首页
  if (route.path === '/') {
    goDashboard();
  }
});

onBeforeUnmount(() => {
  // 调用取消注册函数移除监听器，防止内存泄漏
  unregisterAfterEach();
});

// ===================== 路由判断快捷变量（template用） =====================
const isLoginPage = computed(() => route.path === '/login');
const isDashboardPage = computed(() => route.path === '/dashboard');
const isAlertsListPage = computed(() => route.path === '/alerts');
const isAlertDetailPage = computed(() => route.path.startsWith('/alerts/'));
const isRiskPage = computed(() => route.path === '/risk');
const isOverviewPage = computed(() => route.path === '/overview');
const isScenarioCenterPage = computed(() => route.path === '/scenarios');
const isDatasetCenterPage = computed(() => route.path === '/datasets');
const isModelCenterPage = computed(() => route.path === '/models');
const isRiskInferencePage = computed(() => route.path === '/inference');
const isInferenceRecordsPage = computed(() => route.path === '/inference-records');
const isSituationPage = computed(() => route.path === '/situation');
const isReportCenterPage = computed(() => route.path === '/reports');
const isUsersPage = computed(() => route.path === '/users');
const isSettingsPage = computed(() => route.path === '/settings');
const isNewRoutePage = computed(() => {
  const path = route.path;
  return path === '/overview' || path === '/scenarios' || path.startsWith('/scenarios/') || path === '/datasets'
    || path === '/models' || path === '/inference' || path === '/inference-records' || path === '/situation'
    || path === '/reports' || path === '/users' || path === '/settings';
});
</script>

<template>
  <router-view v-if="isLoginPage" />
  <div v-else class="app-shell">
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
            首页
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isOverviewPage }"
            @click="goOverview"
          >
            全局总览
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isScenarioCenterPage }"
            @click="goScenarioCenter"
          >
            场景中心
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isDatasetCenterPage }"
            @click="goDatasetCenter"
          >
            数据集中心
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isAlertsListPage || isAlertDetailPage }"
            @click="goAlertsList"
          >
            告警中心
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isRiskPage }"
            @click="goAiTrainPage"
          >
            AI模型训练
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isModelCenterPage }"
            @click="goModelCenter"
          >
            模型中心
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isRiskInferencePage }"
            @click="goRiskInference"
          >
            风险研判
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isInferenceRecordsPage }"
            @click="goInferenceRecords"
          >
            推理记录
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isSituationPage }"
            @click="goSituation"
          >
            态势分析
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isReportCenterPage }"
            @click="goReportCenter"
          >
            报告中心
          </button>
          <button
            v-if="isAdmin"
            class="nav-tabs__item"
            :class="{ 'is-active': isUsersPage }"
            @click="goUsers"
          >
            用户管理
          </button>
          <button
            class="nav-tabs__item"
            :class="{ 'is-active': isSettingsPage }"
            @click="goSettings"
          >
            系统设置
          </button>
        </nav>
        <button class="ghost-button" @click="reloadData">刷新模拟数据</button>
        <div class="topbar__user">
          <span class="topbar__user-avatar">{{ currentUser?.display_name?.charAt(0) }}</span>
          <div class="topbar__user-info">
            <span class="topbar__user-name">{{ currentUser?.display_name }}</span>
            <span class="topbar__user-role">{{ isAdmin ? '管理员' : '普通用户' }}</span>
          </div>
          <button class="ghost-button ghost-button--logout" @click="handleLogout">退出登录</button>
        </div>
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

    <!-- 多场景新页面 路由视图渲染 -->
    <div v-else-if="isNewRoutePage" class="new-page-wrap">
      <router-view />
    </div>

    <!-- 加载、错误状态 -->
    <section v-else-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在生成威胁感知数据与可视化面板...</p>
    </section>
    <section v-else-if="error" class="state-card state-card--error">
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
.risk-page-wrap,
.new-page-wrap {
  padding: 24px;
  min-height: auto;
  box-sizing: border-box;
}

.topbar__user {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: 16px;
  padding-left: 16px;
  border-left: 1px solid rgba(125, 201, 255, 0.15);
}

.topbar__user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.9rem;
  font-weight: 600;
  flex-shrink: 0;
}

.topbar__user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.topbar__user-name {
  color: #eaf3ff;
  font-size: 0.88rem;
  font-weight: 600;
}

.topbar__user-role {
  color: rgba(154, 214, 255, 0.65);
  font-size: 0.72rem;
}

.ghost-button--logout {
  color: #ff7b72;
  border-color: rgba(255, 123, 114, 0.3);
}
</style>


