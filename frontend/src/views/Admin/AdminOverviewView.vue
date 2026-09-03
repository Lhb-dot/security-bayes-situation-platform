<script setup lang="ts">
/**
 * AdminOverviewView.vue — 系统管理员（SUPER_ADMIN）登录落地页·平台运行总览大屏
 *
 * 定位（需求 7.0）：管理员无个人首页，登录后进入平台级"驾驶舱"，
 * 一眼确认四个场景是否都在正常运行、哪里出问题。
 * 数据链路：页面 → store（situation / riskEvent / scenario / threshold）→ mockApi；
 * 30 秒轮询自动刷新 + 手动刷新 + 实时时钟；仅 SUPER_ADMIN 可见（路由守卫 + 页内双保险）。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useSituationStore } from '@/stores/situationStore';
import { useRiskEventStore } from '@/stores/riskEventStore';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useThresholdStore } from '@/stores/thresholdStore';
import { useUserStore } from '@/stores/userStore';
import { useModelStore } from '@/stores/modelStore';
import type {
  RankingItem,
  RiskEvent,
  Scenario,
  ScenarioId,
  ThresholdConfig,
  TrendPoint,
  TypeDistribution,
  UserAccount,
} from '@/types/security';
import ScenarioStatusCard from '@/components/admin/ScenarioStatusCard.vue';
import BarChart from '@/components/charts/BarChart.vue';
import PieChart from '@/components/charts/PieChart.vue';
import LineChart from '@/components/charts/LineChart.vue';
import RiskLevelTag from '@/components/common/RiskLevelTag.vue';
import platformDataBackground from '@/assets/quick-links/platform-data.png';
import modelTopologyBackground from '@/assets/quick-links/model-topology.png';
import accessControlBackground from '@/assets/quick-links/access-control.png';
import intelligenceFlowBackground from '@/assets/quick-links/intelligence-flow.png';

const router = useRouter();
const userStore = useUserStore();
const modelStore = useModelStore();
const situationStore = useSituationStore();
const riskEventStore = useRiskEventStore();
const scenarioStore = useScenarioStore();
const thresholdStore = useThresholdStore();

const loading = ref(true);
const error = ref('');
const clock = ref('');
const lastRefresh = ref('--:--:--');
let clockTimer: number | null = null;
let refreshTimer: number | null = null;

// ===================== 权限 =====================
const isSuperAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN');

// ===================== 数据 =====================
const overview = computed(() => situationStore.overview);
const events = computed<RiskEvent[]>(() => riskEventStore.events);
const scenarios = computed<Scenario[]>(() =>
  overview.value?.scenarios && overview.value.scenarios.length > 0
    ? overview.value.scenarios
    : scenarioStore.scenarios
);

/** 各场景事件分组（供状态卡 sparkline / 事件数） */
const eventsByScenario = computed<Map<ScenarioId, RiskEvent[]>>(() => {
  const map = new Map<ScenarioId, RiskEvent[]>();
  for (const ev of events.value) {
    const list = map.get(ev.scenario_id) ?? [];
    list.push(ev);
    map.set(ev.scenario_id, list);
  }
  return map;
});

const thresholdOf = (scenarioId: ScenarioId): ThresholdConfig | undefined =>
  thresholdStore.thresholdByScenario(scenarioId);

// ===================== 顶部指标 =====================
const globalScore = computed(() => Number(overview.value?.global_risk_score ?? 0));
const globalLevel = computed(() => overview.value?.global_risk_level ?? 'low');
const highRiskCount = computed(() => Number(overview.value?.high_risk_count ?? 0));
const activeModelCount = computed(() => Number(overview.value?.active_model_count ?? 0));
const totalDatasetCount = computed(() =>
  scenarios.value.reduce((sum, s) => sum + (Number(s.dataset_count) || 0), 0)
);
const activeScenarioCount = computed(
  () => scenarios.value.filter((s) => s.status === 'active').length
);
const scenarioCount = computed(() => scenarios.value.length);

/** 近 24 小时事件数（口径：occurred_at 距当前 < 24h） */
const recent24hCount = computed(() => {
  const now = Date.now();
  return events.value.filter((ev) => {
    const t = new Date(ev.occurred_at.replace(' ', 'T')).getTime();
    return !Number.isNaN(t) && now - t >= 0 && now - t < 86_400_000;
  }).length;
});

// ===================== 系统运行状态 =====================
type OverallTone = 'ok' | 'warn' | 'danger';

const overallTone = computed<OverallTone>(() => {
  if (events.value.some((e) => e.risk_level === 'HIGH')) return 'danger';
  if (events.value.some((e) => e.risk_level === 'MEDIUM')) return 'warn';
  return 'ok';
});

const overallStatusText = computed(() => {
  if (overallTone.value === 'danger') return `${scenarioCount.value} 个场景接入 · 存在高危事件`;
  if (overallTone.value === 'warn') return `${scenarioCount.value} 个场景接入 · 部分场景需关注`;
  return `${activeScenarioCount.value} / ${scenarioCount.value} 场景正常运行`;
});

const overallStatusLabel = computed(() =>
  overallTone.value === 'danger' ? '异常' : overallTone.value === 'warn' ? '关注' : '正常'
);

const gaugeColor = computed(() => {
  const level = globalLevel.value;
  if (level === 'high' || level === 'critical') return '#ff7b72';
  if (level === 'medium') return '#ffd166';
  return '#53e5c8';
});

