import type {
  AlertRecord,
  AttackFlow,
  DashboardSnapshot,
  DataPreview,
  DataRow,
  HistoryPoint,
  MetricHistory,
  RankingItem,
  ThreatMapData,
  TrendPoint,
  TypeDistribution,
  Scenario,
  ScenarioDetail,
  GlobalOverview,
  Dataset,
  DatasetField,
  DatasetVersion,
  RiskEvent,
  SituationData,
  Report,
  ScenarioId,
  UserAccount,
  UserRole,
  AlgorithmDefinition,
  AlgorithmParamDef,
  InferenceRecord,
  ModelVersionRecord,
  ModelStatus,
  PlatformUserStats,
  EvaluationMetrics,
  ThresholdConfig,
  ThresholdChangeLog,
} from '../types/security';

const attackTypes = ['SQL 注入', '暴力破解', '端口扫描', '异常流量', 'WebShell 投递'];
const hosts = ['web-01', 'db-core-02', 'api-gateway-03', 'auth-node-01', 'cache-edge-02'];
const severities: AlertRecord['riskLevel'][] = ['HIGH', 'MEDIUM', 'CRITICAL'];
const statuses: AlertRecord['status'][] = ['待研判', '处理中', '已隔离'];
const worldPointTemplates = [
  { label: '首尔', lon: 126.978, lat: 37.5665, dx: -12, dy: -14 },
  { label: '东京', lon: 139.6917, lat: 35.6895, dx: 10, dy: -12 },
  { label: '新加坡', lon: 103.8198, lat: 1.3521, dx: 10, dy: 8 },
  { label: '法兰克福', lon: 8.6821, lat: 50.1109, dx: 10, dy: -10 },
  { label: '伦敦', lon: -0.1276, lat: 51.5072, dx: -18, dy: -8 },
  { label: '洛杉矶', lon: -118.2437, lat: 34.0522, dx: 10, dy: -14 },
  { label: '圣保罗', lon: -46.6333, lat: -23.5505, dx: 10, dy: 8 },
];
const chinaPointTemplates = [
  { label: '北京', lon: 116.4074, lat: 39.9042, dx: 12, dy: -14 },
  { label: '上海', lon: 121.4737, lat: 31.2304, dx: 12, dy: -12 },
  { label: '广州', lon: 113.2644, lat: 23.1291, dx: -28, dy: -10 },
  { label: '深圳', lon: 114.0579, lat: 22.5431, dx: 10, dy: 8 },
  { label: '成都', lon: 104.0665, lat: 30.5728, dx: -26, dy: -10 },
  { label: '乌鲁木齐', lon: 87.6168, lat: 43.8256, dx: 10, dy: -10 },
  { label: '哈尔滨', lon: 126.6424, lat: 45.756, dx: 10, dy: -10 },
];
const primaryTargetGeo = { label: '杭州安全中枢', lon: 120.1551, lat: 30.2741 };

let cache: { dashboard: DashboardSnapshot; alerts: AlertRecord[] } | null = null;

const random = (min: number, max: number) => Math.floor(Math.random() * (max - min + 1)) + min;
const sample = <T>(list: T[]): T => list[random(0, list.length - 1)];
const createIp = () => `${random(14, 223)}.${random(0, 255)}.${random(0, 255)}.${random(1, 254)}`;
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
const projectWorld = (lon: number, lat: number) => ({
  x: ((lon + 180) / 360) * 100,
  y: ((90 - lat) / 180) * 100,
});
const projectChina = (lon: number, lat: number) => ({
  x: 8 + ((lon - 73) / 62) * 82,
  y: 12 + ((54 - lat) / 36) * 70,
});

const createTrend = (): TrendPoint[] =>
  Array.from({ length: 12 }, (_, index) => ({
    label: `${String(index * 2).padStart(2, '0')}:00`,
    value: random(18, 96),
    blocked: random(8, 72),
    sources: random(5, 26),
    primaryType: sample(attackTypes),
  }));

const createHistoryPoints = (count: number, baseMin: number, baseMax: number): HistoryPoint[] =>
  Array.from({ length: count }, (_, index) => ({
    label: `${index + 1}日`,
    value: random(baseMin, baseMax),
    blocked: random(Math.max(1, Math.floor(baseMin * 0.35)), Math.max(2, Math.floor(baseMax * 0.72))),
    sources: random(4, 32),
    primaryType: sample(attackTypes),
  }));

const createMetricHistories = (): MetricHistory[] => [
  {
    id: 'threat-total',
    label: '当前威胁总数',
    unit: '次',
    insight: '过去 30 天整体威胁总量呈现波峰前移，最近一周以扫描与异常流量增长最明显。',
    points: createHistoryPoints(30, 520, 1780),
  },
  {
    id: 'critical-events',
    label: '高危事件数',
    unit: '次',
    insight: '高危事件峰值多与夜间爆破和异常登录失败事件叠加出现，建议重点联动账号风控。',
    points: createHistoryPoints(30, 28, 180),
  },
  {
    id: 'ai-accuracy',
    label: 'AI 研判准确率',
    unit: '%',
    insight: '模型稳定维持高准确率，误报主要来自高频扫描和规则边界模糊的混合流量。',
    points: createHistoryPoints(30, 91, 99),
  },
  {
    id: 'response-time',
    label: '平均响应时间',
    unit: 'min',
    insight: '响应时间在自动封禁策略触发后明显改善，说明联动处置链路已开始发挥作用。',
    points: createHistoryPoints(30, 2, 10),
  },
];

const createDistribution = (): TypeDistribution[] => {
  return normalizeDistribution(
    attackTypes.map((label, index) => ({
      label,
      value: random(12, 32),
      color: ['#5ba6ff', '#53e5c8', '#ffd166', '#ff7b72', '#a78bfa'][index],
    }))
  );
};

const normalizeDistribution = (items: TypeDistribution[]): TypeDistribution[] => {
  const total = items.reduce((sum, item) => sum + item.value, 0);
  const percentages = items.map((item) => Math.round((item.value / total) * 100));
  const diff = 100 - percentages.reduce((sum, value) => sum + value, 0);
  percentages[percentages.length - 1] += diff;

  return items.map((item, index) => ({ ...item, value: percentages[index] }));
};

const createProtocolDistribution = (): TypeDistribution[] =>
  normalizeDistribution([
    {
      label: 'HTTP/HTTPS',
      value: random(28, 42),
      color: '#5ba6ff',
    },
    {
      label: 'SSH',
      value: random(12, 24),
      color: '#53e5c8',
    },
    {
      label: 'RDP',
      value: random(10, 18),
      color: '#ffd166',
    },
    {
      label: 'DNS',
      value: random(8, 16),
      color: '#ff7b72',
    },
    {
      label: 'Other',
      value: random(6, 14),
      color: '#a78bfa',
    },
  ]);

const createRanking = (items: string[]): RankingItem[] =>
  items.map((name) => ({ name, score: random(48, 97) })).sort((a, b) => b.score - a.score);

const createFlow = (
  source: { label: string; x: number; y: number },
  target: { label: string; x: number; y: number },
  index: number
): AttackFlow => ({
  id: `${source.label}-${index}`,
  source: source.label,
  sourceIp: createIp(),
  target: target.label,
  attackType: sample(attackTypes),
  severity: sample(severities),
  count: random(18, 120),
  x1: source.x,
  y1: source.y,
  x2: target.x,
  y2: target.y,
});

const createThreatMapData = (
  scope: 'china' | 'world',
  title: string,
  subtitle: string,
  templates: { label: string; lon: number; lat: number; dx?: number; dy?: number }[]
): ThreatMapData => {
  const focus =
    scope === 'world'
      ? projectWorld(primaryTargetGeo.lon, primaryTargetGeo.lat)
      : projectChina(primaryTargetGeo.lon, primaryTargetGeo.lat);

  return {
    scope,
    title,
    subtitle,
    focusLabel: primaryTargetGeo.label,
    focusX: focus.x,
    focusY: focus.y,
    points: templates.map((item, index) => {
      const projected = scope === 'world' ? projectWorld(item.lon, item.lat) : projectChina(item.lon, item.lat);
      return {
        id: `${scope}-${index}`,
        label: item.label,
        value: `${random(18, 80)} 次`,
        x: projected.x,
        y: projected.y,
        delay: index * 0.6,
        dx: item.dx,
        dy: item.dy,
      };
    }),
    flows: templates.map((item, index) => {
      const source = scope === 'world' ? projectWorld(item.lon, item.lat) : projectChina(item.lon, item.lat);
      return createFlow({ label: item.label, ...source }, { label: primaryTargetGeo.label, ...focus }, index);
    }),
  };
};

const createTimeline = (time: string) => {
  const base = time.split(' ')[1];
  return [
    { stage: '扫描', time: `${base} - 06s`, description: '源地址针对多个端口发起连续探测，请求频率明显异常。' },
    { stage: '爆破', time: `${base} - 04s`, description: '认证接口在短时间内出现多次失败登录尝试。' },
    { stage: '请求异常', time: `${base} - 02s`, description: '载荷中出现高危关键字与规避型编码特征。' },
    { stage: '触发高危事件', time: base, description: 'Transformer 模型结合行为链判断为高风险入侵尝试。' },
  ];
};

const createAlert = (index: number): AlertRecord => {
  const timestamp = `2026-03-17 ${String(random(10, 23)).padStart(2, '0')}:${String(random(0, 59)).padStart(2, '0')}:${String(random(0, 59)).padStart(2, '0')}`;
  const attackType = sample(attackTypes);
  const sourceIp = createIp();
  const targetHost = sample(hosts);
  const activeScenarios = SCENARIO_META.filter(s => s.id !== 'flightdeck_operation');

  return {
    id: `ALERT-20260317-${String(index + 1).padStart(4, '0')}`,
    title: `${attackType} 告警 #${index + 1}`,
    attackType,
    sourceIp,
    targetHost,
    riskLevel: sample(severities),
    status: sample(statuses),
    confidence: random(82, 99),
    timestamp,
    aiAnalysis: `模型检测到 ${sourceIp} 在面向 ${targetHost} 的访问中呈现出连续探测、认证重试和异常载荷拼接的行为链，符合 ${attackType} 的模式特征，建议优先进行阻断与主机侧取证。`,
    rawLog: `{"timestamp":"${timestamp}","src_ip":"${sourceIp}","dst_host":"${targetHost}","uri":"/api/auth/login","method":"POST","attack_type":"${attackType}","payload":"SELECT * FROM users WHERE id='1' OR '1'='1'","score":${random(87, 99)}}`,
    recommendations: [
      '立即封禁攻击源 IP，并同步到边界防火墙与 WAF 策略。',
      `对 ${targetHost} 执行快速排查，确认是否存在未授权访问或横向移动痕迹。`,
      '保留相关日志与流量样本，供后续模型复盘与规则优化。',
    ],
    timeline: createTimeline(timestamp),
    flowLength: Number(Math.random().toFixed(2)),
    duration: Number(Math.random().toFixed(2)),
    accessFreq: Number(Math.random().toFixed(2)),
    scenario_id: sample(activeScenarios).id,
  } as AlertRecord;
};

const generateDataset = () => {
  const alerts = Array.from({ length: 12 }, (_, index) => createAlert(index)).sort((a, b) =>
    b.timestamp.localeCompare(a.timestamp)
  );

  cache = {
    dashboard: {
      metrics: [
        { id: 'threat-total', label: '当前威胁总数', value: random(1128, 1860), trend: random(6, 24) },
        { id: 'critical-events', label: '高危事件数', value: random(72, 168), trend: -random(2, 15) },
        { id: 'ai-accuracy', label: 'AI 研判准确率', value: `${random(93, 98)}.${random(0, 9)}%`, trend: random(1, 6) },
        {
          id: 'response-time',
          label: '平均响应时间',
          value: `${random(3, 9)}.${random(1, 9)} min`,
          trend: random(3, 12),
        },
      ],
      metricHistories: createMetricHistories(),
      attackTrend: createTrend(),
      attackTypes: createDistribution(),
      topSourceIps: createRanking(Array.from({ length: 6 }, createIp)),
      topTargetHosts: createRanking(hosts),
      protocolDistribution: createProtocolDistribution(),
      responseActions: createRanking(['自动封禁', '人工研判', '主机隔离', 'WAF 下发', '情报同步']),
      sourceMap: {
        china: createThreatMapData('china', '中国攻击态势', '境内重点区域实时攻击链路', chinaPointTemplates),
        world: createThreatMapData('world', '全球攻击态势', '境外攻击源向安全中枢汇聚', worldPointTemplates),
      },
    },
    alerts,
  };
};

const ensureCache = () => {
  if (!cache) {
    generateDataset();
  }

  return cache as { dashboard: DashboardSnapshot; alerts: AlertRecord[] };
};

const simulateLatency = async <T>(payload: T) =>
  new Promise<T>((resolve) => {
    window.setTimeout(() => resolve(payload), 180);
  });

export const getDashboardSnapshot = async () => {
  requireLogin();
  return simulateLatency(ensureCache().dashboard);
};
export const getAlerts = async () => {
  requireLogin();
  return simulateLatency(ensureCache().alerts);
};
export const getAlertById = async (id: string) => {
  requireLogin();
  return simulateLatency(ensureCache().alerts.find((item) => item.id === id) ?? ensureCache().alerts[0]);
};
export const refreshMockData = () => {
  generateDataset();
};

// ===================== 多场景 Mock 数据 =====================

/**
 * 航母甲板 279/281 字段生成器（需求 3.5.1 字段族）。
 * 278 个输入特征程序化生成（禁止手写），+ Collision 标签 = 279；
 * paired 版额外插入 PlaneID1/PlaneID2 = 281。字段名严格按字段族命名。
 */
