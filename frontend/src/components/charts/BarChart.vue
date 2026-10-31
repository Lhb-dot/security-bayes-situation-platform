<script setup lang="ts">
/**
 * 柱状图薄封装
 * 职责边界：仅 props → option 转换 + 点击事件转发，不含业务判断。
 */
import { computed } from 'vue';
import type { RankingItem } from '@/types/security';
import EChartBase from './EChartBase.vue';
import type { ChartOption } from './chartTypes';
import type { ECElementEvent } from 'echarts';

const props = withDefaults(
  defineProps<{
    data: RankingItem[];
    horizontal?: boolean;
    title?: string;
    height?: string;
    color?: string;
    series?: Array<{ name: string; data: number[] }>;
    categories?: string[];
    stacked?: boolean;
    colors?: string[];
  }>(),
  {
    horizontal: false,
    height: '100%',
    color: '#5ba6ff',
    stacked: false,
    colors: () => ['#5ba6ff', '#53e5c8', '#ff7b72', '#ffd166', '#a78bfa'],
  }
);

const emit = defineEmits<{
  // 柱点击
  'bar-click': [name: string];
}>();

const option = computed<ChartOption>(() => {
  const categories = props.categories ?? props.data.map((item) => item.name);
  const series = props.series
    ? props.series.map((s, index) => ({
        type: 'bar' as const,
        name: s.name,
        data: s.data,
        stack: props.stacked ? 'total' : undefined,
        itemStyle: { color: props.colors[index % props.colors.length], borderRadius: 2 },
        barMaxWidth: 18,
      }))
    : [
        {
          type: 'bar' as const,
          data: props.data.map((item) => item.score),
          itemStyle: { color: props.color, borderRadius: 2 },
          barMaxWidth: 18,
        },
      ];
  return {
    title: props.title
      ? { text: props.title, left: 'center', top: 4, textStyle: { fontSize: 14 } }
      : undefined,
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: props.series ? { bottom: 0 } : undefined,
    grid: { left: 8, right: 24, top: props.title ? 48 : 20, bottom: props.series ? 34 : 8, containLabel: true },
    xAxis: props.horizontal
      ? { type: 'value' }
      : { type: 'category', data: categories },
    yAxis: props.horizontal
      ? { type: 'category', data: categories, inverse: true }
      : { type: 'value' },
    series,
  };
});

const onChartClick = (params: ECElementEvent) => {
  const name = typeof params.name === 'string' ? params.name : String(params.name ?? '');
  emit('bar-click', name);
};
</script>

<template>
  <EChartBase :option="option" :height="height" @chart-click="onChartClick" />
</template>
