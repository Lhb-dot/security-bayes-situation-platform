import type {
  AlertRecord,
  AttackFlow,
  DashboardSnapshot,
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
  RiskEvent,
  SituationData,
  Report,
  ScenarioId,
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

export const getDashboardSnapshot = async () => simulateLatency(ensureCache().dashboard);
export const getAlerts = async () => simulateLatency(ensureCache().alerts);
export const getAlertById = async (id: string) =>
  simulateLatency(ensureCache().alerts.find((item) => item.id === id) ?? ensureCache().alerts[0]);
export const refreshMockData = () => {
  generateDataset();
};

// ===================== 多场景 Mock 数据（新增，不修改以上已有函数） =====================

/** 三个场景元信息定义 — 数据集字段结构严格匹配需求第3节 ARFF 文件定义 */
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
    description: '第一阶段仅预留接口，暂不配置实际数据集，不开展真实训练、推理和风险事件生成',
    risk_level: 'high',
    datasets: [],
    risk_types: ['FLIGHT_DECK_OPERATION_RISK'],
  },
];

/** 场景Mock缓存 */
let scenarioCache: {
  scenarios: Scenario[];
  scenarioDetails: Record<ScenarioId, ScenarioDetail>;
  globalOverview: GlobalOverview;
  datasets: Dataset[];
  situationData: Record<ScenarioId, SituationData>;
  reports: Report[];
} | null = null;

/** 生成单个场景卡片数据 — 航母甲板第一阶段为 inactive */
const generateScenarioCard = (meta: typeof SCENARIO_META[number]): Scenario => ({
  scenario_id: meta.id,
  name: meta.name,
  description: meta.description,
  risk_level: meta.risk_level,
  risk_score: meta.id === 'flightdeck_operation' ? 0 : random(45, 92),
  event_count: meta.id === 'flightdeck_operation' ? 0 : random(30, 180),
  high_risk_count: meta.id === 'flightdeck_operation' ? 0 : random(2, 18),
  dataset_count: meta.id === 'flightdeck_operation' ? 0 : meta.datasets.length,
  model_count: meta.id === 'flightdeck_operation' ? 0 : random(1, 5),
  status: meta.id === 'flightdeck_operation' ? 'inactive' : 'active',
});

/** 生成场景详情态势数据 — 航母甲板无事件、无风险分布 */
const generateScenarioDetail = (meta: typeof SCENARIO_META[number]): ScenarioDetail => {
  const isFlightdeck = meta.id === 'flightdeck_operation';
  return {
    scenario: generateScenarioCard(meta),
    metrics: isFlightdeck ? [] : [
      { id: 'risk-score', label: '当前风险分数', value: random(45, 92), trend: random(-12, 18) },
      { id: 'event-rate', label: '事件发生率', value: `${random(2, 8)}/h`, trend: random(-8, 10) },
      { id: 'model-accuracy', label: '模型检测率', value: `${random(91, 99)}%`, trend: random(1, 5) },
      { id: 'response-time', label: '平均响应时间', value: `${random(3, 15)} min`, trend: -random(2, 8) },
    ],
    trend_data: isFlightdeck ? [] : Array.from({ length: 12 }, (_, i) => ({
      label: `${String(i * 2).padStart(2, '0')}:00`,
      value: random(15, 95),
      blocked: random(5, 60),
      sources: random(3, 20),
      primaryType: 'NETWORK_SECURITY_RISK',
    })),
    risk_distribution: isFlightdeck ? [] : [
      { label: '正常', value: random(55, 80), color: '#53e5c8' },
      { label: '风险', value: random(20, 45), color: '#ff7b72' },
    ],
    recent_events: isFlightdeck ? [] : Array.from({ length: 5 }, (_, i) => ({
      event_id: `${meta.id.toUpperCase()}-EVT-${String(i + 1).padStart(4, '0')}`,
      scenario_id: meta.id,
      dataset_id: meta.id === 'network_security'
        ? (i < 2 ? 'network_security-ds-1' : 'network_security-ds-2')
        : 'power_system-ds-1',
      model_version_id: `MOD-${meta.id}-${String(random(1, 3)).padStart(3, '0')}`,
      original_label: sample(['normal', 'anomaly', '0', '1'] as const),
      risk_type: meta.id === 'network_security' ? 'NETWORK_SECURITY_RISK' : 'POWER_SYSTEM_RISK',
      risk_level: sample(['HIGH', 'MEDIUM', 'LOW'] as const),
      risk_score: Number((Math.random() * 0.45 + 0.4).toFixed(2)),
      occurred_at: `2026-07-${String(20 + i).padStart(2, '0')} ${String(random(8, 20)).padStart(2, '0')}:${String(random(0, 59)).padStart(2, '0')}:00`,
      status: sample(['待处置', '处理中', '已处置'] as const),
      raw_features: { indicator: random(0, 100) },
      description: `模型判定该样本存在${meta.id === 'network_security' ? '网络安全' : '电力系统'}风险`,
    })),
  };
};

