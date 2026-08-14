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
import { getAlertById, getAlerts, getDashboardSnapshot } from './services/mockApi';
import type { AlertRecord, DashboardSnapshot, MetricHistory } from './types/security';
import { useUserStore } from './stores/userStore';

// 页面数据
const dashboard = ref<DashboardSnapshot | null>(null);
const alerts = ref<AlertRecord[]>([]);
const selectedAlert = ref<AlertRecord | null>(null);
const loading = ref(true);
const error = ref('');
const warRoomOpen = ref(false);
const activeMetric = ref<MetricHistory | null>(null);

// ===================== 当前登录用户（与路由守卫同源：Pinia userStore） =====================
// 登录/登出统一走 userStore，避免页面直连 mockApi 导致 Pinia 状态与守卫判断不同步
const userStore = useUserStore();
const currentUser = computed(() => userStore.currentUser);
const isAdmin = computed(() => userStore.isAdmin);

const handleLogout = async () => {
  await userStore.logout();
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
  if (route.path === '/home') return '首页';
  if (route.path === '/risk') return 'AI模型训练与风险研判配置';
  if (route.path === '/alerts') return '告警详情总览';
  if (route.path.startsWith('/alerts/')) return '告警处置分析';
  if (route.path === '/overview') return '全局总览';
  if (route.path === '/scenarios') return '场景中心';
  if (route.path.startsWith('/scenarios/')) return '场景大屏';
  if (route.path === '/datasets') return '数据集中心';
  if (route.path.startsWith('/datasets/')) return '数据集详情';
  if (route.path === '/models') return '模型中心';
  if (route.path === '/inference') return '风险研判';
  if (route.path === '/inference-records') return '推理记录';
  if (route.path === '/reports') return '报告中心';
  if (route.path === '/settings') return isAdmin ? '系统设置' : '设置';
  if (route.path.startsWith('/events/')) return '风险事件详情';
  return '态势感知与威胁可视化平台';
});

// ===================== 路由监听与生命周期 =====================
// 注册路由后置钩子，页面切换时重新加载数据（保存返回的取消注册函数）
const unregisterAfterEach = router.afterEach(() => {
  loadData();
});

onMounted(async () => {
  await loadData();
  // 落地页由路由 '/' 重定向处理（ADMIN → /overview；USER → /home）
  if (route.path === '/') {
    router.push(isAdmin.value ? '/overview' : '/home');
  }
});

onBeforeUnmount(() => {
  // 调用取消注册函数移除监听器，防止内存泄漏
  unregisterAfterEach();
});

// ===================== 路由判断快捷变量（template用） =====================
const isLoginPage = computed(() => route.path === '/login');
const isHomePage = computed(() => route.path === '/home');
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
  return path === '/home' || path === '/overview' || path === '/scenarios' || path.startsWith('/scenarios/') || path === '/datasets' || path.startsWith('/datasets/')
    || path === '/models' || path === '/inference' || path === '/inference-records' || path === '/situation'
    || path === '/reports' || path === '/users' || path === '/settings' || path.startsWith('/events/');
});

// ===================== 顶部导航（Task 005：meta/角色驱动渲染） =====================
// 需求 6.5.2 末段：前端隐藏仅为体验，真正的鉴权在后端。
interface NavItem {
  path: string;
  label: string;
  /** 仅管理员可见/可访问（与路由 meta.requiresAdmin 对应） */
  requiresAdmin?: boolean;
  /** 普通用户隐藏入口（与路由 meta.hiddenForUser 对应） */
  hiddenForUser?: boolean;
  /** 仅普通用户可见入口（与路由 meta.userOnly 对应；管理员隐藏，如 /home） */
  userOnly?: boolean;
  /** 点击动作：复用原导航跳转函数，保持既有行为（如首页重置图表并重载） */
  action?: () => void;
}

const navItems: NavItem[] = [
  { path: '/home', label: '首页', userOnly: true },
  { path: '/overview', label: '全局总览', requiresAdmin: true, hiddenForUser: true, action: goOverview },
  { path: '/scenarios', label: '场景中心', action: goScenarioCenter },
  { path: '/datasets', label: '数据集中心', action: goDatasetCenter },
  { path: '/alerts', label: '告警中心', requiresAdmin: true, hiddenForUser: true, action: goAlertsList },
  { path: '/risk', label: 'AI模型训练', requiresAdmin: true, hiddenForUser: true, action: goAiTrainPage },
  { path: '/models', label: '模型中心', action: goModelCenter },
  { path: '/inference', label: '风险研判', action: goRiskInference },
  { path: '/inference-records', label: '推理记录', action: goInferenceRecords },
  { path: '/reports', label: '报告中心', action: goReportCenter },
  { path: '/settings', label: '设置', action: goSettings },
];

