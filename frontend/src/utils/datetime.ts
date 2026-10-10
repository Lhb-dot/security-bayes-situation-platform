/**
 * datetime.ts — 前端时间解析与格式化的唯一入口。
 *
 * 后端下发的字段有两种形态，务必按来源选对解析函数：
 * 1. ORM DateTime 列由 row_to_dict 转成北京时间 naive 字符串，用 parseBeijingNaive。
 * 2. JSONB 时间或 dashboard_service 直出的 occurred_at 是带时区 ISO 串，用 parseInstant。
 *
 * 格式化一律按北京时间（UTC+8）输出，不依赖浏览器本地时区。
 */

const BEIJING_OFFSET_MS = 8 * 60 * 60 * 1000;

const HAS_ZONE = /[zZ]|[+-]\d{2}:?\d{2}$/;

const pad = (n: number): string => String(n).padStart(2, '0');

/** 北京时间 naive 字符串 → epoch 毫秒；无法解析时返回 null。 */
export const parseBeijingNaive = (value?: string | null): number | null => {
  if (!value) return null;
  const normalized = String(value).trim().replace(' ', 'T');
  if (!normalized) return null;
  const parsed = new Date(HAS_ZONE.test(normalized) ? normalized : `${normalized}+08:00`).getTime();
  return Number.isFinite(parsed) ? parsed : null;
};

/** 带时区 ISO 串 → epoch 毫秒；无时区标记时按 UTC 解释。 */
export const parseInstant = (value?: string | null): number | null => {
  if (!value) return null;
  const raw = String(value).trim();
  if (!raw) return null;
  const parsed = new Date(HAS_ZONE.test(raw) ? raw : `${raw}Z`).getTime();
  return Number.isFinite(parsed) ? parsed : null;
};

/** epoch 秒 → epoch 毫秒；缺失或非法时退回本地时钟。 */
export const toMillis = (createdAt?: number): number =>
  typeof createdAt === 'number' && Number.isFinite(createdAt) && createdAt > 0
    ? createdAt * 1000
    : Date.now();

/** 把 epoch 毫秒拆成北京时间的年月日时分秒（与浏览器时区无关）。 */
export const toBeijingParts = (ms: number) => {
  const d = new Date(ms + BEIJING_OFFSET_MS);
  return {
    year: d.getUTCFullYear(),
    month: d.getUTCMonth() + 1,
    day: d.getUTCDate(),
    hour: d.getUTCHours(),
    minute: d.getUTCMinutes(),
    second: d.getUTCSeconds(),
  };
};

/** epoch 毫秒 → `YYYY-MM-DD HH:mm:ss`（北京时间）。 */
export const formatBeijingDateTime = (ms: number): string => {
  const p = toBeijingParts(ms);
  return `${p.year}-${pad(p.month)}-${pad(p.day)} ${pad(p.hour)}:${pad(p.minute)}:${pad(p.second)}`;
};

/** epoch 毫秒 → `MM-DD HH:mm`（北京时间）。 */
export const formatBeijingShort = (ms: number): string => {
  const p = toBeijingParts(ms);
  return `${pad(p.month)}-${pad(p.day)} ${pad(p.hour)}:${pad(p.minute)}`;
};
