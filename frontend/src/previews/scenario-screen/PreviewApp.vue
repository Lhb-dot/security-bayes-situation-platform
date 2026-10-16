<script setup lang="ts">
import { computed, ref } from 'vue';
import type { FlightdeckProfile, GeologicalProfile, NetworkProfile, PowerProfile } from '@/api/dashboardApi';
import { SCENE_STYLES } from '@/views/Home/dashboard/adminOverview';
import ProfileChart from './ProfileChart.vue';
import CoverageMatrix from './CoverageMatrix.vue';
import GeologicalObservatory from './GeologicalObservatory.vue';
import { governanceRows, modelingChart, profileNumber as number, profilePercent as percent, runtimeCharts, scenarioCharts } from './profileCharts';
import { previewRuntime, previewScenes } from './previewData';
import './preview.css';

const keys = ['network', 'power', 'flight_deck', 'geological'];
const selected = ref(Math.max(0, keys.indexOf(new URLSearchParams(location.search).get('scene') || document.documentElement.dataset.previewScene || 'network')));
const data = computed(() => previewScenes[selected.value]!);
const scene = computed(() => SCENE_STYLES[data.value.scenario_key as keyof typeof SCENE_STYLES]);
const charts = computed(() => scenarioCharts(data.value));
const models = computed(() => modelingChart(data.value));
const operations = computed(() => runtimeCharts(previewRuntime(selected.value)));
const governance = computed(() => governanceRows(data.value));
const governanceTitle = computed(() => ['风险标签口径', '遥测质量与基线', '编码形态与内容分组', '数据职责与风险口径'][selected.value]);
const governanceNote = computed(() => {
  const d = data.value;
  if (d.scenario_key === 'geological') {
    const conflicts = (d as GeologicalProfile).factor_coverage.filter(i => i.datasets.length > 1 && !i.consistent_binning).map(i => i.factor);
    return conflicts.length ? `分箱不一致：${conflicts.join('、')}；跨源统计需先对齐口径` : '多源因子未发现分箱冲突';
  }
  if (d.scenario_key === 'flight_deck') return `同内容文件合并统计 · 内容冗余率 ${percent((d as FlightdeckProfile).redundancy.redundancy_rate)}`;
  if (d.scenario_key === 'network') return '正类显式登记 · 偏离 = 数据集正类占比 / 场景合并占比';
  return '工频合格区间 49.8–50.2 Hz · 基线仅校验参量均值';
});
const metrics = computed(() => {
  const d = data.value;
  const specialty = d.scenario_key === 'network' ? { label: '目的端口覆盖', value: number((d as NetworkProfile).distinct_port_count, 0), unit: '种', detail: 'NF-UNSW · 去重目的端口' }
    : d.scenario_key === 'power' ? { label: '设备类型覆盖', value: number((d as PowerProfile).device_fault_rates.length, 0), unit: '类', detail: '按设备名称去重统计' }
    : d.scenario_key === 'flight_deck' ? { label: '最小间距均值', value: number((d as FlightdeckProfile).distance.min?.mean, 2), unit: '原始单位', detail: '数值原始集 · 样本最小间距的均值' }
    : { label: '可用地形因子', value: number((d as GeologicalProfile).factor_count, 0), unit: '项', detail: '主因子集 · 可计算统计量的字段' };
  return [
    { label: '有效数据资源', value: number(d.dataset_count, 0), unit: '组', detail: `${d.dataset_file_count} 份物理文件 · 按内容指纹去重` },
    { label: '有效样本规模', value: number(d.sample_count, 0), unit: '条', detail: '每个内容分组取代表数据集统计' },
    { label: '登记正类占比', value: percent(d.risk_rate), unit: '', detail: '去重正类 / 全部有效样本；非实时风险率' },
    specialty,
  ];
});
const nav = ['数据集', '模型训练', '模型中心', '风险研判', '推理记录', '风险事件', '报告中心', '用户管理', '设置'];
const message = ref('');
let messageTimer: ReturnType<typeof setTimeout> | undefined;
function previewAction(label: string) {
  message.value = `「${label}」为正式版功能入口，此处仅预览首页设计`;
  clearTimeout(messageTimer);
  messageTimer = setTimeout(() => { message.value = ''; }, 2800);
}
function selectScene(index: number) {
  selected.value = index;
  history.replaceState(null, '', `?scene=${keys[index]}`);
}
function fullscreen() {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void document.documentElement.requestFullscreen().catch(() => previewAction('全屏'));
}
const minimumRows = computed(() => Math.max(3, governance.value.length));
</script>

