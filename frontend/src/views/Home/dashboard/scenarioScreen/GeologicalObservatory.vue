<script setup lang="ts">
import { computed, ref } from 'vue';
import type { GeologicalProfile, ScenarioWorkspace } from '@/api/dashboardApi';
import ProfileChart from './ProfileChart.vue';
import CoverageMatrix from './CoverageMatrix.vue';
import { bars, composition, donut, profileNumber, runtimeCharts } from './profileCharts';
import { taxonomyTypes as types, taxonomyCount, taxonomyMatches, taxonomyLabel } from './landslideTaxonomy';
import './geological.css';
const props = defineProps<{ data: GeologicalProfile; runtime: ScenarioWorkspace | null; runtimeError: string }>();
const selection = ref('all');
const choose = (id: string) => { selection.value = selection.value === id ? 'all' : id; };
const trigger = computed(() => donut('滑坡诱因构成', composition(props.data.catalog_distribution.trigger, props.data.datasets.find(item => item.logical_id === 'dis_global_catalog')?.record_count, 4), '编目诱因 · 含其余/缺失 · 不随分类节点筛选'));
const scale = computed(() => bars('滑坡规模结构', props.data.catalog_distribution.size, '全编目规模统计 · 不随分类节点筛选', '#6fc7d2'));
const operations = computed(() => runtimeCharts(props.runtime));
const selectionLabel = computed(() => taxonomyLabel(selection.value));
const typeCount = (type: { id: string }) => taxonomyCount(props.data.catalog_distribution.category, type.id);
const familyCount = (family: string) => {
  const found = types.filter(type => type.family === family).map(typeCount).filter((count): count is number => count !== null);
  return found.length ? found.reduce((sum, count) => sum + count, 0) : null;
};
const returnedCategoryCount = computed(() => props.data.catalog_distribution.category.reduce((sum, item) => sum + item.count, 0));
const focusCount = computed(() => selection.value === 'all' ? returnedCategoryCount.value : selection.value === 'soil' || selection.value === 'rock' ? familyCount(selection.value) : taxonomyCount(props.data.catalog_distribution.category, selection.value));
const fieldLabels: Record<string, string> = { Slope: '坡度', TWI: '湿度指数', Elevation: '高程', Relief: '地形起伏', SPI: '水流强度', Dis2roads: '距道路', Dis2fault: '距断层', Dis2river: '距河流' };
const leaves = types.map((type, i) => ({ ...type, y: [18, 52, 86, 126, 160][i]!, familyY: type.family === 'soil' ? 52 : 143 }));
const resourceLabel: Record<string, string> = { dis_raw_data: '地形因子主集', dis_landslides: '滑坡标签样本', dis_causative_factors: '致灾因子数据', dis_global_catalog: '全球滑坡编目', dis_guaruja_random: '随机基线样本' };
const modelTotal = computed(() => Math.max(1, ...props.data.modeling.map(item => item.total)));
const otherCategoryCount = computed(() => props.data.catalog_distribution.category.filter(item => !types.some(type => type.name === item.value.trim())).reduce((sum, item) => sum + item.count, 0));
</script>

