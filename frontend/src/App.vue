<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import type { UserRole } from './types/security';
import { useUserStore } from './stores/userStore';
import { useReportJobStore } from './stores/reportJobStore';
import { useTrainingJobStore } from './stores/trainingJobStore';
import { useBatchJobStore } from './stores/batchJobStore';
import { onSeenIdsChange } from './utils/jobSeen';

// 路由实例
const router = useRouter();
const route = useRoute();

// ===================== 当前登录用户（与路由守卫同源：Pinia userStore） =====================
// 登录/登出统一走 userStore，避免页面复制认证状态
const userStore = useUserStore();
const currentUser = computed(() => userStore.currentUser);
const isSuperAdmin = computed(() => userStore.isSuperAdmin);

// ===================== 恢复后台任务（报告 / 训练 / 批量研判） =====================
// 这三类任务在前端都是「进程内」状态，刷新就没了（详见各自的 store）。
// 会话恢复或登录成功时各拉一次本账号的任务列表，把还在跑的接回来继续轮询 ——
// 这样任务完成时不论用户停在哪个页面都能弹通知，刷新过也不会丢。
// 放在 App 层而不是各自的页面：离开那个页面同样应该收到完成通知。
//
// 登出时也要清（下面 else 分支）：store 是全局单例，不清的话上一个账号的任务会留在
// 数组里，下一个账号登录后被当成「本账号未读」挂进顶栏铃铛面板。resumePending 自己
// 也会先 reset 一次，这里只是让「登出后到下次登录前」这段空窗也是干净的。
const reportJobStore = useReportJobStore();
const trainingJobStore = useTrainingJobStore();
const batchJobStore = useBatchJobStore();
watch(
  () => userStore.currentUser,
  (user) => {
    if (!user) {
      reportJobStore.reset();
      trainingJobStore.reset();
      batchJobStore.reset();
      return;
    }
    void reportJobStore.resumePending();
    void trainingJobStore.resumePending();
    void batchJobStore.resumePending();
  },
  { immediate: true },
);

// ===================== 顶栏任务铃铛 =====================
// 三类后台任务（报告 / 训练 / 批量研判）的状态都在各自的 store 里，这里只做汇总展示，
// 不另存一份状态。四种形态：空闲（整块不渲染）→ 有在途（铃铛点亮）→ 有完成未查看
// （叠数字徽章）→ 两者都有。「已完成未查看」用 id 集合差判定，见 utils/jobSeen。
type BellTaskKind = 'generate' | 'export' | 'training' | 'batch';

interface BellTask {
  /** 全局唯一键（同时用来回推是哪一类任务） */
  key: string;
  kind: BellTaskKind;
  title: string;
  running: boolean;
  failed: boolean;
  /** 属于「已完成未查看」：行首亮点 + 计入徽章 */
  unread: boolean;
  /** 已用秒数（在途任务有效） */
  elapsed: number;
  /** 进度补充，如 12/50 */
  progress: string;
  /** 点击跳转的路由 */
  to: string;
  /** 排序用 */
  startedAt: number;
}

const KIND_LABEL: Record<BellTaskKind, string> = {
  generate: '报告生成',
  export: '报告导出',
  training: '模型训练',
  batch: '批量研判',
};

/** 已完成未查看的全局键集合（徽章数字 + 行首亮点） */
const unseenKeys = computed(
  () =>
    new Set<string>([
      ...reportJobStore.unseenJobs.map((job) => `report:${job.jobId}`),
      ...trainingJobStore.unseenJobs.map((job) => `training:${job.modelVersionId}`),
      ...batchJobStore.unseenJobs.map((job) => `batch:${job.jobId}`),
    ]),
);

