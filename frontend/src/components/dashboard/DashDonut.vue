<script setup lang="ts">
/**
 * DashDonut —— 环形占比图 + 图例（对应 demo 内联 svg 的环形图）。
 * 用于「协议分布 / 问题类型分布 / 系统分布 / 触发因素分布 / 风险分区间分布」等。
 */
import { computed } from 'vue';
import { colorAt, fmtInt } from './dashFormat';

const props = withDefaults(
  defineProps<{
    items: Array<{ label?: unknown; value?: unknown; count?: number | null }>;
    size?: number;
    /** 中心文案，默认「合计」 */
    centerLabel?: string;
    /** 图例数值展示为百分比 */
    percent?: boolean;
    /** 图例数值后缀 */
    suffix?: string;
    /** 最多展示的扇区数，其余归入「其他」 */
    limit?: number;
  }>(),
  { size: 160, centerLabel: '合计', percent: false, suffix: '', limit: 0 },
);

const RADIUS = 56;
const STROKE = 20;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const slices = computed(() => {
  let list = props.items.map((item) => ({
    label: String(item.label ?? item.value ?? '—'),
    value: Number(item.count ?? item.value ?? 0) || 0,
  }));
  if (props.limit > 0 && list.length > props.limit) {
    const head = list.slice(0, props.limit);
    const rest = list.slice(props.limit).reduce((sum, item) => sum + item.value, 0);
    list = rest > 0 ? [...head, { label: '其他', value: rest }] : head;
  }
  const total = list.reduce((sum, item) => sum + item.value, 0);
  let offset = 0;
  return {
    total,
    rows: list.map((item, index) => {
      const length = total ? (item.value / total) * CIRCUMFERENCE : 0;
      const row = { ...item, fill: colorAt(index), length, offset };
      offset += length;
      return row;
    }),
  };
});

const legendText = (value: number, total: number): string => {
  if (props.percent && total) return ((value / total) * 100).toFixed(1) + '%';
  return fmtInt(value) + props.suffix;
};
</script>

<template>
  <div class="d-donut">
    <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" role="img">
      <g>
        <circle
          v-if="!slices.total"
          :cx="size / 2"
          :cy="size / 2"
          :r="RADIUS"
          fill="none"
          stroke="rgba(255,255,255,.06)"
          :stroke-width="STROKE"
        />
        <circle
          v-for="slice in slices.rows"
          :key="slice.label"
          :cx="size / 2"
          :cy="size / 2"
          :r="RADIUS"
          fill="none"
          :stroke="slice.fill"
          :stroke-width="STROKE"
          :stroke-dasharray="`${slice.length} ${CIRCUMFERENCE}`"
          :stroke-dashoffset="-slice.offset"
          :transform="`rotate(-90 ${size / 2} ${size / 2})`"
        >
          <title>{{ slice.label }}: {{ fmtInt(slice.value) }}</title>
        </circle>
        <text
          :x="size / 2"
          :y="size / 2 - 1"
          text-anchor="middle"
          fill="#e8f1ff"
          font-size="20"
          font-weight="700"
        >{{ fmtInt(slices.total) }}</text>
        <text :x="size / 2" :y="size / 2 + 15" text-anchor="middle" fill="rgba(220,234,255,.5)" font-size="10">
          {{ centerLabel }}
        </text>
      </g>
    </svg>
    <div class="d-legend">
      <div v-for="slice in slices.rows" :key="'lg-' + slice.label" class="d-lg">
        <span class="d-dot" :style="{ background: slice.fill }"></span>
        <span class="d-lgk" :title="slice.label">{{ slice.label }}</span>
        <span class="d-lgv">{{ legendText(slice.value, slices.total) }}</span>
      </div>
    </div>
  </div>
</template>
