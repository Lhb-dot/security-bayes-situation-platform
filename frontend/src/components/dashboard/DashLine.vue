<script setup lang="ts">
/**
 * DashLine —— 折线/面积图（纯 SVG），支持双序列。
 * 用于「机间距变化曲线」「近 10 天推理活动趋势」。
 *
 * 坐标按容器实测宽度计算（viewBox 与渲染尺寸 1:1），
 * 因此圆点恒为正圆、文字不被横向拉伸。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { fmtInt } from './dashFormat';

const props = withDefaults(
  defineProps<{
    points: Array<{ label: string; value: number | null; value2?: number | null }>;
    height?: number;
    /** 主序列名称 */
    name?: string;
    /** 次序列名称（不传则不画） */
    name2?: string;
    color?: string;
    color2?: string;
    /** 主序列是否填充面积 */
    area?: boolean;
    /** 次序列是否填充面积 */
    area2?: boolean;
    /** 数值后缀 */
    suffix?: string;
  }>(),
  {
    height: 190,
    name: '',
    name2: '',
    color: '#5ba6ff',
    color2: '#53e5c8',
    area: false,
    area2: false,
    suffix: '',
  },
);

const TOP = 18;
const BOTTOM = 24;
/** 首末数据点距绘图区左右边缘的留白 */
const PAD_X = 20;
/** 容器宽度未知时的兜底宽度 */
const FALLBACK_W = 560;

const hostRef = ref<HTMLElement | null>(null);
const hostWidth = ref(0);
let observer: ResizeObserver | null = null;

onMounted(() => {
  const host = hostRef.value;
  if (!host) return;
  hostWidth.value = Math.round(host.getBoundingClientRect().width);
  observer = new ResizeObserver((entries) => {
    const width = entries[0]?.contentRect.width ?? 0;
    if (width > 0) hostWidth.value = Math.round(width);
  });
  observer.observe(host);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});

const viewWidth = computed(() => (hostWidth.value > 0 ? hostWidth.value : FALLBACK_W));

const plotHeight = computed(() => Math.max(props.height - TOP - BOTTOM, 40));

const series = computed(() => {
  const values = props.points.map((p) => Number(p.value ?? 0));
  const values2 = props.points.some((p) => p.value2 !== undefined)
    ? props.points.map((p) => Number(p.value2 ?? 0))
    : [];
  const all = [...values, ...values2];
  const max = Math.max(...all.map((v) => (Number.isFinite(v) ? v : 0)), 0);
  const min = Math.min(...all.map((v) => (Number.isFinite(v) ? v : 0)), 0);
  const span = max - min || 1;
  const width = viewWidth.value;
  const step = props.points.length > 1 ? (width - PAD_X * 2) / (props.points.length - 1) : 0;
  const pointOf = (value: number, index: number) => ({
    x: Math.round((PAD_X + step * index) * 10) / 10,
    y: Math.round((TOP + plotHeight.value - ((value - min) / span) * plotHeight.value) * 10) / 10,
  });
  return {
    main: props.points.map((p, i) => ({ ...pointOf(Number(p.value ?? 0), i), raw: Number(p.value ?? 0) })),
    second: values2.length ? props.points.map((p, i) => ({ ...pointOf(Number(p.value2 ?? 0), i), raw: Number(p.value2 ?? 0) })) : [],
    min,
    max,
  };
});

const path = (points: Array<{ x: number; y: number }>) =>
  points.map((p, index) => `${index === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');

const areaPath = (points: Array<{ x: number; y: number }>) => {
  if (!points.length) return '';
  const base = TOP + plotHeight.value;
  return `${path(points)} L${points[points.length - 1].x},${base} L${points[0].x},${base} Z`;
};

/** 横轴标签稀疏度：按容器宽度算，每 64px 最多放一个标签，避免重叠 */
const labelStep = computed(() => {
  const maxLabels = Math.max(2, Math.floor(viewWidth.value / 64));
  return Math.max(1, Math.ceil(props.points.length / maxLabels));
});
</script>

<template>
  <div ref="hostRef" class="d-line">
    <div v-if="!points.length" class="d-empty">暂无数据</div>
    <svg
      v-else
      :viewBox="`0 0 ${viewWidth} ${height}`"
      width="100%"
      :height="height"
      role="img"
    >
      <path v-if="area" :d="areaPath(series.main)" :fill="color" opacity="0.16" />
      <path v-if="area2 && series.second.length" :d="areaPath(series.second)" :fill="color2" opacity="0.14" />
      <path :d="path(series.main)" fill="none" :stroke="color" stroke-width="2" stroke-linejoin="round" />
      <path
        v-if="series.second.length"
        :d="path(series.second)"
        fill="none"
        :stroke="color2"
        stroke-width="2"
        stroke-dasharray="4 3"
        stroke-linejoin="round"
      />
      <circle v-for="point in series.main" :key="'m' + point.x" :cx="point.x" :cy="point.y" r="2.4" :fill="color">
        <title>{{ name }}: {{ fmtInt(point.raw) }}{{ suffix }}</title>
      </circle>
      <circle v-for="point in series.second" :key="'s' + point.x" :cx="point.x" :cy="point.y" r="2" :fill="color2">
        <title>{{ name2 }}: {{ fmtInt(point.raw) }}{{ suffix }}</title>
      </circle>
      <text
        v-for="(point, index) in points"
        v-show="index % labelStep === 0 || index === points.length - 1"
        :key="'l' + index"
        :x="series.main[index].x"
        :y="height - 8"
        text-anchor="middle"
        fill="rgba(220,234,255,.55)"
        font-size="10"
      >{{ point.label }}</text>
    </svg>
  </div>
</template>
