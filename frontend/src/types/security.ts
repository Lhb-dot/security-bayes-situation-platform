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

export interface MapPoint {
  id: string;
  label: string;
  value: string;
  x: number;
  y: number;
  delay: number;
  dx?: number;
  dy?: number;
}

export interface AttackFlow {
  id: string;
  source: string;
  sourceIp: string;
  target: string;
  attackType: string;
  severity: AlertRecord['riskLevel'];
  count: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ThreatMapData {
  scope: 'china' | 'world';
  title: string;
  subtitle: string;
  focusLabel: string;
  focusX: number;
  focusY: number;
  points: MapPoint[];
  flows: AttackFlow[];
}

export interface TimelineEvent {
  stage: string;
  time: string;
  description: string;
}

export interface AlertRecord {
  id: string;
  title: string;
  attackType: string;
  sourceIp: string;
  targetHost: string;
  riskLevel: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  status: '待研判' | '处理中' | '已隔离';
  confidence: number;
  timestamp: string;
  aiAnalysis: string;
  rawLog: string;
  recommendations: string[];
  timeline: TimelineEvent[];
  // ========== 新增：贝叶斯模型输入流量特征字段 ==========
  flowLength: number; // 流量总长度，采集后端生成
  duration: number; // 流量持续时长
  accessFreq: number; // 单位时间访问频次
}

export interface MetricItem {
  id: string;
  label: string;
  value: number | string;
  trend: number;
}

export interface MetricHistory {
  id: string;
  label: string;
  unit: string;
  insight: string;
  points: HistoryPoint[];
}

export interface DashboardSnapshot {
  metrics: MetricItem[];
  metricHistories: MetricHistory[];
  attackTrend: TrendPoint[];
  attackTypes: TypeDistribution[];
  topSourceIps: RankingItem[];
  topTargetHosts: RankingItem[];
  protocolDistribution: TypeDistribution[];
  responseActions: RankingItem[];
  sourceMap: {
    china: ThreatMapData;
    world: ThreatMapData;
  };
}

// ===================== 多场景架构新增类型（不修改以上已有类型） =====================

/** 四场景标识（V3.0：新增地质风险场景） */
export type ScenarioId = 'network_security' | 'power_system' | 'geological_risk' | 'flightdeck_operation';

/** 场景定义 */
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
  status: 'active' | 'inactive';
}

/** 场景详情（含态势指标） */
export interface ScenarioDetail {
  scenario: Scenario;
  metrics: MetricItem[];
  trend_data: TrendPoint[];
  risk_distribution: TypeDistribution[];
  recent_events: RiskEvent[];
}

/** 全局态势总览 */
export interface GlobalOverview {
  global_risk_score: number;
  global_risk_level: 'critical' | 'high' | 'medium' | 'low';
  scenario_count: number;
  high_risk_count: number;
  active_model_count: number;
  scenarios: Scenario[];
  global_trend: TrendPoint[];
}

/** 数据集字段定义 */
export interface DatasetField {
  field_name: string;
  field_type: string;
  field_role: '输入特征' | '分类标签';
  description: string;
  sample_value: string;
  nullable: boolean;
  /** 枚举字段值域（需求 3.1.5：枚举字段必须按当前数据集定义的值域进行校验） */
  enum_values?: string[];
}

/** 数据集 */
export interface Dataset {
  dataset_id: string;
  name: string;
  description: string;
  scenario_id: ScenarioId;
  record_count: number;
  field_count: number;
  fields: DatasetField[];
  created_at: string;
  data_format: 'csv' | 'arff' | 'json';
  // ========== v2.0：数据集版本与状态（需求 2.3） ==========
  dataset_version: string;   // 最新版本号，如 v1
  uploaded_by: string;       // 上传人账号
  uploaded_at: string;       // 上传时间
  enabled: boolean;          // 启用状态
  referenced: boolean;       // 是否已被模型版本引用（引用后只能停用，不能物理删除）
}

/** 数据集版本（需求 2.3.4） */
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
  uploaded_at: string;
  enabled: boolean;             // 启用状态（停用后不得用于新训练）
  referenced: boolean;          // 是否被模型版本引用
}

/** 模型版本记录（需求 6.7.1 最小信息） */
export interface ModelVersion {
  model_id: string;
  scenario_id: ScenarioId;
  dataset_name: string;
  algo_type: string;
  discrete_method: string;
  accuracy: number;
  f1: number;
  recall: number;
  g_mean: number;
  train_time_s: number;
  created_at: string;
}

