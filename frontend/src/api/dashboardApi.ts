import request, { unwrapData } from '@/utils/request';
import { resolveScenarioId } from '@/api/scenarioApi';

/** 场景键：前端据此选择页面分区（与后端 scenario_key 一致） */
export type ScenarioKey = 'network' | 'power' | 'flight_deck' | 'geological' | 'unknown';

/** 通用计数项 */
export interface CountItem {
  value: string;
  count: number;
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
  /** 字段（属性）总数，= ARFF 头部字段数 */
  attribute_count: number;
  /** 字段名列表，顺序与 ARFF 头部一致 */
  field_names: string[];
  /** 可见性：platform / company / personal */
  visibility: string;
  /** 上传者角色，无上传者时为 null */
  uploader_role: string | null;
  /** 上传时间（ISO 8601 字符串），缺失时为 null */
  uploaded_at: string | null;
  /** 所属同源组 key（内容指纹或显式同源族 ID） */
  source_group: string;
  /** 文件内容指纹 "{size}-{sha1前16位}"，文件缺失时为 "missing:{logical_id}" */
  content_fingerprint: string;
  /** 显式登记的正类取值列表（升序），未登记则为空数组 */
  positive_labels: string[];
  /** 标签列实际取值，按计数降序，最多 12 个 */
  label_values: string[];
  /** 标签类型：二分类 / 多分类 / 数值 / 未知（纯描述性，不参与正类判定） */
  label_kind: 'binary' | 'multiclass' | 'numeric' | 'unknown';
  /** 是否已登记风险口径（= logical_id 在显式登记表中）；false 表示不产风险事件 */
  caliber_registered: boolean;
}

/** 数据集建模覆盖统计（按数据集维度） */
export interface ModelingStat {
  /** 数据集逻辑 ID */
  logical_id: string;
  /** 已发布模型版本数（status === 'PUBLISHED'） */
  published: number;
  /** 草稿模型版本数（非 PUBLISHED） */
  draft: number;
  /** 模型版本总数；为 0 表示「数据白躺」 */
  total: number;
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
  groups: Array<{
    group_id: string;
    datasets: string[];
    record_count: number;
    deduplicated: boolean;
    /** 该同源组包含的物理文件数（成员数） */
    file_count: number;
    /** 该同源组的组 key（内容指纹或显式同源族 ID） */
    fingerprint: string;
  }>;
  /** 每数据集的模型版本覆盖统计（无模型的数据集也在列，published/draft/total 均为 0） */
  modeling: ModelingStat[];
}

/** 数据集风险口径可比性矩阵的一行（每数据集一行） */
export interface CaliberRow {
  /** 数据集逻辑 ID */
  logical_id: string;
  /** 数据集展示名 */
  name: string;
  /** 标签字段名 */
  label_field: string;
  /** 显式登记的正类取值列表 */
  positive_labels: string[];
  /** 标签列实际取值（按计数降序，最多 12 个） */
  label_values: string[];
  /** 标签类型：binary / multiclass / numeric / unknown */
  label_kind: string;
  /** 该数据集样本量 */
  record_count: number;
  /** 该数据集风险样本数 */
  risk_count: number;
  /** 该数据集风险占比 */
  risk_rate: number;
  /** 与场景合并风险占比的偏离倍数（risk_rate / 场景 risk_rate），场景 risk_rate 为 0 时 null */
  deviation: number | null;
  /** 是否已登记风险口径 */
  registered: boolean;
}

/** 流量统计维度覆盖矩阵的一行（每维度一行） */
export interface DimensionCoverage {
  /** 维度中文名（如「协议」「目的端口」） */
  dimension: string;
  /** 维度标识 key */
  key: string;
  /** 覆盖该维度的数据集 logical_id 列表 */
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
  /** 数据集风险口径可比性矩阵（每数据集一行，顺序与 datasets 一致） */
  caliber_matrix: CaliberRow[];
  /** 流量统计维度覆盖矩阵（每维度一行） */
  dimension_coverage: DimensionCoverage[];
}

