/**
 * situationApi.ts — 态势接口（与后端 /api/v1/situation 对齐）
 *
 * 后端已提供态势路由（backend/app/api/v1/endpoints/situation_routes.py），
 * 本模块负责调用与数据映射（后端真实统计 → 前端 SituationData/RiskEvent 结构）。
 */
import request, { unwrapData } from '@/utils/request';
import { getScenarioList, resolveScenarioId } from '@/api/scenarioApi';
import { getRiskEventList } from '@/api/riskEventApi';
import { getModelVersionList } from '@/api/modelVersionApi';
import { getDatasetList } from '@/api/datasetApi';
import type {
  GlobalOverview,
  RiskEvent,
  Scenario,
  ScenarioId,
  SituationData,
  TrendPoint,
} from '@/types/security';

/** 场景态势统计（后端 _aggregate 口径） */
export interface SceneSituationStats {
  total_events: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  pending_count: number;
  processing_count: number;
  resolved_count: number;
}

/** GET /situation/scenes/{id} 返回结构 */
export interface SceneSituation {
  scenario_id: number;
  stats: SceneSituationStats;
  recent_events: Array<Record<string, unknown>>;
}

const STATUS_LABEL: Record<string, string> = {
  PENDING: '待处置',
  PROCESSING: '处理中',
  RESOLVED: '已处置',
};

/** 场景数字 ID → 编码（后端 RiskEvent.scenario_id 是数字，前端 RiskEvent.scenario_id 是编码） */
const SCENARIO_CODE_BY_ID: Record<number, string> = {
  1: 'network_security',
  2: 'power_system',
  3: 'flightdeck_operation',
  4: 'geological_risk',
};

/** 后端风险事件 → 前端 RiskEvent 结构（字段名/状态枚举映射） */
export const mapRiskEvent = (e: Record<string, unknown>): RiskEvent => ({
  event_id: String(e.id ?? ''),
  inference_record_id: String(e.inference_record_id ?? ''),
  created_by_user_id: String(e.created_by_user_id ?? ''),
  scenario_id: (SCENARIO_CODE_BY_ID[Number(e.scenario_id)] ?? e.scenario_id) as RiskEvent['scenario_id'],
  dataset_id: String(e.dataset_id ?? ''),
  dataset_version: String(e.dataset_version ?? ''),
  algorithm_id: String(e.algorithm_id ?? ''),
  model_version_id: String(e.model_version_id ?? ''),
  original_label: String(e.original_label ?? ''),
  risk_type: String(e.risk_type ?? ''),
  risk_level: (e.risk_level as RiskEvent['risk_level']) ?? 'LOW',
  risk_score: Number(e.risk_score ?? 0),
  occurred_at: String(e.occurred_at ?? ''),
  status: (STATUS_LABEL[String(e.status)] ?? String(e.status ?? '待处置')) as RiskEvent['status'],
  raw_features: (e.raw_features ?? {}) as Record<string, unknown>,
  description: String(e.description ?? ''),
});

