import { describe, expect, it } from 'vitest';
import { formatExplanation, shortExplanation } from './explanationText';

describe('formatExplanation', () => {
  it('returns an empty string for empty input', () => {
    expect(formatExplanation('')).toBe('');
  });

  it('formats a long fractional risk score as a percentage', () => {
    expect(formatExplanation('风险评分：0.9999999999998914')).toBe('风险评分：100.0%');
  });

  it('leaves a score that is already formatted unchanged', () => {
    expect(formatExplanation('风险评分：100.0%')).toBe('风险评分：100.0%');
  });

  it('leaves text without a raw score unchanged', () => {
    expect(formatExplanation('没有风险分数')).toBe('没有风险分数');
  });

  it('formats every matching score in the text', () => {
    expect(formatExplanation('风险评分：0.25000001；风险评分：0.50000001')).toBe('风险评分：25.0%；风险评分：50.0%');
  });
});

describe('shortExplanation', () => {
  it('keeps only the feature description for a network event', () => {
    const text = '该网络流量样本被判定为网络安全风险（风险评分：100.0%），协议类型为 tcp，建议重点关注该连接是否存在扫描或攻击行为。';
    expect(shortExplanation(text)).toBe('协议类型为 tcp。');
  });

  it('removes an electricity advice tail that contains commas', () => {
    const text = '该样本被判定为形成电力系统风险（风险评分：83.2%），受影响设备：主变压器，所属系统：输电系统，建议核实相关设备是否存在越限或异常，并检查关联监测数据。';
    expect(shortExplanation(text)).toBe('受影响设备：主变压器，所属系统：输电系统。');
  });

  it('falls back to the original text when the feature body is empty', () => {
    const text = '该网络流量样本被判定为网络安全风险（风险评分：100.0%）';
    expect(shortExplanation(text)).toBe(text);
  });

  it('returns an empty string for empty input', () => {
    expect(shortExplanation('')).toBe('');
  });
});