const buildCarrierFields = (withPlaneIds: boolean): Omit<DatasetField, 'nullable' | 'field_role'>[] => {
  /** 按步数生成等间隔时间步字段（如 Plane1_dir_angle_deg_1..49） */
  const stepFields = (
    name: string,
    count: number,
    description: string,
    sample: string
  ): Omit<DatasetField, 'nullable' | 'field_role'>[] =>
    Array.from({ length: count }, (_, index) => ({
      field_name: `${name}_${index + 1}`,
      field_type: 'float',
      description: `${description} ${index + 1}`,
      sample_value: sample,
    }));

  const fields: Omit<DatasetField, 'nullable' | 'field_role'>[] = [
    // 1/2 号机 49 步航向角
    ...stepFields('Plane1_dir_angle_deg', 49, '1 号机第 N 步航向角（度）', '135.2'),
    ...stepFields('Plane2_dir_angle_deg', 49, '2 号机第 N 步航向角（度）', '118.7'),
    // 单机航向角统计量（5+5）
    { field_name: 'Plane1_dir_mean_deg', field_type: 'float', description: '1 号机航向角均值（度）', sample_value: '126.8' },
    { field_name: 'Plane1_dir_std_deg', field_type: 'float', description: '1 号机航向角标准差（度）', sample_value: '12.4' },
    { field_name: 'Plane1_dir_max_deg', field_type: 'float', description: '1 号机航向角最大值（度）', sample_value: '158.0' },
    { field_name: 'Plane1_dir_min_deg', field_type: 'float', description: '1 号机航向角最小值（度）', sample_value: '101.0' },
    { field_name: 'Plane1_dir_range_deg', field_type: 'float', description: '1 号机航向角极差（度）', sample_value: '57.0' },
    { field_name: 'Plane2_dir_mean_deg', field_type: 'float', description: '2 号机航向角均值（度）', sample_value: '112.4' },
    { field_name: 'Plane2_dir_std_deg', field_type: 'float', description: '2 号机航向角标准差（度）', sample_value: '11.8' },
    { field_name: 'Plane2_dir_max_deg', field_type: 'float', description: '2 号机航向角最大值（度）', sample_value: '149.0' },
    { field_name: 'Plane2_dir_min_deg', field_type: 'float', description: '2 号机航向角最小值（度）', sample_value: '96.0' },
    { field_name: 'Plane2_dir_range_deg', field_type: 'float', description: '2 号机航向角极差（度）', sample_value: '53.0' },
    // 两机相对角度 49 步
    ...stepFields('relative_angle_deg', 49, '两机第 N 步相对角度（度）', '32.5'),
    // 相对角度统计量（4）
    { field_name: 'relative_angle_mean_deg', field_type: 'float', description: '相对角度均值（度）', sample_value: '24.1' },
    { field_name: 'relative_angle_std_deg', field_type: 'float', description: '相对角度标准差（度）', sample_value: '8.6' },
    { field_name: 'relative_angle_max_deg', field_type: 'float', description: '相对角度最大值（度）', sample_value: '46.0' },
    { field_name: 'relative_angle_min_deg', field_type: 'float', description: '相对角度最小值（度）', sample_value: '3.2' },
    // 两机间距 50 步
    ...stepFields('inter_distance', 50, '两机第 N 步间距', '185.4'),
    // 间距统计量（6）
    { field_name: 'inter_dist_mean', field_type: 'float', description: '两机间距均值', sample_value: '168.2' },
    { field_name: 'inter_dist_std', field_type: 'float', description: '两机间距标准差', sample_value: '42.7' },
    { field_name: 'inter_dist_min', field_type: 'float', description: '两机最小间距', sample_value: '12.5' },
    { field_name: 'inter_dist_max', field_type: 'float', description: '两机最大间距', sample_value: '246.0' },
    { field_name: 'inter_dist_range', field_type: 'float', description: '两机间距极差', sample_value: '233.5' },
    { field_name: 'inter_dist_median', field_type: 'float', description: '两机间距中位数', sample_value: '170.0' },
    // 起止间距与总体距离变化（4）
    { field_name: 'start_dist', field_type: 'float', description: '起始间距', sample_value: '240.0' },
    { field_name: 'end_dist', field_type: 'float', description: '结束间距', sample_value: '48.0' },
    { field_name: 'dist_change', field_type: 'float', description: '总体距离变化量', sample_value: '-192.0' },
    { field_name: 'dist_change_ratio', field_type: 'float', description: '总体距离变化率', sample_value: '-0.8' },
    // 逐时间步距离变化量 49 步
    ...stepFields('dist_change_step', 49, '第 N 步距离变化量', '-3.2'),
    // 距离变化统计量（4）
    { field_name: 'dist_change_mean_step', field_type: 'float', description: '逐时间步距离变化均值', sample_value: '-3.9' },
    { field_name: 'dist_change_std_step', field_type: 'float', description: '逐时间步距离变化标准差', sample_value: '6.4' },
    { field_name: 'dist_change_max_step', field_type: 'float', description: '逐时间步距离变化最大值', sample_value: '4.1' },
    { field_name: 'dist_change_min_step', field_type: 'float', description: '逐时间步距离变化最小值', sample_value: '-12.6' },
    // 单机总航程及差值、比值（4）
    { field_name: 'Plane1_total_distance', field_type: 'float', description: '1 号机总航程', sample_value: '2820.5' },
    { field_name: 'Plane2_total_distance', field_type: 'float', description: '2 号机总航程', sample_value: '2695.2' },
    { field_name: 'total_dist_diff', field_type: 'float', description: '两机总航程差值', sample_value: '125.3' },
    { field_name: 'total_dist_ratio', field_type: 'float', description: '两机总航程比值', sample_value: '1.0465' },
  ];

  if (withPlaneIds) {
    fields.push(
      { field_name: 'PlaneID1', field_type: 'string', description: '1 号机标识', sample_value: 'A01' },
      { field_name: 'PlaneID2', field_type: 'string', description: '2 号机标识', sample_value: 'B02' },
    );
  }
  fields.push({ field_name: 'Collision', field_type: 'string', description: '分类标签：0=未碰撞，1=发生碰撞', sample_value: '0' });

  // 断言字段数量：278 输入 + Collision = 279；paired 版 + PlaneID1/2 = 281
  const expected = withPlaneIds ? 281 : 279;
  if (fields.length !== expected) {
    throw new Error(`航母甲板字段生成数量异常：${fields.length}（期望 ${expected}）`);
  }
  return fields;
};

/** 四场景元信息定义 — 数据集字段结构严格匹配需求第3节 ARFF 文件定义 */
const SCENARIO_META: Array<{
  id: ScenarioId;
  name: string;
  description: string;
  risk_level: Scenario['risk_level'];
  datasets: { name: string; desc: string; format: Dataset['data_format']; fields: Omit<DatasetField, 'nullable' | 'field_role'>[] }[];
  risk_types: string[];
}> = [
  {
    id: 'network_security',
    name: '网络安全态势感知',
    description: '识别网络流量中的各类攻击行为，第一阶段仅进行二分类（normal/anomaly）',
    risk_level: 'high',
    datasets: [
      {
        name: 'KDDTrain+ 20 Percent',
        desc: '经典网络入侵检测数据集 KDDTrain+_20Percent0503，ARFF 格式，41 维特征',
        format: 'arff',
        fields: [
          { field_name: 'duration', field_type: 'float', description: '连接持续时间（秒）', sample_value: '0.0' },
          { field_name: 'protocol_type', field_type: 'string', description: '传输层或网络层协议类型（tcp/udp/icmp）', sample_value: 'tcp' },
          { field_name: 'service', field_type: 'string', description: '目标端口对应的网络服务类型', sample_value: 'http' },
          { field_name: 'flag', field_type: 'string', description: '连接状态标志', sample_value: 'SF' },
          { field_name: 'src_bytes', field_type: 'int', description: '从源端到目标端传输的字节数', sample_value: '486' },
          { field_name: 'dst_bytes', field_type: 'int', description: '从目标端到源端传输的字节数', sample_value: '0' },
          { field_name: 'land', field_type: 'int', description: '源地址与目标地址、端口是否相同（1=相同）', sample_value: '0' },
          { field_name: 'wrong_fragment', field_type: 'int', description: '错误分片数量', sample_value: '0' },
          { field_name: 'urgent', field_type: 'int', description: '紧急数据包数量', sample_value: '0' },
          { field_name: 'hot', field_type: 'int', description: '敏感或高风险操作特征数量', sample_value: '0' },
          { field_name: 'num_failed_logins', field_type: 'int', description: '登录失败次数', sample_value: '0' },
          { field_name: 'logged_in', field_type: 'int', description: '是否成功登录（1=成功登录）', sample_value: '1' },
          { field_name: 'num_compromised', field_type: 'int', description: '检测到的系统受损或越权特征数量', sample_value: '0' },
          { field_name: 'root_shell', field_type: 'int', description: '是否获得root shell（1=是）', sample_value: '0' },
          { field_name: 'su_attempted', field_type: 'int', description: '是否尝试执行su提权操作', sample_value: '0' },
          { field_name: 'num_root', field_type: 'int', description: 'root权限相关操作数量', sample_value: '0' },
          { field_name: 'num_file_creations', field_type: 'int', description: '文件创建操作数量', sample_value: '0' },
          { field_name: 'num_shells', field_type: 'int', description: '启动shell的数量', sample_value: '0' },
          { field_name: 'num_access_files', field_type: 'int', description: '访问敏感文件的数量', sample_value: '0' },
          { field_name: 'is_host_login', field_type: 'int', description: '是否属于主机级登录（1=是）', sample_value: '0' },
          { field_name: 'is_guest_login', field_type: 'int', description: '是否使用访客账户登录（1=是）', sample_value: '0' },
          { field_name: 'count', field_type: 'int', description: '统计窗口内连接到同一目标主机的连接数量', sample_value: '1' },
          { field_name: 'srv_count', field_type: 'int', description: '统计窗口内访问同一服务的连接数量', sample_value: '1' },
          { field_name: 'serror_rate', field_type: 'float', description: '同一目标连接中SYN错误连接的比例', sample_value: '0.0' },
          { field_name: 'srv_serror_rate', field_type: 'float', description: '同一服务连接中SYN错误连接的比例', sample_value: '0.0' },
          { field_name: 'rerror_rate', field_type: 'float', description: '同一目标连接中REJ错误连接的比例', sample_value: '0.0' },
          { field_name: 'srv_rerror_rate', field_type: 'float', description: '同一服务连接中REJ错误连接的比例', sample_value: '0.0' },
          { field_name: 'same_srv_rate', field_type: 'float', description: '同一目标连接中使用相同服务的比例', sample_value: '1.0' },
          { field_name: 'diff_srv_rate', field_type: 'float', description: '同一目标连接中使用不同服务的比例', sample_value: '0.0' },
          { field_name: 'srv_diff_host_rate', field_type: 'float', description: '同一服务连接中访问不同目标主机的比例', sample_value: '0.0' },
          { field_name: 'dst_host_count', field_type: 'int', description: '目标主机统计窗口内的连接数量', sample_value: '1' },
          { field_name: 'dst_host_srv_count', field_type: 'int', description: '目标主机统计窗口内使用同一服务的连接数量', sample_value: '1' },
          { field_name: 'dst_host_same_srv_rate', field_type: 'float', description: '目标主机连接中使用相同服务的比例', sample_value: '1.0' },
          { field_name: 'dst_host_diff_srv_rate', field_type: 'float', description: '目标主机连接中使用不同服务的比例', sample_value: '0.0' },
          { field_name: 'dst_host_same_src_port_rate', field_type: 'float', description: '目标主机连接中使用相同源端口的比例', sample_value: '0.0' },
          { field_name: 'dst_host_srv_diff_host_rate', field_type: 'float', description: '目标主机同一服务连接中访问不同主机的比例', sample_value: '0.0' },
          { field_name: 'dst_host_serror_rate', field_type: 'float', description: '目标主机连接中SYN错误连接的比例', sample_value: '0.0' },
          { field_name: 'dst_host_srv_serror_rate', field_type: 'float', description: '目标主机同一服务连接中SYN错误连接的比例', sample_value: '0.0' },
          { field_name: 'dst_host_rerror_rate', field_type: 'float', description: '目标主机连接中REJ错误连接的比例', sample_value: '0.0' },
          { field_name: 'dst_host_srv_rerror_rate', field_type: 'float', description: '目标主机同一服务连接中REJ错误连接的比例', sample_value: '0.0' },
          { field_name: 'class', field_type: 'string', description: '二分类标签：normal=正常，anomaly=异常或攻击', sample_value: 'normal' },
        ],
      },
      {
        name: 'NF-UNSW-NB15-v2',
        desc: '现代网络攻击数据集 NF-UNSW-NB15-v20503，ARFF 格式，41 维特征',
        format: 'arff',
        fields: [
          { field_name: 'L4_SRC_PORT', field_type: 'int', description: '四层源端口', sample_value: '7636' },
          { field_name: 'L4_DST_PORT', field_type: 'int', description: '四层目标端口', sample_value: '6452' },
          { field_name: 'PROTOCOL', field_type: 'int', description: 'IP协议编号', sample_value: '6' },
          { field_name: 'L7_PROTO', field_type: 'int', description: '应用层协议编号', sample_value: '0' },
          { field_name: 'IN_BYTES', field_type: 'int', description: '流入方向字节数', sample_value: '1240' },
          { field_name: 'IN_PKTS', field_type: 'int', description: '流入方向数据包数', sample_value: '8' },
          { field_name: 'OUT_BYTES', field_type: 'int', description: '流出方向字节数', sample_value: '900' },
          { field_name: 'OUT_PKTS', field_type: 'int', description: '流出方向数据包数', sample_value: '6' },
          { field_name: 'TCP_FLAGS', field_type: 'int', description: '连接级TCP标志位汇总值', sample_value: '27' },
          { field_name: 'CLIENT_TCP_FLAGS', field_type: 'int', description: '客户端方向TCP标志位汇总值', sample_value: '19' },
          { field_name: 'SERVER_TCP_FLAGS', field_type: 'int', description: '服务器方向TCP标志位汇总值', sample_value: '8' },
          { field_name: 'FLOW_DURATION_MILLISECONDS', field_type: 'int', description: '流持续时间（毫秒）', sample_value: '124000' },
          { field_name: 'DURATION_IN', field_type: 'int', description: '流入方向持续时间', sample_value: '62000' },
          { field_name: 'DURATION_OUT', field_type: 'int', description: '流出方向持续时间', sample_value: '58000' },
          { field_name: 'MIN_TTL', field_type: 'int', description: '观测到的最小TTL', sample_value: '64' },
          { field_name: 'MAX_TTL', field_type: 'int', description: '观测到的最大TTL', sample_value: '128' },
          { field_name: 'LONGEST_FLOW_PKT', field_type: 'int', description: '流中最长数据包长度', sample_value: '1500' },
          { field_name: 'SHORTEST_FLOW_PKT', field_type: 'int', description: '流中最短数据包长度', sample_value: '40' },
          { field_name: 'MIN_IP_PKT_LEN', field_type: 'int', description: '最小IP数据包长度', sample_value: '40' },
          { field_name: 'MAX_IP_PKT_LEN', field_type: 'int', description: '最大IP数据包长度', sample_value: '1500' },
          { field_name: 'SRC_TO_DST_SECOND_BYTES', field_type: 'float', description: '源到目标方向的每秒字节量', sample_value: '1024.5' },
          { field_name: 'DST_TO_SRC_SECOND_BYTES', field_type: 'float', description: '目标到源方向的每秒字节量', sample_value: '512.3' },
          { field_name: 'RETRANSMITTED_IN_BYTES', field_type: 'int', description: '流入方向重传字节数', sample_value: '0' },
          { field_name: 'RETRANSMITTED_IN_PKTS', field_type: 'int', description: '流入方向重传数据包数', sample_value: '0' },
          { field_name: 'RETRANSMITTED_OUT_BYTES', field_type: 'int', description: '流出方向重传字节数', sample_value: '0' },
          { field_name: 'RETRANSMITTED_OUT_PKTS', field_type: 'int', description: '流出方向重传数据包数', sample_value: '0' },
          { field_name: 'SRC_TO_DST_AVG_THROUGHPUT', field_type: 'float', description: '源到目标方向平均吞吐量', sample_value: '12500.0' },
          { field_name: 'DST_TO_SRC_AVG_THROUGHPUT', field_type: 'float', description: '目标到源方向平均吞吐量', sample_value: '8500.0' },
          { field_name: 'NUM_PKTS_UP_TO_128_BYTES', field_type: 'int', description: '长度不超过128字节的数据包数', sample_value: '2' },
          { field_name: 'NUM_PKTS_128_TO_256_BYTES', field_type: 'int', description: '长度在128至256字节的数据包数', sample_value: '3' },
          { field_name: 'NUM_PKTS_256_TO_512_BYTES', field_type: 'int', description: '长度在256至512字节的数据包数', sample_value: '4' },
          { field_name: 'NUM_PKTS_512_TO_1024_BYTES', field_type: 'int', description: '长度在512至1024字节的数据包数', sample_value: '3' },
          { field_name: 'NUM_PKTS_1024_TO_1514_BYTES', field_type: 'int', description: '长度在1024至1514字节的数据包数', sample_value: '2' },
          { field_name: 'TCP_WIN_MAX_IN', field_type: 'int', description: '流入方向最大TCP窗口值', sample_value: '65535' },
          { field_name: 'TCP_WIN_MAX_OUT', field_type: 'int', description: '流出方向最大TCP窗口值', sample_value: '65535' },
          { field_name: 'ICMP_TYPE', field_type: 'int', description: 'ICMP类型编码', sample_value: '0' },
          { field_name: 'ICMP_IPV4_TYPE', field_type: 'int', description: 'IPv4 ICMP类型编码', sample_value: '0' },
          { field_name: 'DNS_QUERY_TYPE', field_type: 'int', description: 'DNS查询类型编码', sample_value: '1' },
          { field_name: 'DNS_TTL_ANSWER', field_type: 'int', description: 'DNS应答记录TTL', sample_value: '300' },
          { field_name: 'FTP_COMMAND_RET_CODE', field_type: 'int', description: 'FTP命令返回码', sample_value: '0' },
          { field_name: 'Label', field_type: 'int', description: '二分类标签：0=正常流量，1=攻击流量', sample_value: '0' },
        ],
      },
    ],
    risk_types: ['NETWORK_SECURITY_RISK'],
  },
  {
    id: 'power_system',
    name: '电力系统风险态势感知',
    description: '识别电力设备异常与风险事件，保障电网安全稳定运行，第一阶段仅进行二分类',
    risk_level: 'medium',
    datasets: [
      {
        name: 'PowerGrid Knowledgebase',
        desc: '电力设备与监测系统知识库 powergrid_knowledgebase_dataset0503，ARFF 格式，9 维特征',
        format: 'arff',
        fields: [
          { field_name: 'Component', field_type: 'string', description: '发生监测数据的电力设备或组件', sample_value: 'Feeder' },
          { field_name: 'SystemName', field_type: 'string', description: '数据所属的电力业务或监测系统', sample_value: 'Topology Mapping Unit' },
          { field_name: 'VoltageLevel_kV', field_type: 'float', description: '电压等级（kV）', sample_value: '757.97' },
          { field_name: 'CurrentAmp', field_type: 'float', description: '电流值（A）', sample_value: '185.2' },
          { field_name: 'Temperature_C', field_type: 'float', description: '温度（℃）', sample_value: '32.4' },
          { field_name: 'Sensor_Packet_Loss_%', field_type: 'float', description: '传感器数据包丢失率（%）', sample_value: '0.05' },
          { field_name: 'PowerFrequencyHz', field_type: 'float', description: '电网频率（Hz）', sample_value: '50.02' },
          { field_name: 'IssueType', field_type: 'string', description: '观测到的问题类型（输入特征兼事件解释字段）', sample_value: 'Voltage Sag' },
          { field_name: 'Target_Event', field_type: 'int', description: '二分类标签：0=未形成目标风险事件，1=形成目标风险事件', sample_value: '1' },
        ],
      },
    ],
    risk_types: ['POWER_SYSTEM_RISK'],
  },
  {
    id: 'flightdeck_operation',
    name: '航母甲板保障作业态势感知',
    description: '识别舰载机双机协同作业轨迹中的碰撞风险，第一阶段进行二分类（Collision 0/1）',
    risk_level: 'high',
    datasets: [
      {
        name: 'Carrier Feature2 Biaoqian',
        desc: '航母双机作业轨迹清洗标记版 Feature2_Cleaning_biaoqian，ARFF 格式，279 维特征',
        format: 'arff',
        fields: buildCarrierFields(false),
      },
      {
        name: 'Carrier Feature2 Lisan',
        desc: '航母双机作业轨迹清洗离散化版 Feature2_Cleaning_lisan，ARFF 格式，279 维特征',
        format: 'arff',
        fields: buildCarrierFields(false),
      },
      {
        name: 'Carrier Paired Trail Biaoqian',
        desc: '航母双机作业轨迹 paired_TrailData_feature2_biaoqian，ARFF 格式，281 维特征（含 PlaneID1/PlaneID2）',
        format: 'arff',
        fields: buildCarrierFields(true),
      },
    ],
    risk_types: ['FLIGHT_DECK_OPERATION_RISK'],
  },
  {
    id: 'geological_risk',
    name: '地质风险态势感知',
    description: '识别区域滑坡风险，统一以"是否形成滑坡风险"为业务目标，风险样本为正类',
    risk_level: 'high',
    datasets: [
      {
        name: 'DIS_raw_data',
        desc: '滑坡风险基础数据集 DIS_raw_data，ARFF 格式，19 维特征，5000 样本',
        format: 'arff',
        fields: [
          { field_name: 'Lithology', field_type: 'string', description: '岩性类型（编码）', sample_value: '1' },
          { field_name: 'Landuse', field_type: 'string', description: '土地利用类型（编码）', sample_value: '2' },
          { field_name: 'Aspect', field_type: 'float', description: '坡向（度）', sample_value: '215.0' },
          { field_name: 'Slope', field_type: 'float', description: '坡度（度）', sample_value: '28.5' },
          { field_name: 'EVI', field_type: 'float', description: '增强型植被指数', sample_value: '0.42' },
          { field_name: 'Elevation', field_type: 'float', description: '高程（m）', sample_value: '1250.0' },
          { field_name: 'Roughness', field_type: 'float', description: '地表粗糙度', sample_value: '1.8' },
          { field_name: 'Slope_roughness', field_type: 'float', description: '坡度粗糙度', sample_value: '0.35' },
          { field_name: 'G_curvature', field_type: 'float', description: '总曲率', sample_value: '0.02' },
          { field_name: 'Pla_curvature', field_type: 'float', description: '平面曲率', sample_value: '0.01' },
          { field_name: 'Pro_curvature', field_type: 'float', description: '剖面曲率', sample_value: '0.015' },
          { field_name: 'Relief', field_type: 'float', description: '地形起伏度', sample_value: '85.0' },
          { field_name: 'LS', field_type: 'float', description: '坡度长度因子', sample_value: '3.2' },
          { field_name: 'SPI', field_type: 'float', description: '水流功率指数', sample_value: '4.5' },
          { field_name: 'TWI', field_type: 'float', description: '地形湿度指数', sample_value: '6.8' },
          { field_name: 'Dis2roads', field_type: 'float', description: '距道路距离', sample_value: '120.0' },
          { field_name: 'Dis2fault', field_type: 'float', description: '距断层距离', sample_value: '350.0' },
          { field_name: 'Dis2river', field_type: 'float', description: '距河流距离', sample_value: '80.0' },
          { field_name: 'Label', field_type: 'string', description: '分类标签：0=无滑坡风险，1=有滑坡风险', sample_value: '0' },
        ],
      },
      {
        name: 'DIS_Landslides',
        desc: '滑坡发生记录数据集 DIS_Landslides，ARFF 格式，9 维特征，5185 样本',
        format: 'arff',
        fields: [
          { field_name: 'dist_roads', field_type: 'float', description: '距道路距离', sample_value: '150.0' },
          { field_name: 'DEM', field_type: 'float', description: '数字高程模型（高程）', sample_value: '980.0' },
          { field_name: 'TWI', field_type: 'float', description: '地形湿度指数', sample_value: '7.1' },
          { field_name: 'plan_curvature', field_type: 'float', description: '平面曲率', sample_value: '0.008' },
          { field_name: 'profil_curvature', field_type: 'float', description: '剖面曲率', sample_value: '0.012' },
          { field_name: 'Slope', field_type: 'float', description: '坡度（度）', sample_value: '32.0' },
          { field_name: 'Geology', field_type: 'string', description: '地质岩组类型（编码）', sample_value: '2' },
          { field_name: 'LandCover', field_type: 'string', description: '土地覆盖类型（编码）', sample_value: '3' },
          { field_name: 'LS', field_type: 'string', description: '分类标签：0=未发生滑坡，1=发生滑坡', sample_value: '0' },
        ],
      },
      {
        name: 'DIS_Landslide_Causative_Factors',
        desc: '滑坡致灾因子数据集 DIS_Landslide_Causative_Factors，ARFF 格式，13 维特征，5000 样本（类别高度不平衡）',
        format: 'arff',
        fields: [
          { field_name: 'Aspect', field_type: 'string', description: '坡向（编码 1-8）', sample_value: '3' },
          { field_name: 'DF', field_type: 'float', description: '距断层密度', sample_value: '0.45' },
          { field_name: 'DR', field_type: 'float', description: '距道路密度', sample_value: '0.32' },
          { field_name: 'DW', field_type: 'float', description: '距水系密度', sample_value: '0.28' },
          { field_name: 'LULC', field_type: 'string', description: '土地利用与覆盖（编码）', sample_value: '4' },
          { field_name: 'Lithology', field_type: 'string', description: '岩性类型（编码）', sample_value: '2' },
          { field_name: 'NDVI', field_type: 'float', description: '归一化植被指数', sample_value: '0.38' },
          { field_name: 'PC', field_type: 'float', description: '剖面曲率', sample_value: '0.01' },
          { field_name: 'Precip', field_type: 'float', description: '降水量', sample_value: '1450.0' },
          { field_name: 'TPI', field_type: 'float', description: '地形位置指数', sample_value: '0.6' },
          { field_name: 'TWI', field_type: 'float', description: '地形湿度指数', sample_value: '6.5' },
          { field_name: 'Temp', field_type: 'float', description: '温度', sample_value: '18.4' },
          { field_name: 'landslides', field_type: 'string', description: '分类标签：观测到的滑坡数量（0 表示无滑坡，>0 表示有滑坡）', sample_value: '0' },
        ],
      },
      {
        name: 'DIS_Global_Landslide_Catalog_Export',
        desc: '全球滑坡编目数据集 DIS_Global_Landslide_Catalog_Export，ARFF 格式，12 维特征，1000 样本（编目数据，不参与二分类训练）',
        format: 'arff',
        fields: [
          { field_name: 'location_accuracy', field_type: 'string', description: '位置精度（如 exact、5km）', sample_value: 'exact' },
          { field_name: 'landslide_category', field_type: 'string', description: '滑坡类别（如 landslide、mudslide）', sample_value: 'landslide' },
          { field_name: 'landslide_trigger', field_type: 'string', description: '触发因素（如 rain、earthquake）', sample_value: 'rain' },
          { field_name: 'landslide_setting', field_type: 'string', description: '滑坡环境（如 urban、natural_slope）', sample_value: 'natural_slope' },
          { field_name: 'fatality_count', field_type: 'float', description: '死亡人数（区间）', sample_value: '0' },
          { field_name: 'injury_count', field_type: 'float', description: '受伤人数（区间）', sample_value: '2' },
          { field_name: 'country_name', field_type: 'string', description: '国家名称', sample_value: 'China' },
          { field_name: 'admin_division_population', field_type: 'float', description: '行政区人口（区间）', sample_value: '500000' },
          { field_name: 'gazeteer_distance', field_type: 'float', description: '距最近地名距离', sample_value: '1200.0' },
          { field_name: 'longitude', field_type: 'float', description: '经度', sample_value: '103.8' },
          { field_name: 'latitude', field_type: 'float', description: '纬度', sample_value: '30.5' },
          { field_name: 'landslide_size', field_type: 'string', description: '分类标签：滑坡规模（small/medium/large/very_large/catastrophic/unknown）', sample_value: 'small' },
        ],
      },
      {
        name: 'DIS_guaruja_random',
        desc: 'Guaruja 随机采样数据集 DIS_guaruja_random，ARFF 格式，8 维特征，200 样本',
        format: 'arff',
        fields: [
          { field_name: 'twi', field_type: 'float', description: '地形湿度指数', sample_value: '6.2' },
          { field_name: 'curvature', field_type: 'float', description: '曲率', sample_value: '0.015' },
          { field_name: 'slope', field_type: 'float', description: '坡度（度）', sample_value: '25.0' },
          { field_name: 'elevation', field_type: 'float', description: '高程', sample_value: '420.0' },
          { field_name: 'aspect', field_type: 'float', description: '坡向', sample_value: '180.0' },
          { field_name: 'lithology', field_type: 'string', description: '岩性类型（编码）', sample_value: '2' },
          { field_name: 'land_use', field_type: 'string', description: '土地利用类型（编码）', sample_value: '3' },
          { field_name: 'class', field_type: 'string', description: '分类标签：0=未发生滑坡，1=发生滑坡', sample_value: '0' },
        ],
      },
    ],
    risk_types: ['GEOLOGICAL_RISK'],
  },
];

