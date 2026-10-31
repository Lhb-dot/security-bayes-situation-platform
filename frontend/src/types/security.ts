export interface TrendPoint {
  label: string;
  value: number;
  blocked: number;
  sources: number;
  primaryType: string;
}

export interface HistoryPoint {
  label: string;
  value: number;
  blocked: number;
  sources: number;
  primaryType: string;
}

export interface TypeDistribution {
  label: string;
  value: number;
  color: string;
}

export interface RankingItem {
  name: string;
  score: number;
}

export interface MetricItem {
  id: string;
  label: string;
  value: number | string;
  trend: number;
}


export type ScenarioId = 'network_security' | 'power_system' | 'geological_risk' | 'flightdeck_operation';

export interface Scenario {
  scenario_id: ScenarioId;
  name: string;
  description: string;
  risk_level: 'critical' | 'high' | 'medium' | 'low';
  risk_score: number;
  event_count: number;
  high_risk_count: number;
  dataset_count: number;
  model_count: number;
  sample_count?: number;
  published_model_count?: number;
  status: 'active' | 'inactive';
}

export interface GlobalOverview {
  global_risk_score: number;
  global_risk_level: 'critical' | 'high' | 'medium' | 'low';
  scenario_count: number;
  high_risk_count: number;
  active_model_count: number;
  scenarios: Scenario[];
  global_trend: TrendPoint[];
}

export interface DatasetField {
  field_name: string;
  field_type: string;
  field_role: '输入特征' | '分类标签';
  description: string;
  sample_value: string;
  nullable: boolean;
  enum_values?: string[];
}

export interface Dataset {
  dataset_id: string;
  name: string;
  file_name?: string;
  description: string;
  scenario_id: ScenarioId;
  record_count: number;
  field_count: number;
  fields: DatasetField[];
  created_at: string;
  data_format: 'csv' | 'arff' | 'json';
  dataset_version: string;   // 最新版本号，如 v1
  uploaded_by: string;       // 上传人账号
  uploader_name: string;     // 上传人展示名（用户名，非编号）
  uploaded_at: string;       // 上传时间
  enabled: boolean;          // 启用状态
  referenced: boolean;       // 是否已被模型版本引用（引用后只能停用，不能物理删除）
  change_type?: string | null;
  change_type_label?: string | null;
  is_breaking?: boolean;
  base_version_id?: number | null;
}

export interface DatasetVersion {
  dataset_version_id: string;   // 版本唯一编号
  dataset_id: string;           // 所属数据集编码
  dataset_version: string;      // 版本号，如 v1
  name: string;
  scenario_id: ScenarioId;
  data_format: Dataset['data_format'];
  file_path: string;
  record_count: number;
  field_count: number;
  fields: DatasetField[];
  uploaded_by: string;
  uploader_name: string;        // 上传人展示名（用户名，非编号）
  uploaded_at: string;
  enabled: boolean;             // 启用状态（停用后不得用于新训练）
  referenced: boolean;          // 是否被模型版本引用
  change_type?: string | null;
  change_type_label?: string | null;
  is_breaking?: boolean;
  base_version_id?: number | null;
}

// 模型生命周期状态
export type ModelStatus = 'TRAINING' | 'FAILED' | 'DRAFT' | 'PUBLISHED' | 'DISABLED';

// 模型评估指标
export interface EvaluationMetrics {
  accuracy?: number | null;
  recall?: number | null;
  precision?: number | null;
  specificity?: number | null;
  f1?: number | null;
  g_mean?: number | null;
  risk_recall?: number | null;
  risk_f1?: number | null;
  cv_mean?: number | null;
  cv_std?: number | null;
  quality_availability?: Record<string, { available: boolean; reason: string | null }>;
}

export type RiskLevelUpper = 'HIGH' | 'MEDIUM' | 'LOW';

/**
 * 风险等级大小写双轨转换工具（历史包袱：RiskEvent/InferenceRecord 为大写，
 * Scenario/GlobalOverview 为小写）。改造期间统一入口，禁止用 as any 绕过。
 * - 'critical' 归并为 'HIGH'
 * - 无法识别的值兜底为 'LOW'。
 */
export function toRiskLevel(level: string): RiskLevelUpper {
  const normalized = level.toUpperCase();
  if (normalized === 'HIGH' || normalized === 'MEDIUM' || normalized === 'LOW') return normalized;
  if (normalized === 'CRITICAL') return 'HIGH';
  return 'LOW';
}

// 风险事件（统一封装，适配四场景 —最小字段结构，v2.0 补齐必填字段）
export interface RiskEvent {
  event_id: string;
  inference_record_id: string;      // 来源推理记录编号（需求 5.2）
  created_by_user_id: string;       // 发起推理的账号编号（用于访问控制）
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;          // 来源数据集版本
  algorithm_id: string;             // 来源算法
  model_version_id: string;
  original_label: string;
  risk_type: string;
  risk_level: RiskLevelUpper;
  risk_score: number;
  // 故障位置 x 坐标
  fault_position_x?: number | null;
  // 故障位置 y 坐标
  fault_position_y?: number | null;
  occurred_at: string;
  status: '待处置' | '处理中' | '已处置';
  raw_features: Record<string, unknown>;
  description: string;
  dataset_name?: string;
  algorithm_name?: string;
  creator_name?: string;
  handling_comment?: string | null;
}