/** 模型生命周期状态（需求 6.7.2） */
export type ModelStatus = 'TRAINING' | 'FAILED' | 'DRAFT' | 'PUBLISHED' | 'OFFLINE' | 'DISABLED';

/** 模型评估指标（需求 6.4 统一计算规范） */
export interface EvaluationMetrics {
  accuracy: number;
  recall: number;
  precision: number;
  specificity: number;
  f1: number;
  g_mean: number;
}

/** 模型版本（v2.0 生命周期模型，需求 6.7.1） */
export interface ModelVersionRecord {
  model_version_id: string;
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;
  algorithm_id: string;
  training_parameters: Record<string, unknown>;
  evaluation_metrics: EvaluationMetrics;
  train_time_s: number;
  trained_by: string;          // 发起训练的管理员账号
  trained_at: string;
  status: ModelStatus;
  published_by?: string;       // 发布操作管理员
  published_at?: string;
  is_default: boolean;         // 是否为"场景＋数据集"默认推荐模型
}

/** 风险等级（大写枚举：风险事件/推理记录使用；历史大小写双轨，统一走 toRiskLevel 转换） */
export type RiskLevelUpper = 'HIGH' | 'MEDIUM' | 'LOW';

/**
 * 风险等级大小写双轨转换工具（历史包袱：RiskEvent/InferenceRecord 为大写，
 * Scenario/GlobalOverview 为小写）。改造期间统一入口，禁止用 as any 绕过。
 * - 'critical' 归并为 'HIGH'
 * - 无法识别的值兜底为 'LOW'
 */
export function toRiskLevel(level: string): RiskLevelUpper {
  const normalized = level.toUpperCase();
  if (normalized === 'HIGH' || normalized === 'MEDIUM' || normalized === 'LOW') return normalized;
  if (normalized === 'CRITICAL') return 'HIGH';
  return 'LOW';
}

/** 风险事件（统一封装，适配四场景 — 符合需求 5.2 最小字段结构，v2.0 补齐必填字段） */
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
  /** 故障位置 x 坐标（需求 5.2 / 7.4.1：仅航母甲板场景使用，坐标基准 1000px） */
  fault_position_x?: number | null;
  /** 故障位置 y 坐标（需求 5.2 / 7.4.1：仅航母甲板场景使用，坐标基准 1000px） */
  fault_position_y?: number | null;
  occurred_at: string;
  status: '待处置' | '处理中' | '已处置';
  raw_features: Record<string, unknown>;
  description: string;
}

/** 态势分析数据 */
export interface SituationData {
  scenario_id: ScenarioId;
  time_range: string;
  score_history: HistoryPoint[];
  event_distribution: TypeDistribution[];
  risk_trend: TrendPoint[];
  metrics: MetricItem[];
}

// ===================== 态势报告：算法解释 + 结构化报告数据 =====================

/** 单个类别的概率 */
export interface ClassProb {
  class: string;
  probability: number;
}

/** 多视图中的一个视图 */
export interface ViewDistribution {
  name: string;
  distribution: ClassProb[];
}

/** 特征值对单个风险类的加权条件概率贡献 */
export interface ClassContribution {
  class: string;
  weight: number;
  cond_prob?: number;
  contribution?: number;
}

/** 单个特征值的可解释性证据 */
export interface FeatureEvidence {
  attribute: string;
  value: string;
  class_contributions: ClassContribution[];
}

/** 算法可解释性信息（Java /predict 返回，落库 explain_data） */
export interface InferenceExplain {
  prediction_label: string;
  probability: number | null;
  class_distribution: ClassProb[];
  views: ViewDistribution[];
  view_weights: number[];
  feature_evidence: FeatureEvidence[];
}

/** 报告单个特征的加权条件概率信息 */
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

/** 报告结构化数据（report_data，6.10 定义的完整结构） */
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
  data_notes: string;
  analysis_nl: string;
  guidance_nl: string;
}

/** 报告定义 */
export interface Report {
  report_id: string;
  title: string;
  scenario_id: ScenarioId;
  scenario_name: string;
  summary: string;
  content?: string;
  /** 结构化报告数据（自动生成报告时由后端返回，供详情页渲染图表与 NL 文本） */
  report_data?: ReportData;
  created_at: string;
  format: 'markdown' | 'html' | 'pdf';
  status: 'generating' | 'completed' | 'failed';
  file_url?: string;
  /** 是否定时生成 */
  scheduled?: boolean;
  /** 定时生成周期（天） */
  interval_days?: number;
  /** 报告生成者（用户 ID），用于"普通用户只看自己生成的报告" */
  generated_by?: string;
  target_user_id?: string;
}

