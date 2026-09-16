/**
 * scenarioApi.ts — 场景接口（与后端 /api/v1/scenarios 对齐）
 *
 * 薄封装：request 调用 + unwrapData 解包 + 场景编码/数字 ID 互转；
 * 另含 `ApiScenarioOverviewCard → Scenario` 的契约映射（场景中心与平台总览共用）。
 */
import request, { unwrapData } from '@/utils/request';
import type { Scenario, ScenarioId } from '@/types/security';

/** 后端 scenario 行 */
export interface ApiScenario {
  id: number;
  code: string;
  name: string;
  description: string | null;
  access_status: string;
}

/** 场景列表（GET /scenarios，data 为数组） */
export const getScenarioList = async (): Promise<ApiScenario[]> =>
  unwrapData(await request.get('/api/v1/scenarios'));

/** 场景中心卡片（GET /scenarios/overview 的单个场景项，字段口径见 docs/首页字段口径说明.md） */
export interface ApiScenarioOverviewCard {
  scenario_id: number;
  code: string;
  name: string;
  description: string;
  access_status: string;
  /** 去重口径有效数据集数（carrier 同源三份只计 1） */
  dataset_count: number;
  /** 去重口径有效样本量 */
  sample_count: number;
  /** 标签判定为风险的样本数 */
  risk_sample_count: number;
  /** 风险样本占比（百分数，如 14.2） */
  risk_sample_rate: number;
  /** 已发布（PUBLISHED）模型版本数 */
  published_model_count: number;
  event_count: number;
  high_risk_count: number;
  /** 风险分 0-100（所辖事件 risk_score 均值 ×100，无事件记 0） */
  risk_score: number;
  risk_level: 'high' | 'medium' | 'low';
}

/** 场景中心卡片数据（GET /scenarios/overview） */
export interface ApiScenarioOverview {
  scenarios: ApiScenarioOverviewCard[];
  totals: {
    scenario_count: number;
    effective_dataset_count: number;
    effective_sample_count: number;
    published_model_count: number;
    event_count: number;
    high_risk_count: number;
    /** 全局风险分 0-100 */
    risk_score: number;
    risk_level: 'high' | 'medium' | 'low';
  };
}

/**
 * 场景卡片聚合（真实数据，唯一数据源）。
 *
 * 「场景中心」与「平台运行总览」都消费本接口，指标口径完全一致
 * （数据集同源去重、模型只算已发布）。后端按角色限定可见场景与数据可见性。
 */
export const getScenarioOverview = async (): Promise<ApiScenarioOverview> => {
  const overview = unwrapData(await request.get('/api/v1/scenarios/overview'));
  // 场景卡片本身就带数字 ID，顺手预热「编码 → 数字 ID」缓存：
  // 这样从场景中心点进场景大屏时，resolveScenarioId 直接命中缓存，
  // 不必再多发一次 GET /scenarios（原先首次进入场景大屏是两次串行请求）。
  seedScenarioIds(overview.scenarios);
  return overview;
};

/**
 * 后端场景卡片 → 前端 Scenario 契约。
 *
 * 场景中心（`scenarioStore`）与平台运行总览（`getGlobalOverview`）共用这一个映射，
 * 避免两处各自写一套导致字段口径再次分叉。
 */
export const toScenarioCard = (card: ApiScenarioOverviewCard): Scenario => ({
  scenario_id: card.code as ScenarioId,
  name: card.name,
  description: card.description ?? '',
  risk_level: card.risk_level,
  risk_score: card.risk_score,
  event_count: card.event_count,
  high_risk_count: card.high_risk_count,
  // 去重口径：carrier 同源三份只计 1 个有效数据集
  dataset_count: card.dataset_count,
  // 本接口口径下「模型」= 已发布模型版本数
  model_count: card.published_model_count,
  sample_count: card.sample_count,
  published_model_count: card.published_model_count,
  status: card.access_status === 'ACTUAL' ? 'active' : 'inactive',
});

/** 场景详情（GET /scenarios/{scenario_id}，scenario_id 为数字 ID） */
export const getScenarioDetail = async (scenarioId: number): Promise<ApiScenario> =>
  unwrapData(await request.get(`/api/v1/scenarios/${scenarioId}`));

// 场景编码 → 数字 ID 缓存（前端路由用编码，后端接口用数字 ID）
let _idByCodeCache: Record<string, number> | null = null;

/**
 * 用「编码 → 数字 ID」预填缓存。
 *
 * 场景卡片接口（GET /scenarios/overview）返回的每一项都自带数字 scenario_id，
 * 直接拿来预热，可省掉 resolveScenarioId 首次调用时的那次 GET /scenarios。
 */
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

/**
 * 把场景编码（如 network_security）解析为后端数字 ID。
 * 传数字、或纯数字字符串（路由参数常为字符串）时直接返回数字。
 */
export const resolveScenarioId = async (codeOrId: string | number): Promise<number> => {
  if (typeof codeOrId === 'number') return codeOrId;
  const text = String(codeOrId).trim();
  if (/^\d+$/.test(text)) return Number(text);
  if (!_idByCodeCache) {
    const list = await getScenarioList();
    _idByCodeCache = {};
    for (const s of list) _idByCodeCache[s.code] = s.id;
  }
  const id = _idByCodeCache[text];
  if (id == null) throw new Error(`场景不存在: ${codeOrId}`);
  return id;
};