// ===================== 图表数据 =====================
const riskDistribution = computed<TypeDistribution[]>(() => {
  const counts: Record<RiskEvent['risk_level'], number> = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  for (const ev of events.value) counts[ev.risk_level] += 1;
  return [
    { label: '高危', value: counts.HIGH, color: '#ff7b72' },
    { label: '中危', value: counts.MEDIUM, color: '#ffd166' },
    { label: '低危', value: counts.LOW, color: '#53e5c8' },
  ].filter((item) => item.value > 0);
});

/** 场景健康度排行（100 - 风险分，越高越健康） */
const healthRanking = computed<RankingItem[]>(() =>
  [...scenarios.value]
    .map((s) => ({
      name: s.name,
      score: Math.round(Math.min(100, Math.max(0, 100 - (Number(s.risk_score) || 0)))),
    }))
    .sort((a, b) => b.score - a.score)
);

const globalTrend = computed<TrendPoint[]>(() => overview.value?.global_trend ?? []);

// ===================== Platform todos / approvals =====================
interface TodoItem {
  key: string;
  label: string;
  desc: string;
  count: number;
  tone: 'danger' | 'warn' | 'info' | 'ok';
  path: string;
}

const todos = computed<TodoItem[]>(() => {
  const drafts = modelStore.modelVersions.filter((m) => m.status === 'DRAFT').length;
  const failed = modelStore.modelVersions.filter((m) => m.status === 'FAILED').length;
  const training = modelStore.modelVersions.filter((m) => m.status === 'TRAINING').length;
  const pendingHigh = events.value.filter(
    (e) => e.risk_level === 'HIGH' && e.status === '待处置'
  ).length;
  const disabled = Number(userStore.platformStats?.disabled ?? 0);
  const reserved = scenarios.value.filter((s) => s.status === 'inactive').length;
  return [
    {
      key: 'draft',
      label: '待审核发布',
      desc: '训练完成待管理员发布',
      count: drafts,
      tone: drafts > 0 ? 'danger' : 'ok',
      path: '/models',
    },
    {
      key: 'failed',
      label: '训练失败',
      desc: '训练任务异常需排查',
      count: failed,
      tone: failed > 0 ? 'warn' : 'ok',
      path: '/models',
    },
    {
      key: 'training',
      label: '训练中',
      desc: '正在执行的训练任务',
      count: training,
      tone: training > 0 ? 'info' : 'ok',
      path: '/models',
    },
    {
      key: 'pending-high',
      label: '待处置高危',
      desc: '高风险事件尚未处置',
      count: pendingHigh,
      tone: pendingHigh > 0 ? 'danger' : 'ok',
      path: '/alerts',
    },
    {
      key: 'disabled',
      label: '禁用账号',
      desc: '需关注的异常账号',
      count: disabled,
      tone: disabled > 0 ? 'warn' : 'ok',
      path: '/users',
    },
    {
      key: 'reserved',
      label: '预留场景',
      desc: '尚未接入运行的场景',
      count: reserved,
      tone: reserved > 0 ? 'warn' : 'ok',
      path: '/scenarios',
    },
  ];
});

const todoTotal = computed(() => todos.value.reduce((sum, t) => sum + t.count, 0));

const goTodoPage = (path: string): void => {
  router.push({ path });
};

// ===================== Platform scale / organization =====================
const platformStats = computed(() => userStore.platformStats);

const orgStats = computed(() => [
  { key: 'total', label: '账号总数', value: platformStats.value?.total ?? 0, tone: '' },
  { key: 'super', label: '平台管理员', value: platformStats.value?.super_admins ?? 0, tone: '' },
  { key: 'admins', label: '场景管理员', value: platformStats.value?.scenario_admins ?? 0, tone: '' },
  { key: 'users', label: '场景用户', value: platformStats.value?.scenario_users ?? 0, tone: '' },
  {
    key: 'disabled',
    label: '禁用账号',
    value: platformStats.value?.disabled ?? 0,
    tone: (platformStats.value?.disabled ?? 0) > 0 ? 'danger' : 'ok',
  },
]);

const userDistRanking = computed<RankingItem[]>(() =>
  (platformStats.value?.by_scenario ?? [])
    .map((item) => ({ name: item.name, score: item.user_count }))
    .filter((item) => item.score > 0)
);

const adminNamesOf = (scenarioId: ScenarioId): string => {
  const names = userStore.users
    .filter(
      (u: UserAccount) => u.role === 'SCENARIO_ADMIN' && (u.scenario_ids ?? []).includes(scenarioId)
    )
    .map((u) => u.display_name);
  return names.length > 0 ? names.join('、') : '—';
};

const goUsersPage = (): void => {
  router.push({ path: '/users' });
};

// ===================== Quick links =====================
interface QuickLink {
  key: string;
  label: string;
  desc: string;
  path: string;
  accent: 'cyan' | 'violet' | 'blue' | 'green';
  iconPath: string;
  backgroundImage: string;
}