export interface SituationData {
  scenario_id: ScenarioId;
  time_range: string;
  score_history: HistoryPoint[];
  event_distribution: TypeDistribution[];
  risk_trend: TrendPoint[];
  metrics: MetricItem[];
}


export interface ClassProb {
  class: string;
  probability: number;
}

export interface ViewDistribution {
  name: string;
  distribution: ClassProb[];
}

export interface ClassContribution {
  class: string;
  weight: number;
  cond_prob?: number;
  contribution?: number;
}

export interface FeatureEvidence {
  attribute: string;
  value: string;
  class_contributions: ClassContribution[];
}

export interface InferenceExplain {
  contract_version?: string;
  prediction?: string;
  prediction_is_risk?: boolean;
  risk_probability?: number | null;
  risk_threshold?: number | null;
  confidence?: string;
  top_features?: Array<{
    feature_name: string;
    display_name?: string;
    raw_value: unknown;
    processed_value?: unknown;
    contribution?: number;
    direction: string;
    rank: number;
    meaning?: string;
    risk_description?: string;
    recommended_action?: string;
  }>;
  conflict?: { has_conflict: boolean; description: string };
  scenario?: Record<string, unknown>;
  recommended_actions?: string[];
  algorithm_details?: Record<string, unknown>;
  input_snapshot?: Record<string, unknown>;
  model_quality?: {
    risk_recall?: number | null;
    risk_f1?: number | null;
    cv_mean?: number | null;
    cv_std?: number | null;
    availability?: Record<string, { available: boolean; reason: string | null }>;
  };
  prediction_label?: string;
  probability?: number | null;
  class_distribution?: ClassProb[];
  views?: ViewDistribution[];
  view_weights?: number[];
  feature_evidence?: FeatureEvidence[];
}

export interface ReportFeature {
  attribute: string;
  value: string;
  view: string | null;
  weight: number | null;
  cond_probs: Array<{ class: string; cond_prob: number | null }>;
  weighted_contribution: number | null;
  support_direction: string;
  salience: number;
  rank: number;
}

// 报告结构化数据（report_data，6.10 定义的完整结构）
export interface ReportData {
  report_info: {
    title: string;
    generated_at: string;
    report_period: string | null;
    generated_by: string;
    scenario_name: string | null;
    scenario_code: string | null;
    data_scope: string;
    datasets: Array<{ logical_id: string; version: number | null }>;
    algorithms: Array<{ code: string; name: string }>;
    model_versions: Array<{ id: number; algorithm_code: string | null }>;
  };
  overview: {
    total_inferences: number;
    risk_count: number;
    normal_count: number;
    risk_ratio: number | null;
    normal_ratio: number | null;
    high_count: number;
    medium_count: number;
    low_count: number;
    pending_count: number;
    processing_count: number;
    resolved_count: number;
    avg_risk_prob: number | null;
    risk_trend: string;
  };
  prediction: {
    label_distribution: Array<{ label: string; count: number; ratio: number | null }>;
    class_probability: Array<{ class: string; probability: number | null }>;
    risk_prob_buckets: Array<{ range: string; count: number }>;
    low_confidence_count: number;
  };
  model_analysis: Array<{
    model_version_id: number;
    algorithm_code: string | null;
    algorithm_name: string | null;
    inference_count: number;
    risk_count: number;
    views: Array<{
      name: string;
      predicted_label: string;
      distribution: ClassProb[];
      consistent_with_final: boolean;
    }>;
    view_weights: number[];
    calculation_method: string | null;
    has_views: boolean;
  }>;
  feature_analysis: {
    calculation_method: string | null;
    top_features: Array<ReportFeature>;
    all_features: Array<ReportFeature>;
  };
  trend: Array<{
    date: string;
    inference_count: number;
    risk_count: number;
    risk_ratio: number;
    avg_risk_prob: number | null;
  }>;
  key_events: Array<{
    time: string | null;
    risk_level: string;
    probability: number | null;
    risk_type: string;
    status: string;
    key_features: string[];
  }>;
  key_events_total: number;
  data_notes: string;
  analysis_nl: string;
  guidance_nl: string;
}

export interface Report {
  report_id: string;
  title: string;
  scenario_id: ScenarioId | '';
  scenario_name: string;
  content?: string;
  report_data?: ReportData;
  created_at: string;
  format: 'markdown' | 'html' | 'pdf';
  // 后端 report 表没有 status 列，`_serialize` 恒下发 "completed"；前端不渲染该字段
  status: 'completed';
  scheduled?: boolean;
  interval_days?: number;
  next_run_at?: string;
  generated_by?: string;
}

// v2.0 用户与权限

export type UserRole = 'SUPER_ADMIN' | 'SCENARIO_ADMIN' | 'SCENARIO_USER';