/** 单数据集电参量基线与遥测统计（每数据集一行） */
export interface TelemetryByDataset {
  /** 数据集逻辑 ID */
  logical_id: string;
  /** 数据集展示名 */
  name: string;
  /** 该数据集样本量 */
  record_count: number;
  /** 各电参量的均值（key/name/unit 口径与场景画像一致），无法计算时 mean 为 null */
  params: Array<{ key: string; name: string; unit: string; mean: number | null }>;
  /** 工频 PowerFrequencyHz 落在 [49.8, 50.2] 区间的占比 */
  frequency_pass_rate: number;
  /** 遥测丢包率 Sensor_Packet_Loss_% 均值，无该字段时 null */
  packet_loss_mean: number | null;
  /** 全部电参量均值是否都在电力基线区间内 */
  baseline_ok: boolean;
  /** 越界项的中文名列表（baseline_ok 为 true 时为空） */
  violations: string[];
}

/** 设备 / 系统覆盖矩阵的一行 */
export interface ComponentMatrixRow {
  /** 设备名或系统名 */
  value: string;
  /** 该行类型：设备 component / 系统 system */
  kind: 'component' | 'system';
  /** 各数据集下的计数与风险占比 */
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
  /** 跨数据集的电参量基线一致性（每数据集一行） */
  telemetry_by_dataset: TelemetryByDataset[];
  /** 设备 × 系统 覆盖矩阵（每设备/系统一行） */
  component_matrix: ComponentMatrixRow[];
}

/** 同源编码族治理表的一行（每数据集一行） */
export interface EncodingFamilyRow {
  /** 数据集逻辑 ID */
  logical_id: string;
  /** 数据集展示名 */
  name: string;
  /** 所属同源组 key */
  source_group: string;
  /** 编码形态：数值连续 / 离散区间 / 配对轨迹 / 未知 */
  encoding: 'numeric' | 'interval' | 'paired' | 'unknown';
  /** 字段数 */
  attribute_count: number;
  /** 样本量 */
  record_count: number;
  /** 正类（碰撞）样本数 */
  risk_count: number;
  /** 正类数是否与同源组代表一致 */
  collision_consistent: boolean;
  /** 该数据集已发布模型版本数 */
  published_model_count: number;
}

/** 同源冗余度与去重收益 */
export interface RedundancyStat {
  /** 物理文件总数 */
  file_count: number;
  /** 去重后的有效同源组数 */
  effective_group_count: number;
  /** 同源冗余率 = 1 - effective_group_count / file_count */
  redundancy_rate: number;
  /** 去重前样本量（按文件逐个求和） */
  raw_samples: number;
  /** 去重后样本量（同源组代表求和） */
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
  /** 同源编码族治理表（每数据集一行） */
  encoding_family: EncodingFamilyRow[];
  /** 同源冗余度与去重收益 */
  redundancy: RedundancyStat;
}

/** 数据集角色分工矩阵的一行（每数据集一行） */
export interface RoleRow {
  /** 数据集逻辑 ID */
  logical_id: string;
  /** 数据集展示名 */
  name: string;
  /** 数据集角色（因子表 / 风险标签表 / 致灾因子表 / 全球编目表 / 随机基线集 / 未分类） */
  role: string;
  /** 字段数 */
  attribute_count: number;
  /** 标签字段名 */
  label_field: string;
  /** 标签类型：binary / multiclass / numeric / unknown */
  label_kind: string;
  /** 是否参与建模（该数据集存在模型版本） */
  participates_in_training: boolean;
  /** 是否产生风险事件（= 已登记风险口径） */
  produces_risk_events: boolean;
  /** 样本量 */
  record_count: number;
  /** 风险占比 */
  risk_rate: number;
}

/** 地形因子跨数据集覆盖矩阵的一行（每因子一行） */
export interface FactorCoverageRow {
  /** 因子名 */
  factor: string;
  /** 含该因子字段的数据集 logical_id 列表 */
  datasets: string[];
  /** 各数据集中该字段的分箱（取值定义）是否一致 */
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
  /** 数据集角色分工矩阵（每数据集一行） */
  roles: RoleRow[];
  /** 地形因子跨数据集覆盖矩阵（每因子一行） */
  factor_coverage: FactorCoverageRow[];
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
  /** 按当前账号在该场景的高风险阈值判定为高风险的事件数（不是写死的 0.8） */
  high_confidence: number;
  /** 后端实际生效的高风险阈值（0~1），用于渲染「风险分 ≥ x」的说明文字 */
  high_threshold: number;
  /** 后端实际生效的中风险阈值（0~1） */
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