const quickLinks: QuickLink[] = [
  { key: 'scenarios', label: '场景中心', desc: '管理各业务场景与接入状态', path: '/scenarios', accent: 'cyan', iconPath: 'M3 4h18v4H3zM3 10h18v4H3zM3 16h18v4H3z', backgroundImage: platformDataBackground },
  { key: 'train', label: '模型训练', desc: '算法选择与训练任务', path: '/risk', accent: 'violet', iconPath: 'M4 19V9m6 10V5m6 14v-7m4 7H2M4 7l6-3 6 5 4-3', backgroundImage: modelTopologyBackground },
  { key: 'models', label: '模型中心', desc: '模型发布、下线与版本管理', path: '/models', accent: 'violet', iconPath: 'm12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Zm0 9 8-4.5M12 12 4 7.5M12 12v9', backgroundImage: modelTopologyBackground },
  { key: 'datasets', label: '数据集中心', desc: '平台数据与版本管理', path: '/datasets', accent: 'cyan', iconPath: 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3Zm0 0v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6m-16 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6', backgroundImage: platformDataBackground },
  { key: 'users', label: '用户管理', desc: '账号、角色与场景绑定', path: '/users', accent: 'blue', iconPath: 'M16 20v-1.5c0-2.5-2.7-4.5-6-4.5s-6 2-6 4.5V20m6-9a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm7 2c2 0 3.5 1.4 3.5 3.2V20m-2-9a2.8 2.8 0 1 0 0-5.6', backgroundImage: accessControlBackground },
  { key: 'inference', label: '推理记录', desc: '全平台风险推理记录', path: '/inference-records', accent: 'green', iconPath: 'M5 4h10l4 4v12H5V4Zm10 0v4h4M8 13h8M8 17h5M8 9h3', backgroundImage: intelligenceFlowBackground },
  { key: 'reports', label: '报告中心', desc: '态势报告生成与管理', path: '/reports', accent: 'green', iconPath: 'M5 3h10l4 4v14H5V3Zm10 0v4h4M8 12h8M8 16h8M8 8h2', backgroundImage: intelligenceFlowBackground },
  { key: 'settings', label: '系统设置', desc: '阈值与系统参数配置', path: '/settings', accent: 'blue', iconPath: 'M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm0-12.2v2m0 14v2m9-9h-2M5 12H3m15.4-6.4-1.4 1.4M7 17.4l-1.4 1.4m0-13.2L7 7m10 10 1.4 1.4', backgroundImage: accessControlBackground },
];

interface QuickLinkState {
  text: string;
  tone: 'ok' | 'info' | 'warn' | 'danger';
}

const quickLinkState = (key: QuickLink['key']): QuickLinkState => {
  const drafts = modelStore.modelVersions.filter((m) => m.status === 'DRAFT').length;
  const training = modelStore.modelVersions.filter((m) => m.status === 'TRAINING').length;
  const disabled = Number(platformStats.value?.disabled ?? 0);

  switch (key) {
    case 'scenarios':
      return { text: `${activeScenarioCount.value}/${scenarioCount.value} 场景运行`, tone: 'ok' };
    case 'train':
      return training > 0 ? { text: `训练中 ${training} 项`, tone: 'info' } : { text: '暂无训练任务', tone: 'ok' };
    case 'models':
      return drafts > 0 ? { text: `待发布 ${drafts} 个`, tone: 'danger' } : { text: `${activeModelCount.value} 个已发布`, tone: 'ok' };
    case 'datasets':
      return { text: `${totalDatasetCount.value} 个数据集`, tone: 'info' };
    case 'users':
      return disabled > 0 ? { text: `禁用账号 ${disabled} 个`, tone: 'warn' } : { text: `${platformStats.value?.total ?? 0} 个账号正常`, tone: 'ok' };
    case 'inference':
      return { text: `近 24h ${recent24hCount.value} 次`, tone: 'info' };
    case 'reports':
      return { text: '可生成全平台报告', tone: 'ok' };
    case 'settings':
      return { text: `${scenarioCount.value} 个场景已配置`, tone: 'ok' };
    default:
      return { text: '状态正常', tone: 'ok' };
  }
};

// ===================== 事件流 =====================
const latestEvents = computed<RiskEvent[]>(() =>
  [...events.value].sort((a, b) => b.occurred_at.localeCompare(a.occurred_at)).slice(0, 8)
);

const scenarioNameOf = (scenarioId: string): string =>
  scenarios.value.find((s) => s.scenario_id === scenarioId)?.name ?? scenarioId;

const riskLevelLabel = (level: RiskEvent['risk_level']): string => {
  if (level === 'HIGH') return '高危';
  if (level === 'MEDIUM') return '中危';
  return '低危';
};

const statusLabel = (status: RiskEvent['status']): string => status;

const goEventDetail = (eventId: string): void => {
  router.push({ path: `/events/${eventId}` });
};

/** 点击健康度排行柱条 → 对应场景大屏 */
const goScenarioByName = (name: string): void => {
  const target = scenarios.value.find((s) => s.name === name);
  if (target) router.push({ path: `/scenarios/${target.scenario_id}/dashboard` });
};

// ===================== 刷新与时钟 =====================
const refreshData = async (): Promise<void> => {
  try {
    await Promise.all([
      situationStore.fetchGlobalOverview(),
      riskEventStore.fetchEvents(),
      scenarioStore.fetchScenarioList(),
      thresholdStore.fetchThresholds(),
      modelStore.fetchModelVersions(),
      userStore.fetchUsers(),
      userStore.fetchPlatformStats(),
    ]);
    lastRefresh.value = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    error.value = '';
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据加载失败';
  } finally {
    loading.value = false;
  }
};

const tickClock = (): void => {
  clock.value = new Date().toLocaleTimeString('zh-CN', { hour12: false });
};

onMounted(async () => {
  tickClock();
  clockTimer = window.setInterval(tickClock, 1000);
  await refreshData();
  refreshTimer = window.setInterval(refreshData, 30_000);
});

onBeforeUnmount(() => {
  if (clockTimer !== null) window.clearInterval(clockTimer);
  if (refreshTimer !== null) window.clearInterval(refreshTimer);
});
</script>

<template>
  <!-- 权限兜底：仅系统管理员 -->
  <div v-if="!isSuperAdmin" class="admin-overview">
    <section class="admin-state admin-state--error">
      <p>无权访问：本页面仅系统管理员（SUPER_ADMIN）可见</p>
    </section>
  </div>

  <div v-else class="admin-overview">
    <!-- 加载 / 错误 -->
    <section v-if="loading" class="admin-state">
      <div class="loader"></div>
      <p>正在加载平台运行态势...</p>
    </section>
    <section v-else-if="error && !overview" class="admin-state admin-state--error">
      <p>{{ error }}</p>
      <button class="admin-refresh-btn" @click="refreshData">重试</button>
    </section>

    <template v-else>
      <!-- 顶部状态条 -->
      <section class="admin-hero">
        <div class="admin-hero__status">
          <span class="admin-hero__pulse" :class="`admin-hero__pulse--${overallTone}`"></span>
          <div>
            <p class="admin-hero__eyebrow">Platform Operations Console</p>
            <h2 class="admin-hero__title">{{ overallStatusText }}</h2>
            <p class="admin-hero__sub">
              系统运行状态：{{ overallStatusLabel }} · 数据每 30 秒自动刷新 · 全平台跨场景视图
            </p>
          </div>
        </div>
        <div class="admin-hero__meta">
          <span class="admin-hero__welcome">欢迎回来，{{ userStore.currentUser?.display_name }}</span>
          <span class="admin-hero__clock">{{ clock }}</span>
          <span class="admin-hero__refresh">最近刷新 {{ lastRefresh }}</span>
          <button class="admin-refresh-btn" @click="refreshData">刷新数据</button>
        </div>
      </section>

      <!-- 全局指标行 -->
      <section class="admin-metrics">
        <div class="admin-gauge-card">
          <div
            class="admin-gauge"
            :style="{ '--pct': `${globalScore}%`, '--gauge-color': gaugeColor }"
          >
            <div class="admin-gauge__inner">
              <span class="admin-gauge__value">{{ globalScore }}</span>
              <span class="admin-gauge__unit">全局风险分</span>
            </div>
          </div>
          <div class="admin-gauge-card__level">
            <RiskLevelTag :level="globalLevel" size="large" />
          </div>
        </div>

        <div class="admin-stat admin-stat--danger">
          <span class="admin-stat__value">{{ highRiskCount }}</span>
          <span class="admin-stat__label">高危事件</span>
        </div>
        <div class="admin-stat admin-stat--warning">
          <span class="admin-stat__value">{{ recent24hCount }}</span>
          <span class="admin-stat__label">近24h事件</span>
        </div>
        <div class="admin-stat">
          <span class="admin-stat__value">{{ activeModelCount }}</span>
          <span class="admin-stat__label">活跃模型</span>
        </div>
        <div class="admin-stat">
          <span class="admin-stat__value">{{ totalDatasetCount }}</span>
          <span class="admin-stat__label">数据集总数</span>
        </div>
      </section>

      <!-- 主体：场景卡 + 聚合图表 -->
      <!-- 平台待办 / 审批区 -->
      <section class="admin-todos">
        <div class="admin-section-title">
          <h3>平台待办</h3>
          <span>
            {{ todoTotal > 0 ? `${todoTotal} 项需平台方关注，点击进入对应模块` : '暂无待办，平台运行平稳' }}
          </span>
        </div>
        <div class="admin-todos__grid">
          <button
            v-for="todo in todos"
            :key="todo.key"
            type="button"
            class="admin-todo"
            :class="`admin-todo--${todo.tone}`"
            @click="goTodoPage(todo.path)"
          >
            <span class="admin-todo__dot"></span>
            <div class="admin-todo__main">
              <span class="admin-todo__label">{{ todo.label }}</span>
              <span class="admin-todo__desc">{{ todo.desc }}</span>
            </div>
            <span class="admin-todo__count">{{ todo.count }}</span>
          </button>
        </div>
      </section>

      <section class="admin-main">
        <div class="admin-main__scenarios">
          <div class="admin-section-title">
            <h3>场景运行状态</h3>
            <span>点击卡片进入对应场景大屏</span>
          </div>
          <div v-if="scenarios.length" class="admin-scenario-grid">
            <ScenarioStatusCard
              v-for="s in scenarios"
              :key="s.scenario_id"
              :scenario="s"
              :events="eventsByScenario.get(s.scenario_id) ?? []"
              :threshold="thresholdOf(s.scenario_id)"
            />
          </div>
          <p v-else class="admin-empty">暂无场景数据</p>
        </div>

        <div class="admin-main__charts">
          <div class="admin-chart">
            <BarChart
              v-if="healthRanking.length"
              :data="healthRanking"
              horizontal
              height="190px"
              title="场景健康度排行"
              @bar-click="goScenarioByName"
            />
            <p v-else class="admin-empty">暂无数据</p>
          </div>
          <div class="admin-chart">
            <PieChart
              v-if="riskDistribution.length"
              :items="riskDistribution"
              donut
              height="190px"
              title="风险等级分布"
            />
            <p v-else class="admin-empty">暂无数据</p>
          </div>
          <div class="admin-chart">
            <LineChart
              v-if="globalTrend.length"
              :points="globalTrend"
              area
              height="190px"
              title="全局事件趋势（近12h）"
            />
            <p v-else class="admin-empty">暂无数据</p>
          </div>
        </div>
      </section>

      <!-- 全平台最新风险事件流 -->
      <section class="admin-events">
        <div class="admin-section-title">
          <h3>全平台最新风险事件</h3>
          <span>点击事件查看详情与处置</span>
        </div>
        <div v-if="latestEvents.length" class="admin-event-list">
          <button
            v-for="ev in latestEvents"
            :key="ev.event_id"
            type="button"
            class="admin-event"
            @click="goEventDetail(ev.event_id)"
          >
            <span class="admin-event__scenario">{{ scenarioNameOf(ev.scenario_id) }}</span>
            <span class="admin-event__level" :class="`admin-event__level--${ev.risk_level.toLowerCase()}`">
              {{ riskLevelLabel(ev.risk_level) }}
            </span>
            <span class="admin-event__desc" :title="ev.description">{{ ev.description }}</span>
            <span class="admin-event__score">{{ Math.round(ev.risk_score * 100) }}%</span>
            <span class="admin-event__status" :class="`admin-event__status--${ev.status}`">
              {{ statusLabel(ev.status) }}
            </span>
            <span class="admin-event__time">{{ ev.occurred_at }}</span>
          </button>
        </div>
        <p v-else class="admin-empty">暂无风险事件</p>
      </section>

      <!-- 平台规模与组织概览 -->
      <section class="admin-org">
        <div class="admin-section-title">
          <h3>平台规模与组织</h3>
          <span>账号结构与各场景用户分布，点击图表进入用户管理</span>
        </div>
        <div class="admin-org__stats">
          <button
            v-for="stat in orgStats"
            :key="stat.key"
            type="button"
            class="admin-org-stat"
            :class="`admin-org-stat--${stat.tone || 'ok'}`"
            @click="goUsersPage"
          >
            <span class="admin-org-stat__value">{{ stat.value }}</span>
            <span class="admin-org-stat__label">{{ stat.label }}</span>
          </button>
        </div>
        <div class="admin-org__lower">
          <div class="admin-org__chart">
            <BarChart
              v-if="userDistRanking.length"
              :data="userDistRanking"
              horizontal
              height="200px"
              title="各场景用户分布"
              @bar-click="goScenarioByName"
            />
            <p v-else class="admin-empty">暂无用户数据</p>
          </div>
          <div class="admin-org__admins">
            <h4>场景管理员</h4>
            <div v-for="s in scenarios" :key="s.scenario_id" class="admin-org-admin">
              <span class="admin-org-admin__scenario">{{ s.name }}</span>
              <span class="admin-org-admin__name">{{ adminNamesOf(s.scenario_id) }}</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 快捷入口 / 工作台导航 -->
      <section class="admin-quick">
        <div class="admin-section-title">
          <div>
            <h3>快捷入口</h3>
            <span>平台管理工作台</span>
          </div>
          <p class="admin-quick__hint">8 项平台管理能力 · 关键状态实时同步</p>
        </div>
        <div class="admin-quick__grid">
          <button
            v-for="link in quickLinks"
            :key="link.key"
            type="button"
            class="admin-quick-tile"
            :class="`admin-quick-tile--${link.accent}`"
            :style="{ '--quick-background': `url(${link.backgroundImage})` }"
            :aria-label="`前往${link.label}，${quickLinkState(link.key).text}`"
            @click="router.push({ path: link.path })"
          >
            <span class="admin-quick-tile__top">
              <span class="admin-quick-tile__icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path :d="link.iconPath" />
                </svg>
              </span>
              <span class="admin-quick-tile__arrow" aria-hidden="true">→</span>
            </span>
            <span class="admin-quick-tile__label">{{ link.label }}</span>
            <span class="admin-quick-tile__desc">{{ link.desc }}</span>
            <span class="admin-quick-tile__state" :class="`admin-quick-tile__state--${quickLinkState(link.key).tone}`">
              <i aria-hidden="true"></i>{{ quickLinkState(link.key).text }}
            </span>
          </button>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.admin-overview {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 20px;
}

.admin-overview::before {
  content: '';
  position: absolute;
  inset: -80px -60px;
  z-index: -1;
  pointer-events: none;
  background:
    radial-gradient(900px 480px at 12% -8%, rgba(91, 166, 255, 0.1), transparent 60%),
    radial-gradient(760px 420px at 88% 8%, rgba(167, 139, 250, 0.08), transparent 60%);
}

.admin-overview > section {
  animation: admin-fade-up 0.45s ease both;
}

@keyframes admin-fade-up {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ===================== 状态 / 空态 ===================== */
.admin-state {
  display: grid;
  place-items: center;
  gap: 12px;
  min-height: 260px;
  padding: 40px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: rgba(8, 17, 31, 0.7);
  color: rgba(220, 234, 255, 0.75);
}

.admin-state--error {
  border-color: rgba(255, 123, 114, 0.3);
  color: #ff8c84;
}

.admin-empty {
  margin: 0;
  padding: 36px 0;
  text-align: center;
  color: rgba(220, 234, 255, 0.45);
  font-size: 0.88rem;
}

/* ===================== 顶部状态条 ===================== */
.admin-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 20px 24px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.16);
  background:
    linear-gradient(120deg, rgba(18, 38, 70, 0.9), rgba(8, 17, 31, 0.92)),
    radial-gradient(circle at 0% 0%, rgba(91, 166, 255, 0.18), transparent 50%);
  box-shadow: 0 14px 40px rgba(0, 0, 0, 0.22);
}

