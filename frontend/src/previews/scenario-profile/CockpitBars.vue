<template>
  <p v-if="!items.length" class="pf-empty">暂无数据</p>
  <div v-else class="pf-bars" :class="{ 'pf-bars--2': columns === 2 }" :style="listStyle">
    <div
      v-for="item in items"
      :key="item.label"
      class="pf-bar"
      :style="{ '--accent': toneColor(item.tone) }"
      :title="`${item.label}：${valueText(item)}`"
    >
      <span class="pf-bar-label">{{ item.label }}</span>
      <span class="pf-bar-track"><span class="pf-bar-fill" :style="{ width: widthOf(item.value) }"></span></span>
      <span class="pf-bar-value">{{ valueText(item) }}</span>
    </div>
  </div>
</template>
<script setup lang="ts">
/**
 * CockpitBars，细轨道条形列表（与管理员首页的「风险占比」条同一形态）。
 * 条长以本组最大值归一，数值列等宽右对齐；columns=2 时按两列排布，节省纵向空间。
 * count 为 null 表示该口径取不到数，数值列渲染「—」且条长为 0（不是「等于 0」）。
 * percent=true 时数值按 0-1 比率渲染成百分比（风险占比、合格率这类口径用）。
 */
import { computed } from 'vue';
import { fmtInt } from '@/components/dashboard/dashFormat';
import { toneColor, type Tone } from './profileTokens';

export interface CockpitBarItem {
  label: string;
  value: number | null;
  tone?: Tone;
  suffix?: string;
}

const props = withDefaults(
  defineProps<{
    items: CockpitBarItem[];
    columns?: number;
    labelWidth?: number;
    valueWidth?: number;
    max?: number;
    percent?: boolean;
  }>(),
  { columns: 1, labelWidth: 76, valueWidth: 46, max: 0, percent: false },
);

const peak = computed(() => {
  if (props.max > 0) return props.max;
  return props.items.reduce((acc, item) => Math.max(acc, Math.abs(Number(item.value ?? 0))), 0);
});

const widthOf = (value: number | null): string => {
  if (value === null || !Number.isFinite(Number(value)) || !peak.value) return '0%';
  return `${Math.max((Math.abs(Number(value)) / peak.value) * 100, value > 0 ? 2 : 0)}%`;
};

const valueText = (item: CockpitBarItem): string => {
  if (item.value === null || !Number.isFinite(Number(item.value))) return '—';
  if (props.percent) return `${(Number(item.value) * 100).toFixed(1)}%`;
  return `${fmtInt(item.value)}${item.suffix ?? ''}`;
};

const listStyle = computed(() => ({
  '--pf-bar-label': String(props.labelWidth),
  '--pf-bar-value': String(props.valueWidth),
}));
</script>
