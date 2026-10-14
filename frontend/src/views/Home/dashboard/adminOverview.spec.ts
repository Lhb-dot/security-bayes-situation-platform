import { describe, expect, it } from 'vitest';
import { adminOverviewPayload } from '@/test/adminOverviewFixtures';
import { formatOverviewCount, mapAdminOverview, overviewPercentage, sampleMetric } from './adminOverview';

describe('管理员首页统计口径', () => {
  it('使用接口总量，而不是把场景数量相加重建总量', () => {
    const data = mapAdminOverview(adminOverviewPayload());
    expect(data.sampleCount).toBe(4000);
    expect(data.scenes.reduce((sum, row) => sum + row.samples, 0)).toBe(2000);
    expect([data.trainedModels, data.publishedModels, data.inferenceCount, data.reportCount, data.servedUserCount]).toEqual([17, 9, 42, 8, 10]);
    expect([data.eventCount, data.pendingCount, data.processingCount, data.resolvedCount, data.userCount]).toEqual([11, 3, 2, 6, 25]);
  });
  it('缺失可选统计保持未知，不伪装为零', () => {
    const payload = adminOverviewPayload();
    delete payload.runtime.trained_model_count;
    delete payload.runtime.report_count;
    delete payload.runtime.served_user_count;
    const data = mapAdminOverview(payload);
    expect([data.trainedModels, data.reportCount, data.servedUserCount]).toEqual([null, null, null]);
    expect(formatOverviewCount(data.reportCount)).toBe('—');
  });
  it('场景入口使用接口编码，并进行 URL 编码', () => {
    const payload = adminOverviewPayload();
    payload.scenarios[0].code = 'network/自定义';
    expect(mapAdminOverview(payload).scenes[0].path).toBe('/scenarios/network%2F%E8%87%AA%E5%AE%9A%E4%B9%89/dashboard');
  });
  it.each([undefined, null, {}, { totals: {}, runtime: {}, scenarios: null }])('拒绝不完整响应 %j', (payload) => {
    expect(() => mapAdminOverview(payload)).toThrow('首页接口返回的数据不完整');
  });
  it.each([-1, .5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '4', null])('拒绝错误核心计数 %j', (value) => {
    const payload = adminOverviewPayload();
    expect(() => mapAdminOverview({ ...payload, totals: { ...payload.totals, effective_sample_count: value } })).toThrow();
  });
  it('未知风险占比保留为未知，真实零占比仍为零', () => {
    const payload = adminOverviewPayload();
    const first = { ...payload.scenarios[0], risk_rate: null, user_count: null };
    const data = mapAdminOverview({ ...payload, scenarios: [first, ...payload.scenarios.slice(1)] });
    expect(data.scenes[0].riskRate).toBeNull();
    expect(data.scenes[0].userCount).toBeNull();
    expect(data.scenes[1].riskRate).toBe(0);
  });
  it.each([-1, 1.1, NaN, '0.5'])('拒绝错误风险占比 %j', (value) => {
    const payload = adminOverviewPayload();
    expect(() => mapAdminOverview({ ...payload, scenarios: [{ ...payload.scenarios[0], risk_rate: value }] })).toThrow();
  });
  it('重复场景不会被重复计入图表', () => {
    const payload = adminOverviewPayload();
    payload.scenarios.push(payload.scenarios[0]);
    expect(() => mapAdminOverview(payload)).toThrow();
  });
  it('零分母和未知服务人数不会产生 NaN 或错误覆盖率', () => {
    expect(overviewPercentage(0, 0)).toBeNull();
    expect(overviewPercentage(null, 25)).toBeNull();
    expect(overviewPercentage(26, 25)).toBeNull();
    expect(overviewPercentage(10, 25)).toBe(40);
    expect(overviewPercentage(0, 25)).toBe(0);
  });
  it('小样本和大样本量级正确，不强行把少量样本显示成零万', () => {
    expect(sampleMetric(507)).toEqual({ value: '507', unit: '条' });
    expect(sampleMetric(51359)).toEqual({ value: '5.14', unit: '万条' });
    expect(sampleMetric(1e8)).toEqual({ value: '1.00', unit: '亿条' });
    expect(formatOverviewCount(1e12)).toBe('1.00万亿');
  });
});
