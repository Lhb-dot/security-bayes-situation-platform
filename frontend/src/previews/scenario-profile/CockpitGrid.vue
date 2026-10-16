<script setup lang="ts">
/**
 * CockpitGrid —— 覆盖打点矩阵（条目 × 数据集）。
 *
 * 用途：回答「这个统计维度 / 地形因子到底被哪几份数据支撑」。表格式的「覆盖数据集」列
 * 只能把名字排成一行，打点矩阵让「某行只有一颗亮点」（= 只有一份数据能算，跨数据集
 * 不可互相校验）在视觉上直接可见；整行空心点表示该口径在本场景根本没有字段定义。
 *
 * columns=2 时把条目分两栏排布（每栏各自带表头）：地质的 8 个地形因子在单栏里
 * 会超出面板高度，分栏后行数减半，不需要面板内滚动。
 */
import { computed } from 'vue';

export interface CockpitGridRow {
  label: string;
  /** 与 columns 等长的布尔序列：该数据集是否覆盖此条目 */
  on: boolean[];
  /** 覆盖数（后端口径，可能大于 on 中为真的个数，故独立传入） */
  count: number;
}

const props = withDefaults(
  defineProps<{
    columns: string[];
    rows: CockpitGridRow[];
    /** 分栏数（1 或 2） */
    split?: number;
    /** 亮点颜色 */
    accent?: string;
  }>(),
  { split: 1, accent: '#62cdb4' },
);

const chunks = computed(() => {
  const size = Math.ceil(props.rows.length / Math.max(props.split, 1));
  const list: CockpitGridRow[][] = [];
  for (let index = 0; index < props.rows.length; index += size) list.push(props.rows.slice(index, index + size));
  return list.length ? list : [[]];
});

const gridStyle = computed(() => ({ '--pf-grid-cols': String(Math.max(props.columns.length, 1)) }));
</script>

<template>
  <p v-if="!rows.length || !columns.length" class="pf-empty">暂无数据</p>
  <div v-else class="pf-grid" :class="{ 'pf-grid--split': split > 1 }" :style="gridStyle">
    <div v-for="(chunk, chunkIndex) in chunks" :key="`chunk-${chunkIndex}`" class="pf-grid-col">
      <div class="pf-grid-row pf-grid-row--head">
        <span></span>
        <span v-for="column in columns" :key="`h-${column}`" :title="column">{{ column }}</span>
        <span>覆盖</span>
      </div>
      <div v-for="row in chunk" :key="row.label" class="pf-grid-row">
        <span class="pf-grid-name" :title="row.label">{{ row.label }}</span>
        <span
          v-for="(on, index) in row.on"
          :key="`${row.label}-${index}`"
          class="pf-grid-cell"
          :class="{ 'is-on': on }"
          :style="{ '--accent': accent }"
          :title="`${columns[index]}：${on ? '含该口径字段' : '无该口径字段'}`"
        >
          <i></i>
        </span>
        <span class="pf-grid-count">{{ row.count }}</span>
      </div>
    </div>
  </div>
</template>
