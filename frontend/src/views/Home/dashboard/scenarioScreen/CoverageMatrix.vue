<script setup lang="ts">
import { computed } from 'vue';
import type { GeologicalProfile, NetworkProfile, ScenarioProfile } from '@/api/dashboardApi';
const props = defineProps<{ data: ScenarioProfile }>();
const rows = computed(() => props.data.scenario_key === 'network'
  ? (props.data as NetworkProfile).dimension_coverage.map(i => ({ label: i.dimension, datasets: i.datasets }))
  : (props.data as GeologicalProfile).factor_coverage.map(i => ({ label: i.factor, datasets: i.datasets })));
const sources = computed(() => props.data.datasets.slice(0, 6));
const sourceLabels: Record<string, string> = { kdd_train_20: 'KDD', nf_unsw_nb15: 'NF-UNSW', dis_raw_data: '原始因子', dis_landslides: '滑坡标签', dis_causative_factors: '致灾因子', dis_global_catalog: '全球编目', dis_guaruja_random: '随机基线' };
const factorLabels: Record<string, string> = { Slope: '坡度 Slope', TWI: '湿度指数 TWI', Elevation: '高程 Elevation', Relief: '地形起伏 Relief', SPI: '水流强度 SPI', Dis2roads: '距道路距离', Dis2fault: '距断层距离', Dis2river: '距河流距离' };
const geological = computed(() => props.data.scenario_key === 'geological');
</script>
<template>
  <div class="sp-coverage-block" :role="geological ? 'region' : undefined" :aria-label="geological ? '可横向滚动查看全部地形因子覆盖' : undefined" :tabindex="geological ? 0 : undefined">
    <div v-if="!sources.length || !rows.length" class="sp-empty"><span>—</span>暂无字段覆盖数据</div>
    <div v-else-if="geological" class="sp-coverage-matrix sp-coverage-matrix--transposed" role="img" aria-label="数据集与地形因子的字段覆盖热力矩阵" :style="{ '--sources': rows.length, '--dimensions': sources.length }">
      <span class="sp-coverage-corner">来源 / 地形因子</span><span v-for="row in rows" :key="row.label" class="sp-coverage-source" :title="factorLabels[row.label]">{{ row.label }}</span>
      <template v-for="source in sources" :key="source.logical_id"><span class="sp-coverage-label" :title="source.logical_id">{{ sourceLabels[source.logical_id] || source.logical_id }}</span><span v-for="row in rows" :key="row.label" class="sp-coverage-cell" :class="{ 'is-covered': row.datasets.includes(source.logical_id) }" :title="`${source.logical_id} · ${row.label}：${row.datasets.includes(source.logical_id) ? '含该字段' : '无该字段'}`"><i v-if="row.datasets.includes(source.logical_id)"></i><span v-else>—</span></span></template>
    </div>
    <div v-else class="sp-coverage-matrix" role="img" aria-label="数据集与统计维度的字段覆盖热力矩阵" :style="{ '--sources': sources.length, '--dimensions': rows.length }">
      <span class="sp-coverage-corner">{{ data.scenario_key === 'network' ? '统计维度 / 数据来源' : '地形因子 / 数据来源' }}</span>
      <span v-for="source in sources" :key="source.logical_id" class="sp-coverage-source" :title="source.logical_id">{{ sourceLabels[source.logical_id] || source.logical_id }}</span>
      <template v-for="row in rows" :key="row.label">
        <span class="sp-coverage-label">{{ factorLabels[row.label] || row.label }}</span>
        <span v-for="source in sources" :key="source.logical_id" class="sp-coverage-cell" :class="{ 'is-covered': row.datasets.includes(source.logical_id) }" :title="`${row.label} · ${source.logical_id}：${row.datasets.includes(source.logical_id) ? '含该字段' : '无该字段'}`"><i v-if="row.datasets.includes(source.logical_id)"></i><span v-else>—</span></span>
      </template>
    </div>
    <div class="sp-coverage-legend"><span><i></i>字段已覆盖</span><span><b>—</b>无该字段</span><small>{{ data.scenario_key === 'network' ? '展示前 6 个数据源的字段覆盖' : '覆盖表示存在同名因子字段，不代表分箱口径相同' }}</small><small v-if="geological" class="sp-coverage-scroll-hint">左右滑动查看全部因子 →</small></div>
  </div>
</template>
