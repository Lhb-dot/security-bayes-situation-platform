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

/** 三大场景标识 */
export type ScenarioId = 'network_security' | 'power_system' | 'flightdeck_operation';

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
}

/** 模型版本记录 */
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

/** 风险事件（统一封装，适配三场景 — 符合需求 5.2 最小字段结构） */
export interface RiskEvent {
  event_id: string;
  scenario_id: ScenarioId;
  dataset_id: string;
  model_version_id: string;
  original_label: string;
  risk_type: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
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

/** 报告定义 */
export interface Report {
  report_id: string;
  title: string;
  scenario_id: ScenarioId;
  scenario_name: string;
  summary: string;
  created_at: string;
  format: 'markdown' | 'html' | 'pdf';
  status: 'generating' | 'completed' | 'failed';
  file_url?: string;
}