.admin-hero__status {
  display: flex;
  align-items: center;
  gap: 18px;
}

.admin-hero__pulse {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
}

.admin-hero__pulse--ok {
  background: #53e5c8;
  box-shadow: 0 0 16px rgba(83, 229, 200, 0.95);
  animation: admin-hero-pulse 2s ease-in-out infinite;
}

.admin-hero__pulse--warn {
  background: #ffd166;
  box-shadow: 0 0 16px rgba(255, 209, 102, 0.95);
  animation: admin-hero-pulse 1.6s ease-in-out infinite;
}

.admin-hero__pulse--danger {
  background: #ff7b72;
  box-shadow: 0 0 18px rgba(255, 123, 114, 1);
  animation: admin-hero-pulse 1s ease-in-out infinite;
}

@keyframes admin-hero-pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.25); opacity: 0.75; }
}

.admin-hero__eyebrow {
  margin: 0 0 4px;
  font-size: 0.72rem;
  letter-spacing: 3px;
  color: rgba(154, 214, 255, 0.65);
  text-transform: uppercase;
}

.admin-hero__title {
  margin: 0 0 4px;
  font-size: 1.35rem;
  color: #eaf3ff;
}

.admin-hero__sub {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
}

.admin-hero__meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.admin-hero__clock {
  font-size: 1.5rem;
  font-weight: 700;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
  letter-spacing: 1px;
}

