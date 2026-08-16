<script setup lang="ts">
/**
 * BarChart.vue — 柱状图薄封装（Task 008）
 *
 * 职责边界：仅 props → option 转换 + 点击事件转发，不含业务判断。
 */
import { computed } from 'vue';
import type { RankingItem } from '@/types/security';
import EChartBase from './EChartBase.vue';
import type { ChartOption } from './chartTypes';
import type { ECElementEvent } from 'echarts';

const props = withDefaults(
  defineProps<{
    /** 柱状数据（name 为类目，score 为数值） */
    data: RankingItem[];
    /** 横向柱状图（类目在 Y 轴） */
    horizontal?: boolean;
    title?: string;
    height?: string;
    color?: string;
    /** 多系列数据（与 data 类目对齐）；提供时渲染多系列柱状图 */
    series?: Array<{ name: string; data: number[] }>;
    /** 多系列时的类目（缺省取 data 的 name） */
    categories?: string[];
    /** 多系列堆叠（需求 7.3 数据集风险占比堆叠柱状图） */
    stacked?: boolean;
    /** 多系列配色 */
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
  /** 柱点击（需求 7.1 端口预填 / 7.2 设备筛选 / 7.3 数据集联动） */
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