<template>
  <main class="scenario-profile" :style="{ '--scene-accent': scene.color }">
    <header class="sp-masthead">
      <span class="sp-brand"><svg viewBox="0 0 24 24"><path d="M12 2 21 6v6c0 5-5 8-9 10-4-2-9-5-9-10V6z M8 12l3 3 5-6" /></svg>AI SECURITY OPERATIONS CENTER</span>
      <div class="sp-platform-title"><i></i><h1>基于贝叶斯网络的复杂系统智能态势感知平台</h1><i></i></div>
      <div class="sp-account"><span class="sp-preview-badge">独立预览 · 演示数据</span><button class="sp-fullscreen" title="切换全屏" aria-label="切换全屏" @click="fullscreen"><svg viewBox="0 0 24 24"><path d="M4 9V4h5 M15 4h5v5 M20 15v5h-5 M9 20H4v-5" /></svg></button></div>
    </header>
    <div class="sp-content">
      <section class="sp-command">
        <div class="sp-scene-title"><span>{{ scene.english }} / DATA OBSERVATORY</span><h2>{{ data.scenario_name }}<small>态势总览</small></h2></div>
        <nav aria-label="场景功能入口"><button v-for="(item, i) in nav" :key="item" @click="previewAction(item)"><svg v-if="i < 4" viewBox="0 0 24 24"><path :d="['M4 5c0-2 16-2 16 0s-16 2-16 0 M4 5v14c0 2 16 2 16 0V5 M4 12c0 2 16 2 16 0', 'M12 3l8 5v8l-8 5-8-5V8z M4 8l8 5 8-5 M12 13v8', 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z', 'M3 17l5-5 4 3 8-10 M14 5h6v6 M3 21h18'][i]" /></svg>{{ item }}</button></nav>
      </section>
      <section class="sp-metrics" aria-label="场景核心指标">
        <article v-for="(metric, i) in metrics" :key="metric.label" :style="{ '--metric-color': ['#69b7ff', '#4cdac6', '#efc17a', scene.color][i] }" :title="metric.detail">
          <div class="sp-metric-label">{{ metric.label }}<span>0{{ i + 1 }}</span></div>
          <div class="sp-metric-value"><strong>{{ metric.value }}</strong><span>{{ metric.unit }}</span></div>
        </article>
      </section>
      <GeologicalObservatory v-if="data.scenario_key === 'geological'" :data="data as GeologicalProfile" :runtime="previewRuntime(selected)" />
      <div v-else :key="data.scenario_key" class="sp-grid">
        <div class="sp-column"><ProfileChart :spec="charts.left[0]" index="01" /><ProfileChart :spec="charts.left[1]" index="02" /><ProfileChart :spec="models" index="03" /></div>
        <div class="sp-center">
          <section class="sp-panel sp-hero">
            <div class="sp-hero-heading"><div><span>SCENARIO DATA LANDSCAPE</span><h3>{{ charts.main.title }}</h3></div><span class="sp-source-badge"><i></i>全量数据画像</span></div>
            <CoverageMatrix v-if="['network', 'geological'].includes(data.scenario_key)" :data="data" />
            <ProfileChart v-else :spec="charts.main" index="04" />
            <div class="sp-governance" :style="{ '--gov-rows': minimumRows }">
              <header><h3><i></i>{{ governanceTitle }}</h3><span>GOVERNANCE</span></header>
              <div v-for="(row, i) in governance" :key="row.name" class="sp-governance-row"><span class="sp-row-index">{{ String(i + 1).padStart(2, '0') }}</span><span class="sp-governance-name" :title="row.name">{{ row.name }}</span><span class="sp-governance-detail" :title="row.detail">{{ row.detail }}</span><strong :class="{ 'is-warning': row.warn }" :title="row.status">{{ row.status }}</strong></div>
              <p class="sp-governance-note">{{ governanceNote }}</p>
            </div>
          </section>
          <section class="sp-panel sp-assets">
            <header class="sp-panel-heading"><span>05</span><h3>数据资产台账</h3><small>DATA ASSETS · 按物理文件展示</small></header>
            <div class="sp-table-wrap"><table><thead><tr><th>数据集 / 版本</th><th>样本量</th><th>字段</th><th>范围</th></tr></thead><tbody><tr v-for="item in data.datasets" :key="item.logical_id"><td><button :title="item.logical_id" @click="previewAction('数据集详情')">{{ item.logical_id }}<small>V{{ item.version }}</small></button></td><td>{{ number(item.record_count, 0) }}</td><td>{{ number(item.attribute_count, 0) }}</td><td>平台</td></tr></tbody></table></div>
            <p class="sp-asset-note">同内容副本保留在台账中，有效规模仅计一次</p>
          </section>
        </div>
        <div class="sp-column"><ProfileChart :spec="charts.right" index="06" /><ProfileChart :spec="operations[0]" index="07" /><ProfileChart :spec="operations[1]" index="08" /></div>
      </div>
    </div>
    <footer class="sp-footer">
      <div class="sp-switcher" role="tablist" aria-label="预览场景切换"><button v-for="(key, i) in keys" :key="key" role="tab" :aria-selected="selected === i" :class="{ 'is-active': selected === i }" :style="{ '--tab-color': SCENE_STYLES[key as keyof typeof SCENE_STYLES].color }" @click="selectScene(i)"><i></i>{{ ['网络安全', '电力系统', '航保作业', '滑坡灾害'][i] }}</button></div>
      <div class="sp-members"><span>场景用户</span><span>注册 <strong>{{ [12, 8, 6, 10][selected] }}</strong></span><span>启用 <strong>{{ [12, 8, 6, 10][selected]! - selected % 2 }}</strong></span><span>停用 <strong>{{ selected % 2 }}</strong></span></div>
      <span class="sp-footer-label"><i></i>独立设计预览 · 未接入正式首页</span>
    </footer>
    <Transition name="toast"><div v-if="message" class="sp-toast" role="status">{{ message }}</div></Transition>
  </main>
</template>
