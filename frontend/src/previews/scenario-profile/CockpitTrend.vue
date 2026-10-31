<script setup lang="ts">
/**
 * CockpitTrend，近 10 天活动趋势（实线=推理量，虚线=其中判定为风险的量）。
 * 坐标按容器实测宽高计算（viewBox 与渲染尺寸 1:1），因此圆点恒为正圆、文字不被拉伸；
 * 圆点半径与线宽从 --u 读取（见 profileTokens.readUnit），与页面其余尺寸同步缩放。
 * 横轴标签按可用宽度抽稀，保证不重叠。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { fmtInt } from '@/components/dashboard/dashFormat';
import { readUnit } from './profileTokens';

export interface CockpitTrendPoint {
  label: string;
  value: number;
  value2?: number | null;
}

const props = withDefaults(
  defineProps<{
    points: CockpitTrendPoint[];
    name: string;
    name2?: string;
    unit?: string;
    color?: string;
    color2?: string;
  }>(),
  { name2: '', unit: '', color: '#5ba6ff', color2: '#53e5c8' },
);

const hostRef = ref<HTMLElement | null>(null);
const width = ref(360);
const height = ref(90);
const unit = ref(1);
let observer: ResizeObserver | null = null;

const measure = () => {
  const host = hostRef.value;
  if (!host) return;
  const rect = host.getBoundingClientRect();
  if (rect.width > 0) width.value = Math.round(rect.width);
  if (rect.height > 0) height.value = Math.round(rect.height);
  unit.value = readUnit(host);
};

onMounted(() => {
  measure();
  const host = hostRef.value;
  if (!host) return;
  observer = new ResizeObserver(measure);
  observer.observe(host);
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});

const hasSecond = computed(() => props.points.some((point) => point.value2 !== undefined && point.value2 !== null));

const geometry = computed(() => {
  const u = unit.value;
  const top = 14 * u;
  const bottom = 15 * u;
  const left = 4 * u;
  const right = 4 * u;
  const plotW = Math.max(width.value - left - right, 10);
  const plotH = Math.max(height.value - top - bottom, 10);
  const count = props.points.length;
  const values = props.points.flatMap((point) =>
    hasSecond.value ? [Number(point.value) || 0, Number(point.value2) || 0] : [Number(point.value) || 0],
  );
  const peak = Math.max(...values, 0);
  const xAt = (index: number) => left + (count > 1 ? (plotW * index) / (count - 1) : plotW / 2);
  const yAt = (value: number) => top + plotH - (peak ? (Math.max(value, 0) / peak) * plotH : 0);
  const line = (pick: (point: CockpitTrendPoint) => number) =>
    props.points.map((point, index) => `${index === 0 ? 'M' : 'L'}${xAt(index).toFixed(1)},${yAt(pick(point)).toFixed(1)}`).join(' ');
  const area = `${line((point) => Number(point.value) || 0)} L${xAt(count - 1).toFixed(1)},${(top + plotH).toFixed(1)} L${xAt(0).toFixed(1)},${(top + plotH).toFixed(1)} Z`;
  // 横轴标签抽稀：每个标签预留约 52u 宽度，避免 10 个日期挤在一起
  const labelStep = Math.max(1, Math.ceil(count / Math.max(2, Math.floor(plotW / (52 * u)))));
  return {
    u,
    top,
    plotW,
    plotH,
    peak,
    baseY: top + plotH,
    mainPath: count ? line((point) => Number(point.value) || 0) : '',
    secondPath: count && hasSecond.value ? line((point) => Number(point.value2) || 0) : '',
    areaPath: count ? area : '',
    dots: props.points.map((point, index) => ({
      key: `d-${index}`,
      cx: xAt(index),
      cy: yAt(Number(point.value) || 0),
      value: Number(point.value) || 0,
    })),
    labels: props.points.map((point, index) => ({
      key: `l-${index}`,
      x: xAt(index),
      text: point.label,
      show: index % labelStep === 0 || index === count - 1,
    })),
  };
});
</script>

<template>
  <div ref="hostRef" class="pf-trend">
    <div v-if="name2" class="pf-trend-legend">
      <span><i :style="{ background: color }"></i>{{ name }}</span>
      <span><i :style="{ background: color2 }"></i>{{ name2 }}</span>
    </div>
    <p v-if="!points.length" class="pf-empty">暂无数据</p>
    <svg v-else :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none" role="img" :aria-label="name">
      <line :x1="0" :y1="geometry.baseY" :x2="width" :y2="geometry.baseY" stroke="#699abb1f" />
      <line
        :x1="0"
        :y1="geometry.top"
        :x2="width"
        :y2="geometry.top"
        stroke="#699abb1f"
        :stroke-dasharray="`${2 * geometry.u} ${4 * geometry.u}`"
      />
      <text x="0" :y="geometry.top - 3 * geometry.u" fill="#82a0b4">{{ fmtInt(geometry.peak) }}{{ unit }}</text>
      <path :d="geometry.areaPath" :fill="color" opacity="0.16" stroke="none" />
      <path :d="geometry.mainPath" fill="none" :stroke="color" :stroke-width="1.8 * geometry.u" stroke-linejoin="round" />
      <path
        v-if="geometry.secondPath"
        :d="geometry.secondPath"
        fill="none"
        :stroke="color2"
        :stroke-width="1.6 * geometry.u"
        :stroke-dasharray="`${4 * geometry.u} ${3 * geometry.u}`"
        stroke-linejoin="round"
      />
      <circle
        v-for="dot in geometry.dots"
        :key="dot.key"
        :cx="dot.cx"
        :cy="dot.cy"
        :r="2.2 * geometry.u"
        :fill="color"
        stroke="none"
      >
        <title>{{ name }}：{{ fmtInt(dot.value) }}{{ unit }}</title>
      </circle>
      <text
        v-for="label in geometry.labels"
        v-show="label.show"
        :key="label.key"
        :x="label.x"
        :y="height - 3 * geometry.u"
        text-anchor="middle"
        fill="#7c9eb4"
      >{{ label.text }}</text>
    </svg>
  </div>
</template>