// ===================== v2.0 会话与用户（需求 6.2 / 6.5） =====================

/** 内部用户记录：密码仅 mock 内部使用，对外接口不返回 */
interface UserRecord {
  id: number;
  user_id: string;
  username: string;
  display_name: string;
  role: UserRole;
  status: 'active' | 'disabled';
  created_at: string;
  created_by: string;
  last_login_at?: string;
  scenario_ids?: ScenarioId[];
  password: string;
  /** 兼容旧 mock 数据的后端主键，不参与真实认证。 */
  backend_id: number;
  scenario_id: number | null;
  scenario_code: ScenarioId | null;
}

const SESSION_KEY = 'bayes_session_user_id';

/** 预置账号（三级角色）：SUPER_ADMIN（最外层）/ SCENARIO_ADMIN（场景管理员）/ SCENARIO_USER（场景用户）。
 * backend_id 与数据库 seed_test_data.py 注册的 AppUser 主键对齐。 */
let userRecords: UserRecord[] = [
  { id: 1, user_id: 'user_000001', backend_id: 1, username: 'admin', display_name: '系统管理员', role: 'SUPER_ADMIN', status: 'active', password: '123456', created_at: '2026-06-01 09:00:00', created_by: 'system', scenario_id: null, scenario_code: null },
  { id: 6, user_id: 'user_000050', backend_id: 6, username: 'net_admin', display_name: '网络安全公司管理员', role: 'SCENARIO_ADMIN', status: 'active', password: '123456', created_at: '2026-06-05 09:00:00', created_by: 'admin', scenario_ids: ['network_security'], scenario_id: 1, scenario_code: 'network_security' },
  { id: 2, user_id: 'user_000018', backend_id: 2, username: 'alice', display_name: '演示用户A', role: 'SCENARIO_USER', status: 'active', password: '123456', created_at: '2026-06-10 10:00:00', created_by: 'net_admin', scenario_ids: ['network_security'], scenario_id: 1, scenario_code: 'network_security' },
  { id: 3, user_id: 'user_000031', backend_id: 3, username: 'bob', display_name: '演示用户B', role: 'SCENARIO_USER', status: 'active', password: '123456', created_at: '2026-06-18 14:00:00', created_by: 'net_admin', scenario_ids: ['power_system'], scenario_id: 2, scenario_code: 'power_system' },
  { id: 7, user_id: 'user_000042', backend_id: 7, username: 'carol', display_name: '演示用户C', role: 'SCENARIO_USER', status: 'active', password: '123456', created_at: '2026-07-02 11:00:00', created_by: 'admin', scenario_ids: ['geological_risk'], scenario_id: 3, scenario_code: 'geological_risk' },
];

let sessionUser: UserAccount | null = null;

const nowStr = () => {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
};

const loadSession = (): UserAccount | null => {
  const id = window.localStorage.getItem(SESSION_KEY);
  // 兼容两种会话格式：旧的 user_000001（mock 编号）与新登录写入的后端整数 ID（1/2/3）
  const found = userRecords.find(
    (u) => u.user_id === id || String(u.backend_id) === id
  );
  return found ? { ...found } : null;
};

/** 恢复会话：从本地存储还原当前登录用户（未登录返回 null，由路由守卫强制跳登录页，需求 1.1.1） */
const ensureSession = () => {
  if (!sessionUser) sessionUser = loadSession();
  return sessionUser;
};

/** 获取当前登录用户（未登录时返回 null） */
export const getCurrentUser = (): UserAccount | null => ensureSession();

/** Bridge real cookie-auth session into transitional mockApi callers. */
export const syncSession = (user: UserAccount | null): void => {
  sessionUser = user ? { ...user } : null;
  if (user) {
    window.localStorage.setItem(SESSION_KEY, user.user_id || String(user.id));
  } else {
    window.localStorage.removeItem(SESSION_KEY);
  }
};


/** 获取当前登录用户，未登录抛错（业务接口统一调用） */
const requireLogin = (): UserAccount => {
  const user = ensureSession();
  if (!user) throw new Error('未登录，请先登录系统');
  return user;
};

/** 校验管理员权限 */
const requireAdmin = (): UserAccount => {
  const user = requireLogin();
  if (user.role !== 'SUPER_ADMIN') throw new Error('仅最外层管理员可执行此操作');
  return user;
};

/**
 * 场景访问校验（需求 1.1.6 / 6.5：普通用户仅可见绑定场景；管理员可见全部）。
 * 注意：真实权限校验必须由后端完成，mock 层过滤仅为前端联调基线（需求 6.5.x）。
 */
const canAccessScenario = (user: UserAccount, scenarioId: ScenarioId): boolean =>
  user.role === 'SUPER_ADMIN' || (user.scenario_ids ?? []).includes(scenarioId);

/** 场景访问断言：无权访问时抛错 */
const assertScenarioAccess = (user: UserAccount, scenarioId: ScenarioId): void => {
  if (!canAccessScenario(user, scenarioId)) throw new Error('无权访问该场景');
};

/** 登录 */
export const login = async (username: string, password: string): Promise<UserAccount> => {
  const found = userRecords.find((u) => u.username === username && u.password === password);
  if (!found) throw new Error('用户名或密码错误');
  if (found.status === 'disabled') throw new Error('该账号已被禁用，请联系管理员');
  found.last_login_at = nowStr();
  sessionUser = { ...found };
  // 存后端 AppUser 主键（整数），供 request.js 以 X-User-Id 调 /api/v1 数据库接口
  window.localStorage.setItem(SESSION_KEY, String(found.backend_id));
  return { ...found };
};

/** 退出登录 */
export const logout = async (): Promise<void> => {
  sessionUser = null;
  window.localStorage.removeItem(SESSION_KEY);
};

/** 修改本人密码（需求 6.2 普通用户账号管理） */
export const changeOwnPassword = async (oldPassword: string, newPassword: string): Promise<void> => {
  const user = requireLogin();
  const record = userRecords.find((u) => u.user_id === user.user_id)!;
  if (record.password !== oldPassword) throw new Error('原密码不正确');
  if (!newPassword || newPassword.length < 6) throw new Error('新密码长度至少为 6 位');
  record.password = newPassword;
};

/** 管理级角色校验：最外层管理员 或 场景管理员 */
const requireManagement = (): UserAccount => {
  const user = requireLogin();
  if (user.role !== 'SUPER_ADMIN' && user.role !== 'SCENARIO_ADMIN') {
    throw new Error('仅管理级角色可执行此操作');
  }
  return user;
};

/** 场景管理员能否管理该用户（只能管理自己场景的用户） */
const canManageUser = (operator: UserAccount, target: UserAccount): boolean => {
  if (operator.role === 'SUPER_ADMIN') return true;
  const bound = operator.scenario_ids?.[0];
  if (!bound) return false;
  return target.role !== 'SUPER_ADMIN' && (target.scenario_ids ?? []).includes(bound);
};

/** 用户列表（管理级角色）。
 * 系统管理员：只列管理员（SCENARIO_ADMIN）；管理员：只列自己场景的用户（SCENARIO_USER，不含自己）。 */
