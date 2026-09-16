<script setup lang="ts">
/**
 * DashRadar —— 雷达图（对应 demo 的「双机方向角对比雷达」），支持多序列。
 */
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    axes: string[];
    series: Array<{ name: string; color: string; values: Array<number | null> }>;
    /** 半径方向最大值；不传则按数据最大值取整 */
    max?: number;
    size?: number;
    unit?: string;
  }>(),
  { max: 0, size: 250, unit: '' },
);

const RINGS = 4;
/** 半径留出标签空间：size/2 - 30，标签再外移 16px，避免文字被 viewBox 裁切 */
const RADIUS = computed(() => props.size / 2 - 30);
const CENTER = computed(() => props.size / 2);

const scaleMax = computed(() => {
  if (props.max > 0) return props.max;
  const all = props.series.flatMap((item) => item.values.map((value) => Number(value ?? 0)));
  const peak = Math.max(...all, 0);
  return peak > 0 ? Math.ceil(peak / 50) * 50 : 100;
});

const angleAt = (index: number, total: number) => (-Math.PI / 2) + (2 * Math.PI * index) / total;

const pointAt = (index: number, total: number, value: number) => {
  const ratio = Math.min(Math.max(Number(value || 0) / scaleMax.value, 0), 1);
  const angle = angleAt(index, total);
  return `${(CENTER.value + RADIUS.value * ratio * Math.cos(angle)).toFixed(1)},${(CENTER.value + RADIUS.value * ratio * Math.sin(angle)).toFixed(1)}`;
};

const rings = computed(() => Array.from({ length: RINGS }, (_, index) => ((index + 1) / RINGS) * RADIUS.value));

const spokes = computed(() =>
  props.axes.map((_, index) => {
    const angle = angleAt(index, props.axes.length);
    return {
      x2: CENTER.value + RADIUS.value * Math.cos(angle),
      y2: CENTER.value + RADIUS.value * Math.sin(angle),
    };
  }),
);

const axisLabels = computed(() =>
  props.axes.map((label, index) => {
    const angle = angleAt(index, props.axes.length);
    const distance = RADIUS.value + 16;
    return { label, x: CENTER.value + distance * Math.cos(angle), y: CENTER.value + distance * Math.sin(angle) + 3 };
  }),
);

const polygons = computed(() =>
  props.series.map((item) => ({
    name: item.name,
    color: item.color,
    points: item.values.map((value, index) => pointAt(index, props.axes.length, Number(value ?? 0))).join(' '),
    fill: item.color + '22',
  })),
);
</script>

<template>
  <div class="d-donut">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" role="img">
      <circle v-for="(ring, index) in rings" :key="'r' + index" :cx="CENTER" :cy="CENTER" :r="ring" fill="none" stroke="rgba(125,201,255,.13)" />
      <line v-for="(spoke, index) in spokes" :key="'s' + index" :x1="CENTER" :y1="CENTER" :x2="spoke.x2" :y2="spoke.y2" stroke="rgba(125,201,255,.13)" />
      <polygon
        v-for="polygon in polygons"
        :key="polygon.name"
        :points="polygon.points"
        :fill="polygon.fill"
        :stroke="polygon.color"
        stroke-width="2"
      />
      <text v-for="item in axisLabels" :key="'a' + item.label" :x="item.x" :y="item.y" text-anchor="middle" fill="rgba(220,234,255,.6)" font-size="10">
        {{ item.label }}
      </text>
      <text :x="CENTER" :y="size - 2" text-anchor="middle" fill="rgba(220,234,255,.35)" font-size="9">
        半径 {{ scaleMax }}{{ unit }}
      </text>
    </svg>
    <div class="d-legend">
      <div v-for="item in series" :key="'lg' + item.name" class="d-lg">
        <span class="d-dot" :style="{ background: item.color }"></span>
        <span class="d-lgk">{{ item.name }}</span>
      </div>
    </div>
  </div>
</template>
