<script setup lang="ts">
/**
 * DashBars —— 横向条形列表（分类计数 / 比率排行）。
 * items[].count 为条长依据；percent=true 时按百分比展示，否则按整数展示。
 */
import { colorAt, fmtInt, fmtPercent, fmtPercentValue } from './dashFormat';

const props = withDefaults(
  defineProps<{
    items: Array<{ value?: unknown; label?: unknown; count?: number | null; value2?: number | null }>;
    /** 数值前缀（如「端口 」） */
    prefix?: string;
    /** true 表示数值是 0-1 的比率 */
    percent?: boolean;
    /** true 表示数值是 0-100 的百分数 */
    percentValue?: boolean;
    /** 数值保留小数位 */
    digits?: number;
    /** 固定配色；不传则按索引取色 */
    color?: string;
    /** 条长基准；不传取最大值 */
    max?: number;
    /** 数值后缀 */
    suffix?: string;
  }>(),
  { prefix: '', percent: false, percentValue: false, digits: 2, color: '', max: undefined, suffix: '' },
);

const labelOf = (item: Record<string, unknown>) => String(item.value ?? item.label ?? '—');

const numberText = (value: unknown): string => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '—';
  if (props.percent) return fmtPercent(value);
  if (props.percentValue) return fmtPercentValue(value);
  return fmtInt(value) + props.suffix;
};

const barMax = () => {
  if (typeof props.max === 'number' && props.max > 0) return props.max;
  const values = props.items
    .map((item) => Math.abs(Number(item.count ?? 0)))
    .filter((value) => Number.isFinite(value));
  return values.length ? Math.max(...values) : 0;
};
</script>

<template>
  <div v-if="!items.length" class="d-empty">暂无数据</div>
  <div v-else class="d-hbars">
    <div v-for="(item, index) in items" :key="labelOf(item as never) + index" class="d-hbar">
      <span class="d-hbk" :title="labelOf(item as never)">{{ prefix }}{{ labelOf(item as never) }}</span>
      <span class="d-hbt">
        <span
          class="d-hbf"
          :style="{
            width: (barMax() ? Math.min(100, (Math.abs(Number(item.count ?? 0)) / barMax()) * 100) : 0) + '%',
            background: color || colorAt(index),
          }"
        ></span>
      </span>
      <span class="d-hbv">{{ numberText(item.count) }}</span>
    </div>
  </div>
</template>
