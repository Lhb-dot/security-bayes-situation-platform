// 首页看板通用格式化与调色板，取值口径见 docs/首页字段口径说明.md。

// 与 demo 一致的图表配色序列
export const DASH_COLORS = ['#5ba6ff', '#53e5c8', '#ffd166', '#ff7b72', '#a78bfa', '#8a93a6'];

export const fmtInt = (value: unknown): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return Math.round(num).toLocaleString('zh-CN');
};

export const fmtNum = (value: unknown, digits = 2): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return num.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits });
};

export const fmtPercent = (value: unknown, digits = 1): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return (num * 100).toFixed(digits) + '%';
};

// 已经是百分数的数值 → 百分比字符串（入参为 0-100）
export const fmtPercentValue = (value: unknown, digits = 1): string => {
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  return num.toFixed(digits) + '%';
};

export const fmtDateTime = (value: unknown): string => {
  if (!value) return '—';
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

export const fmtDate = (value: unknown): string => String(value ?? '').slice(5);

export const colorAt = (index: number): string => DASH_COLORS[index % DASH_COLORS.length];

export const tagClass = (value: unknown): string => {
  const key = String(value ?? '').toUpperCase();
  if (key === 'HIGH' || key === 'PENDING') return 'd-tag--pending';
  if (key === 'MEDIUM' || key === 'PROCESSING') return 'd-tag--processing';
  if (key === 'RESOLVED') return 'd-tag--resolved';
  if (key === 'LOW') return 'd-tag--low';
  return 'd-tag--ok';
};

export const tagText = (value: unknown): string => {
  const map: Record<string, string> = {
    HIGH: '高危',
    MEDIUM: '中危',
    LOW: '低危',
    PENDING: '待处置',
    PROCESSING: '处理中',
    RESOLVED: '已处置',
  };
  return map[String(value ?? '').toUpperCase()] ?? String(value ?? '—');
};
