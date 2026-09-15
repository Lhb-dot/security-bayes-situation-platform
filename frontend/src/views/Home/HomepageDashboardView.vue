<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useUserStore } from '@/stores/userStore';
import { getAdminDashboard, getScenarioProfile, getScenarioWorkspace, type DashboardOverview, type ScenarioProfile, type ScenarioWorkspace } from '@/api/dashboardApi';
import DashboardBars from '@/components/home/DashboardBars.vue';

const route = useRoute();
const userStore = useUserStore();
const loading = ref(true);
const error = ref('');
const overview = ref<DashboardOverview | null>(null);
const profile = ref<ScenarioProfile | null>(null);
const workspace = ref<ScenarioWorkspace | null>(null);

const isSuperAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN');
const isScenarioAdmin = computed(() => userStore.currentUser?.role === 'SCENARIO_ADMIN');
const scenarioCode = computed(() => String(route.params.scenarioId || userStore.currentUser?.scenario_code || ''));
const mode = computed(() => isSuperAdmin.value ? 'overview' : isScenarioAdmin.value ? 'profile' : 'workspace');
const labels: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '舰面调度',
};
const scenarioName = computed(() => labels[scenarioCode.value] || profile.value?.scenario_name || '业务场景');

const load = async () => {
  loading.value = true;
  error.value = '';
  overview.value = null;
  profile.value = null;
  workspace.value = null;
  try {
    if (mode.value === 'overview') overview.value = await getAdminDashboard();
    else if (mode.value === 'profile') profile.value = await getScenarioProfile(scenarioCode.value);
    else workspace.value = await getScenarioWorkspace(scenarioCode.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '首页数据加载失败';
  } finally {
    loading.value = false;
  }
};

const formatNumber = (value: unknown) => Number(value || 0).toLocaleString('zh-CN');
const formatPercent = (value: unknown) => (Number(value || 0) * 100).toFixed(1) + '%';
const riskLabel = (value: unknown) => ({ HIGH: '高', MEDIUM: '中', LOW: '低', PENDING: '待处置', PROCESSING: '处理中', RESOLVED: '已处置' }[String(value)] || String(value || '—'));

const profileMetrics = computed(() => {
  if (!profile.value) return [] as Array<[string, unknown, string]>;
  const data = profile.value;
  const result: Array<[string, unknown, string]> = [
    ['数据集', data.dataset_count, '个'],
    ['样本量', data.sample_count, '条'],
  ];
  if (data.risk_type === 'power') result.push(['故障率', formatPercent(data.fault_rate), '']);
  else if (data.risk_type === 'flight_deck') result.push(['碰撞率', formatPercent(data.collision_rate), '']);
  else result.push(['风险样本率', formatPercent(data.risk_rate), '']);
  return result;
});

const workspaceMetrics = computed(() => {
  const summary = workspace.value?.summary || {};
  return [['我的待处置', summary.pending, '条'], ['今日新增', summary.today, '条'], ['高置信告警', summary.high_confidence, '条'], ['风险事件', summary.total, '条']] as Array<[string, unknown, string]>;
});

type DashboardSection = { title: string; items: any[]; percent?: boolean; prefix?: string };

const profileSections = computed<DashboardSection[]>(() => {
  const data: any = profile.value;
  if (!data) return [];
  if (data.risk_type === 'network') return [
    { title: '协议分布', items: data.protocol_distribution },
    { title: '目的端口 TOP', items: data.top_ports, prefix: '端口 ' },
    { title: '连接状态 flag / 应用服务', items: [...(data.flag_distribution || []), ...(data.service_distribution || [])] },
    { title: '流量包长五段', items: (data.flow_segments?.labels || []).map((label: string, i: number) => ({ value: label, count: data.flow_segments.counts[i] })) },
  ] as DashboardSection[];
  if (data.risk_type === 'power') return [
    { title: '电参量统计', items: Object.entries(data.params || {}).map(([value, stats]: [string, any]) => ({ value, count: stats.mean })) },
    { title: '问题类型 / 系统分布', items: [...(data.issue_distribution || []), ...(data.system_distribution || [])] },
    { title: '设备故障率', items: data.device_fault_rates, percent: true },
  ] as DashboardSection[];
  if (data.risk_type === 'flight_deck') return [
    { title: '碰撞对比', items: Object.entries(data.collision_comparison || {}).map(([value, stats]: [string, any]) => ({ value, count: stats.mean_min_distance })) },
    { title: '双机方向角', items: [{ value: 'Plane1', count: data.plane1_angle_stats?.mean }, { value: 'Plane2', count: data.plane2_angle_stats?.mean }] },
    { title: '间距曲线', items: (data.distance_curve || []).filter((_: any, i: number) => i % 5 === 0).map((item: any) => ({ value: 'T' + item.step, count: item.mean })) },
  ] as DashboardSection[];
  return [
    { title: '地形因子均值', items: Object.entries(data.factors || {}).map(([value, stats]: [string, any]) => ({ value, count: stats.mean })) },
    { title: '触发因素 / 类型 / 国家', items: [...(data.catalog_distribution?.trigger || []), ...(data.catalog_distribution?.type || []), ...(data.catalog_distribution?.country || [])] },
    { title: '各数据集风险占比', items: (data.datasets || []).map((item: any) => ({ value: item.logical_id, count: item.risk_rate })), percent: true },
  ] as DashboardSection[];
});

const workspaceSections = computed<DashboardSection[]>(() => {
  const data: any = workspace.value;
  if (!data) return [];
  const sections: DashboardSection[] = [
    { title: '处置漏斗', items: data.summary?.status_funnel || [] },
    { title: '风险分区间', items: data.summary?.score_bins || [] },
  ];
  if (data.risk_type === 'network') sections.push({ title: '告警端口 TOP', items: data.top_ports || [] });
  if (data.risk_type === 'power') sections.push({ title: '设备 × 问题类型', items: (data.component_issue_distribution || []).map((item: any) => ({ value: item.component + ' · ' + item.issue, count: item.count })) });
  if (data.risk_type === 'geological') sections.push({ title: '坡度档位风险排行', items: (data.slope_ranking || []).map((item: any) => ({ value: item.label, count: item.mean_risk_score })), percent: true });
  return sections;
});

watch(() => route.params.scenarioId, load);
onMounted(load);
</script>

<template>
  <main class="homepage-dashboard">
    <section v-if="loading" class="home-state"><span class="home-spinner"></span><p>正在加载首页数据...</p></section>
    <section v-else-if="error" class="home-state home-state--error"><p>{{ error }}</p><button class="home-action" @click="load">重试</button></section>

    <template v-else-if="overview">
      <header class="home-header"><div><p class="home-eyebrow">PLATFORM OPERATIONS</p><h1>平台运行总览</h1><p>全平台场景、数据规模与运行态指标</p></div><span class="home-badge">系统管理员首页</span></header>
      <section class="home-metrics"><article v-for="item in [['接入场景', overview.totals.scenario_count, '个'], ['有效数据集', overview.totals.effective_dataset_count, '个'], ['有效样本量', overview.totals.effective_sample_count, '条'], ['可用算法', overview.totals.algorithm_count, '个'], ['风险事件', overview.totals.risk_event_count, '条'], ['推理记录', overview.totals.inference_count, '条']]" :key="item[0]" class="home-metric"><strong>{{ formatNumber(item[1]) }}<small>{{ item[2] }}</small></strong><span>{{ item[0] }}</span></article></section>
      <section class="home-grid home-grid--two"><article class="home-card"><div class="home-card__title"><h2>场景运行清单</h2><span>{{ overview.scenarios.length }} 个场景</span></div><div class="home-table"><div v-for="scene in overview.scenarios" :key="scene.scenario_id" class="home-row"><div><b>{{ scene.name }}</b><small>{{ scene.code }} · {{ scene.access_status }}</small></div><strong>{{ formatNumber(scene.effective_sample_count) }} 条</strong><span>{{ formatPercent(scene.risk_rate) }}</span><span>{{ scene.pending_count }} 待处置</span></div></div></article><article class="home-card"><div class="home-card__title"><h2>运行态指标</h2><span>真实数据库统计</span></div><div class="home-stat-list"><div><span>待处置事件</span><b>{{ overview.totals.pending_event_count }}</b></div><div><span>账号总数</span><b>{{ overview.totals.user_count }}</b></div><div><span>已发布模型</span><b>{{ overview.totals.published_model_count }}</b></div><div><span>推理记录</span><b>{{ overview.totals.inference_count }}</b></div></div></article></section>
    </template>

    <template v-else-if="profile">
      <header class="home-header"><div><p class="home-eyebrow">SCENARIO PROFILE</p><h1>{{ profile.scenario_name }} · 数据画像</h1><p>场景管理员首页 · 数据集全量聚合统计</p></div><span class="home-badge">场景管理员首页</span></header>
      <section class="home-metrics"><article v-for="item in profileMetrics" :key="item[0]" class="home-metric"><strong>{{ typeof item[1] === 'string' ? item[1] : formatNumber(item[1]) }}<small>{{ item[2] }}</small></strong><span>{{ item[0] }}</span></article></section>
      <section class="home-grid home-grid--two"><article v-for="section in profileSections" :key="section.title" class="home-card"><h2>{{ section.title }}</h2><DashboardBars :items="section.items" :prefix="section.prefix" :percent="section.percent" /></article></section>
    </template>

    <template v-else-if="workspace">
      <header class="home-header"><div><p class="home-eyebrow">MY WORKSPACE</p><h1>{{ scenarioName }} · 我的工作台</h1><p>场景用户首页 · 仅统计当前登录用户本人风险事件</p></div><span class="home-badge">场景用户首页</span></header>
      <section class="home-metrics"><article v-for="item in workspaceMetrics" :key="item[0]" class="home-metric"><strong>{{ formatNumber(item[1]) }}<small>{{ item[2] }}</small></strong><span>{{ item[0] }}</span></article></section>
      <section class="home-grid home-grid--two"><article v-for="section in workspaceSections" :key="section.title" class="home-card"><h2>{{ section.title }}</h2><DashboardBars :items="section.items" :percent="section.percent" /></article><article v-if="workspace.risk_type === 'flight_deck'" class="home-card home-card--wide"><h2>双机航向映射散点</h2><div class="home-points"><i v-for="point in workspace.positions" :key="point.event_id" :style="{ left: String((point.x || 0) / 10) + '%', top: String((point.y || 0) / 10) + '%' }"></i><span v-if="!workspace.positions?.length">暂无事件坐标</span></div></article></section>
      <section class="home-card"><div class="home-card__title"><h2>最近告警</h2><span>{{ workspace.recent_events.length }} 条</span></div><div class="home-table"><div v-for="event in workspace.recent_events" :key="event.id" class="home-row"><div><b>{{ event.description || '风险事件' }}</b><small>{{ event.occurred_at }}</small></div><strong>{{ Number(event.risk_score || 0).toFixed(2) }}</strong><span>{{ riskLabel(event.status) }}</span></div><p v-if="!workspace.recent_events.length" class="home-empty">暂无风险事件</p></div></section>
    </template>
  </main>
</template>

<style scoped>
.homepage-dashboard{display:grid;gap:20px;padding-bottom:28px}.home-header{display:flex;justify-content:space-between;align-items:flex-start;gap:18px;padding:24px 26px;background:linear-gradient(135deg,rgba(18,48,90,.92),rgba(8,17,31,.96));border:1px solid rgba(125,201,255,.18);border-radius:10px}.home-eyebrow{font-size:11px;letter-spacing:2px;color:#53e5c8;margin-bottom:8px}.home-header h1{font-size:27px;margin-bottom:8px}.home-header p:last-child{color:rgba(220,234,255,.62);font-size:13px}.home-badge{padding:7px 11px;border:1px solid rgba(83,229,200,.32);color:#53e5c8;font-size:12px;white-space:nowrap}.home-metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.home-metric{min-height:112px;padding:18px;background:rgba(10,22,38,.78);border:1px solid rgba(125,201,255,.14);border-radius:8px}.home-metric strong{display:block;font-size:27px;color:#e8f1ff}.home-metric small{font-size:13px;color:#9ad6ff;margin-left:4px}.home-metric span{display:block;color:rgba(220,234,255,.58);font-size:12px;margin-top:12px}.home-grid{display:grid;gap:18px}.home-grid--two{grid-template-columns:repeat(2,minmax(0,1fr))}.home-card{padding:20px;background:rgba(8,17,31,.82);border:1px solid rgba(125,201,255,.14);border-radius:8px;min-width:0}.home-card--wide{grid-column:1/-1}.home-card h2{font-size:15px;margin-bottom:17px}.home-card__title{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.home-card__title h2{margin:0}.home-card__title span,.home-row small{font-size:11px;color:rgba(220,234,255,.45)}.home-table{display:grid;gap:2px}.home-row{display:grid;grid-template-columns:minmax(0,1fr) 100px 90px 90px;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid rgba(125,201,255,.08);font-size:12px}.home-row:last-child{border-bottom:0}.home-row div{min-width:0}.home-row b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.home-row small{display:block;margin-top:4px}.home-row>strong{color:#9ad6ff}.home-row>span{color:#cfe3ff}.home-stat-list{display:grid;gap:4px}.home-stat-list>div{display:flex;justify-content:space-between;padding:11px 0;border-bottom:1px solid rgba(125,201,255,.08);font-size:12px}.home-stat-list span{color:rgba(220,234,255,.58)}.home-stat-list b{color:#e8f1ff}.home-points{height:240px;position:relative;border:1px solid rgba(125,201,255,.14);background:linear-gradient(90deg,transparent 49.5%,rgba(125,201,255,.12) 50%,transparent 50.5%),linear-gradient(0deg,transparent 49.5%,rgba(125,201,255,.12) 50%,transparent 50.5%);overflow:hidden}.home-points i{position:absolute;width:9px;height:9px;border-radius:50%;background:#ff7b72;box-shadow:0 0 14px #ff7b72;transform:translate(-50%,-50%)}.home-points span{display:grid;place-items:center;height:100%;color:rgba(220,234,255,.45);font-size:12px}.home-state{min-height:260px;display:grid;place-items:center;align-content:center;gap:12px;color:rgba(220,234,255,.62)}.home-state--error{color:#ffb3ad}.home-spinner{width:28px;height:28px;border:2px solid rgba(83,229,200,.25);border-top-color:#53e5c8;border-radius:50%;animation:spin .8s linear infinite}.home-action{padding:8px 14px;border:1px solid rgba(83,229,200,.35);background:transparent;color:#53e5c8;cursor:pointer}.home-empty{color:rgba(220,234,255,.42);font-size:12px;padding:12px 0}@keyframes spin{to{transform:rotate(360deg)}}@media(max-width:1100px){.home-metrics{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.home-header{display:block}.home-badge{display:inline-block;margin-top:16px}.home-grid--two{grid-template-columns:1fr}.home-metrics{grid-template-columns:repeat(2,1fr)}.home-row{grid-template-columns:minmax(0,1fr) 70px}.home-row>span{display:none}}
</style>
