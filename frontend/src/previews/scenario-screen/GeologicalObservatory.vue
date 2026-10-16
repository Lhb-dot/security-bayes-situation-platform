<script setup lang="ts">
import { computed, ref } from 'vue';
import type { GeologicalProfile, WorkspaceBase } from '@/api/dashboardApi';
import ProfileChart from './ProfileChart.vue';
import { profileNumber, runtimeCharts } from './profileCharts';
import { designDistribution, designMatches, designScaleChart, designSelectionLabel, designTotal, designTriggerChart, designTypeCount, landslideDesignTypes as types, landslideSizes as sizes, landslideSizeColors as sizeColors } from './landslideDesign';
import './geological.css';

const props = defineProps<{ data: GeologicalProfile; runtime: WorkspaceBase }>();
const selection = ref('all');
const choose = (id: string) => { selection.value = selection.value === id ? 'all' : id; };
const trigger = computed(() => designTriggerChart(selection.value));
const scale = computed(() => designScaleChart(selection.value));
const operations = computed(() => runtimeCharts(props.runtime));
const selectionLabel = computed(() => designSelectionLabel(selection.value));
const familyCount = (family: string) => types.filter(type => type.family === family).reduce((sum, type) => sum + designTypeCount(type), 0);
const focusCount = computed(() => designDistribution(selection.value, 'sizes').reduce((sum, item) => sum + item.count, 0));
const focusMajor = computed(() => {
  const values = designDistribution(selection.value, 'triggers');
  return [...values].sort((a, b) => b.count - a.count)[0]!;
});
const maxCell = Math.max(...types.flatMap(type => type.sizes));
const cellBackground = (value: number, active: boolean) => `rgba(132, 157, 234, ${(.06 + value / maxCell * .58) * (active ? 1 : .35)})`;
const fieldLabels: Record<string, string> = { Slope: '坡度', TWI: '湿度指数', Elevation: '高程', Relief: '地形起伏', SPI: '水流强度', Dis2roads: '距道路', Dis2fault: '距断层', Dis2river: '距河流' };
const leaves = types.map((type, i) => ({ ...type, y: [18, 52, 86, 126, 160][i]!, familyY: type.family === 'soil' ? 52 : 143 }));
const resourceLabel: Record<string, string> = { dis_raw_data: '地形因子主集', dis_landslides: '滑坡标签样本', dis_causative_factors: '致灾因子数据', dis_global_catalog: '全球滑坡编目', dis_guaruja_random: '随机基线样本' };
const modelTotal = computed(() => Math.max(1, ...props.data.modeling.map(item => item.total)));
</script>