/** 按当前角色过滤可见导航项（管理员全部；普通用户隐藏管理员专属入口） */
const visibleNavItems = computed(() =>
  navItems.filter((item) => {
    if (item.requiresAdmin && !isAdmin.value) return false;
    if (item.hiddenForUser && !isAdmin.value) return false;
    if (item.userOnly && isAdmin.value) return false;
    return true;
  })
);

/** 导航激活态：沿用原 isXxxPage 判断，保持既有高亮逻辑（含告警详情前缀高亮） */
const isNavActive = (item: NavItem): boolean => {
  switch (item.path) {
    case '/home': return isHomePage.value;
    case '/dashboard': return isDashboardPage.value;
    case '/overview': return isOverviewPage.value;
    case '/scenarios': return isScenarioCenterPage.value;
    case '/datasets': return isDatasetCenterPage.value;
    case '/alerts': return isAlertsListPage.value || isAlertDetailPage.value;
    case '/risk': return isRiskPage.value;
    case '/models': return isModelCenterPage.value;
    case '/inference': return isRiskInferencePage.value;
    case '/inference-records': return isInferenceRecordsPage.value;
    case '/situation': return isSituationPage.value;
    case '/reports': return isReportCenterPage.value;
    case '/users': return isUsersPage.value;
    case '/settings': return isSettingsPage.value;
    default: return false;
  }
};

/** 导航点击：优先复用原导航跳转函数（含首页图表重置重载），兜底 router.push */
const handleNavClick = (item: NavItem): void => {
  if (item.action) {
    item.action();
    return;
  }
  router.push(item.path);
};
</script>

<template>
  <router-view v-if="isLoginPage" />
  <div v-else class="app-shell">
    <div class="app-shell__backdrop"></div>
    <header class="topbar">
      <div class="topbar__heading">
        <p class="eyebrow">AI Security Operations Center</p>
        <h1>{{ pageTitle }}</h1>
      </div>
      <div class="topbar__actions">
        <nav class="nav-tabs">
          <button
            v-for="item in visibleNavItems"
            :key="item.path"
            class="nav-tabs__item"
            :class="{ 'is-active': isNavActive(item) }"
            @click="handleNavClick(item)"
          >
            {{ item.path === '/settings' ? (isAdmin ? '系统设置' : '设置') : item.label }}
          </button>
        </nav>
        <div class="topbar__user">
          <span class="topbar__user-avatar">{{ currentUser?.display_name?.charAt(0) }}</span>
          <div class="topbar__user-pop">
            <span class="topbar__user-name">{{ currentUser?.display_name }}</span>
            <span class="topbar__user-role">{{ isAdmin ? '管理员' : '普通用户' }}</span>
            <button class="ghost-button ghost-button--logout" @click="handleLogout">退出登录</button>
          </div>
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

/* 标题区占满首整行（英文 eyebrow + 当前页面标题各一行），导航换到第二行，标题永不被遮挡 */
.topbar__heading {
  flex: 1 1 100%;
  min-width: 0;
}

/* ===================== 用户区：仅头像，悬停弹出姓名/角色/退出 ===================== */
.topbar__user {
  position: relative;
  display: flex;
  align-items: center;
  margin-left: 16px;
  padding-left: 16px;
  border-left: 1px solid rgba(125, 201, 255, 0.15);
}

.topbar__user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  flex-shrink: 0;
  border: 1px solid rgba(125, 201, 255, 0.25);
  transition: box-shadow 0.2s;
}

.topbar__user:hover .topbar__user-avatar {
  box-shadow: 0 0 0 3px rgba(91, 166, 255, 0.18);
}

.topbar__user-pop {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  min-width: 150px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(10, 20, 38, 0.96);
  backdrop-filter: blur(18px);
  box-shadow: 0 14px 44px rgba(0, 0, 0, 0.55);
  opacity: 0;
  visibility: hidden;
  transform: translateY(-6px);
  transition: opacity 0.2s, transform 0.2s, visibility 0.2s;
  z-index: 30;
}

.topbar__user:hover .topbar__user-pop {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
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