<template>
  <div class="sp-grid geo-observatory">
    <div class="sp-column geo-side">
      <ProfileChart :spec="trigger" index="01" />
      <ProfileChart :spec="scale" index="02" />
      <section class="sp-panel geo-resources" aria-label="数据与建模资源">
        <header class="sp-panel-heading"><span>03</span><h3>数据与建模资源</h3><small>DATA & MODELS</small></header>
        <table><thead><tr><th>数据资源</th><th>样本</th><th>模型覆盖</th></tr></thead><tbody><tr v-for="item in data.datasets.slice(0, 6)" :key="item.dataset_id"><td :title="`${item.logical_id} · ${item.attribute_count} 字段 · ${data.roles.find(role => role.logical_id === item.logical_id)?.role || '未分类'}`">{{ resourceLabel[item.logical_id] || item.logical_id }}</td><td>{{ profileNumber(item.record_count, 0) }}</td><td><div class="geo-resource-model" :title="`已发布 ${data.modeling.find(m => m.logical_id === item.logical_id)?.published ?? 0} · 未发布 ${data.modeling.find(m => m.logical_id === item.logical_id)?.draft ?? 0}`"><i :style="{ width: `${(data.modeling.find(m => m.logical_id === item.logical_id)?.published ?? 0) / modelTotal * 100}%` }"></i><b :style="{ width: `${(data.modeling.find(m => m.logical_id === item.logical_id)?.draft ?? 0) / modelTotal * 100}%` }"></b><span>{{ data.modeling.find(m => m.logical_id === item.logical_id)?.total ?? 0 }}</span></div></td></tr></tbody></table>
        <p class="geo-resource-key"><i></i>已发布 <b></b>未发布 <span>前 6 份资源 · 模型版本数</span></p>
      </section>
    </div>
    <div class="geo-center">
      <section class="sp-panel geo-classification" aria-label="滑坡分类画像">
        <header class="geo-hero-header"><div><span>LANDSLIDE TAXONOMY EXPLORER</span><h3>滑坡分类画像<span>类型 · 规模 · 诱因</span></h3></div><span class="geo-design-badge">分类框架</span></header>
        <div class="geo-path"><span>组成物质</span><i>›</i><span>亚类特征</span><i>›</i><span>数据因子支撑</span><strong>{{ profileNumber(returnedCategoryCount, 0) }} <small>条已返回类型记录</small></strong></div>
        <div class="geo-taxonomy" aria-label="点击分类节点查看已返回的细分类统计">
          <svg class="geo-flow-lines" viewBox="0 0 620 180" preserveAspectRatio="none" aria-hidden="true">
            <defs><linearGradient id="soil-connector"><stop stop-color="#5c88b0" stop-opacity=".15"/><stop offset="1" stop-color="#64cfbf" stop-opacity=".6"/></linearGradient><linearGradient id="rock-connector"><stop stop-color="#5c88b0" stop-opacity=".15"/><stop offset="1" stop-color="#ac9fe9" stop-opacity=".6"/></linearGradient></defs>
            <path d="M113 90 C162 90 170 52 218 52" stroke="url(#soil-connector)" stroke-width="7" :class="{ 'is-dim': selection === 'rock' || types.some(type => type.id === selection && type.family === 'rock') }" />
            <path d="M113 90 C164 90 170 143 218 143" stroke="url(#rock-connector)" stroke-width="7" :class="{ 'is-dim': selection === 'soil' || types.some(type => type.id === selection && type.family === 'soil') }" />
            <path v-for="leaf in leaves" :key="leaf.id" :d="`M322 ${leaf.familyY} C370 ${leaf.familyY} 376 ${leaf.y} 427 ${leaf.y}`" :stroke="leaf.family === 'soil' ? 'url(#soil-connector)' : 'url(#rock-connector)'" stroke-width="4" :class="{ 'is-dim': !taxonomyMatches(leaf, selection) }" />
          </svg>
          <button class="geo-root-node" :class="{ 'is-selected': selection === 'all' }" :aria-pressed="selection === 'all'" @click="selection = 'all'"><svg viewBox="0 0 56 32" aria-hidden="true"><path d="M2 28 17 6l11 16 9-13 17 19 M12 28l8-12 7 12 M31 28l8-13 9 13" /></svg><strong>滑坡灾害</strong><span>分类总览</span></button>
          <button class="geo-family-node geo-family-node--soil" :class="{ 'is-selected': selection === 'soil' }" :aria-pressed="selection === 'soil'" @click="choose('soil')"><strong>土质滑坡</strong><span>SOIL <b>{{ profileNumber(familyCount('soil'), 0) }}</b></span></button>
          <button class="geo-family-node geo-family-node--rock" :class="{ 'is-selected': selection === 'rock' }" :aria-pressed="selection === 'rock'" @click="choose('rock')"><strong>岩质滑坡</strong><span>ROCK <b>{{ profileNumber(familyCount('rock'), 0) }}</b></span></button>
          <button v-for="leaf in leaves" :key="leaf.id" class="geo-leaf-node" :class="{ 'geo-leaf-node--rock': leaf.family === 'rock', 'is-selected': selection === leaf.id, 'is-dim': !taxonomyMatches(leaf, selection) }" :style="{ top: `${leaf.y / 180 * 100}%` }" :aria-pressed="selection === leaf.id" :title="`${leaf.name} · ${leaf.english} · 点击聚焦`" @click="choose(leaf.id)"><i></i><span>{{ leaf.name }}</span><strong>{{ profileNumber(typeCount(leaf), 0) }}</strong><small>{{ typeCount(leaf) === null ? '未统计' : '条' }}</small></button>
        </div>
        <div class="geo-focus-bar" aria-live="polite"><span class="geo-focus-dot"></span><span>当前分类 <strong>{{ selectionLabel }}</strong></span><span>已返回记录 <strong>{{ profileNumber(focusCount, 0) }}</strong></span><button :disabled="selection === 'all'" @click="selection = 'all'">重置视图 ↗</button></div>
        <div class="geo-matrix-block geo-live-matrix">
          <header><h4>数据源 × 地形因子覆盖</h4><span>按字段实际存在情况统计</span></header>
          <CoverageMatrix v-if="data.datasets.length && data.factor_coverage.length" :data="data" />
          <div v-else class="sp-empty"><span>—</span>暂无地形因子数据</div>
        </div>
        <p class="geo-classification-note">连线仅示分类关系；“—”表示未返回该细分类，不能视为零。{{ otherCategoryCount ? `另有 ${profileNumber(otherCategoryCount, 0)} 条记录未归入上述亚类。` : '' }}分类记录仅含接口返回的前 8 类。</p>
      </section>
    </div>
    <div class="sp-column geo-side">
      <section class="sp-panel geo-factor-panel" aria-label="地形因子统计摘要">
        <header class="sp-panel-heading"><span>06</span><h3>地形因子统计摘要</h3><small>FACTOR STATISTICS</small></header>
        <div v-if="data.factors.length" class="geo-factor-grid"><div v-for="factor in data.factors.slice(0, 8)" :key="factor.value" class="geo-factor" :title="`${factor.value} · 有效记录 ${factor.stats?.count ?? '—'} · 标准差 ${profileNumber(factor.stats?.std, 2)}`"><span>{{ fieldLabels[factor.value] || factor.value }}<b>{{ profileNumber(factor.mean, 2) }}</b></span><div class="geo-factor-range">{{ profileNumber(factor.stats?.min, 2) }} ～ {{ profileNumber(factor.stats?.max, 2) }}</div></div></div>
        <div v-else class="sp-empty"><span>—</span>暂无地形因子统计</div>
        <p class="sp-chart-note">各因子原始字段均值及范围 · 分箱不同，不直接比较</p>
      </section>
      <ProfileChart :spec="operations[0]" index="07" :error="runtimeError" />
      <ProfileChart :spec="operations[1]" index="08" :error="runtimeError" />
    </div>
  </div>
</template>
