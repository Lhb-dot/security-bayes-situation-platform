<script setup lang="ts">
/**
 * CockpitDonut —— 环形占比图 + 图例（与管理员首页「样本构成」同一画法：
 * viewBox 160、半径 58、pathLength=100 的 dasharray 分段，圆心写合计）。
 * 图例数值默认按占比展示（percent=true），便于回答「谁占大头」。
 */
import { computed } from 'vue';
import { colorAt, fmtInt } from '@/components/dashboard/dashFormat';

export interface CockpitDonutItem {
  label: string;
  value: number;
}

const props = withDefaults(
  defineProps<{
    items: CockpitDonutItem[];
    centerLabel?: string;
    /** 图例数值是否展示为占比 */
    percent?: boolean;
    /** 图例数值后缀（percent=false 时生效） */
    suffix?: string;
    /** 最多几个扇区，其余归入「其他」 */
    limit?: number;
  }>(),
  { centerLabel: '合计', percent: true, suffix: '', limit: 0 },
);

const RADIUS = 58;

const slices = computed(() => {
  let list = props.items.map((item) => ({ label: item.label, value: Number(item.value) || 0 }));
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
      const length = total ? (item.value / total) * 100 : 0;
      const row = { ...item, fill: colorAt(index), length, offset, percentText: total ? ((item.value / total) * 100).toFixed(1) : '0.0' };
      offset += length;
      return row;
    }),
  };
});

const legendText = (row: { value: number; percentText: string }): string =>
  props.percent ? `${row.percentText}%` : `${fmtInt(row.value)}${props.suffix}`;
</script>

<template>
  <p v-if="!items.length" class="pf-empty">暂无数据</p>
  <div v-else class="pf-donut">
    <svg viewBox="0 0 160 160" role="img" :aria-label="centerLabel">
      <circle cx="80" cy="80" :r="RADIUS" fill="none" stroke="#152f45" :stroke-width="13" />
      <circle
        v-for="row in slices.rows"
        :key="row.label"
        cx="80"
        cy="80"
        :r="RADIUS"
        pathLength="100"
        fill="none"
        :stroke="row.fill"
        :stroke-width="13"
        :stroke-dasharray="`${Math.max(0, row.length - 0.6)} ${100 - Math.max(0, row.length - 0.6)}`"
        :stroke-dashoffset="-row.offset"
        transform="rotate(-90 80 80)"
      >
        <title>{{ row.label }}：{{ row.percentText }}%</title>
      </circle>
      <circle cx="80" cy="80" r="43" fill="none" stroke="#24475e" stroke-dasharray="2 5" stroke-width="1" />
      <text x="80" y="77" text-anchor="middle" fill="#dfedf6" font-size="16" font-weight="600">
        {{ fmtInt(slices.total) }}
      </text>
      <text x="80" y="96" text-anchor="middle" fill="#7895aa" font-size="10">{{ centerLabel }}</text>
    </svg>
    <div class="pf-legend">
      <div v-for="row in slices.rows" :key="`lg-${row.label}`" class="pf-legend-row" :title="`${row.label}：${row.percentText}%`">
        <span class="pf-dot" :style="{ background: row.fill }"></span>
        <span>{{ row.label }}</span>
        <strong>{{ legendText(row) }}</strong>
      </div>
    </div>
  </div>
</template>
