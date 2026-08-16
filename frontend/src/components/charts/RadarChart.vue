<script setup lang="ts">
/**
 * RadarChart.vue — 雷达图薄封装（Task 008）
 *
 * 职责边界：仅 props → option 转换，不含业务判断。
 * indicators/series 为图表基础设施结构（非业务类型）。
 */
import { computed } from 'vue';
import EChartBase from './EChartBase.vue';
import type { ChartOption } from './chartTypes';

interface RadarIndicator {
  name: string;
  max?: number;
}

interface RadarSeriesData {
  name: string;
  values: number[];
}

const props = withDefaults(
  defineProps<{
    /** 雷达指示器（维度名称与最大值） */
    indicators: RadarIndicator[];
    /** 雷达系列（多组对比） */
    series: RadarSeriesData[];
    title?: string;
    height?: string;
    colors?: string[];
  }>(),
  {
    height: '100%',
    colors: () => ['#5ba6ff', '#53e5c8', '#ff7b72', '#ffd166'],
  }
);

const option = computed<ChartOption>(() => ({
  title: props.title
    ? { text: props.title, left: 'center', top: 4, textStyle: { fontSize: 14 } }
    : undefined,
  tooltip: { trigger: 'item' },
  legend: { bottom: 0 },
  radar: {
    indicator: props.indicators.map((item) => ({ name: item.name, max: item.max ?? 100 })),
    radius: '65%',
  },
  series: [
    {
      type: 'radar',
      data: props.series.map((item, index) => ({
        name: item.name,
        value: item.values,
        lineStyle: { width: 2 },
        areaStyle: { opacity: 0.12 },
        itemStyle: { color: props.colors[index % props.colors.length] },
      })),
    },
  ],
}));
</script>

<template>
  <EChartBase :option="option" :height="height" />
</template>
