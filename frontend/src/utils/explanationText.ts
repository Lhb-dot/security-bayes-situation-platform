/**
 * 解释文本展示清洗。
 *
 * 历史风险事件的正文里写进了未格式化的风险评分（如 0.9999999999998914）。
 * 该文本按需求 5.7.3 在事件生成时固化入库，生成侧修复只对新事件生效，
 * 所以旧数据统一在展示侧收口。列表页与详情页共用 formatExplanation。
 *
 * 列表页额外用 shortExplanation 去掉正文里不含信息量的两部分（见下），
 * 详情页仍展示完整正文。
 */

/** 匹配「风险评分：」后跟 6 位以上小数的旧格式；新格式（100.0%）只有 1 位小数，不受影响 */
const RAW_SCORE = /(风险评分：)(\d+\.\d{6,})/g;

/** 把正文里残留的长小数风险评分转成百分比，其余内容原样返回 */
export function formatExplanation(text: string): string {
  if (!text) return '';
  return text.replace(RAW_SCORE, (match, prefix: string, raw: string) => {
    const value = Number(raw);
    return Number.isFinite(value) ? `${prefix}${(value * 100).toFixed(1)}%` : match;
  });
}

/**
 * 正文开头「该…被判定为…风险（风险评分：x%）」—— 四种风险类型都是这个句式
 * （`risk_event_service._build_description`）。
 */
const VERDICT_HEAD = /^[^，]*被判定为[^，]*（风险评分：[^）]*）/;

/**
 * 正文结尾「，建议…。」—— 每种风险类型各自固定的模板句
 * （如网络类固定是「建议重点关注该连接是否存在扫描或攻击行为」）。
 * 允许中间带逗号（电力类那句就带），所以只以句号收尾。
 */
const ADVICE_TAIL = /，建议[^。]*。$/;

/**
 * 列表页用的短说明：只保留这条记录独有的特征描述。
 *
 * 完整正文形如（以网络类为例）：
 * ```
 * 该网络流量样本被判定为网络安全风险（风险评分：100.0%），协议类型为 tcp，
 * 建议重点关注该连接是否存在扫描或攻击行为。
 * ```
 * 其中
 * 1. 开头的「该…被判定为…风险（风险评分：x%）」与列表的「所属场景」「风险等级」
 *    两列**完全重复** —— 场景列写「网络安全」，等级列写「高危 100.0%」；
 * 2. 结尾的「建议…。」是**每种风险类型固定的模板句**，同一类型每条事件一字不差。
 *
 * 两者都不含这条记录独有的信息，列表里去掉后只剩中间的特征部分
 * （如「协议类型为 tcp。」）。**详情页仍展示完整正文**，所以信息没丢。
 *
 * 特征部分为空时（数据集没提供任何候选字段）退回完整正文，避免出现空单元格。
 */
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