.admin-hero__refresh {
  font-size: 0.76rem;
  color: rgba(220, 234, 255, 0.5);
}

.admin-hero__welcome {
  font-size: 0.82rem;
  font-weight: 600;
  color: rgba(154, 214, 255, 0.85);
}

.admin-refresh-btn {
  padding: 8px 16px;
  border-radius: 9px;
  border: 1px solid rgba(125, 201, 255, 0.3);
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
  font-size: 0.84rem;
  cursor: pointer;
  transition: background 0.2s, box-shadow 0.2s;
}

.admin-refresh-btn:hover {
  background: rgba(91, 166, 255, 0.24);
  box-shadow: 0 0 16px rgba(91, 166, 255, 0.2);
}

/* ===================== 全局指标行 ===================== */
.admin-metrics {
  display: grid;
  grid-template-columns: 260px repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.admin-gauge-card {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 18px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.16);
  background: linear-gradient(160deg, rgba(16, 34, 62, 0.92), rgba(8, 17, 31, 0.94));
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.18);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.admin-gauge-card:hover {
  transform: translateY(-2px);
  border-color: rgba(125, 201, 255, 0.3);
}

.admin-gauge {
  --pct: 0%;
  --gauge-color: #53e5c8;
  position: relative;
  width: 104px;
  height: 104px;
  border-radius: 50%;
  flex-shrink: 0;
  background: conic-gradient(
    var(--gauge-color) calc(var(--pct) * 1%),
    rgba(125, 201, 255, 0.1) 0
  );
  box-shadow: 0 0 24px color-mix(in srgb, var(--gauge-color) 35%, transparent);
  display: grid;
  place-items: center;
}

