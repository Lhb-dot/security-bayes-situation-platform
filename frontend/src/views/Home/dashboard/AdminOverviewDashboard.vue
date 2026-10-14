<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { rolesForPath } from '@/router/access';
import type { UserRole } from '@/types/security';
import { SCENE_STYLES, exactOverviewCount, formatOverviewCount, overviewPercentage, sampleMetric, type AdminOverviewData } from './adminOverview';

const props = withDefaults(defineProps<{
  data: AdminOverviewData | null;
  preview?: boolean;
  loading?: boolean;
  error?: string;
  statusTitle?: string;
  role?: UserRole | null;
  userName?: string;
  loggingOut?: boolean;
}>(), { preview: false, loading: false, error: '', statusTitle: '', role: 'SUPER_ADMIN', userName: '系统管理员', loggingOut: false });
const emit = defineEmits<{ navigate: [href: string]; refresh: []; logout: [] }>();
const format = formatOverviewCount;
const exact = exactOverviewCount;
const riskPercent = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;
const riskWidth = (value: number | null) => `${(value ?? 0) * 100}%`;
const scenes = computed(() => (props.data?.scenes ?? []).map((scene) => ({
  ...scene, ...SCENE_STYLES[scene.key], users: scene.userCount, admins: scene.adminCount, href: scene.path,
})));
const runtime = computed(() => ({
  trained: props.data?.trainedModels ?? null, published: props.data?.publishedModels ?? 0,
  inferences: props.data?.inferenceCount ?? 0, reports: props.data?.reportCount ?? null,
  users: props.data?.userCount ?? 0, served: props.data?.servedUserCount ?? null,
  pending: props.data?.pendingCount ?? 0, processing: props.data?.processingCount ?? 0, resolved: props.data?.resolvedCount ?? 0,
}));
const totalEvents = computed(() => runtime.value.pending + runtime.value.processing + runtime.value.resolved);
const resolvedPercent = computed(() => overviewPercentage(runtime.value.resolved, totalEvents.value));
const servicePercent = computed(() => overviewPercentage(runtime.value.served, runtime.value.users));
const eventWidth = (value: number) => `${totalEvents.value ? value / totalEvents.value * 100 : 0}%`;
const eventStatuses = computed(() => [
  { key: 'pending', label: '待处置', value: runtime.value.pending },
  { key: 'processing', label: '处理中', value: runtime.value.processing },
  { key: 'resolved', label: '已处置', value: runtime.value.resolved },
]);
const sampleDistributionTotal = computed(() => scenes.value.reduce((sum, scene) => sum + scene.samples, 0));
const icons: Record<string, string> = {
  scene: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  data: 'M4 5c0-2 16-2 16 0s-16 2-16 0 M4 5v14c0 2 16 2 16 0V5 M4 12c0 2 16 2 16 0',
  model: 'M12 3l8 5v8l-8 5-8-5V8z M4 8l8 5 8-5 M12 13v8 M8 5l8 5',
  prediction: 'M3 17l5-5 4 3 8-10 M14 5h6v6 M3 21h18',
  settings: 'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
  network: 'M12 3l8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6z M8 12l3 3 5-6',
  power: 'M13 2L5 14h6l-1 8 9-13h-7z',
  flight: 'M21 3L3 10l7 3 3 7z M10 13l6-5',
  mountain: 'M2 20L9 5l5 9 3-6 5 12z M6 11l3 2 2-3',
  arrow: 'M5 12h14 M14 7l5 5-5 5',
  user: 'M15 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M5 21v-3c0-6 14-6 14 0v3',
  chevron: 'M8 10l4 4 4-4',
};
interface NavigationItem { label: string; detail: string; href: string }
const navigationGroups: Array<{ id: string; label: string; description: string; items: NavigationItem[] }> = [
  { id: 'scene', label: '场景总览', description: '选择场景，直接查看数据画像', items: [] },
  { id: 'data', label: '数据管理', description: '从数据接入到资源管理', items: [{ label: '数据集中心', detail: '上传、查看与管理数据集', href: '/datasets' }] },
  { id: 'model', label: '模型训练', description: '训练、发布与版本管理', items: [{ label: 'AI 模型训练', detail: '选择数据集与算法，发起训练', href: '/risk' }, { label: '模型中心', detail: '模型版本、发布与禁用', href: '/models' }] },
  { id: 'prediction', label: '预测研判', description: '从风险推理到事件闭环', items: [{ label: '风险研判', detail: '使用已发布模型进行预测', href: '/inference' }, { label: '推理记录', detail: '查看历史推理及结果', href: '/inference-records' }, { label: '风险事件', detail: '追踪风险与处置进展', href: '/alerts' }, { label: '报告中心', detail: '生成与查看研判报告', href: '/reports' }] },
  { id: 'settings', label: '系统管理', description: '账号、权限与系统配置', items: [{ label: '用户管理', detail: '管理平台用户及角色', href: '/users' }, { label: '系统设置', detail: '账号安全、基础设置与风险阈值', href: '/settings' }] },
];
const pipeline = [
  { label: '场景接入', icon: 'scene', href: '#scene-overview' },
  { label: '数据管理', icon: 'data', href: '/datasets' },
  { label: '模型训练', icon: 'model', href: '/risk' },
  { label: '风险推理', icon: 'prediction', href: '/inference' },
  { label: '事件处置', icon: 'network', href: '/alerts' },
  { label: '报告生成', icon: 'data', href: '/reports' },
];