export const getUserList = async (): Promise<UserAccount[]> =>
  simulateLatency((() => {
    const operator = requireManagement();
    let list: UserRecord[];
    if (operator.role === 'SUPER_ADMIN') {
      list = [...userRecords];
    } else {
      const bound = operator.scenario_ids?.[0];
      if (!bound) return [];
      list = userRecords.filter(
        (u) => u.role !== 'SUPER_ADMIN' && (u.scenario_ids ?? []).includes(bound)
      );
    }
    return list.map(({ password: _pw, ...rest }) => rest);
  })());

/** Platform account statistics (SUPER_ADMIN only, for the operations overview). */
export const getPlatformUserStats = async (): Promise<PlatformUserStats> => {
  requireAdmin();
  const byScenario = SCENARIO_META.map((meta) => ({
    scenario_id: meta.id,
    name: meta.name,
    user_count: userRecords.filter((u) => (u.scenario_ids ?? []).includes(meta.id)).length,
  }));
  return simulateLatency({
    total: userRecords.length,
    super_admins: userRecords.filter((u) => u.role === 'SUPER_ADMIN').length,
    scenario_admins: userRecords.filter((u) => u.role === 'SCENARIO_ADMIN').length,
    scenario_users: userRecords.filter((u) => u.role === 'SCENARIO_USER').length,
    disabled: userRecords.filter((u) => u.status === 'disabled').length,
    by_scenario: byScenario,
  });
};

/** 管理级角色创建账号（系统管理员只建管理员；管理员只在自己场景建用户） */
export const createUser = async (params: {
  username: string;
  display_name: string;
  password: string;
  role: UserRole;
  /** 初始绑定场景（需求 1.1.6 用户-场景绑定；缺省/空数组表示无可见场景） */
  scenario_ids?: ScenarioId[];
}): Promise<UserAccount> => {
  const operator = requireManagement();
  if (params.role === 'SUPER_ADMIN') throw new Error('系统管理员账号由平台引导创建');
  if (operator.role === 'SUPER_ADMIN') {
    if (params.role !== 'SCENARIO_ADMIN' && params.role !== 'SCENARIO_USER') {
      throw new Error('系统管理员只能创建场景管理员或场景用户账号');
    }
  } else {
    if (params.role !== 'SCENARIO_USER') throw new Error('场景管理员只能创建场景用户账号');
    const bound = operator.scenario_ids?.[0];
    if (!bound || !(params.scenario_ids ?? []).includes(bound)) {
      throw new Error('场景管理员只能在自己场景内创建用户');
    }
  }
  if (params.role === 'SCENARIO_ADMIN' || params.role === 'SCENARIO_USER') {
    if (!params.scenario_ids?.length) throw new Error('场景管理员/场景用户必须绑定场景');
  }
  if (!params.username || !params.password) throw new Error('用户名和密码不能为空');
  if (params.password.length < 6) throw new Error('密码长度至少为 6 位');
  if (userRecords.some((u) => u.username === params.username)) throw new Error('该用户名已存在');
  const newId = `user_${String(userRecords.length + 1).padStart(6, '0')}`;
  const record: UserRecord = {
    id: 0,
    user_id: newId,
    // mock 新注册用户在后端数据库中不存在，backend_id=0 访问 /api/v1 时会被后端 401 拒绝
    backend_id: 0,
    username: params.username,
    display_name: params.display_name || params.username,
    role: params.role,
    status: 'active',
    password: params.password,
    created_at: nowStr(),
    created_by: operator.user_id,
    scenario_ids: params.scenario_ids ?? [],
    scenario_id: null,
    scenario_code: params.scenario_ids?.[0] ?? null,
  };
  userRecords.push(record);
  return { ...record };
};

/** 管理级角色重置用户密码（场景管理员仅自己场景） */
export const resetUserPassword = async (userId: string, newPassword: string): Promise<void> => {
  const operator = requireManagement();
  const record = userRecords.find((u) => u.user_id === userId);
  if (!record) throw new Error('用户不存在');
  if (!canManageUser(operator, record)) throw new Error('无权限管理该用户');
  if (!newPassword || newPassword.length < 6) throw new Error('新密码长度至少为 6 位');
  record.password = newPassword;
};

/** 管理级角色启用/禁用账号（不能禁用自己的账号；场景管理员仅自己场景） */
export const setUserStatus = async (userId: string, status: 'active' | 'disabled'): Promise<void> => {
  const operator = requireManagement();
  if (userId === operator.user_id) throw new Error('不能禁用当前登录的管理员账号');
  const record = userRecords.find((u) => u.user_id === userId);
  if (!record) throw new Error('用户不存在');
  if (!canManageUser(operator, record)) throw new Error('无权限管理该用户');
  record.status = status;
};

/**
 * 当前用户更新自己关注的场景（V3.0 需求：账号不被管理员分配场景，由用户自选）。
 * 同步更新 userRecords 与会话中的当前用户，供其它页面实时读取。
 */
export const updateMyScenarios = async (scenarioIds: ScenarioId[]): Promise<UserAccount> => {
  const user = requireLogin();
  if (user.role === 'SUPER_ADMIN') throw new Error('最外层管理员可见全部场景，无需设置');
  const record = userRecords.find((u) => u.user_id === user.user_id);
  if (!record) throw new Error('用户不存在');
  record.scenario_ids = [...scenarioIds];
  sessionUser = { ...record };
  return { ...record };
};

// ===================== v2.0 数据集版本（需求 2.3） =====================

/** 数据集编码（需求 2.2：三个数据集固定归属场景） */
const DATASET_DEF: Array<{
  dataset_id: string;
  name: string;
  desc: string;
  format: Dataset['data_format'];
  scenario_id: ScenarioId;
  record_count: number;   // 需求 2.1 当前样本数
}> = [
  { dataset_id: 'kdd_train_20_percent', name: 'KDDTrain+ 20 Percent', desc: '经典网络入侵检测数据集 KDDTrain+_20Percent0503，ARFF 格式，41 维特征', format: 'arff', scenario_id: 'network_security', record_count: 7556 },
  { dataset_id: 'nf_unsw_nb15_v2', name: 'NF-UNSW-NB15-v2', desc: '现代网络攻击数据集 NF-UNSW-NB15-v20503，ARFF 格式，41 维特征', format: 'arff', scenario_id: 'network_security', record_count: 23897 },
  { dataset_id: 'powergrid_knowledgebase', name: 'PowerGrid Knowledgebase', desc: '电力设备与监测系统知识库 powergrid_knowledgebase_dataset0503，ARFF 格式，9 维特征', format: 'arff', scenario_id: 'power_system', record_count: 2000 },
  { dataset_id: 'dis_raw_data', name: 'DIS_raw_data', desc: '滑坡风险基础数据集 DIS_raw_data，ARFF 格式，19 维特征', format: 'arff', scenario_id: 'geological_risk', record_count: 5000 },
  { dataset_id: 'dis_landslides', name: 'DIS_Landslides', desc: '滑坡发生记录数据集 DIS_Landslides，ARFF 格式，9 维特征', format: 'arff', scenario_id: 'geological_risk', record_count: 5185 },
  { dataset_id: 'dis_causative_factors', name: 'DIS_Landslide_Causative_Factors', desc: '滑坡致灾因子数据集 DIS_Landslide_Causative_Factors，ARFF 格式，13 维特征', format: 'arff', scenario_id: 'geological_risk', record_count: 5000 },
  { dataset_id: 'dis_global_catalog', name: 'DIS_Global_Landslide_Catalog_Export', desc: '全球滑坡编目数据集 DIS_Global_Landslide_Catalog_Export，ARFF 格式，12 维特征（编目数据，不参与二分类训练）', format: 'arff', scenario_id: 'geological_risk', record_count: 1000 },
  { dataset_id: 'dis_guaruja_random', name: 'DIS_guaruja_random', desc: 'Guaruja 随机采样数据集 DIS_guaruja_random，ARFF 格式，8 维特征', format: 'arff', scenario_id: 'geological_risk', record_count: 200 },
  { dataset_id: 'carrier_feature2_biaoqian', name: 'Carrier Feature2 Biaoqian', desc: '航母双机作业轨迹清洗标记版 Feature2_Cleaning_biaoqian，ARFF 格式，279 维特征', format: 'arff', scenario_id: 'flightdeck_operation', record_count: 507 },
  { dataset_id: 'carrier_feature2_lisan', name: 'Carrier Feature2 Lisan', desc: '航母双机作业轨迹清洗离散化版 Feature2_Cleaning_lisan，ARFF 格式，279 维特征', format: 'arff', scenario_id: 'flightdeck_operation', record_count: 507 },
  { dataset_id: 'carrier_paired_trail_biaoqian', name: 'Carrier Paired Trail Biaoqian', desc: '航母双机作业轨迹 paired_TrailData_feature2_biaoqian，ARFF 格式，281 维特征（含 PlaneID1/PlaneID2）', format: 'arff', scenario_id: 'flightdeck_operation', record_count: 507 },
];

let datasetVersions: DatasetVersion[] = [];

/** 枚举字段值域（需求 3.1.5 / 3.2.1 / 3.3.1 / 3.4.1） */
const ENUM_VALUES: Record<string, Record<string, string[]>> = {
  kdd_train_20_percent: {
    protocol_type: ['tcp', 'udp', 'icmp'],
    flag: ['OTH', 'REJ', 'RSTO', 'RSTOS0', 'RSTR', 'S0', 'S1', 'S2', 'S3', 'SF', 'SH'],
    service: [
      'aol', 'auth', 'bgp', 'courier', 'csnet_ns', 'ctf', 'daytime', 'discard', 'domain', 'domain_u',
      'echo', 'eco_i', 'ecr_i', 'efs', 'exec', 'finger', 'ftp', 'ftp_data', 'gopher', 'harvest',
      'hostnames', 'http', 'http_2784', 'http_443', 'http_8001', 'imap4', 'IRC', 'iso_tsap', 'klogin', 'kshell',
      'ldap', 'link', 'login', 'mtp', 'name', 'netbios_dgm', 'netbios_ns', 'netbios_ssn', 'netstat', 'nnsp',
      'nntp', 'ntp_u', 'other', 'pm_dump', 'pop_2', 'pop_3', 'printer', 'private', 'red_i', 'remote_job',
      'rje', 'shell', 'smtp', 'sql_net', 'ssh', 'sunrpc', 'supdup', 'systat', 'telnet', 'tftp_u',
      'tim_i', 'time', 'urh_i', 'urp_i', 'uucp', 'uucp_path', 'vmnet', 'whois', 'X11', 'Z39_50',
    ],
    land: ['0', '1'],
    logged_in: ['0', '1'],
    is_host_login: ['0', '1'],
    is_guest_login: ['0', '1'],
    class: ['normal', 'anomaly'],
  },
  nf_unsw_nb15_v2: {
    Label: ['0', '1'],
  },
  powergrid_knowledgebase: {
    Component: ['Circuit Breaker', 'Transformer', 'Feeder', 'SCADA Unit', 'PMU', 'Voltage Regulator', 'Protective Relay'],
    SystemName: ['Load Balancing System', 'Fault Detection System', 'Topology Mapping Unit', 'Power Quality Analyzer'],
    IssueType: ['Data Loss', 'Harmonic Distortion', 'Unexpected Trip', 'Current Spike', 'Voltage Sag', 'Frequency Drift'],
    Target_Event: ['0', '1'],
  },
  dis_raw_data: {
    Lithology: ['1', '2', '3', '4', '5'],
    Landuse: ['1', '2', '3', '4'],
    Label: ['0', '1'],
  },
  dis_landslides: {
    Geology: ['1', '2', '3'],
    LandCover: ['1', '2', '3', '4'],
    LS: ['0', '1'],
  },
  dis_causative_factors: {
    Aspect: ['1', '2', '3', '4', '5', '6', '7', '8'],
    LULC: ['1', '2', '3', '4', '5'],
    Lithology: ['1', '2', '3', '4', '5'],
    landslides: ['0', '1'],
  },
  dis_global_catalog: {
    location_accuracy: ['exact', '5km', '10km'],
    landslide_category: ['landslide', 'mudslide', 'debris_flow', 'rock_fall'],
    landslide_trigger: ['rain', 'earthquake', 'anthropogenic', 'snowmelt'],
    landslide_setting: ['urban', 'natural_slope', 'agricultural'],
    country_name: ['China', 'India', 'Nepal', 'Japan', 'USA'],
    landslide_size: ['small', 'medium', 'large', 'very_large', 'catastrophic', 'unknown'],
  },
  dis_guaruja_random: {
    lithology: ['1', '2', '3'],
    land_use: ['1', '2', '3', '4'],
    class: ['0', '1'],
  },
  carrier_feature2_biaoqian: {
    Collision: ['0', '1'],
  },
  carrier_feature2_lisan: {
    Collision: ['0', '1'],
  },
  carrier_paired_trail_biaoqian: {
    PlaneID1: ['A01', 'A02', 'B01'],
    PlaneID2: ['A01', 'A02', 'B01'],
    Collision: ['0', '1'],
  },
};

/** 依据需求第3节固定字段生成数据集版本 v1 */
const initDatasetVersions = (): DatasetVersion[] =>
  SCENARIO_META.flatMap((meta) =>
    meta.datasets.map((ds) => {
      const def = DATASET_DEF.find((d) => d.name === ds.name)!;
      const enumMap = ENUM_VALUES[def.dataset_id] ?? {};
      const fields = ds.fields.map((f, fi) => ({
        ...f,
        nullable: false,
        field_role: fi === ds.fields.length - 1 ? '分类标签' as const : '输入特征' as const,
        enum_values: enumMap[f.field_name],
      }));
      return {
        dataset_version_id: `${def.dataset_id}@v1`,
        dataset_id: def.dataset_id,
        dataset_version: 'v1',
        name: def.name,
        scenario_id: meta.id,
        data_format: def.format,
        file_path: `arff/${def.dataset_id}_0503.arff`,
        record_count: def.record_count,
        field_count: fields.length,
        fields,
        uploaded_by: 'admin',
        uploaded_at: '2026-06-05 09:30:00',
        enabled: true,
        referenced: true, // 初始模型已引用，故仅可停用
      };
    })
  );

/** 获取指定数据集的最新启用版本 */
const latestDatasetVersion = (datasetId: string): DatasetVersion | undefined =>
  [...datasetVersions]
    .filter((v) => v.dataset_id === datasetId)
    .sort((a, b) => (a.dataset_version < b.dataset_version ? 1 : -1))[0];

/** 数据集列表（需求 6.2 数据集列表与字段预览；普通用户只看与已发布模型有关且启用的数据集） */
export const getDatasetList = async (scenarioId?: ScenarioId): Promise<Dataset[]> => {
  const user = requireLogin();
  if (scenarioId) assertScenarioAccess(user, scenarioId);
  let list = datasetVersions.filter((v) => v.dataset_version === latestDatasetVersion(v.dataset_id)?.dataset_version);
  if (scenarioId) list = list.filter((v) => v.scenario_id === scenarioId);
  if (user.role === 'SCENARIO_USER') {
    list = list.filter((v) =>
      canAccessScenario(user, v.scenario_id) &&
      v.enabled &&
      modelVersions.some((m) => m.dataset_id === v.dataset_id && m.status === 'PUBLISHED')
    );
  }
  return simulateLatency(
    list.map((v) => ({
      dataset_id: v.dataset_id,
      name: v.name,
      description: v.fields.map((f) => f.field_name).slice(0, 3).join('、') + ' 等固定字段',
      scenario_id: v.scenario_id,
      record_count: v.record_count,
      field_count: v.field_count,
      fields: v.fields,
      created_at: v.uploaded_at,
      data_format: v.data_format,
      dataset_version: v.dataset_version,
      uploaded_by: v.uploaded_by,
      uploaded_at: v.uploaded_at,
      enabled: v.enabled,
      referenced: v.referenced,
    }))
  );
};

/** 获取数据集字段详情（当前启用版本的固定字段） */
export const getDatasetFields = async (datasetId: string, datasetVersion?: string): Promise<DatasetField[]> => {
  const user = requireLogin();
  const v = datasetVersion
    ? datasetVersions.find((item) => item.dataset_id === datasetId && item.dataset_version === datasetVersion)
    : latestDatasetVersion(datasetId);
  if (v) assertScenarioAccess(user, v.scenario_id);
  return simulateLatency(v?.fields ?? []);
};

/** 数据集预览行确定性种子（需求 2.4：跨分页稳定，禁止 Math.random） */
const previewSeedOf = (datasetId: string, index: number): number => {
  let h = 0;
  for (let i = 0; i < datasetId.length; i++) {
    h = (h * 31 + datasetId.charCodeAt(i)) % 2147483647;
  }
  return (h + index * 1103515245 + 12345) % 2147483647;
};