.admin-gauge::before {
  content: '';
  position: absolute;
  inset: 8px;
  border-radius: 50%;
  background: #0a1729;
}

.admin-gauge__inner {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.admin-gauge__value {
  font-size: 1.7rem;
  font-weight: 800;
  color: #eaf3ff;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.admin-gauge__unit {
  font-size: 0.66rem;
  color: rgba(220, 234, 255, 0.55);
}

.admin-gauge-card__level {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.admin-stat {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(14, 30, 56, 0.9), rgba(8, 17, 31, 0.92));
  position: relative;
  overflow: hidden;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.admin-stat:hover {
  transform: translateY(-2px);
  border-color: rgba(125, 201, 255, 0.3);
}

.admin-stat::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: #5ba6ff;
}

.admin-stat--danger::before { background: #ff7b72; }
.admin-stat--warning::before { background: #ffd166; }

.admin-stat__value {
  font-size: 1.9rem;
  font-weight: 800;
  color: #eaf3ff;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.admin-stat--danger .admin-stat__value { color: #ff8c84; }
.admin-stat--warning .admin-stat__value { color: #ffd166; }

.admin-stat__label {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
}

/* ===================== 主体 ===================== */
.admin-main {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: 18px;
  align-items: stretch;
}

.admin-section-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.admin-section-title h3 {
  position: relative;
  margin: 0;
  font-size: 1rem;
  color: #e8f1ff;
  padding-left: 12px;
}

.admin-section-title h3::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 14px;
  border-radius: 2px;
  background: linear-gradient(180deg, #5ba6ff, #407acc);
}

.admin-section-title span {
  font-size: 0.74rem;
  color: rgba(220, 234, 255, 0.45);
}

.admin-main__scenarios {
  display: flex;
  flex-direction: column;
}

.admin-scenario-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, 1fr);
  gap: 16px;
}

.admin-main__charts {
  display: grid;
  gap: 16px;
}

.admin-chart {
  padding: 14px 16px 10px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(14, 30, 56, 0.9), rgba(8, 17, 31, 0.92));
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16);
  min-height: 0;
}

/* ===================== 事件流 ===================== */
.admin-events {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(14, 30, 56, 0.9), rgba(8, 17, 31, 0.92));
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.18);
}

.admin-event-list {
  display: grid;
  gap: 8px;
}

.admin-event {
  display: grid;
  grid-template-columns: 120px 56px minmax(0, 1fr) 70px 70px 150px;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 14px;
  text-align: left;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.1);
  background: rgba(255, 255, 255, 0.025);
  color: #dbe9ff;
  font-size: 0.84rem;
  cursor: pointer;
  transition: background 0.16s, border-color 0.16s, transform 0.16s;
}

.admin-event:hover {
  background: rgba(91, 166, 255, 0.09);
  border-color: rgba(125, 201, 255, 0.3);
  transform: translateX(3px);
}