const navigation = computed(() => navigationGroups.map((group) => ({
  ...group,
  items: (group.id === 'scene'
    ? scenes.value.map((scene) => ({ label: scene.name, detail: '查看场景数据画像', href: scene.href }))
    : group.items).filter((item) => props.role && rolesForPath(item.href).includes(props.role)),
})).filter((group) => group.items.length > 0 || (group.id === 'scene' && props.role === 'SUPER_ADMIN')));
const metrics = computed(() => {
  const data = props.data;
  if (!data) return [];
  const padded = (value: number) => value < 10 ? String(value).padStart(2, '0') : format(value);
  return [
    { label: '多域态势覆盖', value: padded(data.scenarioCount), unit: '大场景', icon: 'scene', color: '#69b7ff', href: '#scene-overview', title: `${exact(data.scenarioCount)} 个场景，点击选择场景` },
    { label: '异构数据资源', value: padded(data.datasetCount), unit: '套数据集', icon: 'data', color: '#4cdac6', href: '/datasets', title: `${exact(data.datasetCount)} 个有效数据集` },
    { label: '有效样本规模', ...sampleMetric(data.sampleCount), icon: 'prediction', color: '#efc17a', href: '/datasets', title: `${exact(data.sampleCount)} 条有效样本` },
    { label: '算法能力储备', value: padded(data.algorithmCount), unit: '类算法', icon: 'model', color: '#a999ee', href: '/risk', title: `${exact(data.algorithmCount)} 个可用算法` },
  ];
});
const modelStats = computed(() => [
  { label: '训练完成模型', value: runtime.value.trained, href: '/models', icon: 'model' },
  { label: '已发布模型', value: runtime.value.published, href: '/models', icon: 'network' },
  { label: '推理记录', value: runtime.value.inferences, href: '/inference-records', icon: 'prediction' },
  { label: '已生成报告', value: runtime.value.reports, href: '/reports', icon: 'data' },
]);
const donutSegments = computed(() => {
  let offset = 0;
  return scenes.value.map((scene) => {
    const length = sampleDistributionTotal.value ? scene.samples / sampleDistributionTotal.value * 100 : 0;
    const item = { ...scene, length, offset, percent: sampleDistributionTotal.value ? length.toFixed(1) : null };
    offset += length;
    return item;
  });
});
const activeNav = ref<string | null>(null);
const navRoot = ref<HTMLElement | null>(null);
const menuPosition = ref({ left: '0px', top: '51px', width: '340px', '--menu-arrow-left': '20px' });
const selectedNav = computed(() => navigation.value.find((group) => group.id === activeNav.value));
const positionMenu = (id: string) => {
  const root = navRoot.value;
  const trigger = root?.querySelector<HTMLButtonElement>(`[data-category="${id}"]`);
  if (!root || !trigger) return;
  const rootRect = root.getBoundingClientRect();
  const triggerRect = trigger.getBoundingClientRect();
  const viewportWidth = document.documentElement.clientWidth;
  const scale = parseFloat(getComputedStyle(root).fontSize) / 12;
  const edge = 14 * scale;
  const width = Math.min(340 * scale, viewportWidth - 2 * edge);
  // 默认与触发按钮左边对齐；靠近屏幕右边时向左收进，箭头始终指向该按钮。
  const left = Math.max(edge - rootRect.left, Math.min(triggerRect.left - rootRect.left, viewportWidth - edge - rootRect.left - width));
  const arrowLeft = Math.max(20 * scale, Math.min(triggerRect.left + triggerRect.width / 2 - rootRect.left - left, width - 20 * scale));
  menuPosition.value = {
    left: `${left}px`,
    top: `${Math.max(triggerRect.bottom, rootRect.bottom) - rootRect.top + 10 * scale}px`,
    width: `${width}px`,
    '--menu-arrow-left': `${arrowLeft}px`,
  };
};
const repositionMenu = () => { if (activeNav.value) positionMenu(activeNav.value); };
const toggleNav = (id: string) => {
  activeNav.value = activeNav.value === id ? null : id;
  if (activeNav.value) positionMenu(activeNav.value);
};
const closeNav = () => {
  if (activeNav.value) navRoot.value?.querySelector<HTMLButtonElement>(`[data-category="${activeNav.value}"]`)?.focus();
  activeNav.value = null;
};
const closeOutside = (event: PointerEvent) => {
  if (event.target instanceof Node && !navRoot.value?.contains(event.target)) activeNav.value = null;
};
const handleKey = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && activeNav.value) {
    closeNav();
  }
};
const handleFocusOut = (event: FocusEvent) => {
  if (!(event.relatedTarget instanceof Node) || !navRoot.value?.contains(event.relatedTarget)) activeNav.value = null;
};
onMounted(() => {
  document.documentElement.classList.add('admin-overview-mode');
  document.addEventListener('pointerdown', closeOutside);
  document.addEventListener('keydown', handleKey);
  window.addEventListener('resize', repositionMenu);
});
onUnmounted(() => {
  document.documentElement.classList.remove('admin-overview-mode');
  document.removeEventListener('pointerdown', closeOutside);
  document.removeEventListener('keydown', handleKey);
  window.removeEventListener('resize', repositionMenu);
});

