/**
 * 场景接口（与后端 /api/v1/scenarios 对齐）
 * 薄封装：request 调用 + unwrapData 解包 + 场景编码/数字 ID 互转；
 * 另含 `ApiScenarioOverviewCard → Scenario` 的契约映射（场景中心与平台总览共用）。
 */
import request, { unwrapData } from '@/utils/request';
import type { Scenario, ScenarioId } from '@/types/security';

export const SCENARIO_CODE_BY_ID: Record<number, ScenarioId> = {
  1: 'network_security',
  2: 'power_system',
  3: 'flightdeck_operation',
  4: 'geological_risk',
};

export interface ApiScenario {
  id: number;
  code: string;
  name: string;
  description: string | null;
  access_status: string;
}

export const getScenarioList = async (options?: { signal?: AbortSignal }): Promise<ApiScenario[]> =>
  unwrapData(await request.get('/api/v1/scenarios', { signal: options?.signal, timeout: 30_000 }));

export interface ApiScenarioOverviewCard {
  scenario_id: number;
  code: string;
  name: string;
  description: string;
  access_status: string;
  dataset_count: number;
  sample_count: number;
  risk_sample_count: number;
  risk_sample_rate: number;
  published_model_count: number;
  event_count: number;
  high_risk_count: number;
  risk_score: number;
  risk_level: 'high' | 'medium' | 'low';
}

export interface ApiScenarioOverview {
  scenarios: ApiScenarioOverviewCard[];
  totals: {
    scenario_count: number;
    effective_dataset_count: number;
    effective_sample_count: number;
    published_model_count: number;
    event_count: number;
    high_risk_count: number;
    // 全局风险分 0-100
    risk_score: number;
    risk_level: 'high' | 'medium' | 'low';
  };
}

export const getScenarioOverview = async (): Promise<ApiScenarioOverview> => {
  const overview = unwrapData<ApiScenarioOverview>(await request.get('/api/v1/scenarios/overview'));
  seedScenarioIds(overview.scenarios);
  return overview;
};

export const toScenarioCard = (card: ApiScenarioOverviewCard): Scenario => ({
  scenario_id: card.code as ScenarioId,
  name: card.name,
  description: card.description ?? '',
  risk_level: card.risk_level,
  risk_score: card.risk_score,
  event_count: card.event_count,
  high_risk_count: card.high_risk_count,
  // 去重口径：内容完全相同的重复注册文件只计 1 个有效数据集
  dataset_count: card.dataset_count,
  model_count: card.published_model_count,
  sample_count: card.sample_count,
  published_model_count: card.published_model_count,
  status: card.access_status === 'ACTUAL' ? 'active' : 'inactive',
});

let _idByCodeCache: Record<string, number> | null = null;

export const resetScenarioIdCache = (): void => {
  _idByCodeCache = null;
};

export const seedScenarioIds = (
  items: Array<{ code: string; scenario_id: number }>,
): void => {
  if (!_idByCodeCache) _idByCodeCache = {};
  for (const item of items) {
    if (item?.code && typeof item.scenario_id === 'number') {
      _idByCodeCache[item.code] = item.scenario_id;
    }
  }
};

export const resolveScenarioId = async (codeOrId: string | number): Promise<number> => {
  if (typeof codeOrId === 'number') return codeOrId;
  const text = String(codeOrId).trim();
  if (/^\d+$/.test(text)) return Number(text);
  let id = _idByCodeCache?.[text];
  if (id == null) {
    const list = await getScenarioList();
    _idByCodeCache = {};
    for (const s of list) _idByCodeCache[s.code] = s.id;
    id = _idByCodeCache[text];
  }
  if (id == null) throw new Error(`场景不存在: ${codeOrId}`);
  return id;
};
