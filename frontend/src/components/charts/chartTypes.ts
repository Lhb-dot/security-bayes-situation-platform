/**
 * chartTypes.ts — ECharts 图表封装共享类型（Task 008）
 *
 * 按需引入 echarts/core 并组合出本项目图表使用的 option 类型。
 * 业务数据仍来自 src/types/security.ts，本文件仅承载图表基础设施类型。
 */
import type { ComposeOption } from 'echarts/core';
import type {
  BarSeriesOption,
  LineSeriesOption,
  PieSeriesOption,
  RadarSeriesOption,
} from 'echarts/charts';
import type {
  GridComponentOption,
  LegendComponentOption,
  RadarComponentOption,
  TitleComponentOption,
  TooltipComponentOption,
} from 'echarts/components';

/** 本项目图表统一 option 类型（Bar/Line/Pie/Radar + 通用组件） */
export type ChartOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | PieSeriesOption
  | RadarSeriesOption
  | TitleComponentOption
  | TooltipComponentOption
  | GridComponentOption
  | LegendComponentOption
  | RadarComponentOption
>;