/** 场景态势（真实统计 + 近期风险事件） */
export const getSceneSituation = async (scenarioId: number | string): Promise<SceneSituation> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/situation/scenes/${id}`));
};

/** 场景态势分析（映射为前端 SituationData；趋势/历史暂无真实数据，置空） */
export const getSituationData = async (scenarioId: ScenarioId): Promise<SituationData> => {
  const sit = await getSceneSituation(scenarioId);
  const s = sit.stats;
  return {
    scenario_id: scenarioId,
    time_range: '近 7 天',
    score_history: [],
    event_distribution: [
      { label: '高危', value: s.high_count, color: '#ff7b72' },
      { label: '中危', value: s.medium_count, color: '#ffd166' },
      { label: '低危', value: s.low_count, color: '#53e5c8' },
    ],
    risk_trend: [],
    metrics: [
      { id: 'total-events', label: '风险事件', value: s.total_events, trend: 0 },
      { id: 'high-risk', label: '高危', value: s.high_count, trend: 0 },
      { id: 'pending', label: '待处置', value: s.pending_count, trend: 0 },
      { id: 'resolved', label: '已处置', value: s.resolved_count, trend: 0 },
    ],
  };
};

/** 把风险事件按发生日期聚合为真实趋势（无事件时返回空数组，不虚构数据） */
const buildDailyTrend = (events: RiskEvent[]): TrendPoint[] => {
  const byDay = new Map<string, RiskEvent[]>();
  for (const e of events) {
    const day = (e.occurred_at ?? '').slice(0, 10) || '未知';
    const arr = byDay.get(day) ?? [];
    arr.push(e);
    byDay.set(day, arr);
  }
  return [...byDay.keys()].sort().map((day) => {
    const arr = byDay.get(day)!;
    const typeCounts = new Map<string, number>();
    for (const e of arr) {
      const t = e.risk_type || '未知';
      typeCounts.set(t, (typeCounts.get(t) ?? 0) + 1);
    }
    let primaryType = '—';
    let max = 0;
    for (const [t, n] of typeCounts) {
      if (n > max) {
        max = n;
        primaryType = t;
      }
    }
    return {
      label: day.slice(5),
      value: arr.length,
      blocked: arr.filter((e) => e.status === '已处置').length,
      sources: new Set(arr.map((e) => e.dataset_id)).size,
      primaryType,
    };
  });
};

/**
 * 全局态势总览（真实数据，前端聚合）。
 *
 * 数据来源均为后端真实接口：场景 / 风险事件 / 模型版本 / 数据集。
 * SUPER_ADMIN 的风险事件由后端强制过滤为 platform 派生事件（见 risk_event_service.get_list）。
 * 各场景风险评分 = 该场景真实风险事件 risk_score 的均值（换算为 0-100 分）。
 */
export const getGlobalOverview = async (): Promise<GlobalOverview> => {
  const [scenarios, rawEvents, models, datasets] = await Promise.all([
    getScenarioList(),
    getRiskEventList({ page_size: 200 }),
    getModelVersionList({ page_size: 200 }),
    getDatasetList({ page_size: 200 }),
  ]);

  const codeById: Record<number, string> = {};
  for (const s of scenarios) codeById[s.id] = s.code;

  // 用真实场景列表的 id→code 映射覆盖 mapRiskEvent 的硬编码回退，避免种子 ID 顺序变化时错位
  const events: RiskEvent[] = (rawEvents as unknown as Array<Record<string, unknown>>).map((e) => {
    const mapped = mapRiskEvent(e);
    const code = codeById[Number(e.scenario_id)];
    if (code) mapped.scenario_id = code as ScenarioId;
    return mapped;
  });

  const scenarioCards: Scenario[] = scenarios.map((s) => {
    const code = s.code as ScenarioId;
    const list = events.filter((e) => e.scenario_id === code);
    const high = list.filter((e) => e.risk_level === 'HIGH').length;
    const medium = list.filter((e) => e.risk_level === 'MEDIUM').length;
    return {
      scenario_id: code,
      name: s.name,
      description: s.description ?? '',
      risk_level: high > 0 ? 'high' : medium > 0 ? 'medium' : 'low',
      risk_score: list.length
        ? Math.round((list.reduce((sum, e) => sum + e.risk_score, 0) / list.length) * 100)
        : 0,
      event_count: list.length,
      high_risk_count: high,
      dataset_count: datasets.filter((d) => d.scenario_id === code).length,
      model_count: models.filter((m) => (m.scenario_code ?? codeById[m.scenario_id]) === code).length,
      status: s.access_status === 'ACTUAL' ? 'active' : 'inactive',
    };
  });

  const highCount = events.filter((e) => e.risk_level === 'HIGH').length;
  const mediumCount = events.filter((e) => e.risk_level === 'MEDIUM').length;

  return {
    global_risk_score: events.length
      ? Math.round((events.reduce((sum, e) => sum + e.risk_score, 0) / events.length) * 100)
      : 0,
    global_risk_level: highCount > 0 ? 'high' : mediumCount > 0 ? 'medium' : 'low',
    scenario_count: scenarios.length,
    high_risk_count: highCount,
    active_model_count: models.filter((m) => m.status === 'PUBLISHED').length,
    scenarios: scenarioCards,
    global_trend: buildDailyTrend(events),
  };
};