.admin-event__scenario {
  color: #9ad6ff;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.admin-event__level {
  justify-self: start;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
}

.admin-event__level--high {
  background: rgba(255, 123, 114, 0.16);
  color: #ff8c84;
  border: 1px solid rgba(255, 123, 114, 0.3);
}

.admin-event__level--medium {
  background: rgba(255, 209, 102, 0.14);
  color: #ffd166;
  border: 1px solid rgba(255, 209, 102, 0.28);
}

.admin-event__level--low {
  background: rgba(83, 229, 200, 0.14);
  color: #53e5c8;
  border: 1px solid rgba(83, 229, 200, 0.28);
}

.admin-event__desc {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: rgba(234, 243, 255, 0.85);
}

.admin-event__score {
  color: #ffd166;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.admin-event__status {
  font-size: 0.74rem;
  padding: 2px 8px;
  border-radius: 999px;
  justify-self: start;
  background: rgba(220, 234, 255, 0.08);
  color: rgba(220, 234, 255, 0.7);
}

.admin-event__status--已处置 {
  background: rgba(83, 229, 200, 0.13);
  color: #53e5c8;
}

.admin-event__status--处理中 {
  background: rgba(255, 209, 102, 0.13);
  color: #ffd166;
}

.admin-event__status--待处置 {
  background: rgba(255, 123, 114, 0.14);
  color: #ff8c84;
}

.admin-event__time {
  color: rgba(220, 234, 255, 0.45);
  font-variant-numeric: tabular-nums;
  text-align: right;
}

/* ===================== 响应式 ===================== */
/* ===================== 平台待办 ===================== */
.admin-todos {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(14, 30, 56, 0.9), rgba(8, 17, 31, 0.92));
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.18);
}

.admin-todos__grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.admin-todo {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 12px 14px;
  text-align: left;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.1);
  background: rgba(255, 255, 255, 0.025);
  color: #dbe9ff;
  cursor: pointer;
  transition: background 0.16s, border-color 0.16s, transform 0.16s;
}

.admin-todo:hover {
  background: rgba(91, 166, 255, 0.09);
  border-color: rgba(125, 201, 255, 0.3);
  transform: translateY(-1px);
}

.admin-todo__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #53e5c8;
  box-shadow: 0 0 8px rgba(83, 229, 200, 0.6);
}

.admin-todo--danger .admin-todo__dot {
  background: #ff7b72;
  box-shadow: 0 0 8px rgba(255, 123, 114, 0.75);
}

.admin-todo--warn .admin-todo__dot {
  background: #ffd166;
  box-shadow: 0 0 8px rgba(255, 209, 102, 0.7);
}

.admin-todo--info .admin-todo__dot {
  background: #9ad6ff;
  box-shadow: 0 0 8px rgba(154, 214, 255, 0.65);
}

.admin-todo__main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.admin-todo__label {
  font-size: 0.84rem;
  font-weight: 600;
  color: #eaf3ff;
  white-space: nowrap;
}

.admin-todo__desc {
  font-size: 0.7rem;
  color: rgba(220, 234, 255, 0.48);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.admin-todo__count {
  font-size: 1.35rem;
  font-weight: 800;
  color: #eaf3ff;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.admin-todo--danger .admin-todo__count {
  color: #ff8c84;
}

.admin-todo--warn .admin-todo__count {
  color: #ffd166;
}

/* ===================== 平台规模与组织 ===================== */
.admin-org {
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(14, 30, 56, 0.9), rgba(8, 17, 31, 0.92));
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.18);
}

.admin-org__stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.admin-org-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 10px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.1);
  background: rgba(255, 255, 255, 0.025);
  color: #dbe9ff;
  cursor: pointer;
  transition: background 0.16s, border-color 0.16s, transform 0.16s;
}

.admin-org-stat:hover {
  background: rgba(91, 166, 255, 0.09);
  border-color: rgba(125, 201, 255, 0.3);
  transform: translateY(-2px);
}

.admin-org-stat__value {
  font-size: 1.5rem;
  font-weight: 800;
  color: #eaf3ff;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.admin-org-stat__label {
  font-size: 0.74rem;
  color: rgba(220, 234, 255, 0.55);
}

.admin-org-stat--danger .admin-org-stat__value {
  color: #ff8c84;
}

.admin-org__lower {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr);
  gap: 16px;
}

.admin-org__chart {
  min-height: 0;
}

.admin-org__admins {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
}

.admin-org__admins h4 {
  margin: 0 0 10px;
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.65);
  font-weight: 600;
}

.admin-org-admin {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 2px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.07);
  font-size: 0.82rem;
}

.admin-org-admin:last-child {
  border-bottom: none;
}

.admin-org-admin__scenario {
  color: #9ad6ff;
  font-weight: 600;
}

.admin-org-admin__name {
  color: rgba(234, 243, 255, 0.82);
}

/* ===================== 快捷入口 ===================== */
.admin-quick {
  position: relative;
  overflow: hidden;
  padding: 16px 18px;
  border-radius: 16px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background:
    radial-gradient(480px 180px at 100% 0%, rgba(91, 166, 255, 0.1), transparent 72%),
    linear-gradient(160deg, rgba(14, 30, 56, 0.9), rgba(8, 17, 31, 0.92));
  box-shadow: 0 12px 34px rgba(0, 0, 0, 0.18);
}

.admin-quick__hint {
  margin: 0;
  font-size: 0.72rem;
  color: rgba(184, 211, 246, 0.5);
}