/** 生成全部数据集列表 — 航母甲板返回空数组 */
const generateDatasets = (): Dataset[] =>
  SCENARIO_META.flatMap((meta) => {
    if (meta.id === 'flightdeck_operation') return [];
    return meta.datasets.map((ds, i) => ({
      dataset_id: `${meta.id}-ds-${i + 1}`,
      name: ds.name,
      description: ds.desc,
      scenario_id: meta.id,
      record_count: random(10000, 500000),
      field_count: ds.fields.length,
      fields: ds.fields.map((f, fi) => ({
        ...f,
        nullable: false,
        field_role: fi === ds.fields.length - 1 ? '分类标签' as const : '输入特征' as const,
      })),
      created_at: `2026-0${random(3, 6)}-${String(random(1, 28)).padStart(2, '0')}`,
      data_format: ds.format,
    }));
  });

/** 生成全局态势概览 — 航母甲板不计入活跃指标 */
const generateGlobalOverview = (scenarios: Scenario[]): GlobalOverview => {
  const active = scenarios.filter(s => s.status === 'active');
  return {
    global_risk_score: active.length > 0
      ? Math.round(active.reduce((sum, s) => sum + s.risk_score, 0) / active.length)
      : 0,
    global_risk_level: 'high',
    scenario_count: scenarios.length,
    high_risk_count: active.reduce((sum, s) => sum + s.high_risk_count, 0),
    active_model_count: active.reduce((sum, s) => sum + s.model_count, 0),
    scenarios,
    global_trend: active.length > 0 ? Array.from({ length: 12 }, (_, i) => ({
      label: `${String(i * 2).padStart(2, '0')}:00`,
      value: random(30, 88),
      blocked: random(10, 55),
      sources: random(5, 30),
      primaryType: sample(['NETWORK_SECURITY_RISK', 'POWER_SYSTEM_RISK']),
    })) : [],
  };
};

/** 生成态势分析数据 — 航母甲板返回空数据 */
const generateSituationData = (meta: typeof SCENARIO_META[number]): SituationData => {
  const isFlightdeck = meta.id === 'flightdeck_operation';
  return {
    scenario_id: meta.id,
    time_range: isFlightdeck ? '-' : '24h',
    score_history: isFlightdeck ? [] : Array.from({ length: 24 }, (_, i) => ({
      label: `${String(i).padStart(2, '0')}:00`,
      value: random(30, 90),
      blocked: random(5, 45),
      sources: random(2, 18),
      primaryType: sample(['NETWORK_SECURITY_RISK', 'POWER_SYSTEM_RISK']),
    })),
    event_distribution: isFlightdeck ? [] : [
      { label: '正常', value: random(55, 80), color: '#53e5c8' },
      { label: '风险', value: random(20, 45), color: '#ff7b72' },
    ],
    risk_trend: isFlightdeck ? [] : Array.from({ length: 7 }, (_, i) => ({
      label: `第${i + 1}日`,
      value: random(25, 85),
      blocked: random(8, 40),
      sources: random(3, 15),
      primaryType: sample(['NETWORK_SECURITY_RISK', 'POWER_SYSTEM_RISK']),
    })),
    metrics: isFlightdeck ? [] : [
      { id: 'avg-risk', label: '平均风险分数', value: random(40, 80), trend: -random(1, 10) },
      { id: 'peak-risk', label: '峰值风险', value: random(75, 98), trend: random(1, 8) },
      { id: 'event-total', label: '事件总数', value: random(50, 200), trend: random(2, 15) },
    ],
  };
};