// ===================== v2.0 用户与权限（需求 6.5） =====================

/** 角色（三级）：最外层管理员 / 场景管理员 / 场景用户 */
export type UserRole = 'SUPER_ADMIN' | 'SCENARIO_ADMIN' | 'SCENARIO_USER';

/** 用户账号 */
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

/** Platform account statistics (SUPER_ADMIN overview) */
export interface PlatformUserStats {
  total: number;
  super_admins: number;
  scenario_admins: number;
  scenario_users: number;
  disabled: number;
  by_scenario: {
    scenario_id: ScenarioId;
    name: string;
    user_count: number;
  }[];
}

// ===================== v2.0 算法注册（需求 6.6） =====================

/** 算法公开训练参数定义 */
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
}

/** 算法注册定义（需求 6.6.2 算法接入规则） */
export interface AlgorithmDefinition {
  algorithm_id: string;                                   // A2WNB / MAWNB / EMAWNB / CAVWNB / PMWNB
  display_name: string;
  available: boolean;                                     // 可用状态
  input_constraints: string;                              // 支持的输入类型或数据约束
  description: string;
  params: AlgorithmParamDef[];                            // 公开训练参数定义
}

// ===================== v2.0 推理记录（需求 6.2 / 6.8） =====================

/** 推理记录 */
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
}

// ===================== v2.0 风险阈值配置（需求 5.4.1） =====================

/** 按场景风险阈值配置 */
export interface ThresholdConfig {
  user_id?: number;
  scenario_id: ScenarioId;
  medium_threshold: number;
  high_threshold: number;
  updated_by: number | string;                             // 最后修改账号
  updated_at: string;
}

/** 阈值变更记录（需求 5.4.1.5） */
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
  // 兼容旧 mock 数据结构
  log_id?: string;
  changed_at?: string;
  old_medium_threshold?: number;
  old_high_threshold?: number;
  new_medium_threshold?: number;
  new_high_threshold?: number;
}

// ===================== v3.0 数据预览与场景看板（需求 2.4 / 第 7 节） =====================

/** 数据预览行（需求 2.4：单元格为字符串或数值） */
export type DataRow = Record<string, string | number>;

/** 数据集数据预览（需求 2.4：只读分页浏览；后端单次最大返回 100 条，前端每页最多 50） */
export interface DataPreview {
  total: number;
  page: number;
  page_size: number;
  rows: DataRow[];
  label_field: string;
}

/** 航母甲板方向角对比点（需求 7.4：按时间步对比双机方向角，单位：度） */
export interface RadarComparePoint {
  step: number;
  plane1_dir_angle_deg: number;
  plane2_dir_angle_deg: number;
}

/** 场景看板特有图表数据（Task 009 各场景看板消费；字段缺失时图表空态降级） */
export interface ScenarioDashboardCharts {
  /** 网络安全（需求 7.1）：TOP 端口 / 流量分布 */
  network?: {
    top_ports: RankingItem[];
    flow_distribution: TypeDistribution[];
  };
  /** 电力系统（需求 7.2）：设备健康度 / IssueType 分布 */
  power?: {
    device_health: RankingItem[];
    issue_type_distribution: TypeDistribution[];
  };
  /** 地质风险（需求 7.3）：区域风险 / 数据集风险占比 / 关键因子贡献 */
  geological?: {
    region_risk: TypeDistribution[];
    dataset_risk_share: TypeDistribution[];
    factor_contribution: RankingItem[];
  };
  /** 航母甲板（需求 7.4）：间距变化折线 / 方向角对比雷达 */
  flightdeck?: {
    distance_trend: TrendPoint[];
    radar_compare: RadarComparePoint[];
  };
}

/** 场景看板聚合数据（需求第 7 节：三区布局数据源） */
export interface ScenarioDashboardData {
  scenario_id: ScenarioId;
  metrics: MetricItem[];                  // 顶部指标行
  trend_data: TrendPoint[];               // 通用趋势
  risk_distribution: TypeDistribution[];  // 风险等级/类型分布
  recent_events: RiskEvent[];             // 风险事件列表/时间线
  charts: ScenarioDashboardCharts;        // 场景特有图表数据
}

