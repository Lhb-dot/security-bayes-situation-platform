import type { CountItem } from '@/api/dashboardApi';

// 分类结构用于导航，计数只能来自接口；不从诱因、规模或二分类风险标签推断亚类。
export const taxonomyTypes = [
  { id: 'residual', name: '残积土滑坡', english: 'RESIDUAL SOIL', family: 'soil' },
  { id: 'loess', name: '黄土滑坡', english: 'LOESS', family: 'soil' },
  { id: 'fill', name: '填土滑坡', english: 'FILL', family: 'soil' },
  { id: 'bedding', name: '顺层滑坡', english: 'BEDDING-PARALLEL', family: 'rock' },
  { id: 'cross', name: '切层滑坡', english: 'CROSS-BEDDING', family: 'rock' },
];
export const taxonomyMatches = (type: { id: string; family: string }, selection: string) => selection === 'all' || selection === type.id || selection === type.family;
export function taxonomyCount(items: CountItem[], id: string): number | null {
  const type = taxonomyTypes.find(item => item.id === id);
  const matching = items.filter(item => item.value.trim() === type?.name);
  return matching.length ? matching.reduce((sum, item) => sum + item.count, 0) : null;
}
export const taxonomyLabel = (selection: string) => selection === 'all' ? '全部类型' : selection === 'soil' ? '土质滑坡' : selection === 'rock' ? '岩质滑坡' : taxonomyTypes.find(type => type.id === selection)?.name ?? '全部类型';