<template>
  <div class="sp-grid geo-observatory">
    <div class="sp-column geo-side">
      <ProfileChart :spec="trigger" index="01" />
      <ProfileChart :spec="scale" index="02" />
      <section class="sp-panel geo-resources" aria-label="数据与建模资源">
        <header class="sp-panel-heading"><span>03</span><h3>数据与建模资源</h3><small>DATA & MODELS</small></header>
        <table><thead><tr><th>数据资源</th><th>样本</th><th>模型覆盖</th></tr></thead><tbody><tr v-for="item in data.datasets" :key="item.logical_id"><td :title="`${item.logical_id} · ${item.attribute_count} 字段 · ${data.roles.find(role => role.logical_id === item.logical_id)?.role || '未分类'}`">{{ resourceLabel[item.logical_id] || item.logical_id }}</td><td>{{ profileNumber(item.record_count, 0) }}</td><td><div class="geo-resource-model" :title="`已发布 ${data.modeling.find(m => m.logical_id === item.logical_id)?.published ?? 0} · 未发布 ${data.modeling.find(m => m.logical_id === item.logical_id)?.draft ?? 0}`"><i :style="{ width: `${(data.modeling.find(m => m.logical_id === item.logical_id)?.published ?? 0) / modelTotal * 100}%` }"></i><b :style="{ width: `${(data.modeling.find(m => m.logical_id === item.logical_id)?.draft ?? 0) / modelTotal * 100}%` }"></b><span>{{ data.modeling.find(m => m.logical_id === item.logical_id)?.total ?? 0 }}</span></div></td></tr></tbody></table>
        <p class="geo-resource-key"><i></i>已发布 <b></b>未发布 <span>条形按模型版本数绘制</span></p>
      </section>
    </div>
    <div class="geo-center">
      <section class="sp-panel geo-classification" aria-label="滑坡分类画像">
        <header class="geo-hero-header"><div><span>LANDSLIDE TAXONOMY EXPLORER</span><h3>滑坡分类画像<span>类型 · 规模 · 诱因</span></h3></div><span class="geo-design-badge">分类方案演示</span></header>
        <div class="geo-path"><span>组成物质</span><i>›</i><span>亚类特征</span><i>›</i><span>规模交叉分布</span><strong>{{ profileNumber(designTotal, 0) }} <small>条演示编目</small></strong></div>
        <div class="geo-taxonomy" aria-label="点击分类节点联动查看诱因和规模">
          <svg class="geo-flow-lines" viewBox="0 0 620 180" preserveAspectRatio="none" aria-hidden="true">
            <defs><linearGradient id="soil-connector"><stop stop-color="#5c88b0" stop-opacity=".15"/><stop offset="1" stop-color="#64cfbf" stop-opacity=".6"/></linearGradient><linearGradient id="rock-connector"><stop stop-color="#5c88b0" stop-opacity=".15"/><stop offset="1" stop-color="#ac9fe9" stop-opacity=".6"/></linearGradient></defs>
            <path d="M113 90 C162 90 170 52 218 52" stroke="url(#soil-connector)" stroke-width="14" :class="{ 'is-dim': selection === 'rock' || types.some(type => type.id === selection && type.family === 'rock') }" />
            <path d="M113 90 C164 90 170 143 218 143" stroke="url(#rock-connector)" stroke-width="8" :class="{ 'is-dim': selection === 'soil' || types.some(type => type.id === selection && type.family === 'soil') }" />
            <path v-for="leaf in leaves" :key="leaf.id" :d="`M322 ${leaf.familyY} C370 ${leaf.familyY} 376 ${leaf.y} 427 ${leaf.y}`" :stroke="leaf.family === 'soil' ? 'url(#soil-connector)' : 'url(#rock-connector)'" :stroke-width="3 + designTypeCount(leaf) / 38" :class="{ 'is-dim': !designMatches(leaf, selection) }" />
          </svg>
          <button class="geo-root-node" :class="{ 'is-selected': selection === 'all' }" :aria-pressed="selection === 'all'" @click="selection = 'all'"><svg viewBox="0 0 56 32" aria-hidden="true"><path d="M2 28 17 6l11 16 9-13 17 19 M12 28l8-12 7 12 M31 28l8-13 9 13" /></svg><strong>滑坡灾害</strong><span>分类总览</span></button>
          <button class="geo-family-node geo-family-node--soil" :class="{ 'is-selected': selection === 'soil' }" :aria-pressed="selection === 'soil'" @click="choose('soil')"><strong>土质滑坡</strong><span>SOIL <b>{{ (familyCount('soil') / designTotal * 100).toFixed(1) }}%</b></span></button>
          <button class="geo-family-node geo-family-node--rock" :class="{ 'is-selected': selection === 'rock' }" :aria-pressed="selection === 'rock'" @click="choose('rock')"><strong>岩质滑坡</strong><span>ROCK <b>{{ (familyCount('rock') / designTotal * 100).toFixed(1) }}%</b></span></button>
          <button v-for="leaf in leaves" :key="leaf.id" class="geo-leaf-node" :class="{ 'geo-leaf-node--rock': leaf.family === 'rock', 'is-selected': selection === leaf.id, 'is-dim': !designMatches(leaf, selection) }" :style="{ top: `${leaf.y / 180 * 100}%` }" :aria-pressed="selection === leaf.id" :title="`${leaf.name} · ${leaf.english} · 点击聚焦`" @click="choose(leaf.id)"><i></i><span>{{ leaf.name }}</span><strong>{{ designTypeCount(leaf) }}</strong><small>{{ (designTypeCount(leaf) / designTotal * 100).toFixed(1) }}%</small></button>
        </div>
        <div class="geo-focus-bar" aria-live="polite"><span class="geo-focus-dot"></span><span>当前聚焦 <strong>{{ selectionLabel }}</strong></span><span>主要诱因 <strong>{{ focusMajor.value }} <small>{{ (focusMajor.count / focusCount * 100).toFixed(1) }}%</small></strong></span><button :disabled="selection === 'all'" @click="selection = 'all'">重置视图 ↗</button></div>
        <div class="geo-matrix-block">
          <header><h4>类型 × 规模分布</h4><span>同一演示样本集 · 单位：条</span><div class="geo-matrix-key"><i></i><span>少</span><b></b><span>多</span></div></header>
          <div class="geo-cross-matrix" role="table" aria-label="滑坡亚类与规模交叉分布（演示数据）">
            <div class="geo-matrix-row geo-matrix-row--heading" role="row"><span role="columnheader">滑坡亚类</span><span v-for="(size, i) in sizes" :key="size" role="columnheader"><i :style="{ background: sizeColors[i] }"></i>{{ size }}</span></div>
            <div v-for="type in types" :key="type.id" class="geo-matrix-row" :class="{ 'is-focused': selection === type.id, 'is-dim': !designMatches(type, selection) }" role="row"><button role="rowheader" :aria-pressed="selection === type.id" @click="choose(type.id)"><i :class="{ 'is-rock': type.family === 'rock' }"></i>{{ type.name }}</button><span v-for="(value, i) in type.sizes" :key="i" role="cell" :style="{ background: cellBackground(value, designMatches(type, selection)) }" :title="`${type.name} · ${sizes[i]}：${value} 条（演示）`">{{ value }}</span></div>
          </div>
        </div>
        <p class="geo-classification-note">一级按组成物质；土质亚类按土体来源，岩质亚类按岩层关系。分类及联合分布尚待数据核验。</p>
      </section>
    </div>
    <div class="sp-column geo-side">
      <section class="sp-panel geo-factor-panel" aria-label="地形因子数据支撑">
        <header class="sp-panel-heading"><span>06</span><h3>地形因子数据支撑</h3><small>DATA COVERAGE</small></header>
        <div class="geo-factor-grid"><div v-for="factor in data.factor_coverage" :key="factor.factor" class="geo-factor" :title="`${factor.factor} · ${factor.datasets.join('、') || '无数据覆盖'}`"><span>{{ fieldLabels[factor.factor] || factor.factor }}<b>{{ factor.datasets.length }}<small>源</small></b></span><div class="geo-factor-track"><i v-for="i in data.datasets.length" :key="i" :class="{ 'is-filled': i <= factor.datasets.length }"></i></div></div></div>
        <p class="sp-chart-note">含对应因子字段的数据集数 · 不代表因果贡献度</p>
      </section>
      <ProfileChart :spec="operations[0]" index="07" />
      <ProfileChart :spec="operations[1]" index="08" />
    </div>
  </div>
</template>
