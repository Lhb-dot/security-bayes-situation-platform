/**
 * profileTokens —— 场景数据画像驾驶舱（四场景管理员首页）共用的视觉令牌。
 *
 * 与管理员平台总览（AdminOverviewDashboard）保持同一套语言：
 *   - 配色沿用管理员首页的强调色（蓝 / 青 / 金 / 红 / 紫 / 灰）；
 *   - 图标沿用同一批线性图标路径（管理员首页里是内联常量，这里集中登记，
 *     供四个场景看板与 KPI 卡片共用，避免各页面各写一份）。
 * 图表调色板与格式化函数直接复用 components/dashboard/dashFormat（项目既有实现），
 * 不在这里另起一套数值口径。
 */

/** KPI / 条形 / 标签的语义色（与管理员首页的强调色一致） */
export const TONE_COLOR = {
  primary: '#7dc9ff',
  success: '#62cdb4',
  warning: '#ebc07d',
  danger: '#e99686',
  purple: '#a999ee',
  gray: '#9fb3c4',
} as const;

export type Tone = keyof typeof TONE_COLOR;

/** 取值即用：未知 tone 一律回落到 primary，避免模板里出现 undefined 色值 */
export const toneColor = (tone: Tone | undefined): string => TONE_COLOR[tone ?? 'primary'];

/** 处置状态三态的固定配色（与管理员首页的事件状态条一致） */
export const STATUS_COLOR = {
  pending: '#e99686',
  processing: '#ebc07d',
  resolved: '#62cdb4',
} as const;

/** 场景画像用到的线性图标（路径与管理员首页同一套） */
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

/**
 * 读取当前作用域里的 --u 基准（px）。
 *
 * 驾驶舱所有尺寸都是 calc(N * var(--u))，图表里少数只能用数值属性表达的量
 * （SVG 圆点半径等）需要拿到这个基准才能跟 CSS 同步缩放；取不到时按 1 兜底
 * （等于 1440×900 设计基准），不会出现 0 导致图形消失。
 */
export const readUnit = (el: HTMLElement | null): number => {
  if (!el) return 1;
  const value = Number.parseFloat(getComputedStyle(el).getPropertyValue('--u'));
  return Number.isFinite(value) && value > 0 ? value : 1;
};

/** 百分比文本：入参是 0-1 比率，空值给「—」（不写成 0%，那是「全部不合格」的假结论） */
export const percentText = (ratio: number | null | undefined, digits = 1): string =>
  ratio === null || ratio === undefined || !Number.isFinite(Number(ratio))
    ? '—'
    : `${(Number(ratio) * 100).toFixed(digits)}%`;

/**
 * 后端枚举 → 管理端中文。
 * 四个场景看板共用同一份映射：同一枚举在两页给出两种中文，读者会以为是两个口径。
 */
export const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};

export const visibilityText = (value: string | null | undefined): string =>
  value ? (VISIBILITY_TEXT[value] ?? value) : '—';

/** 标签类型（纯描述性，不参与正类判定） */
export const LABEL_KIND_TEXT: Record<string, string> = {
  binary: '二分类',
  multiclass: '多分类',
  numeric: '数值',
  unknown: '未知',
};

export const labelKindText = (kind: string | null | undefined): string =>
  kind ? (LABEL_KIND_TEXT[kind] ?? '未知') : '—';
