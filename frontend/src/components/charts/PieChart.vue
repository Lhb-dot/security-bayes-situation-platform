<template>
  <EChartBase :option="option" :height="height" />
</template>
<script setup lang="ts">
/**
 * 饼图/环形图薄封装
 * 职责边界：仅 props → option 转换，不含业务判断。
 */
import { computed } from 'vue';
import type { TypeDistribution } from '@/types/security';
import EChartBase from './EChartBase.vue';
import type { ChartOption } from './chartTypes';

const props = withDefaults(
  defineProps<{
    items: TypeDistribution[];
    donut?: boolean;
    title?: string;
    height?: string;
  }>(),
  {
    donut: false,
    height: '100%',
  }
);

const option = computed<ChartOption>(() => ({
  title: props.title
    ? { text: props.title, left: 'center', top: 4, textStyle: { fontSize: 14 } }
    : undefined,
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, type: 'scroll' },
  series: [
    {
      type: 'pie',
      radius: props.donut ? ['45%', '70%'] : '70%',
      center: ['50%', '52%'],
      data: props.items.map((item) => ({
        name: item.label,
        value: item.value,
        itemStyle: { color: item.color },
      })),
      label: { color: 'rgba(234,243,255,0.75)', fontSize: 11 },
    },
  ],
}));
</script>
