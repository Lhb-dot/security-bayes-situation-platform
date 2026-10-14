<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { getAdminDashboard, type DashboardOverview, type ScenarioKey } from '@/api/dashboardApi';
import { useUserStore } from '@/stores/userStore';
import DashDonut from '@/components/dashboard/DashDonut.vue';

type SceneId = Exclude<ScenarioKey, 'unknown'>;

interface SceneView {
  key: SceneId;
  name: string;
  shortName: string;
  path: string;
  userCount: number | null;
  adminCount: number | null;
  datasets: number;
  samples: number;
  trainedModels: number | null;
  publishedModels: number | null;
  inferences: number | null;
  events: number | null;
  pending: number | null;
  riskRate: number | null;
}

interface OverviewView {
  scenarioCount: number;
  datasetCount: number;
  sampleCount: number;
  algorithmCount: number;
  trainedModels: number | null;
  publishedModels: number;
  inferenceCount: number;
  reportCount: number | null;
  servedUserCount: number | null;
  eventCount: number;
  pendingCount: number;
  processingCount: number;
  resolvedCount: number;
  userCount: number;
  scenes: SceneView[];
}

const sceneDefinitions: Array<Pick<SceneView, 'key' | 'name' | 'shortName'>> = [
  { key: 'network', name: '网络安全', shortName: '网络' },
  { key: 'power', name: '电力系统', shortName: '电力' },
  { key: 'flight_deck', name: '舰面调度', shortName: '舰面' },
  { key: 'geological', name: '地质风险', shortName: '地质' },
];
const router = useRouter();
const userStore = useUserStore();
const handleLogout = async () => {
  await userStore.logout();
  await router.push('/login');
};

// 正式首页只显示聚合接口返回的数据；请求失败时清空看板，不使用设计快照。
const overview = ref<OverviewView | null>(null);
const error = ref('');
const loading = ref(false);
const clockNow = ref(new Date());
const clockDateFormatter = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' });
const clockTimeFormatter = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' });
const clockDate = computed(() => clockDateFormatter.format(clockNow.value).replace(/\//g, '-'));
const clockTime = computed(() => clockTimeFormatter.format(clockNow.value));
const OVERVIEW_REFRESH_MS = 15_000;
let clockTimer: number | undefined;
let overviewTimer: number | undefined;

const formatInt = (value: number | null) => value === null ? '—' : value.toLocaleString('zh-CN');
const formatSampleScale = (value: number) => value >= 10000 ? `${(value / 10000).toFixed(2)}万` : formatInt(value);
const formatRiskRate = (value: number | null) => value === null ? '—' : `${(value * 100).toFixed(1)}%`;
const riskBarHeight = (value: number | null) => `${Math.max(0, Math.min(1, value ?? 0)) * 100}%`;

const fromApi = (payload: DashboardOverview): OverviewView => ({
  scenarioCount: payload.totals.scenario_count,
  datasetCount: payload.totals.effective_dataset_count,
  sampleCount: payload.totals.effective_sample_count,
  algorithmCount: payload.totals.algorithm_count,
  trainedModels: payload.runtime.trained_model_count ?? null,
  publishedModels: payload.runtime.published_model_count,
  inferenceCount: payload.runtime.inference_count,
  reportCount: payload.runtime.report_count ?? null,
  servedUserCount: payload.runtime.served_user_count ?? null,
  eventCount: payload.runtime.risk_event_count,
  pendingCount: payload.runtime.pending_event_count,
  processingCount: payload.runtime.processing_event_count,
  resolvedCount: payload.runtime.resolved_event_count,
  userCount: payload.runtime.user_count,
  scenes: sceneDefinitions.flatMap((definition) => {
    const row = payload.scenarios.find((item) => item.scenario_key === definition.key);
    if (!row) return [];
    return [{
      ...definition,
      path: `/scenarios/${encodeURIComponent(row.code)}/dashboard`,
      userCount: row?.user_count ?? null,
      adminCount: row?.admin_count ?? null,
      datasets: row.dataset_count,
      samples: row.effective_sample_count,
      trainedModels: row?.trained_model_count ?? null,
      publishedModels: row?.published_model_count ?? null,
      inferences: row?.inference_count ?? null,
      events: row?.event_count ?? null,
      pending: row?.pending_count ?? null,
      riskRate: row?.risk_rate ?? null,
    }];
  }),
});

const loadOverview = async () => {
  if (loading.value) return;
  loading.value = true;
  try {
    const payload = await getAdminDashboard();
    if (!payload?.totals || !payload.runtime || !Array.isArray(payload.scenarios) ||
      [payload.totals.scenario_count, payload.totals.effective_dataset_count,
        payload.totals.effective_sample_count, payload.totals.algorithm_count,
        payload.runtime.published_model_count, payload.runtime.inference_count,
        payload.runtime.risk_event_count, payload.runtime.pending_event_count,
        payload.runtime.processing_event_count, payload.runtime.resolved_event_count,
        payload.runtime.user_count].some((value) => !Number.isFinite(value)) ||
      payload.scenarios.some((row) => typeof row.code !== 'string' ||
        !Number.isFinite(row.dataset_count) || !Number.isFinite(row.effective_sample_count))) {
      throw new Error('首页接口返回的数据不完整');
    }
    overview.value = fromApi(payload);
    error.value = '';
  } catch (err) {
    overview.value = null;
    error.value = err instanceof Error ? err.message : '首页实时数据加载失败';
  } finally {
    loading.value = false;
  }
};

const refreshWhenVisible = () => {
  clockNow.value = new Date();
  if (document.visibilityState === 'visible') void loadOverview();
};

onMounted(() => {
  void loadOverview();
  clockTimer = window.setInterval(() => { clockNow.value = new Date(); }, 1_000);
  overviewTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void loadOverview();
  }, OVERVIEW_REFRESH_MS);
  document.addEventListener('visibilitychange', refreshWhenVisible);
});