/** 预览标签列取值：按 mock 35% 风险率口径判风险类，优先取标签枚举值域 */
const previewLabelValue = (f: DatasetField, seed: number): string => {
  const isRisk = seed % 100 < 35;
  if (f.enum_values && f.enum_values.length > 0) {
    if (f.enum_values.length === 2) return f.enum_values[isRisk ? 1 : 0];
    return f.enum_values[seed % f.enum_values.length];
  }
  return isRisk ? '1' : '0';
};

/** 按数据集字段定义生成一行预览数据（需求 2.4：确定性生成，跨分页稳定） */
const buildPreviewRow = (v: DatasetVersion, index: number, labelField: string): DataRow => {
  const seed = previewSeedOf(v.dataset_id, index);
  const row: DataRow = {};
  for (const f of v.fields) {
    if (f.field_name === labelField) {
      row[f.field_name] = previewLabelValue(f, seed);
    } else if (f.enum_values && f.enum_values.length > 0) {
      row[f.field_name] = f.enum_values[seed % f.enum_values.length];
    } else if (f.field_type === 'int') {
      const base = Number(f.sample_value);
      row[f.field_name] = Number.isFinite(base) ? Math.max(0, base + (seed % 21) - 10) : seed % 100;
    } else if (f.field_type === 'float') {
      const base = Number(f.sample_value);
      const value = Number.isFinite(base) ? base + ((seed % 2001) - 1000) / 100 : (seed % 1000) / 100;
      row[f.field_name] = Number(value.toFixed(2));
    } else {
      row[f.field_name] = f.sample_value || `${f.field_name}_${index}`;
    }
  }
  return row;
};

/**
 * 数据集数据内容预览（需求 2.4：只读分页浏览；后端单次最大返回 100 条，前端每页最多 50）。
 * 访问控制：普通用户仅可预览"与已发布模型关联且启用"的数据集。
 * 注意：真实权限校验必须由后端完成，mock 层过滤仅为前端联调基线（需求 6.5.x）。
 */
export const getDatasetPreview = async (
  datasetId: string,
  params: { page: number; page_size: number }
): Promise<DataPreview> => {
  const user = requireLogin();
  const v = latestDatasetVersion(datasetId);
  if (!v) throw new Error('数据集不存在');
  assertScenarioAccess(user, v.scenario_id);
  if (
    user.role === 'SCENARIO_USER' &&
    !(v.enabled && modelVersions.some((m) => m.dataset_id === datasetId && m.status === 'PUBLISHED'))
  ) {
    throw new Error('无权访问该数据集');
  }
  const page = Math.max(1, params.page);
  const pageSize = Math.min(100, Math.max(1, params.page_size));
  const labelField = v.fields.find((f) => f.field_role === '分类标签')?.field_name ?? '';
  const rows: DataRow[] = [];
  const start = (page - 1) * pageSize;
  const end = Math.min(start + pageSize, v.record_count);
  for (let index = start; index < end; index++) {
    rows.push(buildPreviewRow(v, index, labelField));
  }
  return { total: v.record_count, page, page_size: pageSize, rows, label_field: labelField };
};

/** 获取数据集全部版本（管理员查看） */
export const getDatasetVersions = async (datasetId?: string): Promise<DatasetVersion[]> => {
  requireAdmin();
  const list = datasetId ? datasetVersions.filter((v) => v.dataset_id === datasetId) : [...datasetVersions];
  return simulateLatency(list);
};

/** 管理员上传数据集（创建 v1，需求 2.3.2：必须指定场景并完成字段校验） */
export const uploadDataset = async (params: {
  dataset_id: string;
  name: string;
  scenario_id: ScenarioId;
  data_format: Dataset['data_format'];
  record_count: number;
  fields: DatasetField[];
}): Promise<DatasetVersion> => {
  requireAdmin();
  if (datasetVersions.some((v) => v.dataset_id === params.dataset_id)) throw new Error('该数据集编码已存在');
  if (!params.fields.length) throw new Error('至少需要一个字段');
  if (params.fields.some((f) => !f.field_name.trim())) throw new Error('字段名不能为空');
  if (new Set(params.fields.map((f) => f.field_name)).size !== params.fields.length) throw new Error('字段名不能重复');
  if (params.fields.some((f) => !['int', 'float', 'string'].includes(f.field_type))) throw new Error('字段类型不合法');
  if (params.fields.filter((f) => f.field_role === '分类标签').length !== 1) throw new Error('必须且只能指定一个分类标签字段');
  const version: DatasetVersion = {
    dataset_version_id: `${params.dataset_id}@v1`,
    dataset_id: params.dataset_id,
    dataset_version: 'v1',
    name: params.name,
    scenario_id: params.scenario_id,
    data_format: params.data_format,
    file_path: `arff/${params.dataset_id}_0503.arff`,
    record_count: params.record_count,
    field_count: params.fields.length,
    fields: params.fields,
    uploaded_by: requireAdmin().user_id,
    uploaded_at: nowStr(),
    enabled: true,
    referenced: false,
  };
  datasetVersions.push(version);
  return version;
};

/** 管理员修改数据集 → 创建新版本并保留旧版本（需求 2.3.3） */
export const createDatasetVersion = async (datasetId: string, fields: DatasetField[]): Promise<DatasetVersion> => {
  const operator = requireAdmin();
  const old = latestDatasetVersion(datasetId);
  if (!old) throw new Error('数据集不存在');
  if (!fields.length || fields.some((f) => !f.field_name.trim())) throw new Error('字段结构不完整');
  if (new Set(fields.map((f) => f.field_name)).size !== fields.length) throw new Error('字段名不能重复');
  if (fields.filter((f) => f.field_role === '分类标签').length !== 1) throw new Error('必须且只能指定一个分类标签字段');
  const nextNum = Number(old.dataset_version.replace('v', '')) + 1;
  const version: DatasetVersion = {
    ...old,
    dataset_version_id: `${datasetId}@v${nextNum}`,
    dataset_version: `v${nextNum}`,
    fields,
    field_count: fields.length,
    uploaded_by: operator.user_id,
    uploaded_at: nowStr(),
    enabled: true,
    referenced: old.referenced,
  };
  datasetVersions.push(version);
  return version;
};

/** 停用数据集版本（需求 2.3.5：被模型引用只能停用不能删除） */
export const disableDatasetVersion = async (versionId: string): Promise<void> => {
  requireAdmin();
  const v = datasetVersions.find((item) => item.dataset_version_id === versionId);
  if (!v) throw new Error('数据集版本不存在');
  v.enabled = false;
};

/** 物理删除数据集版本（需求 2.3.6：未被任何模型引用可删除） */
export const deleteDatasetVersion = async (versionId: string): Promise<void> => {
  requireAdmin();
  const v = datasetVersions.find((item) => item.dataset_version_id === versionId);
  if (!v) throw new Error('数据集版本不存在');
  if (v.referenced) throw new Error('该数据集已被模型版本引用，只能停用，不能物理删除');
  datasetVersions = datasetVersions.filter((item) => item.dataset_version_id !== versionId);
};

// ===================== v2.0 算法注册（需求 6.6） =====================

const buildNumParam = (param_name: string, label: string, default_value: number, min: number, max: number, step: number, description: string): AlgorithmParamDef => ({
  param_name, label, type: 'number', default_value, min, max, step, description,
});

/** 五种算法注册（需求 6.6.1，开发人员代码接入，管理员不可增删改算法实现） */
let algorithmRegistry: AlgorithmDefinition[] = [
  {
    algorithm_id: 'A2WNB',
    display_name: '属性增广和加权朴素贝叶斯(A2WNB)',
    available: true,
    input_constraints: '适用于离散化数值特征与枚举特征的二分类数据集',
    description: 'Adaptive Attribute Weighted Naive Bayes，按属性权重指数自适应加权',
    params: [
      { param_name: 'discrete_method', label: '离散化方式', type: 'select', default_value: 'equal_width', options: [{ value: 'equal_width', label: '等宽分箱' }, { value: 'equal_freq', label: '等频分箱' }], description: '数值特征离散化策略' },
      buildNumParam('discrete_bins', '分箱数量', 10, 3, 20, 1, '数值特征离散化的分箱个数'),
      buildNumParam('smoothing', '拉普拉斯平滑', 1.0, 0, 2, 0.1, '条件概率平滑参数'),
      buildNumParam('weight_exponent', '属性权重指数', 1.0, 0.5, 3, 0.1, '属性加权时的权重指数'),
    ],
  },
  {
    algorithm_id: 'MAWNB',
    display_name: '多视图加权朴素贝叶斯(MAWNB)',
    available: true,
    input_constraints: '适用于离散化数值特征与枚举特征的二分类数据集',
    description: 'Model Averaging Weighted Naive Bayes，多个子模型加权平均',
    params: [
      { param_name: 'discrete_method', label: '离散化方式', type: 'select', default_value: 'equal_width', options: [{ value: 'equal_width', label: '等宽分箱' }, { value: 'equal_freq', label: '等频分箱' }], description: '数值特征离散化策略' },
      buildNumParam('discrete_bins', '分箱数量', 10, 3, 20, 1, '数值特征离散化的分箱个数'),
      buildNumParam('smoothing', '拉普拉斯平滑', 1.0, 0, 2, 0.1, '条件概率平滑参数'),
      buildNumParam('ensemble_size', '子模型数量', 5, 1, 10, 1, '集成子模型的数量'),
    ],
  },
  {
    algorithm_id: 'EMAWNB',
    display_name: '增强多视图朴素贝叶斯(EMAWNB)',
    available: true,
    input_constraints: '适用于离散化数值特征与枚举特征的二分类数据集',
    description: 'Exponential Moving Average Weighted Naive Bayes，利用滑动窗口估计加权概率',
    params: [
      { param_name: 'discrete_method', label: '离散化方式', type: 'select', default_value: 'equal_width', options: [{ value: 'equal_width', label: '等宽分箱' }, { value: 'equal_freq', label: '等频分箱' }], description: '数值特征离散化策略' },
      buildNumParam('discrete_bins', '分箱数量', 10, 3, 20, 1, '数值特征离散化的分箱个数'),
      buildNumParam('smoothing', '拉普拉斯平滑', 1.0, 0, 2, 0.1, '条件概率平滑参数'),
      buildNumParam('window_size', '移动窗口大小', 10, 2, 50, 1, '指数移动平均的观测窗口'),
    ],
  },
  {
    algorithm_id: 'CAVWNB',
    display_name: '类依赖属性值加权朴素贝叶斯(CAVWNB)',
    available: true,
    input_constraints: '适用于离散化数值特征与枚举特征的二分类数据集',
    description: 'Differential Weighted Naive Bayes，基于特征差分信号加权',
    params: [
      { param_name: 'discrete_method', label: '离散化方式', type: 'select', default_value: 'equal_width', options: [{ value: 'equal_width', label: '等宽分箱' }, { value: 'equal_freq', label: '等频分箱' }], description: '数值特征离散化策略' },
      buildNumParam('discrete_bins', '分箱数量', 10, 3, 20, 1, '数值特征离散化的分箱个数'),
      buildNumParam('smoothing', '拉普拉斯平滑', 1.0, 0, 2, 0.1, '条件概率平滑参数'),
      buildNumParam('differential_order', '差分阶数', 1, 1, 3, 1, '特征差分的阶数'),
    ],
  },
  {
    algorithm_id: 'PMWNB',
    display_name: '矩阵视图加权朴素贝叶斯(PMWNB)',
    available: true,
    input_constraints: '适用于离散化数值特征与枚举特征的二分类数据集',
    description: 'Probability Mean Weighted Naive Bayes，以概率均值作为加权依据',
    params: [
      { param_name: 'discrete_method', label: '离散化方式', type: 'select', default_value: 'equal_width', options: [{ value: 'equal_width', label: '等宽分箱' }, { value: 'equal_freq', label: '等频分箱' }], description: '数值特征离散化策略' },
      buildNumParam('discrete_bins', '分箱数量', 10, 3, 20, 1, '数值特征离散化的分箱个数'),
      buildNumParam('smoothing', '拉普拉斯平滑', 1.0, 0, 2, 0.1, '条件概率平滑参数'),
      buildNumParam('probability_threshold', '概率均值阈值', 0.5, 0, 1, 0.05, '概率均值决策阈值'),
    ],
  },
];

/** 获取已注册算法列表（需求 6.2 算法代码注册） */
export const getAlgorithms = async (): Promise<AlgorithmDefinition[]> => simulateLatency(algorithmRegistry);

// ===================== v2.0 风险阈值配置（需求 5.4.1） =====================

let thresholds: Record<ScenarioId, ThresholdConfig> = {
  network_security: { scenario_id: 'network_security', medium_threshold: 0.45, high_threshold: 0.75, updated_by: 'admin', updated_at: '2026-06-05 09:30:00' },
  power_system: { scenario_id: 'power_system', medium_threshold: 0.5, high_threshold: 0.8, updated_by: 'admin', updated_at: '2026-06-05 09:30:00' },
  flightdeck_operation: { scenario_id: 'flightdeck_operation', medium_threshold: 0.5, high_threshold: 0.8, updated_by: 'admin', updated_at: '2026-06-05 09:30:00' },
  geological_risk: { scenario_id: 'geological_risk', medium_threshold: 0.5, high_threshold: 0.8, updated_by: 'admin', updated_at: '2026-06-05 09:30:00' },
};
const userThresholds = new Map<string, Record<ScenarioId, ThresholdConfig>>();

let thresholdChangeLogs: ThresholdChangeLog[] = [];
let thresholdLogSeq = 1;

const thresholdConfigFor = (user: UserAccount, scenarioId: ScenarioId): ThresholdConfig => {
  let own = userThresholds.get(user.user_id);
  if (!own) {
    own = Object.fromEntries(
      Object.entries(thresholds).map(([key, value]) => [key, { ...value, user_id: user.id }]),
    ) as Record<ScenarioId, ThresholdConfig>;
    userThresholds.set(user.user_id, own);
  }
  return own[scenarioId];
};

/** 获取当前账号的全部场景阈值配置 */
export const getThresholds = async (): Promise<ThresholdConfig[]> => {
  const user = requireLogin();
  const ids = user.role === 'SUPER_ADMIN' ? Object.keys(thresholds) as ScenarioId[] : (user.scenario_ids ?? []);
  return simulateLatency(ids.map((id) => thresholdConfigFor(user, id)));
};

/** 获取阈值变更记录（需求 5.4.1.5） */
export const getThresholdChangeLogs = async (): Promise<ThresholdChangeLog[]> => {
  const user = requireLogin();
  return simulateLatency(
    thresholdChangeLogs
      .filter((log) => log.user_id === user.id || log.operator_id === user.user_id)
      .sort((a, b) => (b.operated_at ?? b.changed_at ?? '').localeCompare(a.operated_at ?? a.changed_at ?? '')),
  );
};

/** 当前账号按场景保存阈值：范围 [0,1]、high>medium、实时生效、记录变更日志 */
export const saveThreshold = async (scenarioId: ScenarioId, medium_threshold: number, high_threshold: number): Promise<ThresholdConfig> => {
  const operator = requireLogin();
  assertScenarioAccess(operator, scenarioId);
  if (medium_threshold < 0 || medium_threshold > 1 || high_threshold < 0 || high_threshold > 1) {
    throw new Error('阈值必须位于 [0,1] 范围内');
  }
  if (Math.round(medium_threshold * 100) / 100 !== medium_threshold || Math.round(high_threshold * 100) / 100 !== high_threshold) {
    throw new Error('阈值最多只能有两位小数');
  }
  if (high_threshold <= medium_threshold) throw new Error('高风险阈值必须大于中风险阈值');
  const old = thresholdConfigFor(operator, scenarioId);
  thresholdChangeLogs.push({
    id: thresholdLogSeq++,
    user_id: operator.id,
    scenario_id: scenarioId,
    operator_id: operator.user_id,
    operated_at: nowStr(),
    old_medium: old.medium_threshold,
    old_high: old.high_threshold,
    new_medium: medium_threshold,
    new_high: high_threshold,
  });
  const next = { ...old, user_id: operator.id, scenario_id: scenarioId, medium_threshold, high_threshold, updated_by: operator.id, updated_at: nowStr() };
  userThresholds.get(operator.user_id)![scenarioId] = next;
  return next;
};

/** 将真实后端保存结果同步到模拟推理链路。 */
export const syncThreshold = (config: ThresholdConfig): void => {
  const user = requireLogin();
  const own = userThresholds.get(user.user_id) ?? {} as Record<ScenarioId, ThresholdConfig>;
  own[config.scenario_id] = { ...config, user_id: user.id };
  userThresholds.set(user.user_id, own);
};

// ===================== v2.0 模型版本与生命周期（需求 6.7） =====================

let modelVersions: ModelVersionRecord[] = [];
let modelSeq = 1;

