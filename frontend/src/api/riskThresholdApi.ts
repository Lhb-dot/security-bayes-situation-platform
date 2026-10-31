/**
 * 风险阈值配置接口（与后端 /api/v1/risk-thresholds 对齐）
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 阈值按登录账号绑定；系统管理员可配置全部场景，其余账号仅配置绑定场景。
 */
import request, { unwrapData } from '@/utils/request';
import { SCENARIO_CODE_BY_ID } from '@/api/scenarioApi';
import type {
  ApiThresholdChangeLog,
  ApiThresholdConfig,
  ScenarioId,
  ThresholdChangeLog,
  ThresholdConfig,
} from '@/types/security';

export const DEFAULT_MEDIUM_THRESHOLD = 0.5;
export const DEFAULT_HIGH_THRESHOLD = 0.8;

const SCENARIO_CODE_TO_ID = Object.fromEntries(
  Object.entries(SCENARIO_CODE_BY_ID).map(([id, code]) => [code, Number(id)])
) as Record<ScenarioId, number>;
interface ApiScenario {
  id: number;
  code: string;
}

let scenarioIdByCode: Partial<Record<ScenarioId, number>> | null = null;
let scenarioCodeById: Record<number, ScenarioId> = { ...SCENARIO_CODE_BY_ID };

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
  }
  scenarioIdByCode = byCode;
};

const normalizeThreshold = (item: ApiThresholdConfig): ThresholdConfig => ({
  ...item,
  scenario_id: scenarioCodeById[item.scenario_id] ?? SCENARIO_CODE_BY_ID[item.scenario_id],
});
const backendScenarioId = async (scenarioId: ScenarioId | number): Promise<number> => {
  await ensureScenarioMaps();
  return typeof scenarioId === 'number' ? scenarioId : scenarioIdByCode?.[scenarioId] ?? SCENARIO_CODE_TO_ID[scenarioId];
};

export const getRiskThresholds = async (): Promise<ThresholdConfig[]> => {
  await ensureScenarioMaps();
  const data = await unwrapData(await request.get('/api/v1/risk-thresholds'));
  return (Array.isArray(data) ? data : []).map(normalizeThreshold);
};

export const getRiskThresholdAuditLogs = async (): Promise<ThresholdChangeLog[]> => {
  await ensureScenarioMaps();
  const data = await unwrapData<{ items?: ApiThresholdChangeLog[] }>(
    await request.get('/api/v1/risk-thresholds/audit-logs', { params: { page: 1, page_size: 200 } }),
  );
  return (data.items ?? []).map((item: ApiThresholdChangeLog) => ({
    ...item,
    scenario_id: scenarioCodeById[item.scenario_id] ?? SCENARIO_CODE_BY_ID[item.scenario_id] ?? item.scenario_id,
  }));
};

export const updateRiskThreshold = async (
  scenarioId: ScenarioId | number,
  params: { medium_threshold: number; high_threshold: number }
): Promise<ThresholdConfig> =>
  (async () => {
    const id = await backendScenarioId(scenarioId);
    return normalizeThreshold(await unwrapData(await request.put(`/api/v1/risk-thresholds/${id}`, params)));
  })();
