<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

// 路由实例
const router = useRouter();
const route = useRoute();

import type { UserRole } from './types/security';
import { useUserStore } from './stores/userStore';

// ===================== 当前登录用户（与路由守卫同源：Pinia userStore） =====================
// 登录/登出统一走 userStore，避免页面直连 mockApi 导致 Pinia 状态与守卫判断不同步
const userStore = useUserStore();
const currentUser = computed(() => userStore.currentUser);
const isSuperAdmin = computed(() => userStore.isSuperAdmin);

/** 当前角色中文名 */
const roleLabel = computed(() => {
  const role = userStore.currentUser?.role;
  if (role === 'SUPER_ADMIN') return '系统管理员';
  if (role === 'SCENARIO_ADMIN') return '管理员';
  return '用户';
});

/** 当前用户场景名（管理员/用户，显示在头像上方；系统管理员不显示） */
const myScenarioName = computed(() => {
  if (isSuperAdmin.value) return '';
  const id = userStore.currentUser?.scenario_code;
  if (!id) return '';
  const map: Record<string, string> = {
    network_security: '网络安全',
    power_system: '电力系统',
    geological_risk: '地质风险',
    flightdeck_operation: '航母甲板',
  };
  return map[id] ?? id;
});

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
 * 跳转场景中心：系统管理员 → 场景中心列表；管理员/用户 → 自己场景详情页
 */
const goScenarioCenter = () => {
  if (isSuperAdmin.value) {
    router.push({ path: '/scenarios' });
    return;
  }
  const bound = userStore.currentUser?.scenario_code;
  router.push(bound ? { path: `/scenarios/${bound}/dashboard` } : { path: '/scenarios' });
};

/**
 * 跳转用户管理（系统管理员管管理员/用户；管理员管自己用户）
 */
const goUsers = () => {
  router.push({ path: '/users' });
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

const goAlertsList = () => {
  router.push({ path: '/alerts' });
};

// ===================== 页面标题计算属性 =====================
const pageTitle = computed(() => {
  if (route.path === '/login') return '用户登录';
  if (route.path === '/home') return '首页';
  if (route.path === '/risk') return 'AI模型训练与风险研判配置';
  if (route.path === '/alerts') return '风险事件列表';
  if (route.path === '/overview') return '首页';
  if (route.path === '/scenarios') return '场景中心';
  if (route.path.startsWith('/scenarios/')) return isSuperAdmin.value ? '场景大屏' : '首页';
  if (route.path === '/datasets') return '数据集中心';
  if (route.path.startsWith('/datasets/')) return '数据集详情';
  if (route.path === '/models') return '模型中心';
  if (route.path === '/inference') return '风险研判';
  if (route.path === '/inference-records') return '推理记录';
  if (route.path === '/reports') return '报告中心';
  if (route.path === '/settings') return isSuperAdmin.value ? '系统设置' : '设置';
  if (route.path.startsWith('/events/')) return '风险事件详情';
  return '态势感知与威胁可视化平台';
});

onMounted(async () => {
  // 落地页由路由 '/' 重定向处理（SUPER_ADMIN → /overview；管理员/用户 → 自己场景）
  if (route.path === '/') {
    if (isSuperAdmin.value) router.push('/overview');
    else if (userStore.currentUser?.scenario_code) {
      router.push(`/scenarios/${userStore.currentUser.scenario_code}/dashboard`);
    } else router.push('/home');
  }
});

// ===================== 路由判断快捷变量（template用） =====================
const isLoginPage = computed(() => route.path === '/login');
const isHomePage = computed(() => route.path === '/home');
const isAlertsListPage = computed(() => route.path === '/alerts');
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
    || path === '/reports' || path === '/users' || path === '/settings' || path === '/alerts' || path.startsWith('/events/');
});

// ===================== 顶部导航（三级角色驱动渲染） =====================
// 需求 6.5.2 末段：前端隐藏仅为体验，真正的鉴权在后端。
interface NavItem {
  path: string;
  label: string;
  /** 允许访问的角色列表（缺省=所有角色） */
  roles?: UserRole[];
  /** 点击动作：复用原导航跳转函数，保持既有行为 */
  action?: () => void;
}

const ALL_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER'];
const MGMT_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN'];

