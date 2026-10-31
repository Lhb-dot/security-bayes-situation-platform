/**
 * 四场景管理员首页共用的视觉令牌：配色、线性图标、面板与卡片尺寸。
 * 图表调色板与格式化函数复用 components/dashboard/dashFormat。
 */

export const TONE_COLOR = {
  primary: '#7dc9ff',
  success: '#62cdb4',
  warning: '#ebc07d',
  danger: '#e99686',
  purple: '#a999ee',
  gray: '#9fb3c4',
} as const;

export type Tone = keyof typeof TONE_COLOR;

export const toneColor = (tone: Tone | undefined): string => TONE_COLOR[tone ?? 'primary'];

export const STATUS_COLOR = {
  pending: '#e99686',
  processing: '#ebc07d',
  resolved: '#62cdb4',
} as const;

export const PROFILE_ICONS = {
  scene: 'M4 4h6v6H4z M14 4h6v6h-6z M4 14h6v6H4z M14 14h6v6h-6z',
  data: 'M4 5c0-2 16-2 16 0s-16 2-16 0 M4 5v14c0 2 16 2 16 0V5 M4 12c0 2 16 2 16 0',
  model: 'M12 3l8 5v8l-8 5-8-5V8z M4 8l8 5 8-5 M12 13v8 M8 5l8 5',
  prediction: 'M3 17l5-5 4 3 8-10 M14 5h6v6 M3 21h18',
  network: 'M12 3l8 3v6c0 4-4 7-8 9-4-2-8-5-8-9V6z M8 12l3 3 5-6',
  power: 'M13 2L5 14h6l-1 8 9-13h-7z',
  flight: 'M21 3L3 10l7 3 3 7z M10 13l6-5',
  mountain: 'M2 20L9 5l5 9 3-6 5 12z M6 11l3 2 2-3',
  layers: 'M12 3l9 5-9 5-9-5z M3 13l9 5 9-5',
  matrix: 'M3 3h18v18H3z M3 9h18 M3 15h18 M9 3v18 M15 3v18',
  label: 'M3 11l8-8h7v7l-8 8z M15 6h.01',
  trend: 'M3 17l5-5 4 3 8-10 M14 5h6v6',
  user: 'M15 7a3 3 0 1 1-6 0 3 3 0 0 1 6 0 M5 21v-3c0-6 14-6 14 0v3',
  alert: 'M12 3l9 17H3z M12 9v5 M12 17h.01',
} as const;

export type ProfileIconKey = keyof typeof PROFILE_ICONS;

export const readUnit = (el: HTMLElement | null): number => {
  if (!el) return 1;
  const value = Number.parseFloat(getComputedStyle(el).getPropertyValue('--u'));
  return Number.isFinite(value) && value > 0 ? value : 1;
};

export const percentText = (ratio: number | null | undefined, digits = 1): string =>
  ratio === null || ratio === undefined || !Number.isFinite(Number(ratio))
    ? '—'
    : `${(Number(ratio) * 100).toFixed(digits)}%`;

export const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};

export const visibilityText = (value: string | null | undefined): string =>
  value ? (VISIBILITY_TEXT[value] ?? value) : '—';

export const LABEL_KIND_TEXT: Record<string, string> = {
  binary: '二分类',
  multiclass: '多分类',
  numeric: '数值',
  unknown: '未知',
};

export const labelKindText = (kind: string | null | undefined): string =>
  kind ? (LABEL_KIND_TEXT[kind] ?? '未知') : '—';