onUnmounted(() => {
  if (clockTimer !== undefined) window.clearInterval(clockTimer);
  if (overviewTimer !== undefined) window.clearInterval(overviewTimer);
  document.removeEventListener('visibilitychange', refreshWhenVisible);
});

const scenes = computed(() => overview.value?.scenes ?? []);
const sampleComposition = computed(() => scenes.value.map((scene) => ({ label: scene.name, value: scene.samples })));
const platformPipeline = [
  { number: '01', label: '场景接入' },
  { number: '02', label: '数据治理' },
  { number: '03', label: '模型训练' },
  { number: '04', label: '风险推理' },
  { number: '05', label: '事件处置' },
  { number: '06', label: '报告生成' },
];
const riskTotal = computed(() => (overview.value?.pendingCount ?? 0) + (overview.value?.processingCount ?? 0) + (overview.value?.resolvedCount ?? 0));
const resolutionRate = computed(() => riskTotal.value > 0
  ? Math.round((overview.value?.resolvedCount ?? 0) / riskTotal.value * 100)
  : 0);

const headlineMetrics = computed(() => {
  const data = overview.value;
  if (!data) return [];
  return [
    { label: '多域态势覆盖', value: formatInt(data.scenarioCount), unit: '大场景', tone: 'blue', exact: `${formatInt(data.scenarioCount)} 个场景` },
    { label: '异构数据资源', value: formatInt(data.datasetCount), unit: '套数据集', tone: 'cyan', exact: `${formatInt(data.datasetCount)} 个去重有效数据集` },
    { label: '有效样本规模', value: formatSampleScale(data.sampleCount), unit: '条样本', tone: 'amber', exact: `${formatInt(data.sampleCount)} 条有效样本` },
    { label: '算法能力储备', value: formatInt(data.algorithmCount), unit: '类算法', tone: 'violet', exact: `${formatInt(data.algorithmCount)} 个可用算法` },
  ];
});

// 与 App.vue 中系统管理员导航保持一致。
const adminNavigation = [
  { label: '首页', href: '/overview' },
  { label: '场景中心', href: '/scenarios' },
  { label: '数据集中心', href: '/datasets' },
  { label: '风险事件', href: '/alerts' },
  { label: 'AI模型训练', href: '/risk' },
  { label: '模型中心', href: '/models' },
  { label: '风险研判', href: '/inference' },
  { label: '推理记录', href: '/inference-records' },
  { label: '报告中心', href: '/reports' },
  { label: '用户管理', href: '/users' },
  { label: '系统设置', href: '/settings' },
];
</script>

