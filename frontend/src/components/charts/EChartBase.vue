<script setup lang="ts">
/**
 * EChartBase.vue — 通用 ECharts 包装器（Task 008）
 *
 * 职责边界：仅负责 init / setOption / resize / dispose / loading，
 * 不含任何业务图表逻辑；option 由上层组件传入。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { init, registerTheme, use } from 'echarts/core';
import type { ECharts } from 'echarts/core';
import type { ECElementEvent } from 'echarts';
import { BarChart, LineChart, PieChart, RadarChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { ChartOption } from './chartTypes';

// 按需注册（模块级执行一次；echarts.use 重复调用会合并，无副作用）
use([
  BarChart,
  LineChart,
  PieChart,
  RadarChart,
  GridComponent,
  LegendComponent,
  RadarComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
]);

// 暗色主题（配色与全局 style.css 一致：#5ba6ff / #53e5c8 / #ff7b72 / #ffd166）
let themeRegistered = false;
const registerBayesDarkTheme = () => {
  if (themeRegistered) return;
  themeRegistered = true;
  registerTheme('bayes-dark', {
    color: ['#5ba6ff', '#53e5c8', '#ff7b72', '#ffd166', '#a78bfa', '#ffb26b'],
    backgroundColor: 'transparent',
    textStyle: { color: '#eaf3ff' },
    title: { textStyle: { color: '#eaf3ff' } },
    legend: { textStyle: { color: 'rgba(234,243,255,0.8)' } },
    tooltip: {
      backgroundColor: 'rgba(10,20,38,0.94)',
      borderColor: 'rgba(125,201,255,0.25)',
      textStyle: { color: '#eaf3ff' },
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: 'rgba(125,201,255,0.25)' } },
      axisLabel: { color: 'rgba(234,243,255,0.7)' },
      splitLine: { lineStyle: { color: 'rgba(125,201,255,0.12)' } },
    },
    valueAxis: {
      axisLine: { lineStyle: { color: 'rgba(125,201,255,0.25)' } },
      axisLabel: { color: 'rgba(234,243,255,0.7)' },
      splitLine: { lineStyle: { color: 'rgba(125,201,255,0.12)' } },
    },
    radar: {
      axisName: { color: 'rgba(234,243,255,0.8)' },
      axisLine: { lineStyle: { color: 'rgba(125,201,255,0.25)' } },
      splitLine: { lineStyle: { color: 'rgba(125,201,255,0.12)' } },
      splitArea: {
        areaStyle: { color: ['rgba(91,166,255,0.04)', 'rgba(91,166,255,0.08)'] },
      },
    },
  });
};
registerBayesDarkTheme();

const props = withDefaults(
  defineProps<{
    /** ECharts option（由上层组件/页面提供） */
    option: ChartOption;
    /** 容器高度（宽度始终 100%） */
    height?: string;
    /** 加载态：true 时显示 loading 遮罩 */
    loading?: boolean;
    /** setOption 是否不合并（默认 false 增量合并） */
    notMerge?: boolean;
  }>(),
  {
    height: '100%',
    loading: false,
    notMerge: false,
  }
);

const emit = defineEmits<{
  /** ECharts 实例点击事件（供上层实现"点击图表联动/跳转"交互） */
  'chart-click': [params: ECElementEvent];
}>();

const container = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;
let observer: ResizeObserver | null = null;
let resizeFrame = 0;

const applyOption = () => {
  chart?.setOption(props.option, { notMerge: props.notMerge });
};

const applyLoading = () => {
  if (!chart) return;
  if (props.loading) {
    chart.showLoading('default', {
      text: '',
      color: '#5ba6ff',
      maskColor: 'rgba(5,11,22,0.4)',
    });
  } else {
    chart.hideLoading();
  }
};

const resizeChart = () => {
  if (resizeFrame) cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(() => chart?.resize());
};

onMounted(() => {
  if (!container.value) return;
  chart = init(container.value, 'bayes-dark');
  applyOption();
  applyLoading();
  chart.on('click', (params: ECElementEvent) => {
    emit('chart-click', params);
  });
  observer = new ResizeObserver(resizeChart);
  observer.observe(container.value);
});

watch(() => props.option, applyOption, { deep: true });
watch(() => props.loading, applyLoading);

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
  if (resizeFrame) cancelAnimationFrame(resizeFrame);
  if (chart) {
    chart.dispose();
    chart = null;
  }
});
</script>

<template>
  <div ref="container" class="echart-base" :style="{ height }"></div>
</template>

<style scoped>
.echart-base {
  width: 100%;
  min-height: 0;
}
</style>
