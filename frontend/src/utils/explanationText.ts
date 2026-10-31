/**
 * 解释文本展示清洗。
 * 历史风险事件的正文里写进了未格式化的风险评分（如 0.9999999999998914）。
 * 该文本在事件生成时固化入库，生成侧修复只对新事件生效，
 * 所以旧数据统一在展示侧收口。列表页与详情页共用 formatExplanation。
 */

const RAW_SCORE = /(风险评分：)(\d+\.\d{6,})/g;

export function formatExplanation(text: string): string {
  if (!text) return '';
  return text.replace(RAW_SCORE, (match, prefix: string, raw: string) => {
    const value = Number(raw);
    return Number.isFinite(value) ? `${prefix}${(value * 100).toFixed(1)}%` : match;
  });
}

const VERDICT_HEAD = /^[^，]*被判定为[^，]*（风险评分：[^）]*）/;

const ADVICE_TAIL = /，建议[^。]*。$/;

export function shortExplanation(text: string): string {
  if (!text) return '';
  const full = formatExplanation(text);
  const body = full
    .replace(VERDICT_HEAD, '')
    .replace(/^，/, '')
    .replace(ADVICE_TAIL, '。')
    .trim();
  return body || full;
}
