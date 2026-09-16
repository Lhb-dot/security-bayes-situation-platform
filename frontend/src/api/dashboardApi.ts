import request, { unwrapData } from '@/utils/request';
import { resolveScenarioId } from '@/api/scenarioApi';

/** 场景键：前端据此选择页面分区（与后端 scenario_key 一致） */
export type ScenarioKey = 'network' | 'power' | 'flight_deck' | 'geological' | 'unknown';

/** 通用计数项 */
export interface CountItem {
  value: string;
  count: number;
}

/** 标签 + 数值项（柱状图/条形图统一结构） */
export interface LabelValue {
  label: string;
  value?: number | null;
  count?: number | null;
}

/** 数值列统计 */
export interface NumericStats {
  mean: number;
  min: number;
  max: number;
  median: number;
  std: number;
  range: number;
  count: number;
}

/** 数据集统计条目 */
export interface DatasetStat {
  dataset_id: number;
  logical_id: string;
  /** 面向用户的中文展示名（后端 dataset_display_name 生成），展示一律用它，缺失时回退 logical_id */
  name?: string;
  version: number;
  label_field: string;
  /** 标签字段是否属于风险标签（如 dis_global_catalog 的 label 是灾害规模，非风险标签） */
  is_risk_label: boolean;
  record_count: number;
  risk_count: number;
  risk_rate: number;
}

// ---------------------------------------------------------------------------
// ① 平台总览
// ---------------------------------------------------------------------------

export interface AdminTotals {
  scenario_count: number;
  effective_dataset_count: number;
  effective_sample_count: number;
  risk_sample_count: number;
  risk_rate: number;
  algorithm_count: number;
  published_model_count: number;
  inference_count: number;
  risk_event_count: number;
  pending_event_count: number;
  user_count: number;
}

export interface AdminScenarioCard {
  scenario_id: number;
  code: string;
  scenario_key: ScenarioKey;
  name: string;
  access_status: string;
  dataset_count: number;
  effective_sample_count: number;
  risk_count: number;
  risk_rate: number;
  published_model_count: number;
  model_count: number;
  inference_count: number;
  event_count: number;
  pending_count: number;
}

export interface AdminRuntime {
  risk_event_count: number;
  pending_event_count: number;
  processing_event_count: number;
  resolved_event_count: number;
  inference_count: number;
  user_count: number;
  published_model_count: number;
  algorithm_count: number;
}

export interface DashboardOverview {
  totals: AdminTotals;
  scenarios: AdminScenarioCard[];
  runtime: AdminRuntime;
}

// ---------------------------------------------------------------------------
// ② 场景数据画像（管理端）
// ---------------------------------------------------------------------------

export interface ProfileBase {
  scenario_id: number;
  scenario_code: string;
  scenario_key: ScenarioKey;
  scenario_name: string;
  access_status: string;
  risk_type: string | null;
  dataset_count: number;
  dataset_file_count: number;
  sample_count: number;
  risk_count: number;
  risk_rate: number;
  datasets: DatasetStat[];
  groups: Array<{ group_id: string; datasets: string[]; record_count: number; deduplicated: boolean }>;
}

export interface NetworkProfile extends ProfileBase {
  protocol_distribution: CountItem[];
  protocol_total: number;
  distinct_port_count: number;
  top_ports: CountItem[];
  flags: CountItem[];
  services: CountItem[];
  flow_segments: Array<{ label: string; value: number }>;
  traffic: {
    avg_in_bytes: number;
    avg_retrans_in_bytes: number;
    retransmission_ratio: number;
    in_bytes_stats: NumericStats | null;
    retrans_stats: NumericStats | null;
  };
}

export interface PowerProfile extends ProfileBase {
  params: Array<{ name: string; key: string; unit: string; stats: NumericStats | null }>;
  fault_count: number;
  fault_rate: number;
  issues: CountItem[];
  components: CountItem[];
  systems: CountItem[];
  device_fault_rates: Array<{ value: string; count: number; risk_count: number; risk_rate: number }>;
}

