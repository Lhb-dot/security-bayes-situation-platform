<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue';
import type { FlightdeckProfile, GeologicalProfile, NetworkProfile, PowerProfile, ScenarioProfile, ScenarioWorkspace } from '@/api/dashboardApi';
import type { ApiScenario } from '@/api/scenarioApi';
import type { UserRole } from '@/types/security';
import { rolesForPath } from '@/router/access';
import { SCENE_STYLES } from '../adminOverview';
import ProfileChart from './ProfileChart.vue';
import CoverageMatrix from './CoverageMatrix.vue';
import { governanceRows, modelingChart, profileNumber as number, profilePercent as percent, runtimeCharts, scenarioCharts } from './profileCharts';
import './scenarioScreen.css';

const props = defineProps<{
  data: ScenarioProfile | null; runtime: ScenarioWorkspace | null; scenarios: ApiScenario[];
  members: { total: number; enabled: number; disabled: number } | null;
  role: UserRole | null; userName: string; loading: boolean; error: string;
  runtimeError: string; memberError: string; loggingOut: boolean; updatedAt: string;
}>();
const emit = defineEmits<{ navigate: [href: string]; refresh: []; logout: [] }>();
const scene = computed(() => {
  const key = props.data?.scenario_key;
  return key && key !== 'unknown' ? SCENE_STYLES[key] : SCENE_STYLES.network;
});
const charts = computed(() => props.data ? scenarioCharts(props.data) : null);
const models = computed(() => props.data ? modelingChart(props.data) : null);
const operations = computed(() => runtimeCharts(props.runtime));
const governance = computed(() => props.data ? governanceRows(props.data).slice(0, 6) : []);
const governanceTitle = computed(() => ({ network: '风险标签口径', power: '遥测质量与基线', flight_deck: '编码形态与内容分组', geological: '数据职责与风险口径', unknown: '数据口径' })[props.data?.scenario_key ?? 'unknown']);
const governanceNote = computed(() => {
  const d = props.data;
  if (d?.scenario_key === 'geological') {
    const conflicts = (d as GeologicalProfile).factor_coverage.filter(item => item.datasets.length > 1 && !item.consistent_binning).map(item => item.factor);
    return conflicts.length ? `分箱不一致：${conflicts.join('、')}；跨源统计需先对齐口径` : '多源因子未发现分箱冲突';
  }
  if (d?.scenario_key === 'flight_deck') return `同内容文件合并统计 · 内容冗余率 ${percent((d as FlightdeckProfile).redundancy.redundancy_rate)}`;
  if (d?.scenario_key === 'network') return '偏离 = 数据集正类占比 / 场景合并占比 · 全部口径见数据集详情';
  return '工频合格区间 49.8–50.2 Hz · 基线仅校验参量均值';
});
const metrics = computed(() => {
  const d = props.data;
  if (!d) return [];
  const specialty = d.scenario_key === 'network' ? { label: '目的端口覆盖', value: number((d as NetworkProfile).distinct_port_count, 0), unit: '种', detail: 'NF-UNSW · 去重目的端口' }
    : d.scenario_key === 'power' ? { label: '设备类型覆盖', value: number((d as PowerProfile).device_fault_rates.length, 0), unit: '类', detail: '按设备名称去重统计' }
    : d.scenario_key === 'flight_deck' ? { label: '最小间距均值', value: number((d as FlightdeckProfile).distance.min?.mean, 2), unit: '原始单位', detail: '数值原始集 · 样本最小间距的均值' }
    : { label: '可用地形因子', value: number((d as GeologicalProfile).factor_count, 0), unit: '项', detail: '主因子集 · 可计算统计量的字段' };
  return [
    { label: '有效数据资源', value: number(d.dataset_count, 0), unit: '组', detail: `${d.dataset_file_count} 份物理文件 · 按内容指纹去重` },
    { label: '有效样本规模', value: number(d.sample_count, 0), unit: '条', detail: '每个内容分组取代表数据集统计' },
    { label: '登记正类占比', value: d.sample_count ? percent(d.risk_rate) : '—', unit: '', detail: '去重正类 / 全部有效样本；非实时风险率' }, specialty,
  ];
});
const nav = computed(() => [
  { label: '平台首页', href: '/overview' }, { label: '数据集', href: '/datasets' },
  { label: '模型训练', href: '/risk' }, { label: '模型中心', href: '/models' },
  { label: '风险研判', href: '/inference' }, { label: '推理记录', href: '/inference-records' },
  { label: '风险事件', href: '/alerts' }, { label: '报告中心', href: '/reports' },
  { label: '用户管理', href: '/users' }, { label: '设置', href: '/settings' },
].filter(item => props.role && rolesForPath(item.href).includes(props.role)));
const navIcons: Record<string, string> = {
  '/overview': 'M3 10.5 12 3l9 7.5 M5 9v11h14V9 M9 20v-6h6v6',
  '/datasets': 'M4 5c0-2 16-2 16 0s-16 2-16 0 M4 5v14c0 2 16 2 16 0V5 M4 12c0 2 16 2 16 0',
  '/risk': 'M12 3l8 5v8l-8 5-8-5V8z M4 8l8 5 8-5 M12 13v8',
  '/models': 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  '/inference': 'M3 17l5-5 4 3 8-10 M14 5h6v6 M3 21h18',
  '/inference-records': 'M6 3h9l4 4v14H6z M15 3v5h4 M9 12h7 M9 16h7',
  '/alerts': 'M12 3l8 4v5c0 4.5-3.3 7.6-8 9-4.7-1.4-8-4.5-8-9V7z M12 8v5 M12 16h.01',
  '/reports': 'M5 3h14v18H5z M8 16v-3 M12 16V8 M16 16v-5',
  '/users': 'M16 11a3 3 0 1 0-2.4-4.8 M4 20v-2c0-2.2 2.1-4 5-4s5 1.8 5 4v2z M17 14c2 .5 3 1.8 3 4v2',
  '/settings': 'M4 7h16 M4 17h16 M8 4v6 M16 14v6',
};
const sceneKeys: Record<string, keyof typeof SCENE_STYLES> = { network_security: 'network', power_system: 'power', flightdeck_operation: 'flight_deck', geological_risk: 'geological' };
const visibleScenes = computed(() => props.scenarios.map(item => ({ ...item, style: SCENE_STYLES[sceneKeys[item.code]!] })).filter(item => item.style));
const minimumRows = computed(() => Math.max(3, governance.value.length));
const visibilityName = (value: string) => ({ platform: '平台', company: '公司', personal: '个人' })[value] ?? value;
const statusTitle = computed(() => [props.error, props.error && props.data ? '画像保留上次成功读取的数据' : '', props.updatedAt ? `画像上次更新：${props.updatedAt}` : '', '点击刷新'].filter(Boolean).join(' · '));
async function fullscreen() {
  try {
    if (document.fullscreenElement) await document.exitFullscreen();
    else await document.documentElement.requestFullscreen();
  } catch { /* 浏览器不支持全屏时保留当前大屏布局。 */ }
}
onMounted(() => document.documentElement.classList.add('scenario-screen-mode'));
onUnmounted(() => document.documentElement.classList.remove('scenario-screen-mode'));
</script>