/** 生成报告列表（航母甲板不生成报告） */
const generateReports = (): Report[] =>
  SCENARIO_META.filter((m) => m.id !== 'flightdeck_operation').flatMap((meta) =>
    Array.from({ length: random(1, 3) }, (_, i) => ({
      report_id: `RPT-${meta.id}-${String(i + 1).padStart(3, '0')}`,
      title: `${meta.name}态势报告 - ${i === 0 ? '周报' : i === 1 ? '月报' : '分析报告'}`,
      scenario_id: meta.id,
      scenario_name: meta.name,
      summary: `基于 ${meta.datasets.map((d) => d.name).join('、')} 数据生成的态势分析报告`,
      created_at: `2026-07-${String(20 - i * 3).padStart(2, '0')} ${String(random(8, 18)).padStart(2, '0')}:00`,
      format: sample(['markdown', 'html', 'pdf'] as const),
      status: sample(['completed', 'completed', 'completed', 'generating'] as const),
      file_url: i === 0 ? `/reports/${meta.id}-report.pdf` : undefined,
    }))
  );

/** 生成或刷新全部场景模拟数据 */
const generateScenarioMockData = () => {
  const scenarios = SCENARIO_META.map(generateScenarioCard);
  const scenarioDetails: Record<ScenarioId, ScenarioDetail> = {} as Record<ScenarioId, ScenarioDetail>;
  const situationData: Record<ScenarioId, SituationData> = {} as Record<ScenarioId, SituationData>;
  for (const meta of SCENARIO_META) {
    scenarioDetails[meta.id] = generateScenarioDetail(meta);
    situationData[meta.id] = generateSituationData(meta);
  }
  scenarioCache = {
    scenarios,
    scenarioDetails,
    globalOverview: generateGlobalOverview(scenarios),
    datasets: generateDatasets(),
    situationData,
    reports: generateReports(),
  };
};

/** 确保场景缓存 */
const ensureScenarioCache = () => {
  if (!scenarioCache) generateScenarioMockData();
  return scenarioCache!;
};

// ===================== 多场景导出接口 =====================

/** 获取三个场景列表 */
export const getScenarioList = async (): Promise<Scenario[]> =>
  simulateLatency(ensureScenarioCache().scenarios);

/** 获取单个场景详情及态势数据 */
export const getScenarioDetail = async (scenarioId: ScenarioId): Promise<ScenarioDetail> =>
  simulateLatency(ensureScenarioCache().scenarioDetails[scenarioId]);

/** 获取全局态势概览 */
export const getGlobalOverview = async (): Promise<GlobalOverview> =>
  simulateLatency(ensureScenarioCache().globalOverview);

/** 获取数据集列表，支持按场景筛选 */
export const getDatasetList = async (scenarioId?: ScenarioId): Promise<Dataset[]> => {
  const all = ensureScenarioCache().datasets;
  return simulateLatency(scenarioId ? all.filter((d) => d.scenario_id === scenarioId) : all);
};

/** 获取数据集字段详情 */
export const getDatasetFields = async (datasetId: string): Promise<DatasetField[]> => {
  const ds = ensureScenarioCache().datasets.find((d) => d.dataset_id === datasetId);
  return simulateLatency(ds?.fields ?? []);
};

/** 获取态势分析数据 */
export const getSituationData = async (scenarioId: ScenarioId): Promise<SituationData> =>
  simulateLatency(ensureScenarioCache().situationData[scenarioId]);

/** 获取报告列表 */
export const getReportList = async (): Promise<Report[]> =>
  simulateLatency(ensureScenarioCache().reports);

/** 获取全平台风险事件列表（跨场景聚合） */
export const getRiskEvents = async (): Promise<RiskEvent[]> => {
  const cache = ensureScenarioCache();
  const all: RiskEvent[] = [];
  for (const meta of SCENARIO_META) {
    if (meta.id === 'flightdeck_operation') continue;
    const detail = cache.scenarioDetails[meta.id];
    if (detail) all.push(...detail.recent_events);
  }
  all.sort((a, b) => b.occurred_at.localeCompare(a.occurred_at));
  return simulateLatency(all);
};