watch(() => props.role, () => { activeNav.value = null; });
const onNavigate = (event: MouseEvent, href: string) => {
  if (href === '#scene-overview') {
    event.preventDefault();
    toggleNav('scene');
    navRoot.value?.querySelector<HTMLButtonElement>('[data-category="scene"]')?.focus();
    return;
  }
  activeNav.value = null;
  // 预览保持普通链接；正式页面使用已有路由，同时保留新标签页 / Ctrl 点击行为。
  if (props.preview || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  event.preventDefault();
  emit('navigate', href);
};
</script>

<template>
  <main class="admin-overview">
    <header class="masthead">
      <a class="brand" href="/overview" aria-label="进入正式管理员首页" @click="onNavigate($event, '/overview')">AI SECURITY OPERATIONS CENTER</a>
      <div class="masthead-title"><span class="title-decoration"></span><h1>基于贝叶斯网络的复杂系统智能态势感知平台</h1><span class="title-decoration title-decoration--right"></span></div>
      <div class="header-account">
        <span v-if="preview" class="preview-badge" title="演示数据，非实时统计">设计预览</span>
        <button v-else class="preview-badge runtime-badge" :class="{ 'runtime-badge--error': !!error }" type="button" :disabled="loading" :title="statusTitle || '点击刷新平台数据'" @click="emit('refresh')">{{ loading ? '读取数据' : error ? (data ? '更新失败' : '连接失败') : '实时数据' }}</button>
        <span class="account-avatar"><svg viewBox="0 0 24 24"><path :d="icons.user" /></svg></span><span :title="userName">系统管理员</span>
        <button v-if="!preview" type="button" class="logout-button" :disabled="loggingOut" @click="emit('logout')">{{ loggingOut ? '退出中…' : '退出登录' }}</button>
      </div>
    </header>

    <div class="dashboard-content" :class="{ 'dashboard-content--unavailable': !data }">
      <section class="command-bar" aria-label="驾驶舱功能导航">
        <div class="command-title"><span class="eyebrow">PLATFORM COMMAND CENTER</span><h2>领导驾驶舱</h2></div>
        <nav ref="navRoot" class="module-navigation" aria-label="按业务分类的功能入口" @focusout="handleFocusOut">
          <button v-for="group in navigation" :id="`category-${group.id}`" :key="group.id" type="button" :data-category="group.id" :class="{ 'is-active': activeNav === group.id }" :aria-expanded="activeNav === group.id" aria-controls="category-panel" @click="toggleNav(group.id)">
            <svg class="module-icon" viewBox="0 0 24 24" aria-hidden="true"><path :d="icons[group.id]" /></svg><span>{{ group.label }}</span><svg class="chevron" viewBox="0 0 24 24" aria-hidden="true"><path :d="icons.chevron" /></svg>
          </button>
          <div v-if="selectedNav" id="category-panel" class="category-panel" :style="menuPosition" :aria-labelledby="`category-${selectedNav.id}`">
            <div class="category-heading"><div><strong>{{ selectedNav.label }}</strong><span>{{ selectedNav.description }}</span></div><button type="button" class="close-menu" aria-label="关闭功能菜单" @click="closeNav">×</button></div>
            <a v-for="item in selectedNav.items" :key="item.href" :href="item.href" @click="onNavigate($event, item.href)"><span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons.arrow" /></svg></a>
            <p v-if="selectedNav.id === 'scene' && !selectedNav.items.length" class="category-empty" role="status">{{ loading ? '正在读取场景…' : '暂无已接入场景' }}</p>
            <button v-if="!preview && selectedNav.id === 'settings'" type="button" class="category-logout" :disabled="loggingOut" @click="activeNav = null; emit('logout')">{{ loggingOut ? '正在退出…' : '退出登录' }}</button>
          </div>
        </nav>
      </section>

      <template v-if="data">
      <section class="headline-metrics" :aria-busy="loading" aria-label="平台核心数据概览">
        <a v-for="metric in metrics" :key="metric.label" class="metric-card" :class="{ 'count--long': metric.value.length > 5 || (metric.unit.length > 2 && metric.value.length > 3) }" :href="metric.href" :style="{ '--accent': metric.color }" :title="metric.title" @click="onNavigate($event, metric.href)">
          <div class="metric-top"><span>{{ metric.label }}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons[metric.icon]" /></svg></div>
          <div class="metric-value"><strong>{{ metric.value }}</strong><span>{{ metric.unit }}</span></div>
          <div class="metric-bottom"><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons.arrow" /></svg></div>
          <span class="metric-watermark" aria-hidden="true"></span>
        </a>
      </section>

      <section class="overview-grid" aria-label="平台态势与运营数据">
        <aside class="left-panels">
          <section class="panel members-panel">
            <div class="panel-heading"><span class="panel-number">01</span><h3>场景分布</h3></div>
            <table class="member-table"><thead><tr><th scope="col">场景</th><th scope="col">用户</th><th scope="col">管理员</th></tr></thead><tbody><tr v-for="scene in scenes" :key="scene.key"><th scope="row"><span class="scene-dot" :style="{ background: scene.color }"></span>{{ scene.name }}</th><td>{{ format(scene.users) }}</td><td>{{ format(scene.admins) }}</td></tr><tr v-if="!scenes.length" class="member-empty"><td colspan="3">暂无场景成员</td></tr></tbody></table>
          </section>

          <section class="panel distribution-panel">
            <div class="panel-heading"><span class="panel-number">02</span><h3>样本构成</h3></div>
            <div class="distribution-content">
              <svg class="donut" viewBox="0 0 160 160" role="img" aria-label="各场景有效样本占比">
                <circle cx="80" cy="80" r="58" fill="none" stroke="#152f45" stroke-width="13" />
                <circle v-for="scene in donutSegments" :key="scene.key" cx="80" cy="80" r="58" pathLength="100" fill="none" :stroke="scene.color" stroke-width="13" :stroke-dasharray="`${Math.max(0, scene.length - 0.65)} ${100 - Math.max(0, scene.length - 0.65)}`" :stroke-dashoffset="-scene.offset" transform="rotate(-90 80 80)"><title>{{ scene.name }}：{{ scene.percent === null ? '暂无样本' : `${scene.percent}%` }}</title></circle>
                <circle cx="80" cy="80" r="43" fill="none" stroke="#24475e" stroke-dasharray="2 5" stroke-width="1" />
                <text x="80" y="77" text-anchor="middle" fill="#dfedf6" font-size="15" font-weight="600">{{ sampleDistributionTotal ? '样本分布' : '暂无样本' }}</text><text x="80" y="97" text-anchor="middle" fill="#7895aa" font-size="10">{{ scenes.length === 4 ? '四大场景' : `${scenes.length} 类场景` }}</text>
              </svg>
              <div class="sample-legend"><span v-if="!scenes.length" class="empty-hint">暂无样本数据</span><div v-for="scene in donutSegments" :key="scene.key"><span class="scene-dot" :style="{ background: scene.color }"></span><span>{{ scene.name }}</span><strong>{{ scene.percent ?? '—' }}<small v-if="scene.percent !== null">%</small></strong></div></div>
            </div>
          </section>

          <section class="panel sample-risk-panel">
            <div class="panel-heading"><span class="panel-number">03</span><h3>风险占比</h3></div>
            <div class="risk-bars"><span v-if="!scenes.length" class="empty-hint">暂无场景数据</span><div v-for="scene in scenes" :key="scene.key" class="risk-bar-row" :style="{ '--accent': scene.color }"><span>{{ scene.name }}</span><div class="risk-bar-track"><span :style="{ width: riskWidth(scene.riskRate) }"></span></div><strong>{{ riskPercent(scene.riskRate) }}</strong></div></div>
            <p class="panel-footnote">按数据集标签统计的样本占比</p>
          </section>
        </aside>

        <section id="scene-overview" class="situation-stage" aria-label="四大场景态势与平台能力链路">
          <div class="stage-heading"><div><span class="eyebrow">MULTI-SCENARIO SITUATION</span><h3>多域态势总览</h3></div></div>
          <div class="situation-map">
            <div class="map-grid" aria-hidden="true"></div><div class="radar-sweep" aria-hidden="true"></div><div class="orbit orbit-outer" aria-hidden="true"></div><div class="orbit orbit-middle" aria-hidden="true"></div><div class="orbit orbit-inner" aria-hidden="true"></div>
            <svg class="scene-connections" viewBox="0 0 700 440" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="overview-line"><stop stop-color="#66b9f2" stop-opacity=".12"/><stop offset=".5" stop-color="#67d8e1" stop-opacity=".6"/><stop offset="1" stop-color="#66b9f2" stop-opacity=".12"/></linearGradient></defs><path d="M350 211Q260 125 133 98 M350 211Q440 125 567 98 M350 211Q260 285 133 330 M350 211Q440 285 567 330" stroke="url(#overview-line)" fill="none" stroke-width="1.5"/><path d="M350 211Q260 125 133 98 M350 211Q440 125 567 98 M350 211Q260 285 133 330 M350 211Q440 285 567 330" stroke="#65cedd" stroke-opacity=".5" stroke-dasharray="3 12" fill="none"/></svg>
            <div class="central-hub"><span class="hub-eyebrow">BAYESIAN NETWORK</span><strong>复杂系统<br/>态势感知</strong><span class="hub-rule"></span><span class="hub-caption">跨域融合 · 智能研判</span></div>
            <a v-for="scene in scenes" :key="scene.key" :href="scene.href" class="scene-card" :class="`scene-card--${scene.key}`" :style="{ '--accent': scene.color }" :aria-label="`进入${scene.name}场景，${exact(scene.samples)} 条有效样本，${exact(scene.datasets)} 个数据集`" :title="`有效样本：${exact(scene.samples)}；数据集：${exact(scene.datasets)}`" @click="onNavigate($event, scene.href)">
              <div class="scene-card-heading"><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons[scene.icon]" /></svg><span>{{ scene.name }}</span><span class="scene-enter">↗</span></div>
              <span class="scene-english">{{ scene.english }}</span>
              <div class="scene-card-stats"><div class="scene-stat scene-stat--samples" :class="{ 'count--long': format(scene.samples).length > 4 }"><strong>{{ format(scene.samples) }}</strong><span>有效样本</span></div><div class="scene-stat scene-stat--datasets" :class="{ 'count--long': format(scene.datasets).length > 2 }"><strong>{{ format(scene.datasets) }}</strong><span>数据集数量</span></div></div>
            </a>
            <span v-if="!scenes.length" class="scene-empty">暂无场景数据</span>
          </div>
          <section class="pipeline-section" aria-label="平台业务能力链路">
            <div class="pipeline-heading"><h3>平台能力链路</h3><span>从数据接入到风险闭环</span></div>
            <ol class="pipeline"><li v-for="(step, index) in pipeline" :key="step.label"><a :href="step.href" @click="onNavigate($event, step.href)"><span class="pipeline-index">{{ String(index + 1).padStart(2, '0') }}</span><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons[step.icon]" /></svg><strong>{{ step.label }}</strong></a><span v-if="index < pipeline.length - 1" class="pipeline-arrow" aria-hidden="true">›</span></li></ol>
          </section>
        </section>

        <aside class="right-panels">
          <section class="panel event-panel">
            <div class="panel-heading"><span class="panel-number">04</span><h3>事件状态</h3></div>
            <div class="event-summary"><div><strong>{{ format(data.eventCount) }}</strong><span>累计风险事件</span></div><div class="resolution"><span>处置率</span><strong>{{ resolvedPercent ?? '—' }}<small v-if="resolvedPercent !== null">%</small></strong></div></div>
            <div class="event-track" aria-label="风险事件状态分布"><span :style="{ width: eventWidth(runtime.pending) }"></span><span :style="{ width: eventWidth(runtime.processing) }"></span><span :style="{ width: eventWidth(runtime.resolved) }"></span></div>
            <div class="event-status"><a v-for="status in eventStatuses" :key="status.key" href="/alerts" :class="{ 'count--long': status.value >= 1e6 }" :title="`${status.label}：${exact(status.value)}`" @click="onNavigate($event, '/alerts')"><span><i :class="`status-${status.key}`"></i>{{ status.label }}</span><strong>{{ format(status.value) }}</strong></a></div>
          </section>

          <section class="panel model-panel">
            <div class="panel-heading"><span class="panel-number">05</span><h3>模型发布</h3></div>
            <div class="model-stat-grid"><a v-for="stat in modelStats" :key="stat.label" :class="{ 'count--long': stat.value !== null && stat.value >= 1e6 }" :title="`${stat.label}：${exact(stat.value)}`" :href="stat.href" @click="onNavigate($event, stat.href)"><span>{{ stat.label }}</span><strong>{{ format(stat.value) }}</strong><svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons[stat.icon]" /></svg></a></div>
          </section>

          <section class="panel users-panel">
            <div class="panel-heading"><span class="panel-number">06</span><h3>用户规模</h3></div>
            <div class="user-stats"><a href="/users" @click="onNavigate($event, '/users')"><span>平台注册用户</span><strong>{{ format(runtime.users) }}<small>人</small></strong></a><a href="/users" title="至少发起过一次推理或生成过报告的去重账号数" @click="onNavigate($event, '/users')"><span>研判服务用户</span><strong>{{ format(runtime.served) }}<small>人</small></strong></a></div>
            <div class="user-coverage"><span>研判服务覆盖率</span><strong>{{ servicePercent === null ? '—' : `${servicePercent}%` }}</strong></div><div class="coverage-track"><span :style="{ width: servicePercent === null ? '0%' : `${servicePercent}%` }"></span></div>
          </section>
        </aside>
      </section>

      </template>
      <section v-else class="overview-state" :aria-busy="loading" role="status" aria-live="polite">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="icons.data" /></svg>
        <strong>{{ loading ? '正在读取平台实时数据…' : '平台数据暂不可用' }}</strong>
        <p>{{ loading ? '正在汇总场景、数据集、模型与运行情况' : error || '请稍后重新连接平台服务' }}</p>
        <button v-if="!loading" type="button" @click="emit('refresh')">重新连接</button>
      </section>
    </div>
  </main>
</template>


<style scoped src="./AdminOverviewDashboard.css"></style>
