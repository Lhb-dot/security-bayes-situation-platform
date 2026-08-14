/**
 * scenarioApi.ts — 场景接口（与后端 /api/v1/scenarios 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 */
import request, { unwrapData } from '@/utils/request';
import type { Scenario, ScenarioDetail, ScenarioId } from '@/types/security';

/** 场景列表（GET /scenarios，data 为数组） */
export const getScenarioList = async (): Promise<Scenario[]> =>
  unwrapData(await request.get('/api/v1/scenarios'));

/** 场景详情（GET /scenarios/{scenario_id}，含态势指标） */
export const getScenarioDetail = async (scenarioId: ScenarioId): Promise<ScenarioDetail> =>
  unwrapData(await request.get(`/api/v1/scenarios/${scenarioId}`));
