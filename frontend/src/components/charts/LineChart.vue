<script setup lang="ts">
/**
 * LineChart.vue — 折线/面积图薄封装（Task 008）
 *
 * 职责边界：仅 props → option 转换，不含业务判断。
 */
import { computed } from 'vue';
import type { TrendPoint } from '@/types/security';
import EChartBase from './EChartBase.vue';
import type { ChartOption } from './chartTypes';

const props = withDefaults(
  defineProps<{
    /** 折线数据（label 为横轴类目，value 为纵轴数值） */
    points: TrendPoint[];
    /** 面积填充 */
    area?: boolean;
    smooth?: boolean;
    title?: string;
    height?: string;
    color?: string;
  }>(),
  {
    area: false,
    smooth: true,
    height: '100%',
    color: '#5ba6ff',
  }
);

const option = computed<ChartOption>(() => ({
  title: props.title
    ? { text: props.title, left: 'center', top: 4, textStyle: { fontSize: 14 } }
    : undefined,
  tooltip: { trigger: 'axis' },
  grid: { left: 8, right: 16, top: props.title ? 48 : 20, bottom: 8, containLabel: true },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: props.points.map((point) => point.label),
  },
  yAxis: { type: 'value' },
  series: [
    {
      type: 'line',
      data: props.points.map((point) => point.value),
      smooth: props.smooth,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: { width: 2, color: props.color },
      itemStyle: { color: props.color },
      areaStyle: props.area ? { color: props.color, opacity: 0.18 } : undefined,
    },
  ],
}));
</script>

<template>
  <EChartBase :option="option" :height="height" />
</template>