export interface UserAccount {
  id: number;
  user_id: string;
  username: string;
  display_name: string;
  role: UserRole;
  status: 'active' | 'disabled';
  created_at: string;
  created_by: string;
  last_login_at?: string;
  scenario_id: number | null;
  scenario_code: ScenarioId | null;
  /** @deprecated 仅为旧展示组件兼容；正式数据源只返回单个 scenario_code。 */
  scenario_ids?: ScenarioId[];
}

// v2.0 算法注册

export interface AlgorithmParamDef {
  param_name: string;                                     // 参数名
  label: string;                                          // 显示名称
  type: 'number' | 'string' | 'boolean' | 'select';
  default_value: number | string | boolean;
  min?: number;                                           // number 类型范围
  max?: number;
  step?: number;
  options?: { value: string; label: string }[];           // select 类型可选项
  description: string;
  requires_numeric_features?: boolean;
}

// 算法注册定义
export interface AlgorithmDefinition {
  algorithm_id: string;                                   // A2WNB / MAWNB / EMAWNB / CAVWNB / PMWNB / DIWNB / KFDB / FLNB / FTAWNB
  display_name: string;
  available: boolean;                                     // 可用状态
  input_constraints: string;                              // 支持的输入类型或数据约束
  description: string;
  params: AlgorithmParamDef[];                            // 公开训练参数定义
}

// v2.0 推理记录

export interface InferenceRecord {
  inference_record_id: string;
  user_id: string;                                        // 发起推理的账号（访问控制用）
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;
  algorithm_id: string;
  model_version_id: string;
  input_features: Record<string, unknown>;
  original_label: string;                                 // 数据集原始预测标签
  risk_type: string;                                      // 风险类为映射后的统一类型，正常类为空
  risk_level: RiskLevelUpper;                             // 正常类为 LOW 占位
  risk_score: number;                                     // 模型对风险类的输出概率
  is_risk: boolean;                                       // 是否为风险类
  occurred_at: string;
  model_evaluation?: {
    available: boolean;
    source: 'ai' | 'fallback' | null;
    markdown: string | null;
    generated_at: string | null;
  };
}

// v2.0 风险阈值配置

export interface ThresholdConfig {
  user_id?: number;
  scenario_id: ScenarioId;
  medium_threshold: number;
  high_threshold: number;
  updated_by: number | string;                             // 最后修改账号
  updated_at: string;
}

/**
 * 后端原始形状：`scenario_id` 是场景数字主键（`risk_threshold.scenario_id` 为 BigInteger FK）。
 * 只在 `api/riskThresholdApi.ts` 的转换函数入参处出现，页面层一律用 `ThresholdConfig`。
 */
export interface ApiThresholdConfig extends Omit<ThresholdConfig, 'scenario_id'> {
  scenario_id: number;
}

// 阈值变更记录
export interface ThresholdChangeLog {
  id?: number;
  user_id?: number;
  scenario_id: ScenarioId;
  operator_id: number | string;                            // 操作账号ID
  operated_at?: string;
  old_medium?: number;
  old_high?: number;
  new_medium?: number;
  new_high?: number;
}

// 后端原始形状：`scenario_id` 是场景数字主键。
export interface ApiThresholdChangeLog extends Omit<ThresholdChangeLog, 'scenario_id'> {
  scenario_id: number;
}

// v3.0 数据预览与场景看板

// 数据预览行
export type DataRow = Record<string, string | number>;

// 数据集数据预览
export interface DataPreview {
  total: number;
  page: number;
  page_size: number;
  rows: DataRow[];
  label_field: string;
}

// 航母甲板方向角对比点
export interface RadarComparePoint {
  step: number;
  plane1_dir_angle_deg: number;
  plane2_dir_angle_deg: number;
}

// 场景看板特有图表数据
export interface ScenarioDashboardCharts {
  // 网络安全TOP 端口 / 流量分布
  network?: {
    top_ports: RankingItem[];
    flow_distribution: TypeDistribution[];
  };
  // 电力系统设备健康度 / IssueType 分布
  power?: {
    device_health: RankingItem[];
    issue_type_distribution: TypeDistribution[];
  };
  // 地质风险区域风险 / 数据集风险占比 / 关键因子贡献
  geological?: {
    region_risk: TypeDistribution[];
    dataset_risk_share: TypeDistribution[];
    factor_contribution: RankingItem[];
  };
  // 航母甲板间距变化折线 / 方向角对比雷达
  flightdeck?: {
    distance_trend: TrendPoint[];
    radar_compare: RadarComparePoint[];
  };
}

// 场景看板聚合数据
export interface ScenarioDashboardData {
  scenario_id: ScenarioId;
  metrics: MetricItem[];                  // 顶部指标行
  trend_data: TrendPoint[];               // 通用趋势
  risk_distribution: TypeDistribution[];  // 风险等级/类型分布
  recent_events: RiskEvent[];             // 风险事件列表/时间线
  charts: ScenarioDashboardCharts;        // 场景特有图表数据
}
