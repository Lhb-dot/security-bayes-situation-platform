/**
 * riskThresholdApi.ts — 风险阈值配置接口（与后端 /api/v1/risk-thresholds 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 阈值按登录账号绑定；系统管理员可配置全部场景，其余账号仅配置绑定场景。
 */
import request, { unwrapData } from '@/utils/request';
import type { ScenarioId, ThresholdChangeLog, ThresholdConfig } from '@/types/security';

const SCENARIO_ID_TO_CODE: Record<number, ScenarioId> = {
  1: 'network_security',
  2: 'power_system',
  3: 'flightdeck_operation',
  4: 'geological_risk',
};
const SCENARIO_CODE_TO_ID: Record<ScenarioId, number> = {
  network_security: 1,
  power_system: 2,
  flightdeck_operation: 3,
  geological_risk: 4,
};
interface ApiScenario {
  id: number;
  code: string;
}

let scenarioIdByCode: Partial<Record<ScenarioId, number>> | null = null;
let scenarioCodeById: Record<number, ScenarioId> = { ...SCENARIO_ID_TO_CODE };

/** Resolve database scenario IDs instead of assuming sequence values. */
const ensureScenarioMaps = async (): Promise<void> => {
  if (scenarioIdByCode) return;
  const byCode: Partial<Record<ScenarioId, number>> = { ...SCENARIO_CODE_TO_ID };
  try {
    const scenarios = (await unwrapData(await request.get('/api/v1/scenarios'))) as ApiScenario[];
    for (const scenario of scenarios ?? []) {
      const code = scenario.code as ScenarioId;
      byCode[code] = scenario.id;
      scenarioCodeById[scenario.id] = code;
    }
  } catch {
    // Keep the known seed mapping as a local fallback when the scenario API is unavailable.
  }
  scenarioIdByCode = byCode;
};

type BackendThreshold = Omit<ThresholdConfig, 'scenario_id'> & { scenario_id: number | ScenarioId };
const normalizeThreshold = (item: BackendThreshold): ThresholdConfig => ({
  ...item,
  scenario_id: typeof item.scenario_id === 'number'
    ? scenarioCodeById[item.scenario_id] ?? SCENARIO_ID_TO_CODE[item.scenario_id]
    : item.scenario_id,
});
const backendScenarioId = async (scenarioId: ScenarioId | number): Promise<number> => {
  await ensureScenarioMaps();
  return typeof scenarioId === 'number' ? scenarioId : scenarioIdByCode?.[scenarioId] ?? SCENARIO_CODE_TO_ID[scenarioId];
};

/** 查询当前账号全部阈值（GET /risk-thresholds） */
export const getRiskThresholds = async (): Promise<ThresholdConfig[]> => {
  await ensureScenarioMaps();
  const data = await unwrapData(await request.get('/api/v1/risk-thresholds'));
  return (Array.isArray(data) ? data : []).map(normalizeThreshold);
};

/** 按场景查询当前账号风险阈值（未配置时 data 为 null） */
export const getRiskThreshold = async (scenarioId: ScenarioId): Promise<ThresholdConfig | null> =>
  (async () => {
    const data = await unwrapData(await request.get(`/api/v1/risk-thresholds/${await backendScenarioId(scenarioId)}`));
    return data ? normalizeThreshold(data) : null;
  })();

/** 查询当前账号全部阈值修改记录 */
export const getRiskThresholdAuditLogs = async (): Promise<ThresholdChangeLog[]> => {
  await ensureScenarioMaps();
  const data = await unwrapData(
    await request.get('/api/v1/risk-thresholds/audit-logs', { params: { page: 1, page_size: 200 } }),
  );
  type BackendAuditLog = Omit<ThresholdChangeLog, 'scenario_id'> & { scenario_id: number };
  return (data.items ?? []).map((item: BackendAuditLog) => ({
    ...item,
    scenario_id: scenarioCodeById[item.scenario_id] ?? SCENARIO_ID_TO_CODE[item.scenario_id] ?? item.scenario_id,
  }));
};

/** 更新当前账号场景风险阈值（实时生效并写审计日志） */
export const updateRiskThreshold = async (
  scenarioId: ScenarioId | number,
  params: { medium_threshold: number; high_threshold: number }
): Promise<ThresholdConfig> =>
  (async () => {
    const id = await backendScenarioId(scenarioId);
    return normalizeThreshold(await unwrapData(await request.put(`/api/v1/risk-thresholds/${id}`, params)));
  })();
