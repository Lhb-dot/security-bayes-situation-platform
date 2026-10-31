import request, { unwrapData } from '@/utils/request';
import { resolveScenarioId } from '@/api/scenarioApi';

// 场景键：前端据此选择页面分区（与后端 scenario_key 一致）
export type ScenarioKey = 'network' | 'power' | 'flight_deck' | 'geological' | 'unknown';

export interface CountItem {
  value: string;
  count: number;
}

export interface NumericStats {
  mean: number;
  min: number;
  max: number;
  median: number;
  std: number;
  range: number;
  count: number;
}

export interface DatasetStat {
  dataset_id: number;
  logical_id: string;
  name?: string;
  version: number;
  label_field: string;
  is_risk_label: boolean;
  record_count: number;
  risk_count: number;
  risk_rate: number;
  attribute_count: number;
  field_names: string[];
  visibility: string;
  uploader_role: string | null;
  // 上传时间（ISO 8601 字符串），缺失时为 null
  uploaded_at: string | null;
  source_group: string;
  // 文件内容指纹 "{size}-{sha1前16位}"，文件缺失时为 "missing:{logical_id}"
  content_fingerprint: string;
  positive_labels: string[];
  // 标签列实际取值，按计数降序，最多 12 个
  label_values: string[];
  label_kind: 'binary' | 'multiclass' | 'numeric' | 'unknown';
  caliber_registered: boolean;
}

export interface ModelingStat {
  logical_id: string;
  published: number;
  draft: number;
  // 模型版本总数；为 0 表示"数据白躺"
  total: number;
}


export interface AdminTotals {
  scenario_count: number;
  effective_dataset_count: number;
  effective_sample_count: number;
  risk_sample_count: number;
  risk_rate: number;
  algorithm_count: number;
  published_model_count: number;
  trained_model_count?: number;
  inference_count: number;
  report_count?: number;
  served_user_count?: number;
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
  user_count: number;
  admin_count: number;
  dataset_count: number;
  effective_sample_count: number;
  risk_count: number;
  risk_rate: number;
  published_model_count: number;
  trained_model_count?: number;
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
  report_count?: number;
  served_user_count?: number;
  trained_model_count?: number;
  user_count: number;
  published_model_count: number;
  algorithm_count: number;
}

export interface DashboardOverview {
  totals: AdminTotals;
  scenarios: AdminScenarioCard[];
  runtime: AdminRuntime;
}


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
  groups: Array<{
    group_id: string;
    datasets: string[];
    record_count: number;
    deduplicated: boolean;
    file_count: number;
    fingerprint: string;
  }>;
  // 每数据集的模型版本覆盖统计（无模型的数据集也在列，published/draft/total 均为 0）
  modeling: ModelingStat[];
}

export interface CaliberRow {
  logical_id: string;
  // 数据集名（= logical_id）
  name: string;
  label_field: string;
  positive_labels: string[];
  // 标签列实际取值（按计数降序，最多 12 个）
  label_values: string[];
  // 标签类型：binary / multiclass / numeric / unknown
  label_kind: string;
  record_count: number;
  risk_count: number;
  risk_rate: number;
  // 与场景合并风险占比的偏离倍数（risk_rate / 场景 risk_rate），场景 risk_rate 为 0 时 null
  deviation: number | null;
  registered: boolean;
}

export interface DimensionCoverage {
  dimension: string;
  key: string;
  // 覆盖该维度的数据集 logical_id 列表
  datasets: string[];
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
  // 数据集风险口径可比性矩阵（每数据集一行，顺序与 datasets 一致）
  caliber_matrix: CaliberRow[];
  dimension_coverage: DimensionCoverage[];
}