/** 基于统一混淆矩阵语义生成评估指标（需求 6.4.3） */
const makeMetrics = (): EvaluationMetrics => {
  const N = 1000;
  const tp = random(380, 540);
  const fn = random(30, 90);
  const fp = random(25, 80);
  const tn = N - tp - fn - fp;
  const accuracy = (tp + tn) / N;
  const recall = tp / (tp + fn);
  const precision = tp / (tp + fp);
  const specificity = tn / (tn + fp);
  const f1 = (2 * precision * recall) / (precision + recall);
  const gMean = Math.sqrt(recall * specificity);
  const round = (v: number) => Number(v.toFixed(4));
  return { accuracy: round(accuracy), recall: round(recall), precision: round(precision), specificity: round(specificity), f1: round(f1), g_mean: round(gMean) };
};

const makeModelVersion = (scenario_id: ScenarioId, dataset_id: string, algorithm_id: string, status: ModelStatus, is_default: boolean, trained_by = 'admin', trained_at?: string): ModelVersionRecord => {
  const v = latestDatasetVersion(dataset_id)!;
  const published = status === 'PUBLISHED';
  const t = trained_at ?? `2026-0${random(3, 6)}-${String(random(1, 28)).padStart(2, '0')} ${String(random(8, 18)).padStart(2, '0')}:00`;
  return {
    model_version_id: `mv_${dataset_id}_${String(modelSeq++).padStart(4, '0')}`,
    scenario_id,
    dataset_id,
    dataset_version: v.dataset_version,
    algorithm_id,
    training_parameters: { discrete_method: 'equal_width', discrete_bins: 10, smoothing: 1.0 },
    evaluation_metrics: makeMetrics(),
    train_time_s: Number((Math.random() * 8 + 2).toFixed(1)),
    trained_by,
    trained_at: t,
    status,
    published_by: published ? trained_by : undefined,
    published_at: published ? t : undefined,
    is_default,
  };
};

/** 初始化模型版本：每个数据集预置已发布/草稿/下线模型（满足 6.7.3/6.7.4 演示） */
const initModelVersions = (): ModelVersionRecord[] => {
  const list: ModelVersionRecord[] = [
    // KDD：1 个默认已发布 + 1 个草稿 + 1 个已下线
    makeModelVersion('network_security', 'kdd_train_20_percent', 'PMWNB', 'PUBLISHED', true),
    makeModelVersion('network_security', 'kdd_train_20_percent', 'MAWNB', 'DRAFT', false),
    makeModelVersion('network_security', 'kdd_train_20_percent', 'EMAWNB', 'OFFLINE', false),
    // NF-UNSW：2 个已发布（无默认，演示"需手动选择"）+ 1 个失败
    makeModelVersion('network_security', 'nf_unsw_nb15_v2', 'A2WNB', 'PUBLISHED', false),
    makeModelVersion('network_security', 'nf_unsw_nb15_v2', 'CAVWNB', 'PUBLISHED', false),
    makeModelVersion('network_security', 'nf_unsw_nb15_v2', 'PMWNB', 'FAILED', false),
    // PowerGrid：1 个默认已发布 + 1 个草稿
    makeModelVersion('power_system', 'powergrid_knowledgebase', 'MAWNB', 'PUBLISHED', true),
    makeModelVersion('power_system', 'powergrid_knowledgebase', 'A2WNB', 'DRAFT', false),
    // 地质风险：4 个可训练数据集各至少 1 个已发布；dis_raw_data 设默认（dis_global_catalog 为编目数据，不建模型）
    makeModelVersion('geological_risk', 'dis_raw_data', 'PMWNB', 'PUBLISHED', true),
    makeModelVersion('geological_risk', 'dis_raw_data', 'A2WNB', 'DRAFT', false),
    makeModelVersion('geological_risk', 'dis_landslides', 'MAWNB', 'PUBLISHED', false),
    makeModelVersion('geological_risk', 'dis_landslides', 'CAVWNB', 'DRAFT', false),
    makeModelVersion('geological_risk', 'dis_causative_factors', 'EMAWNB', 'PUBLISHED', false),
    makeModelVersion('geological_risk', 'dis_guaruja_random', 'A2WNB', 'PUBLISHED', false),
    // 航母甲板：3 个数据集各至少 1 个已发布
    makeModelVersion('flightdeck_operation', 'carrier_feature2_biaoqian', 'PMWNB', 'PUBLISHED', true),
    makeModelVersion('flightdeck_operation', 'carrier_feature2_lisan', 'EMAWNB', 'PUBLISHED', false),
    makeModelVersion('flightdeck_operation', 'carrier_paired_trail_biaoqian', 'A2WNB', 'PUBLISHED', false),
  ];
  return list;
};

const algoName = (id: string) => algorithmRegistry.find((a) => a.algorithm_id === id)?.display_name ?? id;

/** 获取模型版本列表（普通用户仅见 PUBLISHED，需求 6.7.5） */
export const getModelVersions = async (scenarioId?: ScenarioId, datasetId?: string): Promise<ModelVersionRecord[]> => {
  const user = requireLogin();
  if (scenarioId) assertScenarioAccess(user, scenarioId);
  let list = [...modelVersions];
  if (user.role === 'SCENARIO_USER') list = list.filter((m) => canAccessScenario(user, m.scenario_id) && m.status === 'PUBLISHED');
  if (scenarioId) list = list.filter((m) => m.scenario_id === scenarioId);
  if (datasetId) list = list.filter((m) => m.dataset_id === datasetId);
  return simulateLatency(list.sort((a, b) => b.trained_at.localeCompare(a.trained_at)));
};

/** 管理员发起训练（需求 6.3.1：选择场景/数据集版本/算法，配置参数，训练成功生成 DRAFT） */
export const trainModel = async (params: {
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;
  algorithm_id: string;
  training_parameters: Record<string, unknown>;
}): Promise<ModelVersionRecord & { train_time_s: number }> => {
  const operator = requireAdmin();
  const v = datasetVersions.find((item) =>
    item.dataset_id === params.dataset_id && item.dataset_version === params.dataset_version
  );
  if (!v) throw new Error('数据集不存在');
  if (v.scenario_id !== params.scenario_id) throw new Error('数据集与场景不匹配，禁止跨场景训练');
  if (!v.enabled) throw new Error('该数据集版本已停用，不能用于新训练');
  const algo = algorithmRegistry.find((a) => a.algorithm_id === params.algorithm_id);
  if (!algo || !algo.available) throw new Error('所选算法不可用');
  // 参数校验：类型与范围（需求 6.6.3）
  const merged: Record<string, unknown> = {};
  for (const p of algo.params) {
    const raw = params.training_parameters[p.param_name];
    const value = raw === undefined || raw === '' ? p.default_value : raw;
    if (p.type === 'number') {
      const num = Number(value);
      if (Number.isNaN(num)) throw new Error(`参数 ${p.label} 必须为数值`);
      if (p.min !== undefined && num < p.min) throw new Error(`参数 ${p.label} 不得小于 ${p.min}`);
      if (p.max !== undefined && num > p.max) throw new Error(`参数 ${p.label} 不得大于 ${p.max}`);
      merged[p.param_name] = num;
    } else if (p.type === 'select' && p.options && !p.options.some((o) => o.value === value)) {
      throw new Error(`参数 ${p.label} 取值不合法`);
    } else {
      merged[p.param_name] = value;
    }
  }
  const model: ModelVersionRecord = {
    model_version_id: `mv_${params.dataset_id}_${String(modelSeq++).padStart(4, '0')}`,
    scenario_id: params.scenario_id,
    dataset_id: params.dataset_id,
    dataset_version: v.dataset_version,
    algorithm_id: params.algorithm_id,
    training_parameters: merged,
    evaluation_metrics: makeMetrics(),
    train_time_s: Number((Math.random() * 8 + 2).toFixed(1)),
    trained_by: operator.user_id,
    trained_at: nowStr(),
    status: 'DRAFT', // 训练成功 → DRAFT（需求 6.7.2 TRAINING → DRAFT）
    is_default: false,
  };
  modelVersions.unshift(model);
  return simulateLatency(model);
};

/** 管理员发布模型（DRAFT → PUBLISHED，需求 6.7.2） */
export const publishModel = async (modelVersionId: string): Promise<void> => {
  const operator = requireAdmin();
  const m = modelVersions.find((item) => item.model_version_id === modelVersionId);
  if (!m) throw new Error('模型版本不存在');
  if (m.status !== 'DRAFT') throw new Error('仅 DRAFT 状态模型可发布');
  m.status = 'PUBLISHED';
  m.published_by = operator.user_id;
  m.published_at = nowStr();
};

/** 管理员下线模型（PUBLISHED → OFFLINE；默认模型下线时自动取消默认，需求 6.7.4.5） */
export const offlineModel = async (modelVersionId: string): Promise<void> => {
  requireAdmin();
  const m = modelVersions.find((item) => item.model_version_id === modelVersionId);
  if (!m) throw new Error('模型版本不存在');
  if (m.status !== 'PUBLISHED') throw new Error('仅已发布模型可下线');
  m.status = 'OFFLINE';
  if (m.is_default) m.is_default = false;
};

/** 管理员设置默认推荐模型（每个"场景＋数据集"最多一个，需求 6.7.4） */
export const setDefaultModel = async (modelVersionId: string): Promise<void> => {
  requireAdmin();
  const m = modelVersions.find((item) => item.model_version_id === modelVersionId);
  if (!m) throw new Error('模型版本不存在');
  if (m.status !== 'PUBLISHED') throw new Error('默认推荐模型必须为已发布状态');
  for (const item of modelVersions) {
    if (item.scenario_id === m.scenario_id && item.dataset_id === m.dataset_id) item.is_default = false;
  }
  m.is_default = true;
};

/** 重新发布已下线模型（需求 6.7.5.7 管理员可重新发布已下线模型） */
export const rePublishModel = async (modelVersionId: string): Promise<void> => {
  const operator = requireAdmin();
  const m = modelVersions.find((item) => item.model_version_id === modelVersionId);
  if (!m) throw new Error('模型版本不存在');
  if (m.status !== 'OFFLINE') throw new Error('仅 OFFLINE 模型可重新发布');
  m.status = 'PUBLISHED';
  m.published_by = operator.user_id;
  m.published_at = nowStr();
};

// ===================== v2.0 推理记录与风险事件闭环（需求 4 / 5 / 6.2） =====================

let inferenceRecords: InferenceRecord[] = [];
let riskEvents: RiskEvent[] = [];
let inferSeq = 1;
let eventSeq = 1;

// 报告持久化：存 localStorage，刷新不丢（支持定时报告的管理）
const REPORTS_KEY = 'bayes_reports';
let reports: Report[] = (() => {
  try {
    return JSON.parse(window.localStorage.getItem(REPORTS_KEY) || '[]') as Report[];
  } catch {
    return [];
  }
})();
const saveReports = () => {
  try {
    window.localStorage.setItem(REPORTS_KEY, JSON.stringify(reports));
  } catch {
    // 存储失败忽略
  }
};

/** 场景风险类型映射（需求 5.3） */
const riskTypeOf = (scenario_id: ScenarioId): string =>
  scenario_id === 'network_security'
    ? 'NETWORK_SECURITY_RISK'
    : scenario_id === 'power_system'
      ? 'POWER_SYSTEM_RISK'
      : scenario_id === 'geological_risk'
        ? 'GEOLOGICAL_RISK'
        : 'FLIGHT_DECK_OPERATION_RISK';

/** 按数据集生成原始标签（需求 3.2/3.3/3.4） */
const originalLabelOf = (dataset_id: string, isRisk: boolean): string => {
  if (dataset_id === 'kdd_train_20_percent') return isRisk ? 'anomaly' : 'normal';
  // 地质（Label/LS/landslides/class）与航母（Collision）均为 0/1 二分类标签；
  // dis_causative_factors 的 landslides 正类以 '1' 表示（>0，mock 简化）
  return isRisk ? '1' : '0';
};

/**
 * 依据数据集字段定义生成一条完整输入特征样本（枚举取合法值域、数值取样例值附近），
 * 供种子推理记录保存完整字段（需求 3.1：禁止缺列）。
 */
const buildSeedFeatures = (datasetId: string): Record<string, unknown> => {
  const v = latestDatasetVersion(datasetId)!;
  const features: Record<string, unknown> = {};
  for (const f of v.fields) {
    if (f.field_role !== '输入特征') continue;
    if (f.enum_values && f.enum_values.length > 0) {
      features[f.field_name] = sample(f.enum_values);
    } else if (f.field_type === 'float' || f.field_type === 'int') {
      const base = Number(f.sample_value);
      const jitter = Math.abs(base) < 10 ? random(-1, 1) : random(-5, 5);
      features[f.field_name] = Number((base + jitter).toFixed(3));
    } else {
      features[f.field_name] = f.sample_value;
    }
  }
  return features;
};

/**
 * 航母双机轨迹样本生成器（需求 3.5.1）：49 步方向角/相对角 + 50 步间距 + 派生统计量。
 * 与 buildCarrierFields 共用同一字段命名，保证 validateInputFeatures 可过、看板可聚合。
 */
const buildCarrierTrajectoryFeatures = (collision: boolean, withPlaneIds: boolean): Record<string, unknown> => {
  const features: Record<string, unknown> = {};
  const p1Dir: number[] = [];
  const p2Dir: number[] = [];
  const relAngles: number[] = [];
  const distances: number[] = [];
  const base1 = random(100, 160);
  const base2 = random(100, 160);
  const startDist = random(140, 260);
  const endDist = collision ? random(5, 20) : random(50, 100);
  let prev1 = base1;
  let prev2 = base2;
  let total1 = 0;
  let total2 = 0;
  for (let step = 1; step <= 49; step++) {
    const t = step / 49;
    const d1 = Number((base1 + Math.sin(t * Math.PI * 2) * 8 + random(-4, 4)).toFixed(2));
    const d2 = Number((base2 + Math.sin(t * Math.PI * 2 + 1.4) * 8 + random(-4, 4)).toFixed(2));
    p1Dir.push(d1);
    p2Dir.push(d2);
    relAngles.push(Number(Math.abs(d1 - d2).toFixed(2)));
    distances.push(Number((startDist - (startDist - endDist) * t + Math.sin(t * Math.PI * 3) * 2.5).toFixed(2)));
    total1 += 55 + Math.abs(d1 - prev1) * 0.8;
    total2 += 55 + Math.abs(d2 - prev2) * 0.8;
    prev1 = d1;
    prev2 = d2;
  }
  distances.push(Number(Math.max(2, endDist + random(-1, 1)).toFixed(2)));

  const avg = (arr: number[]) => arr.reduce((s, v) => s + v, 0) / arr.length;
  const std = (arr: number[]) => Math.sqrt(arr.reduce((s, v) => s + (v - avg(arr)) ** 2, 0) / arr.length);
  const minOf = (arr: number[]) => Math.min(...arr);
  const maxOf = (arr: number[]) => Math.max(...arr);
  const round = (v: number) => Number(v.toFixed(2));

  for (let i = 0; i < 49; i++) {
    features[`Plane1_dir_angle_deg_${i + 1}`] = p1Dir[i];
    features[`Plane2_dir_angle_deg_${i + 1}`] = p2Dir[i];
    features[`relative_angle_deg_${i + 1}`] = relAngles[i];
  }
  for (let i = 0; i < 50; i++) {
    features[`inter_distance_${i + 1}`] = distances[i];
  }
  features.Plane1_dir_mean_deg = round(avg(p1Dir));
  features.Plane1_dir_std_deg = round(std(p1Dir));
  features.Plane1_dir_max_deg = round(maxOf(p1Dir));
  features.Plane1_dir_min_deg = round(minOf(p1Dir));
  features.Plane1_dir_range_deg = round(maxOf(p1Dir) - minOf(p1Dir));
  features.Plane2_dir_mean_deg = round(avg(p2Dir));
  features.Plane2_dir_std_deg = round(std(p2Dir));
  features.Plane2_dir_max_deg = round(maxOf(p2Dir));
  features.Plane2_dir_min_deg = round(minOf(p2Dir));
  features.Plane2_dir_range_deg = round(maxOf(p2Dir) - minOf(p2Dir));
  features.relative_angle_mean_deg = round(avg(relAngles));
  features.relative_angle_std_deg = round(std(relAngles));
  features.relative_angle_max_deg = round(maxOf(relAngles));
  features.relative_angle_min_deg = round(minOf(relAngles));
  const sortedDist = [...distances].sort((a, b) => a - b);
  features.inter_dist_mean = round(avg(distances));
  features.inter_dist_std = round(std(distances));
  features.inter_dist_min = round(minOf(distances));
  features.inter_dist_max = round(maxOf(distances));
  features.inter_dist_range = round(maxOf(distances) - minOf(distances));
  features.inter_dist_median = round((sortedDist[24] + sortedDist[25]) / 2);
  features.start_dist = round(distances[0]);
  features.end_dist = round(distances[49]);
  features.dist_change = round(distances[49] - distances[0]);
  features.dist_change_ratio = Number(((distances[49] - distances[0]) / Math.max(distances[0], 1)).toFixed(4));
  const distSteps: number[] = [];
  for (let i = 0; i < 49; i++) {
    const step = round(distances[i + 1] - distances[i]);
    distSteps.push(step);
    features[`dist_change_step_${i + 1}`] = step;
  }
  features.dist_change_mean_step = round(avg(distSteps));
  features.dist_change_std_step = round(std(distSteps));
  features.dist_change_max_step = round(maxOf(distSteps));
  features.dist_change_min_step = round(minOf(distSteps));
  features.Plane1_total_distance = Number(total1.toFixed(1));
  features.Plane2_total_distance = Number(total2.toFixed(1));
  features.total_dist_diff = Number(Math.abs(total1 - total2).toFixed(1));
  features.total_dist_ratio = Number((total1 / Math.max(total2, 1)).toFixed(4));
  if (withPlaneIds) {
    features.PlaneID1 = sample(['A01', 'A02', 'B01']);
    features.PlaneID2 = sample(['A01', 'A02', 'B01']);
  }
  return features;
};

