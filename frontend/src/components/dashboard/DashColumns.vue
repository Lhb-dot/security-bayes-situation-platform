<script setup lang="ts">
/**
 * DashColumns —— 纵向柱状图（纯 SVG，对应 demo 内联 svg 的柱图）。
 * 用于「各场景有效样本量 / 数据集数量 / 风险占比 / 包长五段 / 两数据集规模对比」等。
 */
import { computed } from 'vue';
import { colorAt, fmtInt, fmtPercent, fmtPercentValue } from './dashFormat';

const props = withDefaults(
  defineProps<{
    items: Array<{ label?: unknown; value?: number | null; count?: number | null }>;
    height?: number;
    /** 数值是 0-1 的比率 */
    percent?: boolean;
    /** 数值是 0-100 的百分数 */
    percentValue?: boolean;
    digits?: number;
    /** 单色柱；不传则按索引取色 */
    color?: string;
    /** 轴标题（左下角单位提示） */
    axisUnit?: string;
  }>(),
  { height: 200, percent: false, percentValue: false, digits: 2, color: '', axisUnit: '' },
);

const VIEW_W = 560;
const TOP = 20;
const BOTTOM = 26;

const plotHeight = computed(() => Math.max(props.height - TOP - BOTTOM, 40));

const values = computed(() => props.items.map((item) => Number(item.value ?? item.count ?? 0)));
const peak = computed(() => Math.max(...values.value.map((v) => (Number.isFinite(v) ? Math.abs(v) : 0)), 0));

const slot = computed(() => (VIEW_W - 60) / Math.max(props.items.length, 1));
const barWidth = computed(() => Math.min(116, slot.value * 0.72));

const valueText = (value: number): string => {
  if (!Number.isFinite(value)) return '—';
  if (props.percent) return fmtPercent(value, 1);
  if (props.percentValue) return fmtPercentValue(value, 1);
  return fmtInt(value);
};

const bars = computed(() =>
  props.items.map((item, index) => {
    const value = Math.abs(values.value[index] || 0);
    const ratio = peak.value ? value / peak.value : 0;
    const height = Math.round(Math.max(ratio * plotHeight.value, value > 0 ? 2.5 : 0) * 10) / 10;
    const x = Math.round((30 + slot.value * index + (slot.value - barWidth.value) / 2) * 10) / 10;
    return {
      key: String(item.label ?? index),
      label: String(item.label ?? index),
      raw: values.value[index],
      x,
      y: Math.round((TOP + plotHeight.value - height) * 10) / 10,
      height,
      width: Math.round(barWidth.value * 10) / 10,
      centerX: Math.round((x + barWidth.value / 2) * 10) / 10,
      fill: props.color || colorAt(index),
      text: valueText(values.value[index]),
    };
  }),
);
</script>

<template>
  <div v-if="!items.length" class="d-empty">暂无数据</div>
  <svg
    v-else
    :viewBox="`0 0 ${VIEW_W} ${height}`"
    width="100%"
    :height="height"
    preserveAspectRatio="none"
    role="img"
  >
    <g v-for="bar in bars" :key="bar.key">
      <rect :x="bar.x" :y="bar.y" :width="bar.width" :height="bar.height" rx="4" :fill="bar.fill">
        <title>{{ bar.label }}: {{ bar.text }}</title>
      </rect>
      <text
        :x="bar.centerX"
        :y="Math.max(bar.y - 5, 11)"
        text-anchor="middle"
        fill="#cfe3ff"
        font-size="10"
      >{{ bar.text }}</text>
      <text :x="bar.centerX" :y="height - 8" text-anchor="middle" fill="rgba(220,234,255,.6)" font-size="10">
        {{ bar.label }}
      </text>
    </g>
    <text v-if="axisUnit" x="30" :y="height - 8" fill="rgba(220,234,255,.38)" font-size="9">{{ axisUnit }}</text>
  </svg>
</template>