export interface TelemetryByDataset {
  logical_id: string;
  // 数据集名（= logical_id）
  name: string;
  record_count: number;
  // 各电参量的均值（key/name/unit 口径与场景画像一致），无法计算时 mean 为 null
  params: Array<{ key: string; name: string; unit: string; mean: number | null }>;
  // 工频 PowerFrequencyHz 落在 [49.8, 50.2] 区间的占比
  frequency_pass_rate: number;
  // 遥测丢包率 Sensor_Packet_Loss_% 均值，无该字段时 null
  packet_loss_mean: number | null;
  baseline_ok: boolean;
  // 越界项的中文名列表（baseline_ok 为 true 时为空）
  violations: string[];
}

export interface ComponentMatrixRow {
  value: string;
  // 该行类型：设备 component / 系统 system
  kind: 'component' | 'system';
  counts: Array<{ logical_id: string; count: number; risk_rate: number }>;
}

export interface PowerProfile extends ProfileBase {
  params: Array<{ name: string; key: string; unit: string; stats: NumericStats | null }>;
  fault_count: number;
  fault_rate: number;
  issues: CountItem[];
  components: CountItem[];
  systems: CountItem[];
  device_fault_rates: Array<{ value: string; count: number; risk_count: number; risk_rate: number }>;
  telemetry_by_dataset: TelemetryByDataset[];
  component_matrix: ComponentMatrixRow[];
}

export interface EncodingFamilyRow {
  logical_id: string;
  // 数据集名（= logical_id）
  name: string;
  source_group: string;
  encoding: 'numeric' | 'interval' | 'paired' | 'unknown';
  attribute_count: number;
  record_count: number;
  risk_count: number;
  collision_consistent: boolean;
  published_model_count: number;
}

export interface RedundancyStat {
  file_count: number;
  effective_group_count: number;
  // 重复内容冗余率 = 1 - effective_group_count / file_count
  redundancy_rate: number;
  raw_samples: number;
  deduped_samples: number;
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
  encoding_family: EncodingFamilyRow[];
  redundancy: RedundancyStat;
}

export interface RoleRow {
  logical_id: string;
  // 数据集名（= logical_id）
  name: string;
  role: string;
  attribute_count: number;
  label_field: string;
  // 标签类型：binary / multiclass / numeric / unknown
  label_kind: string;
  participates_in_training: boolean;
  produces_risk_events: boolean;
  record_count: number;
  risk_rate: number;
}

export interface FactorCoverageRow {
  factor: string;
  // 含该因子字段的数据集 logical_id 列表
  datasets: string[];
  consistent_binning: boolean;
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
  roles: RoleRow[];
  factor_coverage: FactorCoverageRow[];
}

export type ScenarioProfile = NetworkProfile | PowerProfile | FlightdeckProfile | GeologicalProfile;


export interface EventSummary {
  total: number;
  pending: number;
  processing: number;
  resolved: number;
  today: number;
  // 按当前账号在该场景的高风险阈值判定为高风险的事件数（不是写死的 0.8）
  high_confidence: number;
  // 后端实际生效的高风险阈值（0~1），用于渲染"风险分 ≥ x"的说明文字
  high_threshold: number;
  // 后端实际生效的中风险阈值（0~1）
  medium_threshold: number;
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


export const getAdminDashboard = async (options?: { signal?: AbortSignal }): Promise<DashboardOverview> =>
  unwrapData(await request.get('/api/v1/dashboard/admin/overview', {
    signal: options?.signal,
    params: { _t: Date.now() },
    timeout: 30_000,
  }));

export const getScenarioProfile = async (scenarioId: number | string, options?: { signal?: AbortSignal }): Promise<ScenarioProfile> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/dashboard/scenarios/${id}/profile`, { signal: options?.signal, timeout: 30_000 }));
};

export const getScenarioWorkspace = async (scenarioId: number | string, options?: { signal?: AbortSignal }): Promise<ScenarioWorkspace> => {
  const id = await resolveScenarioId(scenarioId);
  return unwrapData(await request.get(`/api/v1/dashboard/scenarios/${id}/workspace`, { signal: options?.signal, timeout: 30_000 }));
};
