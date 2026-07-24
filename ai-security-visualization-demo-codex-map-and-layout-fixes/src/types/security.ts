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