<template>
  <main class="cockpit dash-page">
    <div class="cockpit-grid" aria-hidden="true"></div>
    <header class="screen-header">
      <div class="header-side header-side--left">AI SECURITY OPERATIONS CENTER</div>
      <div class="header-title"><span>基于贝叶斯网络的复杂系统智能态势感知平台</span><i></i></div>
      <div class="header-side header-side--right">
        <div class="nav-switcher">
          <button class="nav-switcher__trigger" type="button" aria-haspopup="true" aria-controls="admin-overview-navigation"><span class="live-dot" :class="{ 'live-dot--offline': !overview }"></span><span class="nav-switcher__label">平台运行总览</span><svg class="nav-switcher__chevron" viewBox="0 0 12 8" aria-hidden="true"><path d="m1 1 5 5 5-5" /></svg></button>
          <nav id="admin-overview-navigation" class="nav-switcher__menu" aria-label="系统导航">
            <span class="nav-switcher__menu-title">平台功能导航 <small>PLATFORM MODULES</small></span>
            <a v-for="item in adminNavigation" :key="item.href" :href="item.href" :aria-current="item.href === '/overview' ? 'page' : undefined">{{ item.label }}</a>
            <button type="button" class="nav-switcher__logout" @click="handleLogout">退出登录</button>
          </nav>
        </div>
      </div>
    </header>

    <section class="screen-body">
      <div class="screen-toolbar">
        <div class="toolbar-heading"><span class="section-code">PLATFORM COMMAND CENTER</span><strong>多域复杂系统态势感知驾驶舱</strong></div>
        <div class="toolbar-clock" aria-label="北京时间">
          <span>北京时间 <small>{{ clockDate }}</small></span>
          <time :datetime="clockNow.toISOString()">{{ clockTime }}</time>
        </div>
      </div>

      <div v-if="!overview" class="overview-state" role="status" aria-live="polite">
        <strong>{{ loading ? '正在读取平台实时数据…' : '平台数据暂不可用' }}</strong>
        <p v-if="!loading">{{ error || '请检查后台服务连接后重试。' }}</p>
        <button v-if="!loading" type="button" @click="loadOverview">重试连接</button>
      </div>
      <template v-else>
      <section class="headline-strip" aria-label="平台核心指标">
        <article v-for="metric in headlineMetrics" :key="metric.label" class="headline-stat" :class="`tone-${metric.tone}`" :title="metric.exact">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}<small>{{ metric.unit }}</small></strong>
        </article>
      </section>
      <section class="cockpit-columns">
        <aside class="wing wing--left">
          <section class="info-panel resource-panel">
            <div class="panel-head"><span class="panel-number">01</span><h2>场景成员分布</h2><small>SCENARIO MEMBERS</small></div>
            <div class="member-table">
              <div class="member-table-head"><span>场景</span><span>用户数</span><span>管理员数</span></div>
              <div v-for="scene in scenes" :key="scene.key" class="member-table-row">
                <span>{{ scene.name }}</span>
                <strong :title="scene.userCount === null ? '当前无实时账号数据' : `${scene.userCount} 位场景用户`">{{ formatInt(scene.userCount) }}</strong>
                <strong :title="scene.adminCount === null ? '当前无实时账号数据' : `${scene.adminCount} 位场景管理员`">{{ formatInt(scene.adminCount) }}</strong>
              </div>
            </div>
          </section>

          <section class="info-panel composition-panel">
            <div class="panel-head"><span class="panel-number">02</span><h2>场景样本构成</h2><small>DATA DISTRIBUTION</small></div>
            <div class="composition-chart"><DashDonut :items="sampleComposition" :size="158" center-label="有效样本" percent /></div>
          </section>

          <section class="info-panel risk-sample-panel">
            <div class="panel-head"><span class="panel-number">03</span><h2>场景风险样本占比</h2><small>RISK SAMPLE RATE</small></div>
            <div class="risk-column-chart" role="list" aria-label="各场景风险样本占比">
              <div v-for="scene in scenes" :key="scene.key" class="risk-column" :class="`risk-column--${scene.key}`" role="listitem" :aria-label="`${scene.name}：${formatRiskRate(scene.riskRate)}`">
                <div class="risk-column-plot">
                  <div v-if="scene.riskRate !== null" class="risk-column-fill" :style="{ height: riskBarHeight(scene.riskRate) }"><strong>{{ formatRiskRate(scene.riskRate) }}</strong></div>
                  <strong v-else class="risk-column-missing">—</strong>
                </div>
                <span class="risk-column-label">{{ scene.name }}</span>
              </div>
            </div>
          </section>
        </aside>

        <section class="main-stage">
          <div class="stage-topline"><span><i></i> MULTI-SCENARIO SITUATION MAP</span><span>已覆盖 {{ overview.scenarioCount }} 类场景</span></div>
          <div class="radar-map">
            <div class="map-ambient" aria-hidden="true"></div>
            <div class="radar-sweep" aria-hidden="true"></div>
            <div class="orbit orbit--outer" aria-hidden="true"></div>
            <div class="orbit orbit--middle" aria-hidden="true"></div>
            <div class="orbit orbit--inner" aria-hidden="true"></div>
            <div class="radar-cross radar-cross--horizontal" aria-hidden="true"></div>
            <div class="radar-cross radar-cross--vertical" aria-hidden="true"></div>
            <svg class="map-links" viewBox="0 0 1000 570" preserveAspectRatio="none" aria-hidden="true">
              <defs><linearGradient id="linkGrad"><stop offset="0" stop-color="#28d2d7" stop-opacity=".2"/><stop offset=".5" stop-color="#5fd7ed" stop-opacity=".9"/><stop offset="1" stop-color="#28d2d7" stop-opacity=".2"/></linearGradient></defs>
              <path class="flow-link" d="M500 285 Q390 170 215 145 M500 285 Q610 170 785 145 M500 285 Q390 400 215 425 M500 285 Q610 400 785 425" fill="none" stroke="url(#linkGrad)" stroke-width="2" stroke-dasharray="6 7" />
              <circle class="link-beacon" cx="215" cy="145" r="4" fill="#5ce3ef" /><circle class="link-beacon" cx="785" cy="145" r="4" fill="#5ce3ef" /><circle class="link-beacon" cx="215" cy="425" r="4" fill="#5ce3ef" /><circle class="link-beacon" cx="785" cy="425" r="4" fill="#5ce3ef" />
            </svg>

            <div class="hub"><span class="hub-kicker">BAYESIAN NETWORK</span><strong>复杂系统<br />态势感知</strong><span class="hub-divider"></span><small>{{ formatInt(overview.sampleCount) }} 条有效样本</small></div>

            <a v-for="scene in scenes" :key="scene.key" class="scene-node" :class="`scene-node--${scene.key}`" :href="scene.path" :aria-label="`进入${scene.name}场景大屏`">
              <span class="node-dot"></span><span class="node-name">{{ scene.name }}</span><strong>{{ formatInt(scene.samples) }}</strong><small>有效样本 · {{ scene.datasets }} 个数据集</small>
            </a>

          </div>
        </section>

        <aside class="wing wing--right">
          <section class="info-panel risk-panel">
            <div class="panel-head"><span class="panel-number">04</span><h2>风险事件闭环</h2><small>EVENT DISPOSITION</small></div>
            <div class="risk-total"><strong>{{ formatInt(overview.eventCount) }}</strong><span>累计风险事件</span><em>{{ riskTotal > 0 ? `处置率 ${resolutionRate}%` : '暂无运行态事件' }}</em></div>
            <div class="status-track"><i :style="{ width: `${riskTotal ? overview.pendingCount / riskTotal * 100 : 0}%` }"></i><i :style="{ width: `${riskTotal ? overview.processingCount / riskTotal * 100 : 0}%` }"></i><i :style="{ width: `${riskTotal ? overview.resolvedCount / riskTotal * 100 : 0}%` }"></i></div>
            <div class="risk-status"><div><i class="pending"></i><span>待处置</span><b>{{ overview.pendingCount }}</b></div><div><i class="processing"></i><span>处理中</span><b>{{ overview.processingCount }}</b></div><div><i class="resolved"></i><span>已处置</span><b>{{ overview.resolvedCount }}</b></div></div>
          </section>

          <section class="info-panel model-panel">
            <div class="panel-head"><span class="panel-number">05</span><h2>成果产出与服务覆盖</h2><small>PLATFORM OUTPUT</small></div>
            <div class="mini-stats" :class="{ 'mini-stats--dense': overview.trainedModels !== null || overview.reportCount !== null || overview.servedUserCount !== null }"><div v-if="overview.trainedModels !== null"><span>训练完成模型</span><strong>{{ formatInt(overview.trainedModels) }}</strong></div><div><span>已发布模型</span><strong>{{ formatInt(overview.publishedModels) }}</strong></div><div><span>推理记录</span><strong>{{ formatInt(overview.inferenceCount) }}</strong></div><div><span>风险事件</span><strong>{{ formatInt(overview.eventCount) }}</strong></div><div v-if="overview.reportCount !== null"><span>已生成报告</span><strong>{{ formatInt(overview.reportCount) }}</strong></div><div v-if="overview.servedUserCount !== null" title="至少发起过一次推理或生成过报告的去重账号数"><span>研判服务用户</span><strong>{{ formatInt(overview.servedUserCount) }}</strong></div><div><span>平台注册用户</span><strong>{{ formatInt(overview.userCount) }}</strong></div></div>
          </section>

          <section class="info-panel capability-panel">
            <div class="panel-head"><span class="panel-number">06</span><h2>平台链路能力</h2><small>CAPABILITY CHAIN</small></div>
            <ol class="capability-flow" aria-label="平台能力链路">
              <li v-for="step in platformPipeline" :key="step.number" class="capability-step">
                <span>{{ step.number }}</span><strong>{{ step.label }}</strong>
              </li>
            </ol>
          </section>
        </aside>
      </section>
      </template>

    </section>
  </main>