const runningTasks = computed<BellTask[]>(() => {
  const rows: BellTask[] = [
    ...reportJobStore.runningJobs.map((job): BellTask => ({
      key: `report:${job.jobId}`,
      kind: job.kind,
      title: job.title,
      running: true,
      failed: false,
      unread: false,
      elapsed: job.elapsed,
      progress: '',
      to: '/reports',
      startedAt: job.startedAt,
    })),
    ...trainingJobStore.runningJobs.map((job): BellTask => ({
      key: `training:${job.modelVersionId}`,
      kind: 'training',
      title: job.title,
      running: true,
      failed: false,
      unread: false,
      elapsed: job.elapsed,
      progress: '',
      to: '/models',
      startedAt: job.startedAt,
    })),
    ...batchJobStore.runningJobs.map((job): BellTask => ({
      key: `batch:${job.jobId}`,
      kind: 'batch',
      title: job.title,
      running: true,
      failed: false,
      unread: false,
      elapsed: job.elapsed,
      progress: job.total ? `${job.processed}/${job.total}` : '',
      to: '/inference-records',
      startedAt: job.startedAt,
    })),
  ];
  return rows.sort((a, b) => a.startedAt - b.startedAt); // 先提交的排前面
});

const finishedTasks = computed<BellTask[]>(() => {
  const unread = unseenKeys.value;
  const rows: BellTask[] = [
    ...reportJobStore.finishedJobs.map((job): BellTask => ({
      key: `report:${job.jobId}`,
      kind: job.kind,
      title: job.title,
      running: false,
      failed: job.status === 'FAILED',
      unread: unread.has(`report:${job.jobId}`),
      elapsed: job.elapsed,
      progress: '',
      to: '/reports',
      startedAt: job.startedAt,
    })),
    ...trainingJobStore.finishedJobs.map((job): BellTask => ({
      key: `training:${job.modelVersionId}`,
      kind: 'training',
      title: job.title,
      running: false,
      failed: job.status === 'FAILED',
      unread: unread.has(`training:${job.modelVersionId}`),
      elapsed: job.elapsed,
      progress: '',
      to: '/models',
      startedAt: job.startedAt,
    })),
    ...batchJobStore.finishedJobs.map((job): BellTask => ({
      key: `batch:${job.jobId}`,
      kind: 'batch',
      title: job.title,
      running: false,
      failed: job.status === 'FAILED',
      unread: unread.has(`batch:${job.jobId}`),
      elapsed: job.elapsed,
      progress: '',
      to: '/inference-records',
      startedAt: job.startedAt,
    })),
  ];
  return rows.sort((a, b) => b.startedAt - a.startedAt); // 最近完成的排前面
});

const hasRunning = computed(() => runningTasks.value.length > 0);
const unseenCount = computed(() => unseenKeys.value.size);
/** 徽章文案：超过 99 条折叠成「99+」，避免三位数撑破圆形徽章 */
const unseenBadge = computed(() => (unseenCount.value > 99 ? '99+' : String(unseenCount.value)));

/**
 * 面板里有没有行。**不再用「有没有未读」门控面板** —— 悬停总要展开，
 * 一条任务都没有时展开看到的是一行「暂无任务」。
 */
const hasTasks = computed(() => runningTasks.value.length > 0 || finishedTasks.value.length > 0);

/**
 * 面板展开完全交给 CSS `:hover` —— 鼠标一离开铃铛（含面板）就收起，不留延迟。
 *
 * 斜向移动会「先离开铃铛的横向范围、再落到面板上」，中间那一小段本来会丢 hover；
 * 用 `.topbar-bell::before` 补一块不可见的走廊（见 scoped 样式里的说明），
 * 所以不需要靠收起延迟来兜。
 */

/**
 * 点某一行：**只有点击才算「看过」** —— 把这一条标为已读，然后跳到对应页面。
 * 面板停留不改变已读状态：停在上面看几秒不算看过，得点进去。
 */
const openTask = (task: BellTask) => {
  const id = task.key.slice(task.key.indexOf(':') + 1);
  if (task.key.startsWith('report:')) reportJobStore.markAllSeen([id]);
  else if (task.key.startsWith('training:')) trainingJobStore.markAllSeen([id]);
  else batchJobStore.markAllSeen([id]);
  router.push(task.to);
};