.admin-quick__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.admin-quick-tile {
  --quick-accent: #75c7ff;
  --quick-tint: rgba(91, 166, 255, 0.12);
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  min-width: 0;
  min-height: 154px;
  padding: 14px 15px 13px;
  text-align: left;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.1);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.018));
  color: #dbe9ff;
  cursor: pointer;
  overflow: hidden;
  transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.admin-quick-tile::before {
  content: '';
  position: absolute;
  z-index: 0;
  inset: 0;
  pointer-events: none;
  background-image: var(--quick-background);
  background-size: cover;
  background-position: center;
  opacity: 0.12;
  mix-blend-mode: screen;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.admin-quick-tile::after {
  content: '';
  position: absolute;
  right: -28px;
  bottom: -42px;
  width: 112px;
  height: 112px;
  border-radius: 50%;
  pointer-events: none;
  background: var(--quick-tint);
  filter: blur(8px);
  opacity: 0.55;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.admin-quick-tile--cyan {
  --quick-accent: #72d5ff;
  --quick-tint: rgba(73, 205, 255, 0.16);
}

.admin-quick-tile--violet {
  --quick-accent: #b7a0ff;
  --quick-tint: rgba(157, 124, 255, 0.16);
}

.admin-quick-tile--blue {
  --quick-accent: #8eb4ff;
  --quick-tint: rgba(92, 138, 255, 0.16);
}

.admin-quick-tile--green {
  --quick-accent: #72dfbd;
  --quick-tint: rgba(77, 218, 172, 0.15);
}

.admin-quick-tile:hover {
  border-color: color-mix(in srgb, var(--quick-accent) 52%, transparent);
  background: linear-gradient(145deg, var(--quick-tint), rgba(255, 255, 255, 0.035));
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.06);
  transform: translateY(-3px);
}

.admin-quick-tile:hover::after {
  opacity: 0.95;
  transform: scale(1.12);
}

.admin-quick-tile:hover::before {
  opacity: 0.17;
  transform: scale(1.025);
}

.admin-quick-tile > span {
  position: relative;
  z-index: 1;
}

.admin-quick-tile:focus-visible {
  outline: 2px solid var(--quick-accent);
  outline-offset: 3px;
}

.admin-quick-tile:active {
  transform: translateY(-1px) scale(0.985);
}

.admin-quick-tile__top {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
}

.admin-quick-tile__icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid color-mix(in srgb, var(--quick-accent) 30%, transparent);
  border-radius: 9px;
  background: var(--quick-tint);
  color: var(--quick-accent);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.09);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.admin-quick-tile__icon svg {
  width: 18px;
  height: 18px;
}

.admin-quick-tile:hover .admin-quick-tile__icon {
  transform: scale(1.08);
  box-shadow: 0 0 18px var(--quick-tint), inset 0 1px 0 rgba(255, 255, 255, 0.12);
}

.admin-quick-tile__label {
  font-size: 0.92rem;
  font-weight: 700;
  color: #eaf3ff;
}

.admin-quick-tile__desc {
  font-size: 0.72rem;
  color: rgba(220, 234, 255, 0.5);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.admin-quick-tile__arrow {
  color: rgba(220, 234, 255, 0.42);
  font-size: 1.05rem;
  line-height: 1;
  transition: transform 0.2s ease, color 0.2s ease;
}

.admin-quick-tile:hover .admin-quick-tile__arrow {
  transform: translateX(4px);
  color: var(--quick-accent);
}

.admin-quick-tile__state {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: auto;
  max-width: 100%;
  padding: 4px 7px;
  border-radius: 999px;
  font-size: 0.67rem;
  line-height: 1;
  color: rgba(220, 234, 255, 0.66);
  background: rgba(255, 255, 255, 0.045);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.admin-quick-tile__state i {
  width: 5px;
  height: 5px;
  flex: 0 0 5px;
  border-radius: 50%;
  background: #8eb4ff;
}

.admin-quick-tile__state--ok i { background: #53e5c8; box-shadow: 0 0 7px rgba(83, 229, 200, 0.72); }
.admin-quick-tile__state--info i { background: #7dc9ff; }
.admin-quick-tile__state--warn i { background: #ffd166; box-shadow: 0 0 7px rgba(255, 209, 102, 0.58); }
.admin-quick-tile__state--danger i { background: #ff7b72; box-shadow: 0 0 7px rgba(255, 123, 114, 0.6); }

@supports not (color: color-mix(in srgb, white, black)) {
  .admin-quick-tile:hover,
  .admin-quick-tile__icon {
    border-color: rgba(125, 201, 255, 0.32);
  }
}

@media (max-width: 1280px) {
  .admin-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .admin-todos__grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .admin-org__stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .admin-org__lower {
    grid-template-columns: 1fr;
  }
  .admin-quick__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .admin-main {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .admin-hero {
    flex-direction: column;
    align-items: flex-start;
  }
  .admin-scenario-grid {
    grid-template-columns: 1fr;
  }
  .admin-todos__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .admin-org__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .admin-event {
    grid-template-columns: 96px 52px minmax(0, 1fr) 64px 64px;
  }
  .admin-event__time {
    display: none;
  }
}

@media (max-width: 640px) {
  .admin-metrics {
    grid-template-columns: 1fr;
  }
  .admin-todos__grid {
    grid-template-columns: 1fr;
  }
  .admin-quick__grid {
    grid-template-columns: 1fr;
  }
  .admin-event {
    grid-template-columns: 88px 48px minmax(0, 1fr);
  }
  .admin-event__score,
  .admin-event__status {
    display: none;
  }
}
</style>
