/**
 * situationApi.ts — 态势接口（与后端 /api/v1/situation 对齐）
 *
 * 后端已提供态势路由（backend/app/api/v1/endpoints/situation_routes.py），
 * 本模块负责调用与数据映射（后端真实统计 → 前端 SituationData/RiskEvent 结构）。
 */
import request, { unwrapData } from '@/utils/request';
import { resolveScenarioId } from '@/api/scenarioApi';
import type { RiskEvent, ScenarioId, SituationData } from '@/types/security';

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