/** 按场景生成风险事件描述（需求 5.7.2 口径：解释文本在事件生成时固化存储） */
const describeRiskEvent = (scenario_id: ScenarioId, features: Record<string, unknown>): string => {
  if (scenario_id === 'power_system') {
    const voltage = features.VoltageLevel_kV !== undefined && features.VoltageLevel_kV !== null
      ? `，当前电压 ${features.VoltageLevel_kV} kV`
      : '';
    return `模型判定该样本形成电力系统风险，问题现象为 ${(features.IssueType as string) || '未记录'}${voltage}。`;
  }
  if (scenario_id === 'geological_risk') {
    // 不同地质数据集字段命名存在大小写差异，做回退取数，避免描述出现 "--"
    const slope = features.Slope ?? features.slope ?? '--';
    const twi = features.TWI ?? features.twi ?? '--';
    const dis2fault = features.Dis2fault ?? features.Dis2roads ?? '--';
    return `模型判定该样本存在滑坡风险，坡度 ${slope}°，TWI ${twi}，距断层 ${dis2fault}m。`;
  }
  if (scenario_id === 'flightdeck_operation') {
    return `模型判定该双机作业轨迹存在碰撞风险，最小间距 ${features.inter_dist_min ?? '--'}，接近率 ${features.dist_change_ratio ?? '--'}，方向角偏差 ${features.relative_angle_max_deg ?? '--'}°。`;
  }
  // KDD 使用 service/protocol_type，NF-UNSW 使用 L4_DST_PORT/PROTOCOL，做回退取数
  const port = features.L4_DST_PORT ?? features.service ?? '未记录';
  const protocol = features.PROTOCOL ?? features.protocol_type ?? '未记录';
  const bytes = features.IN_BYTES !== undefined && features.IN_BYTES !== null
    ? `，流入字节数 ${features.IN_BYTES}`
    : features.src_bytes !== undefined && features.src_bytes !== null
      ? `，源端字节数 ${features.src_bytes}`
      : '';
  const retrans = features.RETRANSMITTED_IN_BYTES !== undefined && Number(features.RETRANSMITTED_IN_BYTES) > 0
    ? `，流入重传 ${features.RETRANSMITTED_IN_BYTES} 字节`
    : '';
  return `模型判定该网络流量样本存在网络安全风险，目标端口 ${port}，协议 ${protocol}${bytes}${retrans}。`;
};

/** 航母甲板故障位置（需求 7.4.1）：x 随方向角偏差变化、y 随最小间距变化，坐标基准 1000px，clamp 限幅 */
const flightdeckFaultPosition = (features: Record<string, unknown>): { fault_position_x: number; fault_position_y: number } => {
  const relAngleMax = Number(features.relative_angle_max_deg ?? 30);
  const minDist = Number(features.inter_dist_min ?? 100);
  return {
    fault_position_x: clamp(Math.round(500 + (relAngleMax - 30) * 8), 50, 950),
    fault_position_y: clamp(Math.round(450 - minDist * 4), 40, 960),
  };
};

/** 预置推理记录与风险事件（供告警中心/态势展示，同时满足访问控制演示） */
const initInferenceAndEvents = (): void => {
  const seed: Array<{
    user_id: string;
    scenario_id: ScenarioId;
    dataset_id: string;
    algorithm_id: string;
    day: number;
    hour: number;
    is_risk: boolean;
    risk_prob: number;
    features: Record<string, unknown>;
    /** 是否使用当前时间（今日告警演示，需求 7.1 今日告警数） */
    today?: boolean;
  }> = [
    // 网络安全/电力：features 保存完整字段（需求 5.5 raw_features 使用规则），支撑看板聚合
    { user_id: 'user_000018', scenario_id: 'network_security', dataset_id: 'nf_unsw_nb15_v2', algorithm_id: 'PMWNB', day: 25, hour: 10, is_risk: true, risk_prob: 0.93, features: buildSeedFeatures('nf_unsw_nb15_v2') },
    { user_id: 'user_000018', scenario_id: 'network_security', dataset_id: 'kdd_train_20_percent', algorithm_id: 'A2WNB', day: 26, hour: 14, is_risk: false, risk_prob: 0.21, features: buildSeedFeatures('kdd_train_20_percent') },
    { user_id: 'user_000018', scenario_id: 'power_system', dataset_id: 'powergrid_knowledgebase', algorithm_id: 'MAWNB', day: 28, hour: 9, is_risk: true, risk_prob: 0.78, features: buildSeedFeatures('powergrid_knowledgebase') },
    { user_id: 'user_000031', scenario_id: 'network_security', dataset_id: 'nf_unsw_nb15_v2', algorithm_id: 'CAVWNB', day: 27, hour: 16, is_risk: true, risk_prob: 0.66, features: buildSeedFeatures('nf_unsw_nb15_v2') },
    { user_id: 'user_000031', scenario_id: 'power_system', dataset_id: 'powergrid_knowledgebase', algorithm_id: 'A2WNB', day: 29, hour: 11, is_risk: false, risk_prob: 0.3, features: buildSeedFeatures('powergrid_knowledgebase') },
    { user_id: 'user_000042', scenario_id: 'network_security', dataset_id: 'kdd_train_20_percent', algorithm_id: 'EMAWNB', day: 30, hour: 20, is_risk: true, risk_prob: 0.85, features: buildSeedFeatures('kdd_train_20_percent') },
    // 今日告警（需求 7.1 指标卡"今日告警数"非零演示）
    { user_id: 'user_000018', scenario_id: 'network_security', dataset_id: 'nf_unsw_nb15_v2', algorithm_id: 'A2WNB', day: 1, hour: 9, is_risk: true, risk_prob: 0.88, today: true, features: buildSeedFeatures('nf_unsw_nb15_v2') },
    { user_id: 'user_000031', scenario_id: 'network_security', dataset_id: 'kdd_train_20_percent', algorithm_id: 'CAVWNB', day: 1, hour: 10, is_risk: true, risk_prob: 0.72, today: true, features: buildSeedFeatures('kdd_train_20_percent') },
    // 地质风险（carol）：4 个可训练数据集，features 保存完整字段
    { user_id: 'user_000042', scenario_id: 'geological_risk', dataset_id: 'dis_raw_data', algorithm_id: 'PMWNB', day: 1, hour: 9, is_risk: true, risk_prob: 0.86, features: buildSeedFeatures('dis_raw_data') },
    { user_id: 'user_000042', scenario_id: 'geological_risk', dataset_id: 'dis_raw_data', algorithm_id: 'A2WNB', day: 2, hour: 8, is_risk: false, risk_prob: 0.18, features: buildSeedFeatures('dis_raw_data') },
    { user_id: 'user_000042', scenario_id: 'geological_risk', dataset_id: 'dis_landslides', algorithm_id: 'MAWNB', day: 3, hour: 11, is_risk: true, risk_prob: 0.74, features: buildSeedFeatures('dis_landslides') },
    { user_id: 'user_000042', scenario_id: 'geological_risk', dataset_id: 'dis_causative_factors', algorithm_id: 'EMAWNB', day: 4, hour: 15, is_risk: true, risk_prob: 0.68, features: buildSeedFeatures('dis_causative_factors') },
    { user_id: 'user_000042', scenario_id: 'geological_risk', dataset_id: 'dis_guaruja_random', algorithm_id: 'A2WNB', day: 5, hour: 10, is_risk: false, risk_prob: 0.22, features: buildSeedFeatures('dis_guaruja_random') },
    // 航母甲板（carol）：三份 carrier 数据集，features 使用同一轨迹生成器
    { user_id: 'user_000042', scenario_id: 'flightdeck_operation', dataset_id: 'carrier_feature2_biaoqian', algorithm_id: 'PMWNB', day: 2, hour: 14, is_risk: true, risk_prob: 0.9, features: buildCarrierTrajectoryFeatures(true, false) },
    { user_id: 'user_000042', scenario_id: 'flightdeck_operation', dataset_id: 'carrier_feature2_lisan', algorithm_id: 'EMAWNB', day: 3, hour: 16, is_risk: false, risk_prob: 0.3, features: buildCarrierTrajectoryFeatures(false, false) },
    { user_id: 'user_000042', scenario_id: 'flightdeck_operation', dataset_id: 'carrier_paired_trail_biaoqian', algorithm_id: 'A2WNB', day: 4, hour: 13, is_risk: true, risk_prob: 0.84, features: buildCarrierTrajectoryFeatures(true, true) },
  ];

  const byUser = (id: string) => userRecords.find((u) => u.user_id === id)?.username ?? id;

  for (const s of seed) {
    const model = modelVersions.find((m) => m.dataset_id === s.dataset_id && m.status !== 'FAILED') ?? modelVersions.find((m) => m.dataset_id === s.dataset_id)!;
    const occurred_at = s.today
      ? nowStr()
      : `2026-07-${String(s.day).padStart(2, '0')} ${String(s.hour).padStart(2, '0')}:${String(random(0, 59)).padStart(2, '0')}:00`;
    const record: InferenceRecord = {
      inference_record_id: `infer_${String(inferSeq++).padStart(6, '0')}`,
      user_id: s.user_id,
      scenario_id: s.scenario_id,
      dataset_id: s.dataset_id,
      dataset_version: model.dataset_version,
      algorithm_id: s.algorithm_id,
      model_version_id: model.model_version_id,
      input_features: s.features,
      original_label: originalLabelOf(s.dataset_id, s.is_risk),
      risk_type: s.is_risk ? riskTypeOf(s.scenario_id) : '',
      risk_level: s.is_risk ? (s.risk_prob >= 0.8 ? 'HIGH' : s.risk_prob >= 0.6 ? 'MEDIUM' : 'LOW') : 'LOW',
      risk_score: s.risk_prob,
      is_risk: s.is_risk,
      occurred_at,
    };
    inferenceRecords.push(record);
    if (s.is_risk) {
      const fault = s.scenario_id === 'flightdeck_operation' ? flightdeckFaultPosition(s.features) : null;
      riskEvents.push({
        event_id: `evt_${s.scenario_id}_${String(eventSeq++).padStart(6, '0')}`,
        inference_record_id: record.inference_record_id,
        created_by_user_id: s.user_id,
        scenario_id: s.scenario_id,
        dataset_id: s.dataset_id,
        dataset_version: model.dataset_version,
        algorithm_id: s.algorithm_id,
        model_version_id: model.model_version_id,
        original_label: record.original_label,
        risk_type: record.risk_type,
        risk_level: record.risk_level,
        risk_score: s.risk_prob,
        fault_position_x: fault?.fault_position_x,
        fault_position_y: fault?.fault_position_y,
        occurred_at,
        status: '待处置',
        raw_features: s.features,
        description: describeRiskEvent(s.scenario_id, s.features),
      });
    }
  }
  // 供告警中心按用户查看：attribution 便捷字段在展示层用 created_by_user_id 查询
  void byUser;
};

/** 过滤风险事件：普通用户强制按本人过滤，管理员查全平台（需求 5.2 访问控制 / 6.8） */
const filterRiskEvents = (user: UserAccount, scenarioId?: ScenarioId, userId?: string): RiskEvent[] => {
  let list = [...riskEvents];
  if (user.role === 'SCENARIO_USER') {
    if (scenarioId) assertScenarioAccess(user, scenarioId);
    list = list.filter((e) => canAccessScenario(user, e.scenario_id));
    list = list.filter((e) => e.created_by_user_id === user.user_id);
  }
  else if (userId) list = list.filter((e) => e.created_by_user_id === userId);
  if (scenarioId) list = list.filter((e) => e.scenario_id === scenarioId);
  return list.sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
};

/** 获取风险事件列表（普通用户仅本人，管理员全部；需求 6.2） */
export const getRiskEvents = async (scenarioId?: ScenarioId): Promise<RiskEvent[]> =>
  simulateLatency(filterRiskEvents(requireLogin(), scenarioId));

/** 过滤推理记录：普通用户仅本人，管理员全部或指定用户（需求 6.2 / 6.8） */
const filterInferenceRecords = (user: UserAccount, scenarioId?: ScenarioId, userId?: string): InferenceRecord[] => {
  let list = [...inferenceRecords];
  if (user.role === 'SCENARIO_USER') {
    if (scenarioId) assertScenarioAccess(user, scenarioId);
    list = list.filter((r) => canAccessScenario(user, r.scenario_id));
    list = list.filter((r) => r.user_id === user.user_id);
  }
  else if (userId) list = list.filter((r) => r.user_id === userId);
  if (scenarioId) list = list.filter((r) => r.scenario_id === scenarioId);
  return list.sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
};

/** 获取推理记录列表（普通用户仅本人；管理员可查全部或按用户筛选） */
export const getInferenceRecords = async (scenarioId?: ScenarioId, userId?: string): Promise<InferenceRecord[]> =>
  simulateLatency(filterInferenceRecords(requireLogin(), scenarioId, userId));

/** 推理结果 */
export interface InferenceResult {
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_probability: number;
  original_label: string;
  risk_type: string;
  recommendation: string;
  model_used: string;
  is_risk: boolean;
  description: string;
  inference_record_id: string;
  generated_event_id?: string;
}

/** 推理输入特征校验（需求 3.1.3 / 3.1.5 / 3.1.6）：必填字段、数值类型、枚举值域、键名保持正式字段名 */
const validateInputFeatures = (dataset_id: string, input: Record<string, unknown>): void => {
  const v = latestDatasetVersion(dataset_id);
  if (!v) throw new Error('数据集不存在');
  const inputFields = v.fields.filter((f) => f.field_role === '输入特征');
  for (const f of inputFields) {
    const raw = input[f.field_name];
    if (raw === undefined || raw === null || raw === '') {
      throw new Error(`输入特征「${f.field_name}」不能为空`);
    }
    if (f.field_type === 'float' || f.field_type === 'int') {
      if (Number.isNaN(Number(raw))) throw new Error(`输入特征「${f.field_name}」必须为数值`);
    }
    if (f.enum_values && f.enum_values.length > 0) {
      const sv = String(raw);
      if (!f.enum_values.includes(sv)) {
        throw new Error(`输入特征「${f.field_name}」取值不合法，允许值：${f.enum_values.join(' / ')}`);
      }
    }
  }
  // 需求 3.1.6：不得仅按列序号互换使用，必须同时校验数据集标识和字段名（字段名校验已在上方完成）
  void v;
};

