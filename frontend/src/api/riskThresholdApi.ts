/**
 * riskThresholdApi.ts — 风险阈值配置接口（与后端 /api/v1/risk-thresholds 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 5.4.1）：查询登录用户可读；修改仅 ADMIN。
 */
import request, { unwrapData } from '@/utils/request';
import type { ScenarioId, ThresholdConfig } from '@/types/security';

/** 按场景查询风险阈值（GET /risk-thresholds/{scenario_id}；未配置时 data 为 null） */
export const getRiskThreshold = async (scenarioId: ScenarioId): Promise<ThresholdConfig | null> =>
  unwrapData(await request.get(`/api/v1/risk-thresholds/${scenarioId}`));

/** 更新场景风险阈值（PUT /risk-thresholds/{scenario_id}，仅管理员；实时生效并写审计日志） */
export const updateRiskThreshold = async (
  scenarioId: ScenarioId,
  params: { medium_threshold: number; high_threshold: number }
): Promise<ThresholdConfig> => unwrapData(await request.put(`/api/v1/risk-thresholds/${scenarioId}`, params));