</template>

<style scoped>
.cockpit { --cyan: #56dbe7; --faint: #7e9db9; display: flex; flex-direction: column; min-height: 100vh; padding: 0; overflow: hidden; color: #dff5ff; background: radial-gradient(ellipse at 50% 58%, rgba(0,95,154,.20), transparent 47%), linear-gradient(180deg,#041121,#071a30 52%,#061220); font-family: var(--font-ui); }
.cockpit-grid { position: absolute; inset: 0; pointer-events: none; opacity: .24; background-image: linear-gradient(rgba(74,155,206,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(74,155,206,.12) 1px,transparent 1px); background-size: 42px 42px; mask-image: linear-gradient(180deg,#000,transparent 90%); }
.screen-header,.screen-body { position: relative; z-index: 1; }
.screen-header { z-index: 20; height: 67px; display: grid; grid-template-columns: 280px 1fr 225px; align-items: center; padding: 0 28px; border-bottom: 1px solid rgba(74,173,224,.25); background: linear-gradient(90deg,rgba(4,15,29,.93),rgba(8,40,69,.91),rgba(4,15,29,.93)); box-shadow: 0 10px 35px rgba(0,0,0,.25); }
.header-side { display: flex; align-items: center; gap: 10px; color: #9fc9df; font-size: 11px; line-height: 1.3; letter-spacing: .1em; }
.header-side--left { color: #80d5f0; font-size: 12px; font-weight: 600; letter-spacing: .12em; white-space: nowrap; text-shadow: 0 0 12px rgba(76,202,234,.28); }
.header-title { position: relative; justify-self: center; min-width: 480px; padding: 10px 32px 12px; border-bottom: 2px solid rgba(99,218,243,.75); clip-path: polygon(7% 0,93% 0,100% 100%,0 100%); background: linear-gradient(180deg,rgba(39,115,170,.32),rgba(8,52,96,.54)); color: #d7f8ff; font-size: clamp(19px,1.6vw,26px); font-weight: 750; letter-spacing: .1em; text-align: center; text-shadow: 0 0 14px rgba(74,218,245,.38); white-space: nowrap; }
.header-title i { position: absolute; bottom: -2px; left: 28%; right: 28%; height: 2px; background: #8cf7ff; box-shadow: 0 0 14px #56dce6; }
.header-side--right { justify-content: flex-end; white-space: nowrap; }.live-dot { width: 6px; height: 6px; border-radius: 50%; background: #5ee5b8; box-shadow: 0 0 10px #5ee5b8; }
.nav-switcher { position: relative; padding-bottom: 12px; margin-bottom: -12px; }.nav-switcher__trigger { display: grid; grid-template-columns: 7px minmax(0,1fr) 12px; align-items: center; gap: 10px; width: 184px; height: 36px; padding: 0 12px; border: 1px solid rgba(91,211,235,.58); border-radius: 4px; color: #d9f7ff; background: linear-gradient(120deg,rgba(18,90,126,.54),rgba(7,43,74,.88)); box-shadow: 0 0 0 2px rgba(50,174,214,.08),inset 0 1px rgba(152,239,247,.14); font-size: 13px; font-weight: 650; letter-spacing: .04em; cursor: pointer; }.nav-switcher__label { min-width: 0; text-align: left; white-space: nowrap; }.nav-switcher__trigger:hover,.nav-switcher:focus-within .nav-switcher__trigger { border-color: #87ebf4; box-shadow: 0 0 16px rgba(66,208,229,.23),inset 0 1px rgba(152,239,247,.2); }.nav-switcher__trigger:focus-visible { outline: 2px solid #a5f5ff; outline-offset: 2px; }.nav-switcher__chevron { display: block; width: 12px; height: 8px; fill: none; stroke: #89e8f2; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; transition: transform .18s ease; }.nav-switcher:hover .nav-switcher__chevron,.nav-switcher:focus-within .nav-switcher__chevron { transform: rotate(180deg); }
.nav-switcher__menu { position: absolute; top: 100%; right: 0; z-index: 30; display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 5px; width: 438px; max-width: calc(100vw - 28px); padding: 12px; border: 1px solid rgba(94,202,232,.48); border-radius: 4px; background: linear-gradient(135deg,rgba(8,37,65,.98),rgba(4,20,38,.98)); box-shadow: 0 18px 38px rgba(0,6,17,.65),inset 0 1px rgba(103,220,237,.14); opacity: 0; visibility: hidden; pointer-events: none; transform: translateY(-6px); transition: opacity .18s ease,transform .18s ease,visibility .18s ease; }.nav-switcher:hover .nav-switcher__menu,.nav-switcher:focus-within .nav-switcher__menu { opacity: 1; visibility: visible; pointer-events: auto; transform: translateY(0); }.nav-switcher__menu-title { grid-column: 1 / -1; display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 9px; border-bottom: 1px solid rgba(94,202,232,.2); color: #c9f3ff; font-size: 12px; font-weight: 650; letter-spacing: .08em; }.nav-switcher__menu-title small { color: #5f9fbb; font-size: 9px; letter-spacing: .13em; }.nav-switcher__menu a { padding: 9px 7px; border: 1px solid rgba(94,202,232,.12); border-radius: 3px; color: #a8ccde; background: rgba(47,125,161,.07); font-size: 11px; letter-spacing: 0; text-align: center; text-decoration: none; white-space: nowrap; }.nav-switcher__menu a:hover,.nav-switcher__menu a:focus-visible { border-color: rgba(109,223,237,.38); color: #e5fbff; background: rgba(45,137,172,.22); outline: none; }.nav-switcher__menu a[aria-current="page"] { border-color: rgba(103,217,229,.48); color: #dfffff; background: rgba(58,166,197,.23); }
.screen-body { display: flex; flex: 1; flex-direction: column; width: min(1880px,calc(100% - 44px)); min-height: 0; margin: 0 auto; }
.overview-state { display: flex; flex: 1; align-items: center; justify-content: center; flex-direction: column; gap: 14px; min-height: 300px; color: #9fc9df; text-align: center; }
.overview-state strong { color: #d7f5ff; font-size: 21px; letter-spacing: .08em; }
.overview-state p { max-width: 70ch; margin: 0; font-size: 12px; }
.overview-state button,.nav-switcher__logout { border: 1px solid rgba(94,202,232,.35); border-radius: 3px; color: #c6eafa; background: rgba(47,125,161,.15); cursor: pointer; }
.overview-state button { padding: 9px 20px; font-size: 12px; }
.overview-state button:hover,.nav-switcher__logout:hover { border-color: #87ebf4; background: rgba(45,137,172,.3); }
.nav-switcher__logout { padding: 9px 7px; font-size: 11px; }
.screen-toolbar { height: 73px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }.toolbar-heading { display: grid; gap: 2px; }.section-code,.panel-head small { color: #4e8eae; font-size: 9px; letter-spacing: .18em; }.toolbar-heading strong { color: #d7f5ff; font-size: 17px; letter-spacing: .06em; }.toolbar-clock { display: grid; justify-items: end; gap: 2px; min-width: 190px; padding: 3px 0 3px 14px; border-left: 2px solid rgba(90,218,233,.6); text-align: right; white-space: nowrap; }.toolbar-clock > span { color: #80b6cb; font-size: 10px; letter-spacing: .08em; }.toolbar-clock small { margin-left: 7px; color: #6e9db4; font-size: 10px; letter-spacing: .04em; }.toolbar-clock time { color: #d7f9ff; font-family: Consolas,monospace; font-size: 23px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.05; letter-spacing: .1em; text-shadow: 0 0 12px rgba(80,214,239,.42); }
.headline-strip { display: grid; grid-template-columns: repeat(8,minmax(0,1fr)); gap: 9px; margin-bottom: 11px; }.headline-stat { --accent: #58b9f3; position: relative; min-width: 0; height: 85px; padding: 12px 13px; border: 1px solid rgba(75,159,208,.22); background: linear-gradient(125deg,rgba(12,43,70,.90),rgba(5,25,45,.83)); box-shadow: inset 0 1px rgba(93,211,234,.08); }.headline-stat::before { position: absolute; content: ''; top: 0; left: 0; width: 44px; height: 2px; background: var(--accent); box-shadow: 0 0 12px var(--accent); }.headline-stat::after { position: absolute; content: ''; right: 7px; bottom: 6px; width: 18px; height: 18px; border-right: 1px solid rgba(87,163,203,.15); border-bottom: 1px solid rgba(87,163,203,.15); }.headline-stat > span { display: block; color: #8cafc8; font-size: 10px; white-space: nowrap; }.headline-stat strong { display: block; margin-top: 3px; overflow: hidden; color: var(--accent); font-size: clamp(19px,1.65vw,29px); font-weight: 700; font-variant-numeric: tabular-nums; text-overflow: ellipsis; white-space: nowrap; }.headline-stat small { margin-left: 4px; color: #7c9fb7; font-size: 10px; font-weight: 400; }.tone-cyan { --accent:#56e0dc; }.tone-amber { --accent:#f7ca68; }.tone-violet { --accent:#b2a1f7; }.tone-blue { --accent:#62b7f5; }
.cockpit-columns { display: grid; flex: 1; grid-template-columns: minmax(270px, .93fr) minmax(520px, 2.25fr) minmax(280px, .96fr); gap: 10px; min-height: min(645px,calc(100vh - 272px)); }.wing { display: grid; gap: 10px; grid-template-rows: 1fr 1.22fr .8fr; min-width: 0; }.wing--right { grid-template-rows: 1.08fr .96fr .98fr; }
.info-panel,.main-stage { position: relative; min-width: 0; border: 1px solid rgba(70,164,218,.25); background: linear-gradient(145deg,rgba(8,31,56,.89),rgba(4,21,39,.93)); box-shadow: inset 0 0 28px rgba(21,81,123,.1); }.info-panel::before,.main-stage::before { position: absolute; content: ''; top: -1px; left: -1px; width: 35px; height: 20px; border-top: 2px solid #62dcf2; border-left: 2px solid #62dcf2; pointer-events: none; }.info-panel::after,.main-stage::after { position: absolute; content: ''; right: -1px; bottom: -1px; width: 35px; height: 20px; border-right: 2px solid #62dcf2; border-bottom: 2px solid #62dcf2; pointer-events: none; }.info-panel { padding: 13px 14px; overflow: hidden; }.panel-head { display: flex; align-items: baseline; gap: 8px; padding-bottom: 8px; border-bottom: 1px solid rgba(90,167,206,.16); }.panel-number { color: #4acddd; font-size: 11px; font-family: Consolas,monospace; }.panel-head h2 { margin: 0; color: #cceefa; font-size: 13px; font-weight: 650; white-space: nowrap; }.panel-head small { margin-left: auto; overflow: hidden; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }
.member-table { display: grid; margin-top: 5px; }.member-table-head,.member-table-row { display: grid; grid-template-columns: minmax(0,1.2fr) minmax(0,.65fr) minmax(0,.85fr); align-items: center; gap: 5px; }.member-table-head { min-height: 19px; color: #6599b4; font-size: 9px; }.member-table-head span:not(:first-child),.member-table-row strong { text-align: right; }.member-table-row { min-height: 28px; border-top: 1px dashed rgba(111,183,221,.12); }.member-table-row span { overflow: hidden; color: #9fc2d7; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }.member-table-row strong { color: #91ddf7; font-size: 16px; font-weight: 650; font-variant-numeric: tabular-nums; }
.composition-panel { display: flex; flex-direction: column; }.composition-chart { display: grid; flex: 1; place-items: center; min-height: 175px; }.composition-chart :deep(.d-donut) { flex-wrap: nowrap; gap: 5px; }.composition-chart :deep(svg) { flex: 0 0 auto; max-width: 48%; height: auto; }.composition-chart :deep(.d-legend) { min-width: 0; gap: 6px; font-size: 10px; }.composition-chart :deep(.d-lgv) { font-size: 10px; }
.risk-sample-panel { display: flex; flex-direction: column; }.risk-column-chart { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); align-items: end; gap: 4px; flex: 1; min-height: 0; padding-top: 8px; }.risk-column { --bar: #5bb9f4; display: grid; justify-items: center; gap: 5px; min-width: 0; }.risk-column--power { --bar: #51ded4; }.risk-column--flight_deck { --bar: #f4c66d; }.risk-column--geological { --bar: #f08485; }.risk-column-plot { display: flex; align-items: flex-end; justify-content: center; box-sizing: border-box; width: 100%; height: 65px; padding-top: 14px; border-bottom: 1px solid rgba(121,205,231,.35); background: repeating-linear-gradient(to top,transparent 0 15px,rgba(89,166,207,.08) 16px); }.risk-column-fill { position: relative; width: 28px; max-width: 70%; min-height: 2px; border-radius: 3px 3px 0 0; background: linear-gradient(180deg,var(--bar),rgba(31,103,149,.55)); box-shadow: 0 0 13px var(--bar),inset 0 1px rgba(255,255,255,.32); }.risk-column-fill strong { position: absolute; bottom: calc(100% + 3px); left: 50%; transform: translateX(-50%); color: #d9f8ff; font-size: 10px; font-weight: 700; font-variant-numeric: tabular-nums; white-space: nowrap; }.risk-column-missing { align-self: center; color: #76a8bb; font-size: 13px; }.risk-column-label { color: #94bdd1; font-size: 9px; white-space: nowrap; }
.main-stage { display: flex; flex-direction: column; overflow: hidden; background: radial-gradient(ellipse at center,rgba(12,92,145,.29),transparent 50%),linear-gradient(180deg,rgba(6,31,57,.86),rgba(3,20,40,.96)); }.stage-topline { display: flex; align-items: center; justify-content: space-between; padding: 13px 17px 0; color: #64a5c5; font-size: 9px; letter-spacing: .12em; }.stage-topline i { display: inline-block; width: 6px; height: 6px; margin-right: 5px; border-radius: 50%; background: #5ce0e0; box-shadow: 0 0 9px #5ce0e0; }.stage-topline span:last-child { letter-spacing: 0; }
.radar-map { position: relative; flex: 1; min-height: 420px; isolation: isolate; }.map-ambient { position: absolute; inset: 0; background: radial-gradient(ellipse at center,rgba(32,177,227,.13),transparent 47%),repeating-radial-gradient(circle at center,transparent 0 44px,rgba(58,157,209,.055) 45px 46px); mask-image: radial-gradient(circle,#000 5%,transparent 70%); }.orbit { position: absolute; left: 50%; top: 51%; border: 1px solid rgba(46,188,218,.15); border-radius: 50%; transform: translate(-50%,-50%); box-shadow: 0 0 20px rgba(0,146,190,.07),inset 0 0 20px rgba(0,146,190,.07); }.orbit--outer { width: min(82%,590px); aspect-ratio: 1; border-style: dashed; }.orbit--middle { width: min(62%,430px); aspect-ratio: 1; }.orbit--inner { width: min(40%,280px); aspect-ratio: 1; border-color: rgba(91,227,238,.35); }.radar-cross { position: absolute; background: linear-gradient(90deg,transparent,rgba(50,160,211,.12),transparent); }.radar-cross--horizontal { top: 51%; left: 6%; right: 6%; height: 1px; }.radar-cross--vertical { top: 8%; bottom: 8%; left: 50%; width: 1px; background: linear-gradient(transparent,rgba(50,160,211,.12),transparent); }.map-links { position: absolute; inset: 0; width: 100%; height: 100%; }
.hub { position: absolute; left: 50%; top: 51%; display: flex; align-items: center; justify-content: center; flex-direction: column; width: clamp(160px,19vw,240px); aspect-ratio: 1; border: 2px solid rgba(94,226,242,.67); border-radius: 50%; transform: translate(-50%,-50%); background: radial-gradient(circle,rgba(26,116,167,.72),rgba(8,47,91,.90) 65%,rgba(3,28,55,.95)); box-shadow: 0 0 0 9px rgba(34,150,199,.08),0 0 0 20px rgba(34,150,199,.055),0 0 38px rgba(50,191,231,.28),inset 0 0 34px rgba(52,180,224,.28); text-align: center; }.hub-kicker { color: #70dff1; font-size: 9px; letter-spacing: .22em; }.hub strong { margin: 10px 0; color: #f0fdff; font-size: clamp(19px,2vw,28px); font-weight: 750; line-height: 1.35; letter-spacing: .08em; text-shadow: 0 0 16px rgba(91,231,252,.6); }.hub-divider { width: 36px; height: 1px; background: #66dceb; }.hub small { margin-top: 9px; color: #9ccddd; font-size: 10px; }
.scene-node { position: absolute; display: grid; gap: 2px; width: clamp(128px,12vw,176px); padding: 10px 11px 9px; border: 1px solid rgba(88,201,230,.38); clip-path: polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px); color: #bfe7f6; background: linear-gradient(130deg,rgba(8,52,82,.93),rgba(5,32,61,.92)); text-align: left; text-decoration: none; cursor: pointer; box-shadow: inset 0 0 20px rgba(43,160,202,.13); transition: border-color .2s,background .2s,transform .2s; }.scene-node:hover { border-color: #6de6ec; background: linear-gradient(130deg,rgba(14,91,128,.96),rgba(7,45,80,.95)); transform: translateY(-2px); }.scene-node--network { left: 6%; top: 14%; }.scene-node--power { right: 6%; top: 14%; }.scene-node--flight_deck { left: 6%; bottom: 14%; }.scene-node--geological { right: 6%; bottom: 14%; }.node-dot { position: absolute; top: 14px; right: 12px; width: 5px; height: 5px; border-radius: 50%; background: #5adbe2; box-shadow: 0 0 10px #5adbe2; }.node-name { color: #9fcee1; font-size: 11px; }.scene-node strong { color: #dcf9ff; font-size: 22px; font-variant-numeric: tabular-nums; line-height: 1.2; }.scene-node small { color: #6f9eb5; font-size: 9px; }
.risk-panel { display: flex; flex-direction: column; }.risk-total { display: flex; align-items: baseline; gap: 8px; margin: 10px 0 6px; }.risk-total strong { color: #72dded; font-size: 36px; line-height: 1; font-variant-numeric: tabular-nums; }.risk-total span { color: #9ac2d6; font-size: 10px; }.risk-total em { margin-left: auto; color: #7198ad; font-size: 9px; font-style: normal; white-space: nowrap; }.status-track { display: flex; height: 5px; border-radius: 10px; overflow: hidden; background: rgba(106,168,202,.13); }.status-track i:first-child { background: #f08275; }.status-track i:nth-child(2) { background: #f1c267; }.status-track i:nth-child(3) { background: #56d6bb; }.risk-status { display: grid; grid-template-columns: repeat(3,1fr); gap: 5px; margin-top: auto; }.risk-status div { display: grid; gap: 5px; padding: 7px 6px; border: 1px solid rgba(96,168,207,.15); background: rgba(21,65,98,.26); }.risk-status i { width: 6px; height: 6px; border-radius: 50%; }.risk-status i.pending { background: #f08275; }.risk-status i.processing { background: #f1c267; }.risk-status i.resolved { background: #56d6bb; }.risk-status span { color: #82a9bd; font-size: 9px; }.risk-status b { color: #d5f4ff; font-size: 17px; font-weight: 600; font-variant-numeric: tabular-nums; }
.model-panel { display: flex; flex-direction: column; }.mini-stats { display: grid; grid-template-columns: repeat(2,1fr); gap: 6px; margin-top: 9px; }.mini-stats > div { min-height: 52px; padding: 7px 10px; border: 1px solid rgba(96,168,207,.17); background: rgba(16,60,93,.25); }.mini-stats span { display: block; color: #82a5ba; font-size: 9px; }.mini-stats strong { display: block; margin-top: 1px; color: #7edfe9; font-size: 19px; line-height: 1; font-variant-numeric: tabular-nums; }
.capability-panel { display: flex; flex-direction: column; }.capability-flow { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); grid-template-rows: repeat(2,minmax(0,1fr)); gap: 16px 16px; flex: 1; min-height: 0; margin: 10px 0 0; padding: 0; list-style: none; }.capability-step { position: relative; display: flex; align-items: center; justify-content: center; flex-direction: column; min-width: 0; padding: 3px 2px; border: 1px solid rgba(95,206,228,.34); border-radius: 3px; background: linear-gradient(135deg,rgba(19,84,123,.45),rgba(6,43,75,.67)); box-shadow: inset 0 1px rgba(148,233,244,.1),0 0 12px rgba(46,171,210,.08); text-align: center; }.capability-step span { color: #57cadd; font-family: Consolas,monospace; font-size: 9px; line-height: 1.2; }.capability-step strong { color: #d0f3ff; font-size: 11px; font-weight: 650; white-space: nowrap; }.capability-step::after { position: absolute; color: #5ccee0; font-size: 20px; font-weight: 400; line-height: 1; text-shadow: 0 0 9px rgba(71,215,237,.45); }.capability-step:nth-child(-n+2)::after { content: '›'; top: 50%; right: -13px; transform: translateY(-50%); }.capability-step:nth-child(3)::after { content: '↓'; bottom: -18px; left: 50%; transform: translateX(-50%); font-size: 16px; }.capability-step:nth-child(4) { grid-column: 3; grid-row: 2; }.capability-step:nth-child(5) { grid-column: 2; grid-row: 2; }.capability-step:nth-child(6) { grid-column: 1; grid-row: 2; border-color: rgba(103,228,198,.55); background: linear-gradient(135deg,rgba(21,96,103,.48),rgba(6,55,72,.7)); }.capability-step:nth-child(4)::after,.capability-step:nth-child(5)::after { content: '‹'; top: 50%; left: -13px; transform: translateY(-50%); }.capability-step:nth-child(6) strong { color: #b9f9e9; }
.headline-strip { grid-template-columns: repeat(4,minmax(0,1fr)); gap: 10px; margin-bottom: 11px; }.headline-stat { height: 82px; }.headline-stat strong { font-size: clamp(23px,2vw,32px); }
.model-panel .mini-stats { flex: 1; min-height: 0; grid-auto-rows: minmax(0,1fr); }
.model-panel .mini-stats > div { display: flex; flex-direction: column; justify-content: center; min-height: 0; padding: 4px 8px; }.model-panel .mini-stats strong { font-size: 19px; }
.model-panel .mini-stats--dense { grid-template-columns: repeat(3,minmax(0,1fr)); }.model-panel .mini-stats--dense > div { padding: 3px 7px; }.model-panel .mini-stats--dense strong { font-size: 16px; }.model-panel .mini-stats--dense > div:last-child:nth-child(3n+1) { grid-column: 1 / -1; }.model-panel .mini-stats--dense > div:last-child:nth-child(3n+2) { grid-column: span 2; }
.radar-sweep { position: absolute; left: 50%; top: 51%; width: min(82%,590px); aspect-ratio: 1; border-radius: 50%; pointer-events: none; background: conic-gradient(from 0deg, transparent 0deg 285deg, rgba(49,190,219,.03) 319deg, rgba(80,230,241,.29) 355deg, transparent 360deg); mask-image: radial-gradient(circle,transparent 0 27%,#000 31% 66%,transparent 71%); transform: translate(-50%,-50%) rotate(0deg); animation: radar-rotate 14s linear infinite; }
.orbit--outer { animation: radar-rotate 42s linear infinite reverse; }.orbit--middle { border-style: dotted; animation: radar-rotate 32s linear infinite; }.orbit--inner { animation: orbit-breathe 5s ease-in-out infinite; }
.flow-link { animation: link-flow 1.6s linear infinite; }.link-beacon { transform-box: fill-box; transform-origin: center; animation: beacon-pulse 2.6s ease-in-out infinite; }.link-beacon:nth-of-type(2) { animation-delay: .65s; }.link-beacon:nth-of-type(3) { animation-delay: 1.3s; }.link-beacon:nth-of-type(4) { animation-delay: 1.95s; }
.hub { animation: hub-breathe 5s ease-in-out infinite; }.hub::after { position: absolute; content: ''; inset: -14px; border: 1px solid rgba(101,231,245,.34); border-radius: 50%; pointer-events: none; animation: hub-ring 4s ease-out infinite; }
.node-dot,.stage-topline i,.live-dot { animation: beacon-pulse 2.8s ease-in-out infinite; }.scene-node--power .node-dot { animation-delay: .7s; }.scene-node--flight_deck .node-dot { animation-delay: 1.4s; }.scene-node--geological .node-dot { animation-delay: 2.1s; }
.live-dot--offline { animation: none; background: #708498; box-shadow: none; }
.info-panel::before,.main-stage::before { animation: edge-glow 5s ease-in-out infinite; }.info-panel::after,.main-stage::after { animation: edge-glow 5s ease-in-out 2.5s infinite; }
.scene-node:focus-visible { outline: 2px solid #9ef3ff; outline-offset: 3px; }
@keyframes radar-rotate { to { transform: translate(-50%,-50%) rotate(360deg); } }
@keyframes orbit-breathe { 50% { border-color: rgba(113,236,245,.6); box-shadow: 0 0 28px rgba(36,190,223,.18),inset 0 0 28px rgba(36,190,223,.18); } }
@keyframes link-flow { to { stroke-dashoffset: -26; } }
@keyframes beacon-pulse { 50% { opacity: .48; transform: scale(.7); } }
@keyframes hub-breathe { 50% { box-shadow: 0 0 0 9px rgba(34,150,199,.1),0 0 0 20px rgba(34,150,199,.07),0 0 58px rgba(50,191,231,.45),inset 0 0 42px rgba(52,180,224,.35); } }
@keyframes hub-ring { 0% { opacity: .72; transform: scale(.91); } 80%,100% { opacity: 0; transform: scale(1.17); } }
@keyframes edge-glow { 50% { opacity: .38; } }
@media (prefers-reduced-motion: reduce) { .cockpit *, .cockpit *::before, .cockpit *::after { animation: none !important; transition-duration: .01ms !important; } }
@media (max-width:1450px) { .screen-header { grid-template-columns: 245px 1fr 215px; padding: 0 14px; }.header-side--left { font-size: 11px; letter-spacing: .09em; }.header-title { min-width: 0; font-size: 20px; }.nav-switcher__trigger { font-size: 12px; }.cockpit-columns { grid-template-columns: minmax(245px,.95fr) minmax(440px,2fr) minmax(245px,.95fr); }.scene-node { width: 132px; } }
@media (max-width:1100px) { .screen-header { grid-template-columns: 205px 1fr 170px; }.header-side--left { font-size: 9px; letter-spacing: .06em; }.header-title { padding-inline: 10px; font-size: 16px; letter-spacing: .02em; }.nav-switcher__trigger { width: 164px; font-size: 11px; }.headline-strip { grid-template-columns: repeat(4,minmax(0,1fr)); }.cockpit-columns { grid-template-columns: minmax(240px,1fr) minmax(430px,1.75fr); }.wing--right { grid-column: 1 / -1; grid-template-columns: repeat(3,minmax(0,1fr)); grid-template-rows: none; }.main-stage { min-height: 590px; }.wing--right .info-panel { min-height: 190px; } }
@media (max-width:750px) { .screen-header { grid-template-columns: 1fr; height: auto; min-height: 72px; padding: 8px 10px; }.header-side--left { display: none; }.header-side--right { justify-content: center; margin-top: 8px; }.nav-switcher__menu { left: 50%; right: auto; grid-template-columns: repeat(2,minmax(0,1fr)); transform: translate(-50%,-6px); }.nav-switcher:hover .nav-switcher__menu,.nav-switcher:focus-within .nav-switcher__menu { transform: translate(-50%,0); }.header-title { font-size: 14px; white-space: normal; }.screen-body { width: calc(100% - 20px); }.screen-toolbar { height: auto; min-height: 82px; flex-wrap: wrap; padding: 10px 0; }.headline-strip { grid-template-columns: repeat(2,minmax(0,1fr)); }.cockpit-columns { grid-template-columns: 1fr; }.wing { grid-template-rows: auto; }.wing--right { display: grid; grid-column: auto; grid-template-columns: 1fr; }.main-stage { min-height: 570px; }.radar-map { min-height: 445px; }.scene-node { width: 124px; padding: 7px; }.scene-node--network,.scene-node--flight_deck { left: 2%; }.scene-node--power,.scene-node--geological { right: 2%; }.scene-node strong { font-size: 18px; }.hub { width: 156px; }.hub strong { font-size: 18px; } }
</style>