// ===================== 新增页面 Mock 数据 =====================

/** 模型版本记录（扩展字段供展示用） */
export interface ModelVersionRecord {
  model_id: string;
  scenario_id: ScenarioId;
  dataset_name: string;
  algo_type: string;
  discrete_method: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  g_mean: number;
  train_time_s: number;
  status: 'running' | 'stopped' | 'error';
  created_at: string;
  updated_at: string;
}

/** 生成模型版本列表 */
const generateModelVersions = (): ModelVersionRecord[] =>
  SCENARIO_META.flatMap((meta) =>
    Array.from({ length: random(2, 4) }, (_, i) => ({
      model_id: `MOD-${meta.id}-${String(i + 1).padStart(3, '0')}`,
      scenario_id: meta.id,
      dataset_name: sample(meta.datasets).name,
      algo_type: sample(['PMWNB', 'naive_bayes', 'bayesian_network'] as const),
      discrete_method: sample(['equal_width', 'equal_freq'] as const),
      accuracy: Number((Math.random() * 0.15 + 0.82).toFixed(4)),
      precision: Number((Math.random() * 0.15 + 0.80).toFixed(4)),
      recall: Number((Math.random() * 0.15 + 0.78).toFixed(4)),
      f1: Number((Math.random() * 0.12 + 0.80).toFixed(4)),
      g_mean: Number((Math.random() * 0.12 + 0.79).toFixed(4)),
      train_time_s: Number((Math.random() * 10 + 2).toFixed(1)),
      status: sample(['running', 'stopped', 'stopped', 'error'] as const),
      created_at: `2026-0${random(3, 6)}-${String(random(1, 28)).padStart(2, '0')} ${String(random(8, 18)).padStart(2, '0')}:00`,
      updated_at: `2026-0${random(5, 7)}-${String(random(1, 28)).padStart(2, '0')} ${String(random(8, 18)).padStart(2, '0')}:00`,
    }))
  );

/** 获取模型版本列表 */
export const getModelVersions = async (): Promise<ModelVersionRecord[]> =>
  simulateLatency(generateModelVersions());

/** 推理结果 */
export interface InferenceResult {
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_probability: number;
  original_label: string;
  risk_type: string;
  recommendation: string;
  model_used: string;
}

/** 执行风险推理 — 接受动态输入特征 */
export const getInferenceResult = async (_input: Record<string, unknown>): Promise<InferenceResult> =>
  simulateLatency({
    risk_level: sample(['HIGH', 'MEDIUM', 'LOW'] as const),
    risk_probability: Number((Math.random() * 0.6 + 0.2).toFixed(2)),
    original_label: sample(['normal', 'anomaly', '0', '1'] as const),
    risk_type: sample(['NETWORK_SECURITY_RISK', 'POWER_SYSTEM_RISK'] as const),
    recommendation: sample(['立即隔离源地址', '加强访问控制', '持续监控', '无需处理'] as const),
    model_used: `PMWNB-${sample(['v2.1', 'v2.3', 'v3.0'])}`,
  });

/** 模型训练结果 */
export interface TrainResult {
  accuracy: number;
  recall: number;
  f1: number;
  g_mean: number;
  train_time_s: number;
  algo_type: string;
  discrete_method: string;
}

/** 执行模型训练 — 接收场景/数据集/算法参数 */
export const trainModel = async (params: {
  scenario_id: ScenarioId;
  dataset_id: string;
  algo_type: string;
  discrete_method: string;
}): Promise<TrainResult> =>
  simulateLatency({
    accuracy: Number((Math.random() * 0.12 + 0.85).toFixed(4)),
    recall: Number((Math.random() * 0.15 + 0.78).toFixed(4)),
    f1: Number((Math.random() * 0.12 + 0.80).toFixed(4)),
    g_mean: Number((Math.random() * 0.12 + 0.79).toFixed(4)),
    train_time_s: Number((Math.random() * 8 + 2).toFixed(1)),
    algo_type: params.algo_type,
    discrete_method: params.discrete_method,
  });