<template>
  <main class="scenario-profile" :class="data ? `scene-${data.scenario_key}` : ''" :style="{ '--scene-accent': scene.color }">
    <header class="sp-masthead">
      <span class="sp-brand"><svg viewBox="0 0 24 24"><path d="M12 2 21 6v6c0 5-5 8-9 10-4-2-9-5-9-10V6z M8 12l3 3 5-6" /></svg>AI SECURITY OPERATIONS CENTER</span>
      <div class="sp-platform-title"><i></i><h1>基于贝叶斯网络的复杂系统智能态势感知平台</h1><i></i></div>
      <div class="sp-account"><button class="sp-status" :class="{ 'is-error': error }" :title="statusTitle" :disabled="loading" @click="emit('refresh')">{{ loading ? '更新中…' : error ? '更新失败 · 重试' : '刷新数据 ↻' }}</button><span class="sp-user-name" :title="userName">{{ userName }}</span><button class="sp-logout" :disabled="loggingOut" @click="emit('logout')">退出</button><button class="sp-fullscreen" title="切换全屏" aria-label="切换全屏" @click="fullscreen"><svg viewBox="0 0 24 24"><path d="M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5" /></svg></button></div>
    </header>
    <div v-if="data && charts && models" class="sp-content">
      <section class="sp-command">
        <div class="sp-scene-title"><h2>{{ data.scenario_name }}<small>态势总览</small></h2></div>
        <nav aria-label="场景功能入口"><button v-for="item in nav" :key="item.href" @click="emit('navigate', item.href)"><svg v-if="navIcons[item.href]" viewBox="0 0 24 24" aria-hidden="true"><path :d="navIcons[item.href]" /></svg>{{ item.label }}</button></nav>
      </section>
      <section class="sp-metrics" aria-label="场景核心指标">
        <article v-for="(metric, i) in metrics" :key="metric.label" :style="{ '--metric-color': ['#69b7ff', '#4cdac6', '#efc17a', scene.color][i] }" :title="metric.detail">
          <div class="sp-metric-label">{{ metric.label }}</div>
          <div class="sp-metric-value"><strong>{{ metric.value }}</strong><span>{{ metric.unit }}</span></div>
          <p>{{ metric.detail }}</p>
        </article>
      </section>
      <div :key="data.scenario_key" class="sp-grid">
        <div class="sp-column"><ProfileChart :spec="charts.left[0]" /><ProfileChart :spec="charts.left[1]" /><ProfileChart :spec="models" /></div>
        <div class="sp-center">
          <section class="sp-panel sp-hero">
            <div class="sp-hero-heading"><div><h3>{{ charts.main.title }}</h3></div><span class="sp-source-badge"><i></i>数据画像</span></div>
            <CoverageMatrix v-if="['network', 'geological'].includes(data.scenario_key)" :data="data" />
            <ProfileChart v-else :spec="charts.main" />
            <div class="sp-governance" :style="{ '--gov-rows': minimumRows }">
              <header><h3><i></i>{{ governanceTitle }}</h3></header>
              <div v-for="row in governance" :key="row.name" class="sp-governance-row"><span class="sp-governance-name" :title="row.name">{{ row.name }}</span><span class="sp-governance-detail" :title="row.detail">{{ row.detail }}</span><strong :class="{ 'is-warning': row.warn }" :title="row.status">{{ row.status }}</strong></div>
              <p class="sp-governance-note" :title="governanceNote">{{ governanceNote }}</p>
            </div>
          </section>
          <section class="sp-panel sp-assets">
            <header class="sp-panel-heading"><h3>数据资产台账</h3><span class="sp-assets-caption">按物理文件展示</span></header>
            <div class="sp-table-wrap"><table><thead><tr><th>数据集 / 版本</th><th>样本量</th><th>字段</th><th>范围</th></tr></thead><tbody><tr v-for="item in data.datasets.slice(0, 6)" :key="item.dataset_id"><td><button :title="item.logical_id" @click="emit('navigate', `/datasets/${item.dataset_id}`)">{{ item.logical_id }}<small>V{{ item.version }}</small></button></td><td>{{ number(item.record_count, 0) }}</td><td>{{ number(item.attribute_count, 0) }}</td><td>{{ visibilityName(item.visibility) }}</td></tr></tbody></table></div>
            <p class="sp-asset-note">共 {{ data.datasets.length }} 份文件，显示前 6 份 · 同内容副本的有效规模仅计一次</p>
          </section>
        </div>
        <div class="sp-column"><ProfileChart :spec="charts.right" /><ProfileChart :spec="operations[0]" :error="runtimeError" /><ProfileChart :spec="operations[1]" :error="runtimeError" /></div>
      </div>
    </div>
    <div v-else class="sp-page-state" role="status" :aria-busy="loading"><span>{{ loading ? '正在读取场景数据…' : '场景数据暂不可用' }}</span><p>{{ error || '正在连接数据服务，请稍候' }}</p><button v-if="!loading" @click="emit('refresh')">重新加载</button><button v-if="role === 'SUPER_ADMIN'" @click="emit('navigate', '/overview')">返回平台首页</button></div>
    <footer class="sp-footer">
      <div class="sp-switcher" aria-label="可访问场景"><button v-for="item in visibleScenes" :key="item.code" :aria-current="data?.scenario_id === item.id ? 'page' : undefined" :class="{ 'is-active': data?.scenario_id === item.id }" :style="{ '--tab-color': item.style.color }" @click="emit('navigate', `/scenarios/${encodeURIComponent(item.code)}/dashboard`)"><i></i>{{ item.style.name }}</button></div>
      <div v-if="role === 'SCENARIO_ADMIN'" class="sp-members" :title="memberError"><span>场景用户</span><span>注册 <strong>{{ number(members?.total, 0) }}</strong></span><span>启用 <strong>{{ number(members?.enabled, 0) }}</strong></span><span>停用 <strong>{{ number(members?.disabled, 0) }}</strong></span><button v-if="memberError" class="sp-status" @click="emit('refresh')">重试</button></div>
      <span class="sp-footer-label"><i></i>{{ runtime?.scope.self_only ? '运行统计：本人范围' : '场景数据全量统计' }}</span>
    </footer>
  </main>
</template>
