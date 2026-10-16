/** Design exploration only. These taxonomy and cross-tab examples are NOT backend facts. */
import type { CountItem } from '@/api/dashboardApi';
import type { ProfileChartSpec } from './profileCharts';
import { bars } from './profileCharts';

export const landslideSizes = ['小型', '中型', '大型', '特大型'];
export const landslideSizeColors = ['#5baee2', '#58d1c1', '#d9b775', '#ca8aa9'];
export const landslideTriggers = ['降雨', '工程扰动', '地震', '其他 / 未知'];
export type LandslideFamily = 'soil' | 'rock';
export interface LandslideDesignType {
  id: string; name: string; english: string; family: LandslideFamily;
  sizes: number[]; triggers: number[];
}
// 一级按组成物质；土质亚类按土体来源，岩质亚类按滑面与岩层关系。
// 名称参考自然资源部门科普，样本量和联合分布全部为独立设计示意。
export const landslideDesignTypes: LandslideDesignType[] = [
  { id: 'residual', name: '残积土滑坡', english: 'RESIDUAL SOIL', family: 'soil', sizes: [158, 108, 44, 16], triggers: [210, 72, 18, 26] },
  { id: 'loess', name: '黄土滑坡', english: 'LOESS', family: 'soil', sizes: [87, 81, 34, 12], triggers: [112, 48, 26, 28] },
  { id: 'fill', name: '填土滑坡', english: 'FILL', family: 'soil', sizes: [82, 34, 10, 2], triggers: [48, 64, 6, 10] },
  { id: 'bedding', name: '顺层滑坡', english: 'BEDDING-PARALLEL', family: 'rock', sizes: [76, 86, 44, 12], triggers: [102, 52, 42, 22] },
  { id: 'cross', name: '切层滑坡', english: 'CROSS-BEDDING', family: 'rock', sizes: [39, 38, 28, 9], triggers: [48, 24, 30, 12] },
];
export const designTypeCount = (type: LandslideDesignType) => type.sizes.reduce((sum, value) => sum + value, 0);
export const designTotal = landslideDesignTypes.reduce((sum, type) => sum + designTypeCount(type), 0);
export const designMatches = (type: LandslideDesignType, selection: string) => selection === 'all' || selection === type.family || selection === type.id;
export const designSelectionLabel = (selection: string) => selection === 'all' ? '全部类型' : selection === 'soil' ? '土质滑坡' : selection === 'rock' ? '岩质滑坡' : landslideDesignTypes.find(type => type.id === selection)?.name || '全部类型';
export const designDistribution = (selection: string, dimension: 'sizes' | 'triggers'): CountItem[] => {
  const types = landslideDesignTypes.filter(type => designMatches(type, selection));
  const labels = dimension === 'sizes' ? landslideSizes : landslideTriggers;
  return labels.map((value, i) => ({ value, count: types.reduce((sum, type) => sum + (type[dimension][i] ?? 0), 0) }));
};
export function designTriggerChart(selection: string): ProfileChartSpec {
  const items = designDistribution(selection, 'triggers');
  return {
    title: '滑坡诱因构成', tag: 'TRIGGER PROFILE', available: true,
    note: '当前分类的诱因构成 · 分类联动与数值均为设计示意',
    option: {
      animation: false, color: ['#5bd3c3', '#71aff0', '#c6a1ef', '#c7af7e'],
      tooltip: { trigger: 'item', confine: true, backgroundColor: '#0c2539', borderColor: '#3b657f', textStyle: { color: '#d5e9f4', fontSize: 11 }, formatter: '{b}：{c} 条（{d}%）' },
      legend: { right: 0, top: 'middle', orient: 'vertical', itemWidth: 6, itemHeight: 6, itemGap: 10, textStyle: { color: '#a8c3d4', fontSize: 10 }, formatter: name => `${name}  ${items.find(item => item.value === name)?.count ?? 0}` },
      series: [{ type: 'pie', radius: ['47%', '72%'], center: ['28%', '50%'], label: { show: false }, labelLine: { show: false }, itemStyle: { borderColor: '#0b2032', borderWidth: 3 }, data: items.map(item => ({ name: item.value, value: item.count })), emphasis: { label: { show: true, position: 'center', formatter: '{d}%', color: '#e4f4fc', fontSize: 20 } } }],
    },
  };
}
export function designScaleChart(selection: string): ProfileChartSpec {
  const chart = bars('滑坡规模结构', designDistribution(selection, 'sizes'), '规模与类型分别统计 · 不以规模代替滑坡类型', '#6fc7d2');
  chart.tag = 'SCALE COMPOSITION';
  const series = chart.option.series;
  if (Array.isArray(series) && series[0] && series[0].type === 'bar') {
    series[0].data = designDistribution(selection, 'sizes').map((item, i) => ({ value: item.count, itemStyle: { color: landslideSizeColors[i] } }));
  }
  return chart;
}