const navItems: NavItem[] = [
  // 普通用户/管理员的"首页"就是场景大屏（/scenarios/{场景}/dashboard），不再单独显示 /home 入口
  { path: '/overview', label: '首页', roles: ['SUPER_ADMIN'], action: goOverview },
  { path: '/scenarios', label: '场景中心', roles: ALL_ROLES, action: goScenarioCenter },
  { path: '/datasets', label: '数据集中心', roles: ALL_ROLES, action: goDatasetCenter },
  { path: '/alerts', label: '告警中心', roles: ALL_ROLES, action: goAlertsList },
  { path: '/risk', label: 'AI模型训练', roles: MGMT_ROLES, action: goAiTrainPage },
  { path: '/models', label: '模型中心', roles: ALL_ROLES, action: goModelCenter },
  { path: '/inference', label: '风险研判', roles: ALL_ROLES, action: goRiskInference },
  { path: '/inference-records', label: '推理记录', roles: ALL_ROLES, action: goInferenceRecords },
  { path: '/reports', label: '报告中心', roles: ALL_ROLES, action: goReportCenter },
  { path: '/users', label: '用户管理', roles: MGMT_ROLES, action: goUsers },
  { path: '/settings', label: '设置', roles: ALL_ROLES, action: goSettings },
];

/** 按当前角色过滤可见导航项 */
const visibleNavItems = computed(() => {
  const role = userStore.currentUser?.role;
  return navItems.filter((item) => !item.roles || (role ? item.roles.includes(role) : false));
});

/** 导航激活态：沿用原 isXxxPage 判断，保持既有高亮逻辑（含告警详情前缀高亮） */
const isNavActive = (item: NavItem): boolean => {
  switch (item.path) {
    case '/home': return isHomePage.value;
    case '/overview': return isOverviewPage.value;
    case '/scenarios':
      // 系统管理员：场景中心列表高亮；管理员/用户：自己场景大屏（首页）高亮
      if (isSuperAdmin.value) return isScenarioCenterPage.value;
      return route.path.startsWith('/scenarios/') || isScenarioCenterPage.value;
    case '/datasets': return isDatasetCenterPage.value;
    case '/alerts': return isAlertsListPage.value;
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
        <div class="topbar__heading-left">
          <p class="eyebrow">AI Security Operations Center</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <!-- 当前场景（管理员/用户）：与标题同字号，放标题行最右 -->
        <span v-if="myScenarioName" class="topbar__heading-scenario">{{ myScenarioName }}</span>
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
            {{ item.path === '/settings' ? (isSuperAdmin ? '系统设置' : '设置') : (item.path === '/scenarios' ? (isSuperAdmin ? '场景中心' : '首页') : item.label) }}
          </button>
        </nav>
        <div class="topbar__user">
          <span class="topbar__user-avatar">{{ currentUser?.display_name?.charAt(0) }}</span>
          <div class="topbar__user-pop">
            <span class="topbar__user-name">{{ currentUser?.display_name }}</span>
            <span class="topbar__user-role">{{ roleLabel }}</span>
            <button class="ghost-button ghost-button--logout" @click="handleLogout">退出登录</button>
          </div>
        </div>
      </div>
    </header>

    <!-- AI风险研判页面 单独路由视图渲染 -->
    <div v-if="isRiskPage" class="risk-page-wrap">
      <router-view />
    </div>

    <!-- 多场景新页面 路由视图渲染 -->
    <div v-else-if="isNewRoutePage" class="new-page-wrap">
      <router-view />
    </div>

  </div>
</template>

<style scoped>
.risk-page-wrap,
.new-page-wrap {
  padding: 20px 16px; /* 缩小页面内边距，让数据集/模型等表格更宽 */
  min-height: auto;
  box-sizing: border-box;
}

/* 标题区占满首整行（英文 eyebrow + 当前页面标题各一行），导航换到第二行，标题永不被遮挡。
   左侧标题 + 右侧当前场景（管理员/用户）同字号大字，flex 两端对齐 */
.topbar__heading {
  flex: 1 1 100%;
  min-width: 0;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.topbar__heading-left {
  min-width: 0;
}

/* 当前场景大字（与页面标题同字号 clamp，标题行最右） */
.topbar__heading-scenario {
  flex-shrink: 0;
  color: #9ad6ff;
  font-size: clamp(1.6rem, 2vw, 2.6rem);
  font-weight: 600;
  white-space: nowrap;
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