/** 已用时长：秒 → 「12 秒 / 3 分 05 秒 / 1 小时 02 分」 */
const formatElapsed = (seconds: number): string => {
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) return `${total} 秒`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} 分 ${String(total % 60).padStart(2, '0')} 秒`;
  return `${Math.floor(minutes / 60)} 小时 ${String(minutes % 60).padStart(2, '0')} 分`;
};

// 已读集合存在 localStorage，storage 事件只在**别的**标签页触发 —— 正好用来同步：
// 一个标签页看过之后，另一个标签页的徽章跟着清掉。
let stopSeenSync: (() => void) | null = null;
/** 终态任务过期扫描间隔（1 分钟） */
const TASK_EXPIRY_SWEEP_MS = 60_000;
/**
 * 终态任务保留 24h。空闲时轮询已经停了，面板数据没有别的刷新时机 ——
 * 到点的行得靠这个低频定时器自己消失。三个 store 只在**真的有行被丢掉**时
 * 才替换数组引用，所以扫一遍不会引起多余渲染。
 */
let expiryTimer: number | null = null;
onMounted(() => {
  stopSeenSync = onSeenIdsChange(() => {
    reportJobStore.syncSeen();
    trainingJobStore.syncSeen();
    batchJobStore.syncSeen();
  });
  expiryTimer = window.setInterval(() => {
    reportJobStore.purgeExpired();
    trainingJobStore.purgeExpired();
    batchJobStore.purgeExpired();
  }, TASK_EXPIRY_SWEEP_MS);
});
onBeforeUnmount(() => {
  stopSeenSync?.();
  if (expiryTimer !== null) window.clearInterval(expiryTimer);
});

/** 当前角色中文名 */
const roleLabel = computed(() => {
  const role = userStore.currentUser?.role;
  if (role === 'SUPER_ADMIN') return '系统管理员';
  if (role === 'SCENARIO_ADMIN') return '场景管理员';
  return '场景用户';
});

/** 场景编码 → 中文名（顶栏展示用；未收录的原样显示） */
const SCENARIO_NAME: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '舰面调度态势',
};

/** 当前用户场景名（管理员/用户，显示在头像上方；系统管理员不显示） */
const myScenarioName = computed(() => {
  if (isSuperAdmin.value) return '';
  const id = userStore.currentUser?.scenario_code;
  if (!id) return '';
  return SCENARIO_NAME[id] ?? id;
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

// 说明：顶部 bar 只保留品牌名「AI Security Operations Center」+ 当前场景，
// 不再渲染页面大标题——bar 下方的各页面自带标题/说明，避免重复。
// 浏览器标签页标题全站统一为品牌名，由 index.html 的 <title> 静态提供，不随路由变化。

// 落地页跳转不在这里做：路由 '/' 的函数式 redirect 已覆盖（它复用 guards.ts 的 roleLanding）。
// 此前这里另有一份 onMounted 跳转，它在 vue-router 首次导航 resolve 之前执行，
// 此时 route.path 仍是 '/'，于是把用户请求的深链（如 #/reports）顶成角色落地页 —— 已移除。

// ===================== 路由判断快捷变量（template用） =====================
const isLoginPage = computed(() => route.path === '/login');
const isRiskPage = computed(() => route.path === '/risk');
// 内容区渲染不再维护「新页面白名单」：模板用 v-else 兜住所有非 /risk 路由。
// 原先的白名单漏掉一条就会白屏（/situation 就这么烂了两年），且新增路由必须记得补。

// ===================== 顶部导航（三级角色驱动渲染） =====================
// 需求 6.5.2 末段：前端隐藏仅为体验，真正的鉴权在后端。
interface NavItem {
  path: string;
  /** 普通角色（场景管理员/场景用户）的显示文案 */
  label: string;
  /** 系统管理员的显示文案（缺省沿用 label） */
  superAdminLabel?: string;
  /** 允许访问的角色列表（缺省=所有角色） */
  roles?: UserRole[];
  /** 点击动作：复用原导航跳转函数，保持既有行为 */
  action: () => void;
  /** 激活态判定：与显示文案一样按角色区分（原先散在 isXxxPage 与 isNavActive 两处） */
  isActive: () => boolean;
}

const ALL_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN', 'SCENARIO_USER'];
const MGMT_ROLES: UserRole[] = ['SUPER_ADMIN', 'SCENARIO_ADMIN'];

/** 是否正停在某个路径上（精确匹配，与原 isXxxPage 判断一致） */
const atPath = (path: string): boolean => route.path === path;

const navItems: NavItem[] = [
  // 普通用户/管理员的"首页"就是场景大屏（/scenarios/{场景}/dashboard）
  { path: '/overview', label: '首页', roles: ['SUPER_ADMIN'], action: goOverview, isActive: () => atPath('/overview') },
  {
    path: '/scenarios',
    label: '首页',
    superAdminLabel: '场景中心',
    roles: ALL_ROLES,
    action: goScenarioCenter,
    // 系统管理员：场景中心列表高亮；管理员/用户：自己场景大屏（首页）高亮
    isActive: () =>
      isSuperAdmin.value ? atPath('/scenarios') : route.path.startsWith('/scenarios/') || atPath('/scenarios'),
  },
  { path: '/datasets', label: '数据集中心', roles: ALL_ROLES, action: goDatasetCenter, isActive: () => atPath('/datasets') },
  { path: '/alerts', label: '告警中心', roles: ALL_ROLES, action: goAlertsList, isActive: () => atPath('/alerts') },
  { path: '/risk', label: 'AI模型训练', roles: MGMT_ROLES, action: goAiTrainPage, isActive: () => atPath('/risk') },
  { path: '/models', label: '模型中心', roles: ALL_ROLES, action: goModelCenter, isActive: () => atPath('/models') },
  { path: '/inference', label: '风险研判', roles: ALL_ROLES, action: goRiskInference, isActive: () => atPath('/inference') },
  { path: '/inference-records', label: '推理记录', roles: ALL_ROLES, action: goInferenceRecords, isActive: () => atPath('/inference-records') },
  { path: '/reports', label: '报告中心', roles: ALL_ROLES, action: goReportCenter, isActive: () => atPath('/reports') },
  { path: '/users', label: '用户管理', roles: MGMT_ROLES, action: goUsers, isActive: () => atPath('/users') },
  { path: '/settings', label: '设置', superAdminLabel: '系统设置', roles: ALL_ROLES, action: goSettings, isActive: () => atPath('/settings') },
];

/** 按当前角色过滤可见导航项 */
const visibleNavItems = computed(() => {
  const role = userStore.currentUser?.role;
  return navItems.filter((item) => !item.roles || (role ? item.roles.includes(role) : false));
});

/** 导航显示文案：系统管理员用 superAdminLabel（缺省沿用 label） */
const navLabel = (item: NavItem): string =>
  isSuperAdmin.value ? (item.superAdminLabel ?? item.label) : item.label;
</script>

<template>
  <router-view v-if="isLoginPage" />
  <div v-else class="app-shell">
    <div class="app-shell__backdrop"></div>
    <header class="topbar">
      <div class="topbar__heading">
        <p class="eyebrow">AI Security Operations Center</p>
        <!-- 当前场景（管理员/用户）：放标题行最右 -->
        <span v-if="myScenarioName" class="topbar__heading-scenario">{{ myScenarioName }}</span>
      </div>
      <div class="topbar__actions">
        <nav class="nav-tabs">
          <button
            v-for="item in visibleNavItems"
            :key="item.path"
            class="nav-tabs__item"
            :class="{ 'is-active': item.isActive() }"
            @click="item.action()"
          >
            {{ navLabel(item) }}
          </button>
        </nav>
        <div class="topbar-right">
          <!-- 后台任务铃铛：常驻。空闲时是灰色静态图标、悬停不出面板；
               有在途任务点亮，有完成未查看叠数字 -->
          <div
            class="topbar-bell"
            :class="{ 'is-live': hasRunning }"
          >
            <button class="topbar-bell__btn" type="button" aria-label="后台任务">
              <svg
                class="topbar-bell__icon"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.8"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              <span v-if="unseenCount" class="topbar-bell__badge">{{ unseenBadge }}</span>
            </button>

            <div class="topbar-bell__panel">
              <div v-if="runningTasks.length" class="topbar-bell__group">
                <p class="topbar-bell__caption">进行中</p>
                <button
                  v-for="task in runningTasks"
                  :key="task.key"
                  class="topbar-bell__row"
                  type="button"
                  @click="openTask(task)"
                >
                  <span class="topbar-bell__dot is-running"></span>
                  <span class="topbar-bell__row-main">
                    <span class="topbar-bell__row-title">{{ task.title }}</span>
                    <span class="topbar-bell__row-meta">
                      {{ KIND_LABEL[task.kind] }}<template v-if="task.progress"> · {{ task.progress }}</template>
                    </span>
                  </span>
                  <span class="topbar-bell__row-time">{{ formatElapsed(task.elapsed) }}</span>
                </button>
              </div>

              <div v-if="finishedTasks.length" class="topbar-bell__group">
                <p class="topbar-bell__caption">已完成</p>
                <button
                  v-for="task in finishedTasks"
                  :key="task.key"
                  class="topbar-bell__row"
                  type="button"
                  @click="openTask(task)"
                >
                  <span
                    class="topbar-bell__dot"
                    :class="task.failed ? 'is-failed' : task.unread ? 'is-unread' : ''"
                  ></span>
                  <span class="topbar-bell__row-main">
                    <span class="topbar-bell__row-title">{{ task.title }}</span>
                    <span class="topbar-bell__row-meta">{{ KIND_LABEL[task.kind] }}</span>
                  </span>
                  <span class="topbar-bell__row-time" :class="{ 'is-failed': task.failed }">
                    {{ task.failed ? '失败' : '已完成' }}
                  </span>
                </button>
              </div>

              <p v-if="!hasTasks" class="topbar-bell__empty">暂无任务</p>
            </div>
          </div>

          <div class="topbar__user">
            <span class="topbar__user-avatar">{{ currentUser?.display_name?.charAt(0) }}</span>
            <div class="topbar__user-pop">
              <span class="topbar__user-name">{{ currentUser?.display_name }}</span>
              <span class="topbar__user-role">{{ roleLabel }}</span>
              <button class="ghost-button ghost-button--logout" @click="handleLogout">退出登录</button>
            </div>
          </div>
        </div>
      </div>
    </header>

    <!-- AI风险研判页面 单独路由视图渲染 -->
    <div v-if="isRiskPage" class="risk-page-wrap">
      <router-view />
    </div>

    <!-- 其余页面（含 404 兜底）统一渲染，不再依赖白名单 -->
    <div v-else class="new-page-wrap">
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

/* 品牌行占满首整行（左侧英文 eyebrow + 右侧当前场景），导航换到第二行。
   页面大标题已移除：bar 下方各页面自带标题/说明，避免重复。 */
.topbar__heading {
  flex: 1 1 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

/* 标题行不再有大标题，eyebrow 底部外边距归零，避免行间空隙过大 */
.topbar__heading .eyebrow {
  margin-bottom: 0;
}

/* 当前场景大字（标题行最右） */
.topbar__heading-scenario {
  flex-shrink: 0;
  color: #9ad6ff;
  font-size: clamp(1.6rem, 2vw, 2.6rem);
  font-weight: 600;
  white-space: nowrap;
}

/* ===================== 顶栏右侧：任务铃铛 + 用户区 ===================== */
/* 两者必须包在同一个容器里：.topbar__actions 是 space-between，单独塞第 3 个孩子会
   漂到导航与用户区中间的空档正中（1920 下离头像 300+px）。 */
.topbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-shrink: 0;
}

/* ===================== 任务铃铛 ===================== */
/* 悬停桥接（纵向）：padding-bottom 把按钮下方 12px 并入触发区，margin-bottom 抵消占位
   （按钮仍在垂直居中的位置），面板 top:100% 正好贴住那块内边距 ——
   鼠标从铃铛笔直往下滑进面板，中间不断。面板是子元素，:hover 覆盖整棵子树。 */
.topbar-bell {
  position: relative;
  padding-bottom: 12px;
  margin-bottom: -12px;
}

/* 悬停桥接（横向）：面板 320px 宽、右对齐在铃铛下方，而铃铛只有 36px 宽 ——
   鼠标斜着往下走时，会先离开铃铛的横向范围、再落到面板上，中间那一小段本来会丢
   hover。这块不可见的走廊盖住「按钮整个高度 + 下方 12px 内边距」，于是
   「按钮 → 走廊 → 面板」连成一片，斜向路径不会断，也就不需要靠「收起延迟」兜底
   （离开即收起，实测 Δ≈0.4ms）。
   走廊横向会压到导航，所以给 .nav-tabs 加了正 z-index 让它始终在走廊之上 ——
   既不会被挡掉点击，也不会出现「走廊留住 hover → 面板不关 → 走廊一直可见」的死锁。
   visibility 同样只在悬停时才可见，未展开时完全不参与命中测试。 */
.topbar-bell::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  visibility: hidden;
}

.topbar-bell:hover::before {
  visibility: visible;
}

.topbar-bell__btn {
  position: relative;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(125, 201, 255, 0.18);
  border-radius: 50%;
  background: rgba(8, 17, 31, 0.7);
  color: rgba(154, 214, 255, 0.5);
  transition: color 0.2s, border-color 0.2s, box-shadow 0.2s;
}

/* 有在途任务：点亮 */
.topbar-bell.is-live .topbar-bell__btn {
  color: #7dc9ff;
  border-color: rgba(125, 201, 255, 0.45);
  box-shadow: 0 0 0 3px rgba(91, 166, 255, 0.14);
}

.topbar-bell.is-live .topbar-bell__icon {
  animation: bell-ring 3s ease-in-out infinite;
  transform-origin: 50% 12%;
}

.topbar-bell__icon {
  width: 19px;
  height: 19px;
}

@keyframes bell-ring {
  0%, 86%, 100% { transform: rotate(0deg); }
  90% { transform: rotate(11deg); }
  94% { transform: rotate(-9deg); }
  97% { transform: rotate(5deg); }
}

.topbar-bell__badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 17px;
  height: 17px;
  padding: 0 4px;
  border-radius: 999px;
  background: #ff6b5e;
  color: #fff;
  font-size: 0.62rem;
  font-weight: 600;
  line-height: 17px;
  text-align: center;
  box-shadow: 0 0 0 2px rgba(6, 13, 24, 0.92);
}

.topbar-bell__panel {
  position: absolute;
  top: 100%;
  right: 0;
  width: 320px;
  /* .app-shell 是 overflow:hidden，矮视口下高面板会被裁掉，所以自己限高内滚 */
  max-height: min(60vh, 420px);
  overflow-y: auto;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(10, 20, 38, 0.96);
  backdrop-filter: blur(18px);
  box-shadow: 0 14px 44px rgba(0, 0, 0, 0.55);
  opacity: 0;
  visibility: hidden;
  transform: translateY(-6px);
  z-index: 30;
}

/* 淡入放在「显示」这条规则上、隐藏那条不写 transition —— 这样离开时是**瞬时**收起
   （transition 取的是目标状态的声明值，隐藏态没写就是 none），只有出现时有个淡入。 */
.topbar-bell:hover .topbar-bell__panel {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
  transition: opacity 0.15s, transform 0.15s;
}

.topbar-bell__group + .topbar-bell__group {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid rgba(125, 201, 255, 0.12);
}

.topbar-bell__caption {
  margin: 0;
  padding: 4px 8px;
  color: rgba(154, 214, 255, 0.5);
  font-size: 0.68rem;
  letter-spacing: 0.08em;
}

/* 面板空态：一条任务都没有时展开看到的就是它（铃铛此时是灰色的） */
.topbar-bell__empty {
  margin: 0;
  padding: 6px 8px;
  color: rgba(154, 214, 255, 0.42);
  font-size: 0.78rem;
  text-align: center;
}

.topbar-bell__row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  transition: background 0.18s;
}

.topbar-bell__row:hover {
  background: rgba(91, 166, 255, 0.14);
}

.topbar-bell__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: rgba(154, 214, 255, 0.26);
}

.topbar-bell__dot.is-running {
  background: #5ba6ff;
  box-shadow: 0 0 0 3px rgba(91, 166, 255, 0.18);
}

.topbar-bell__dot.is-unread {
  background: #ff6b5e;
}

.topbar-bell__dot.is-failed {
  background: #ff7b72;
}

.topbar-bell__row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.topbar-bell__row-title {
  color: #eaf3ff;
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-bell__row-meta {
  color: rgba(154, 214, 255, 0.55);
  font-size: 0.68rem;
}

.topbar-bell__row-time {
  flex-shrink: 0;
  color: rgba(154, 214, 255, 0.75);
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
}

.topbar-bell__row-time.is-failed {
  color: #ff7b72;
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

