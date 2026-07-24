<script setup lang="ts">
import { computed, ref } from 'vue';
import type { TrendPoint } from '../types/security';

const props = defineProps<{
  points: TrendPoint[];
  labelStep?: number;
}>();

const chartWidth = 820;
const chartHeight = 260;
const padding = 26;
const hoveredIndex = ref(0);

const maxValue = computed(() => Math.max(...props.points.map((item) => item.value), 1));
const pointMeta = computed(() =>
  props.points.map((point, index) => {
    const x = padding + (index / Math.max(props.points.length - 1, 1)) * (chartWidth - padding * 2);
    const y = chartHeight - padding - (point.value / maxValue.value) * (chartHeight - padding * 2);
    return { ...point, x, y };
  })
);

const polyline = computed(() => pointMeta.value.map((point) => `${point.x},${point.y}`).join(' '));
const area = computed(
  () => `${padding},${chartHeight - padding} ${polyline.value} ${chartWidth - padding},${chartHeight - padding}`
);
const activePoint = computed(() => pointMeta.value[hoveredIndex.value] ?? pointMeta.value[0]);

const onMove = (event: MouseEvent) => {
  const bounds = (event.currentTarget as HTMLElement).getBoundingClientRect();
  const ratio = (event.clientX - bounds.left) / bounds.width;
  const nextIndex = Math.min(props.points.length - 1, Math.max(0, Math.round(ratio * (props.points.length - 1))));
  hoveredIndex.value = nextIndex;
};
</script>

<template>
  <div class="line-chart" @mousemove="onMove" @mouseleave="hoveredIndex = 0">
    <svg :viewBox="`0 0 ${chartWidth} ${chartHeight}`" preserveAspectRatio="none">
      <defs>
        <linearGradient id="trend-gradient" x1="0%" x2="100%" y1="0%" y2="0%">
          <stop offset="0%" stop-color="#53e5c8" />
          <stop offset="100%" stop-color="#5ba6ff" />
        </linearGradient>
        <linearGradient id="trend-area" x1="0%" x2="0%" y1="0%" y2="100%">
          <stop offset="0%" stop-color="rgba(91,166,255,0.45)" />
          <stop offset="100%" stop-color="rgba(91,166,255,0)" />
        </linearGradient>
      </defs>
      <g class="line-chart__grid">
        <line
          v-for="index in 5"
          :key="index"
          :x1="padding"
          :x2="chartWidth - padding"
          :y1="index * 45"
          :y2="index * 45"
        />
      </g>
      <polygon :points="area" fill="url(#trend-area)" />
      <polyline :points="polyline" fill="none" stroke="url(#trend-gradient)" stroke-width="4" stroke-linecap="round" />
      <line
        v-if="activePoint"
        class="line-chart__focus-line"
        :x1="activePoint.x"
        :x2="activePoint.x"
        :y1="padding"
        :y2="chartHeight - padding"
      />
      <g v-for="(point, index) in pointMeta" :key="point.label" class="line-chart__point">
        <circle :cx="point.x" :cy="point.y" :r="hoveredIndex === index ? 8 : 5" />
      </g>
    </svg>

    <div
      v-if="activePoint"
      class="line-chart__tooltip"
      :style="{ left: `${(activePoint.x / chartWidth) * 100}%`, top: `${(activePoint.y / chartHeight) * 100}%` }"
    >
      <strong>{{ activePoint.label }}</strong>
      <span>攻击总量 {{ activePoint.value }}</span>
      <span>拦截数量 {{ activePoint.blocked }}</span>
      <span>活跃源 {{ activePoint.sources }}</span>
      <span>主类型 {{ activePoint.primaryType }}</span>
    </div>

    <div class="line-chart__labels" :style="{ gridTemplateColumns: `repeat(${points.length}, minmax(20px, 1fr))` }">
      <span
        v-for="(point, index) in points"
        :key="point.label"
        :class="{ 'is-active': hoveredIndex === index }"
        :style="{ opacity: index % (labelStep ?? 1) === 0 || hoveredIndex === index ? 1 : 0.22 }"
        @mouseenter="hoveredIndex = index"
      >
        {{ point.label }}
      </span>
    </div>
  </div>
</template>