export interface FlightdeckProfile extends ProfileBase {
  collision_count: number;
  collision_rate: number;
  distance: Record<string, NumericStats | null>;
  approach: { abs_change_ratio_mean: number | null; change_ratio_mean: number | null };
  total_distance: { plane1_mean: number | null; plane2_mean: number | null; diff_mean: number | null };
  direction: Record<'plane1' | 'plane2', { mean: number | null; std: number | null; stats: NumericStats | null }>;
  relative_angle: { mean: number | null; max: number | null };
  distance_curve: Array<{ step: number; mean: number | null }>;
  collision_comparison: Record<'collision' | 'normal', { count: number; mean_min_distance: number | null }>;
}

export interface GeologicalProfile extends ProfileBase {
  factors: Array<{ value: string; mean: number | null; stats: NumericStats | null }>;
  factor_count: number;
  catalog_distribution: {
    trigger: CountItem[];
    category: CountItem[];
    size: CountItem[];
    country: CountItem[];
  };
}

export type ScenarioProfile = NetworkProfile | PowerProfile | FlightdeckProfile | GeologicalProfile;

// ---------------------------------------------------------------------------
// ③ 我的工作台（场景用户；管理端亦可，范围按角色收窄）
// ---------------------------------------------------------------------------

export interface EventSummary {
  total: number;
  pending: number;
  processing: number;
  resolved: number;
  today: number;
  high_confidence: number;
  avg_risk_score: number;
  max_risk_score: number;
  score_bins: Array<{ label: string; count: number }>;
  status_funnel: Array<{ label: string; status: string; count: number }>;
  daily_trend: Array<{ date: string; total: number; resolved: number; pending: number }>;
}

export interface RiskEventRow {
  id: number;
  description: string;
  risk_score: number | null;
  risk_level: string;
  status: string;
  occurred_at: string | null;
  raw_features?: Record<string, unknown>;
}

export interface WorkspaceBase {
  scenario_id: number;
  scenario_code: string;
  scenario_key: ScenarioKey;
  scenario_name: string;
  risk_type: string | null;
  summary: EventSummary;
  recent_events: RiskEventRow[];
  scope: { self_only: boolean; user_id: number };
  activity_trend: Array<{ date: string; total: number; risk: number }>;
}

export interface NetworkWorkspace extends WorkspaceBase {
  top_ports: CountItem[];
  abnormal_ports: Array<{ value: string; count: number; deviation: number }>;
  port_deviation: Array<{ value: string; count: number; deviation: number }>;
  port_baseline: number;
  flow_segments: Array<{ label: string; value: number }>;
}

export interface PowerWorkspace extends WorkspaceBase {
  telemetry: Array<{ key: string; name: string; unit: string; stats: NumericStats | null }>;
  component_issue_distribution: Array<{ component: string; issue: string; count: number }>;
  device_ranking: CountItem[];
  issue_ranking: CountItem[];
}

export interface FlightdeckWorkspace extends WorkspaceBase {
  positions: Array<{ event_id: number; x: number | null; y: number | null; risk_score: number | null; status: string }>;
  position_count: number;
  min_inter_distance: number | null;
  distance_distribution: Array<{ label: string; count: number }>;
  distance_stats: NumericStats | null;
  direction_stats: Array<{ label: string; stats: NumericStats | null }>;
}

export interface GeologicalWorkspace extends WorkspaceBase {
  factor_contribution: CountItem[];
  factor_means: Array<{ value: string; mean: number }>;
  trigger_distribution: CountItem[];
  slope_ranking: Array<{ label: string; count: number; mean_risk_score: number; max_risk_score: number }>;
  slope_bucket_count: number;
  dataset_prior: DatasetStat[];
}

export type ScenarioWorkspace =
  | NetworkWorkspace
  | PowerWorkspace
  | FlightdeckWorkspace
  | GeologicalWorkspace;

// ---------------------------------------------------------------------------
// 请求封装
// ---------------------------------------------------------------------------

export const getAdminDashboard = async (): Promise<DashboardOverview> =>
  unwrapData(await request.get('/api/v1/dashboard/admin/overview'));

export const getScenarioProfile = async (scenarioId: number | string): Promise<ScenarioProfile> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/dashboard/scenarios/${id}/profile`));
};

export const getScenarioWorkspace = async (scenarioId: number | string): Promise<ScenarioWorkspace> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/dashboard/scenarios/${id}/workspace`));
};