/** 单条样本推理（需求 6.2）：选择已发布模型 → 按绑定数据集字段输入 → 推理 → 生成记录与风险事件 */
export const executeInference = async (params: {
  model_version_id: string;
  input_features: Record<string, unknown>;
}): Promise<InferenceResult> => {
  const user = requireLogin();
  const model = modelVersions.find((m) => m.model_version_id === params.model_version_id);
  if (!model) throw new Error('模型版本不存在');
  if (model.status !== 'PUBLISHED') throw new Error('仅已发布模型可执行推理');
  assertScenarioAccess(user, model.scenario_id);
  validateInputFeatures(model.dataset_id, params.input_features);
  const cfg = thresholdConfigFor(user, model.scenario_id);
  // 模拟模型输出：约 35% 判为风险类（risk_score 为模型对风险类的输出概率，需求 5.4）
  const isRisk = Math.random() < 0.35;
  const risk_probability = isRisk
    ? Number((Math.random() * 0.4 + 0.58).toFixed(4))
    : Number((Math.random() * 0.5).toFixed(4));
  const original_label = originalLabelOf(model.dataset_id, isRisk);
  // 风险等级：由 risk_score 与场景阈值计算（需求 5.4）
  let risk_level: 'HIGH' | 'MEDIUM' | 'LOW' = 'LOW';
  if (isRisk) {
    if (risk_probability >= cfg.high_threshold) risk_level = 'HIGH';
    else if (risk_probability >= cfg.medium_threshold) risk_level = 'MEDIUM';
    else risk_level = 'LOW';
  }
  const occurred_at = nowStr();
  const record: InferenceRecord = {
    inference_record_id: `infer_${String(inferSeq++).padStart(6, '0')}`,
    user_id: user.user_id,
    scenario_id: model.scenario_id,
    dataset_id: model.dataset_id,
    dataset_version: model.dataset_version,
    algorithm_id: model.algorithm_id,
    model_version_id: model.model_version_id,
    input_features: params.input_features,
    original_label,
    risk_type: isRisk ? riskTypeOf(model.scenario_id) : '',
    risk_level,
    risk_score: risk_probability,
    is_risk: isRisk,
    occurred_at,
  };
  inferenceRecords.unshift(record);

  let generated_event_id: string | undefined;
  if (isRisk) {
    const fault = model.scenario_id === 'flightdeck_operation' ? flightdeckFaultPosition(params.input_features) : null;
    const event: RiskEvent = {
      event_id: `evt_${model.scenario_id}_${String(eventSeq++).padStart(6, '0')}`,
      inference_record_id: record.inference_record_id,
      created_by_user_id: user.user_id,
      scenario_id: model.scenario_id,
      dataset_id: model.dataset_id,
      dataset_version: model.dataset_version,
      algorithm_id: model.algorithm_id,
      model_version_id: model.model_version_id,
      original_label,
      risk_type: record.risk_type,
      risk_level,
      risk_score: risk_probability,
      fault_position_x: fault?.fault_position_x,
      fault_position_y: fault?.fault_position_y,
      occurred_at,
      status: '待处置',
      raw_features: params.input_features,
      description: describeRiskEvent(model.scenario_id, params.input_features),
    };
    riskEvents.unshift(event);
    generated_event_id = event.event_id;
  }

  const recommendations = isRisk
    ? (model.scenario_id === 'power_system'
        ? ['通知运维人员现场核查目标设备', '结合 IssueType 排查对应问题现象', '加强该设备链路监测']
        : model.scenario_id === 'geological_risk'
          ? ['通知地质灾害监测人员现场核查', '结合坡度/TWI/距断层等因子评估', '加强该区域监测频次']
          : model.scenario_id === 'flightdeck_operation'
            ? ['通知甲板指挥员复核双机间距', '核查方向角偏差与接近率', '暂停该作业窗口并复盘轨迹']
            : ['立即封禁源地址并同步边界防火墙策略', '保留样本日志用于模型复盘', '加强该主机访问控制']
      ).join('；')
    : '该样本判定为正常，无需处置。';

  return simulateLatency({
    risk_level,
    risk_probability,
    original_label,
    risk_type: isRisk ? record.risk_type : '',
    recommendation: recommendations,
    model_used: `${algoName(model.algorithm_id)}（${model.model_version_id}）`,
    is_risk: isRisk,
    description: isRisk ? describeRiskEvent(model.scenario_id, params.input_features) : '模型判定该样本为正常样本。',
    inference_record_id: record.inference_record_id,
    generated_event_id,
  });
};

/** 更新风险事件处置状态 */
export const updateRiskEventStatus = async (eventId: string, status: RiskEvent['status']): Promise<void> => {
  const event = riskEvents.find((e) => e.event_id === eventId);
  if (!event) throw new Error('风险事件不存在');
  event.status = status;
};

/**
 * 获取单个风险事件详情（需求 5.7 / 5.2 访问控制：普通用户仅本人事件）。
 * 注意：真实权限校验必须由后端完成，mock 层过滤仅为前端联调基线（需求 6.5.x）。
 */
export const getRiskEventById = async (eventId: string): Promise<RiskEvent> => {
  const user = requireLogin();
  const event = riskEvents.find((e) => e.event_id === eventId);
  if (!event) throw new Error('风险事件不存在');
  assertScenarioAccess(user, event.scenario_id);
  if (user.role === 'SCENARIO_USER' && event.created_by_user_id !== user.user_id) throw new Error('无权查看该事件');
  return event;
};

/**
 * 按推理记录查询关联风险事件（供推理记录页"查看事件"跳转；无关联返回 null）。
 * 访问控制与 getRiskEventById 一致。
 */
export const getRiskEventByInferenceRecordId = async (recordId: string): Promise<RiskEvent | null> => {
  const user = requireLogin();
  const event = riskEvents.find((e) => e.inference_record_id === recordId);
  if (!event) return null;
  assertScenarioAccess(user, event.scenario_id);
  if (user.role === 'SCENARIO_USER' && event.created_by_user_id !== user.user_id) throw new Error('无权查看该事件');
  return event;
};

// ===================== 场景 / 态势 / 报告（角色感知，需求 6.8） =====================

/** 生成场景卡片数据 — 四场景均已接入（需求 1.1）；统计口径按当前用户数据范围（需求 6.8） */
const generateScenarioCard = (meta: typeof SCENARIO_META[number], user?: UserAccount): Scenario => {
  const events = user ? filterRiskEvents(user, meta.id) : [];
  const highCount = events.filter((e) => e.risk_level === 'HIGH').length;
  return {
    scenario_id: meta.id,
    name: meta.name,
    description: meta.description,
    risk_level: meta.risk_level,
    risk_score: events.length > 0 ? Math.round(events.reduce((s, e) => s + e.risk_score, 0) / events.length * 100) : 0,
    event_count: events.length,
    high_risk_count: highCount,
    dataset_count: meta.datasets.length,
    model_count: modelVersions.filter((m) => m.scenario_id === meta.id && m.status === 'PUBLISHED').length,
    status: 'active',
  };
};

/** 模拟风险趋势点 — 已接入场景允许模拟态势数据（需求只禁止未接入场景使用虚构数据）。
 *  曲线基于"当前用户可见风险事件"的平均分数作基线再叠加随机波动：
 *  普通用户本人事件少 → 基线低，管理员全平台事件多 → 基线高，从而体现个人/全局态势差异（需求 6.8）。 */
const makeTrendPoint = (base: number, primaryType: string, label: string): TrendPoint => ({
  label,
  value: Math.max(0, Math.min(100, Math.round(base + random(-14, 14)))),
  blocked: random(2, Math.max(3, Math.round(base * 0.4))),
  sources: random(2, 12),
  primaryType,
});

/** 按当前用户可见事件生成趋势基线 */
const trendBaseOf = (events: RiskEvent[], user: UserAccount, defaultBase: number): number => {
  if (events.length === 0) return user.role === 'SUPER_ADMIN' ? defaultBase : Math.max(18, Math.round(defaultBase * 0.35));
  const avg = events.reduce((s, e) => s + e.risk_score, 0) / events.length;
  return Math.max(18, Math.min(90, Math.round(avg * 100)));
};

/** 场景详情态势（按当前用户数据范围统计；四场景均已接入） */
const generateScenarioDetail = (meta: typeof SCENARIO_META[number], user: UserAccount): ScenarioDetail => {
  const events = filterRiskEvents(user, meta.id);
  const records = filterInferenceRecords(user, meta.id);
  const riskCount = events.length;
  const avgScore = riskCount > 0 ? Number((events.reduce((s, e) => s + e.risk_score, 0) / riskCount).toFixed(2)) : 0;
  const normalCount = records.filter((r) => !r.is_risk).length;
  const primaryType = meta.risk_types[0] ?? 'NETWORK_SECURITY_RISK';
  const base = trendBaseOf(events, user, 58);
  return {
    scenario: generateScenarioCard(meta, user),
    metrics: [
      { id: 'risk-score', label: '当前风险分数', value: riskCount > 0 ? Math.round(avgScore * 100) : 0, trend: 0 },
      { id: 'event-rate', label: '风险事件数', value: riskCount, trend: 0 },
      { id: 'model-accuracy', label: '推理记录数', value: records.length, trend: 0 },
      { id: 'response-time', label: '已处置事件数', value: events.filter((e) => e.status === '已处置').length, trend: 0 },
    ],
    trend_data: Array.from({ length: 12 }, (_, i) =>
      makeTrendPoint(base, primaryType, `${String(i * 2).padStart(2, '0')}:00`)
    ),
    risk_distribution: [
      { label: '正常', value: Math.max(normalCount, 0), color: '#53e5c8' },
      { label: '风险', value: riskCount, color: '#ff7b72' },
    ],
    recent_events: events.slice(0, 5),
  };
};

/** 全局态势总览（按当前用户数据范围统计） */
const generateGlobalOverview = (user: UserAccount): GlobalOverview => {
  const accessible = SCENARIO_META.filter((m) => canAccessScenario(user, m.id));
  const scenarios = accessible.map((m) => generateScenarioCard(m, user));
  const activeEvents = filterRiskEvents(user);
  const globalScore = activeEvents.length > 0
    ? Math.round(activeEvents.reduce((s, e) => s + e.risk_score, 0) / activeEvents.length * 100)
    : 0;
  return {
    global_risk_score: globalScore,
    global_risk_level: globalScore >= 75 ? 'high' : globalScore >= 45 ? 'medium' : 'low',
    scenario_count: accessible.length,
    high_risk_count: activeEvents.filter((e) => e.risk_level === 'HIGH').length,
    active_model_count: modelVersions.filter((m) => m.status === 'PUBLISHED').length,
    scenarios,
    global_trend: Array.from({ length: 12 }, (_, i) =>
      makeTrendPoint(trendBaseOf(activeEvents, user, 52), 'NETWORK_SECURITY_RISK', `${String(i * 2).padStart(2, '0')}:00`)
    ),
  };
};

/** 态势分析数据（按当前用户数据范围统计） */
const generateSituationData = (meta: typeof SCENARIO_META[number], user: UserAccount): SituationData => {
  const events = filterRiskEvents(user, meta.id);
  const records = filterInferenceRecords(user, meta.id);
  const primaryType = meta.risk_types[0] ?? 'NETWORK_SECURITY_RISK';
  const base = trendBaseOf(events, user, 55);
  return {
    scenario_id: meta.id,
    time_range: '24h',
    score_history: Array.from({ length: 24 }, (_, i) =>
      makeTrendPoint(base, primaryType, `${String(i).padStart(2, '0')}:00`)
    ),
    event_distribution: [
      { label: '正常', value: records.filter((r) => !r.is_risk).length, color: '#53e5c8' },
      { label: '风险', value: events.length, color: '#ff7b72' },
    ],
    risk_trend: Array.from({ length: 7 }, (_, i) =>
      makeTrendPoint(base, primaryType, `第${i + 1}日`)
    ),
    metrics: [
      { id: 'avg-risk', label: '平均风险分数', value: events.length > 0 ? Math.round(events.reduce((s, e) => s + e.risk_score, 0) / events.length * 100) : 0, trend: 0 },
      { id: 'peak-risk', label: '风险事件数', value: events.length, trend: 0 },
      { id: 'event-total', label: '推理记录数', value: records.length, trend: 0 },
    ],
  };
};

/** 报告列表（P1：可基于本人/全局/指定用户数据生成） */
const generateReports = (user: UserAccount): Report[] =>
  SCENARIO_META.filter((m) => m.id !== 'flightdeck_operation').flatMap((meta) =>
    Array.from({ length: random(1, 2) }, (_, i) => {
      const scheduled = i === 0;
      return {
        report_id: `RPT-${meta.id}-${String(i + 1).padStart(3, '0')}`,
        title: `${meta.name}态势报告 - ${i === 0 ? '周报' : '月报'}`,
        scenario_id: meta.id,
        scenario_name: meta.name,
        summary: `基于 ${user.role === 'SUPER_ADMIN' ? '全平台' : '本人'} ${meta.name} 数据生成的态势分析报告`,
        created_at: `2026-07-${String(20 - i * 3).padStart(2, '0')} ${String(random(8, 18)).padStart(2, '0')}:00`,
        format: sample(['markdown', 'html', 'pdf'] as const),
        status: 'completed' as const,
        file_url: i === 0 ? `/reports/${meta.id}-report.pdf` : undefined,
        scheduled,
        interval_days: scheduled ? 7 : undefined,
        generated_by: 'demo',
      };
    })
  );

/** 生成或刷新全部场景模拟数据 */
const generateScenarioMockData = () => {
  datasetVersions = initDatasetVersions();
  modelVersions = initModelVersions();
  inferenceRecords = [];
  riskEvents = [];
  inferSeq = 1;
  eventSeq = 1;
  initInferenceAndEvents();
};

/** 确保多场景缓存与数据已初始化 */
const ensureScenarioCache = () => {
  if (datasetVersions.length === 0) generateScenarioMockData();
  return { datasetVersions, modelVersions, inferenceRecords, riskEvents };
};

// ===================== 多场景导出接口 =====================

/** 获取四个场景列表（需求 1.1 场景列表，标明接入状态） */
export const getScenarioList = async (): Promise<Scenario[]> => {
  ensureScenarioCache();
  const user = requireLogin();
  return simulateLatency(
    SCENARIO_META.filter((m) => canAccessScenario(user, m.id)).map((m) => generateScenarioCard(m, user))
  );
};

/** 获取单个场景详情及态势数据（需求 6.8 个人/全局态势） */
export const getScenarioDetail = async (scenarioId: ScenarioId): Promise<ScenarioDetail> => {
  ensureScenarioCache();
  const user = requireLogin();
  assertScenarioAccess(user, scenarioId);
  const meta = SCENARIO_META.find((s) => s.id === scenarioId)!;
  return simulateLatency(generateScenarioDetail(meta, user));
};

/** 获取全局态势概览 */
export const getGlobalOverview = async (): Promise<GlobalOverview> => {
  ensureScenarioCache();
  return simulateLatency(generateGlobalOverview(requireLogin()));
};

/** 获取态势分析数据 */
export const getSituationData = async (scenarioId: ScenarioId): Promise<SituationData> => {
  ensureScenarioCache();
  const user = requireLogin();
  assertScenarioAccess(user, scenarioId);
  const meta = SCENARIO_META.find((s) => s.id === scenarioId)!;
  return simulateLatency(generateSituationData(meta, user));
};

/** 获取报告列表（按角色隔离，数据共享自同一 reports 存储）：
 * - 系统管理员 SUPER_ADMIN：全部报告
 * - 场景管理员 SCENARIO_ADMIN：自己场景下的所有报告（含该场景用户生成的）
 * - 场景用户 SCENARIO_USER：仅自己生成的报告
 */
export const getReportList = async (): Promise<Report[]> => {
  ensureScenarioCache();
  const user = requireLogin();
  const demo = generateReports(user);
  let list: Report[];
  if (user.role === 'SUPER_ADMIN') {
    list = [...reports, ...demo];
  } else if (user.role === 'SCENARIO_ADMIN') {
    const myScenarios = user.scenario_ids ?? [];
    list = [
      ...reports.filter((r) => myScenarios.includes(r.scenario_id)),
      ...demo.filter((r) => myScenarios.includes(r.scenario_id)),
    ];
  } else {
    list = reports.filter((r) => r.generated_by === user.user_id);
  }
  return simulateLatency(list);
};

/** 依据指定数据范围生成态势报告（P1） */
export const generateReport = async (params: {
  scenario_id: ScenarioId;
  title: string;
  scope: 'self' | 'all' | 'user';
  target_user_id?: string;
  format?: 'markdown' | 'html' | 'pdf';
  scheduled?: boolean;
  interval_days?: number;
}): Promise<Report> => {
  const user = requireLogin();
  if (user.role === 'SCENARIO_USER' && params.scope !== 'self') throw new Error('普通用户只能基于本人数据生成报告');
  const meta = SCENARIO_META.find((s) => s.id === params.scenario_id);
  const events = filterRiskEvents(user, params.scenario_id, params.scope === 'user' ? params.target_user_id : undefined);
  const scopeLabel = params.scope === 'all' ? '全平台' : params.scope === 'user' ? `用户 ${params.target_user_id}` : '本人';
  const report: Report = {
    report_id: `RPT-${params.scenario_id}-${String(random(100, 999))}`,
    title: params.title,
    scenario_id: params.scenario_id,
    scenario_name: meta?.name ?? params.scenario_id,
    summary: `基于 ${scopeLabel} 数据生成，共统计 ${events.length} 条风险事件`,
    created_at: nowStr(),
    format: params.format ?? 'markdown',
    scheduled: params.scheduled ?? false,
    interval_days: params.scheduled ? params.interval_days : undefined,
    status: 'completed',
    file_url: undefined,
    generated_by: user.user_id,
  };
  reports.unshift(report);
  saveReports();
  return simulateLatency(report);
};

/** 修改报告的定时设置（开启/关闭定时、修改周期天数），刷新后仍保留 */
export const updateReportSchedule = async (
  reportId: string,
  scheduled: boolean,
  intervalDays?: number,
): Promise<void> => {
  requireLogin();
  const report = reports.find((r) => r.report_id === reportId);
  if (!report) throw new Error('报告不存在');
  report.scheduled = scheduled;
  report.interval_days = scheduled ? intervalDays : undefined;
  saveReports();
  return simulateLatency(undefined);
};
