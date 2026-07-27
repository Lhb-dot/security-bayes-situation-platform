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
    // 贝叶斯模型输入流量特征，本地mock随机生成演示，后端对接后替换为采集真实数据
    // 归一化 0 ~ 1 浮点数，和模型输入维度完全对应
    flowLength: Number(Math.random().toFixed(2)),
    duration: Number(Math.random().toFixed(2)),
    accessFreq: Number(Math.random().toFixed(2)),
    scenario_id: sample(SCENARIO_META).id,
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

/** 三个场景元信息定义 */
const SCENARIO_META: Array<{
  id: ScenarioId;
  name: string;
  description: string;
  risk_level: Scenario['risk_level'];
  datasets: { name: string; desc: string; format: Dataset['data_format']; fields: Omit<DatasetField, 'nullable'>[] }[];
  risk_types: string[];
}> = [
  {
    id: 'network_security',
    name: '网络安全态势感知',
    description: '识别网络流量中的各类攻击行为，包括 DoS、Probe、R2L、Exploit 等多种攻击类型检测',
    risk_level: 'high',
    datasets: [
      {
        name: 'KDD Cup 1999',
        desc: '经典网络入侵检测数据集，包含 41 维特征',
        format: 'csv',
        fields: [
          { field_name: 'duration', field_type: 'float', description: '连接持续时间', sample_value: '0.0' },
          { field_name: 'protocol_type', field_type: 'string', description: '协议类型 (tcp/udp/icmp)', sample_value: 'tcp' },
          { field_name: 'service', field_type: 'string', description: '目标服务类型', sample_value: 'http' },
          { field_name: 'flag', field_type: 'string', description: '连接状态标志', sample_value: 'SF' },
          { field_name: 'src_bytes', field_type: 'int', description: '源到目标字节数', sample_value: '486' },
          { field_name: 'dst_bytes', field_type: 'int', description: '目标到源字节数', sample_value: '0' },
          { field_name: 'count', field_type: 'int', description: '过去2秒内相同目标连接数', sample_value: '1' },
          { field_name: 'label', field_type: 'string', description: '攻击类型标签', sample_value: 'normal' },
        ],
      },
      {
        name: 'NSL-KDD',
        desc: 'KDD 改进版本，去除冗余记录，更均衡的训练/测试集',
        format: 'csv',
        fields: [
          { field_name: 'duration', field_type: 'float', description: '连接持续时间', sample_value: '0.0' },
          { field_name: 'protocol_type', field_type: 'string', description: '协议类型', sample_value: 'tcp' },
          { field_name: 'service', field_type: 'string', description: '目标服务类型', sample_value: 'private' },
          { field_name: 'flag', field_type: 'string', description: '连接状态标志', sample_value: 'S0' },
          { field_name: 'src_bytes', field_type: 'int', description: '源到目标字节数', sample_value: '0' },
          { field_name: 'dst_bytes', field_type: 'int', description: '目标到源字节数', sample_value: '0' },
          { field_name: 'hot', field_type: 'int', description: '热指标计数', sample_value: '0' },
          { field_name: 'label', field_type: 'string', description: '攻击类型标签', sample_value: 'neptune' },
        ],
      },
      {
        name: 'UNSW-NB15',
        desc: '现代网络攻击数据集，涵盖 9 类最新攻击类型',
        format: 'csv',
        fields: [
          { field_name: 'dur', field_type: 'float', description: '连接持续时间(秒)', sample_value: '0.124' },
          { field_name: 'proto', field_type: 'string', description: '传输协议', sample_value: 'tcp' },
          { field_name: 'service', field_type: 'string', description: '应用层服务', sample_value: 'dns' },
          { field_name: 'state', field_type: 'string', description: '连接状态', sample_value: 'CON' },
          { field_name: 'spkts', field_type: 'int', description: '源发出的数据包数', sample_value: '8' },
          { field_name: 'dpkts', field_type: 'int', description: '目标发出的数据包数', sample_value: '6' },
          { field_name: 'sbytes', field_type: 'int', description: '源发出的字节数', sample_value: '1240' },
          { field_name: 'label', field_type: 'int', description: '0=正常 1=攻击', sample_value: '1' },
        ],
      },
      {
        name: 'CIC-IDS2017',
        desc: '加拿大网络安全研究所入侵检测数据集',
        format: 'csv',
        fields: [
          { field_name: 'flow_duration', field_type: 'float', description: '流持续时间(微秒)', sample_value: '100245' },
          { field_name: 'tot_fwd_pkts', field_type: 'int', description: '正向总数据包数', sample_value: '12' },
          { field_name: 'tot_bwd_pkts', field_type: 'int', description: '反向总数据包数', sample_value: '8' },
          { field_name: 'fwd_pkt_len_mean', field_type: 'float', description: '正向平均包长度', sample_value: '86.5' },
          { field_name: 'bwd_pkt_len_mean', field_type: 'float', description: '反向平均包长度', sample_value: '42.3' },
          { field_name: 'flow_bytes/s', field_type: 'float', description: '每秒流量字节数', sample_value: '2456.78' },
          { field_name: 'label', field_type: 'string', description: '攻击类型', sample_value: 'BENIGN' },
        ],
      },
    ],
    risk_types: ['Normal', 'DoS', 'Probe', 'R2L', 'Exploit'],
  },
  {
    id: 'power_system',
    name: '电力系统风险态势感知',
    description: '识别电力设备异常、负荷过载、停电类风险，保障电网安全稳定运行',
    risk_level: 'medium',
    datasets: [
      {
        name: '电力负荷数据集',
        desc: '包含区域电力负荷历史数据与异常事件标注',
        format: 'csv',
        fields: [
          { field_name: 'timestamp', field_type: 'datetime', description: '采集时间戳', sample_value: '2024-06-01 00:00:00' },
          { field_name: 'load_value', field_type: 'float', description: '当前负荷值(MW)', sample_value: '2350.5' },
          { field_name: 'voltage', field_type: 'float', description: '电压等级(kV)', sample_value: '220.0' },
          { field_name: 'current', field_type: 'float', description: '电流值(A)', sample_value: '185.2' },
          { field_name: 'frequency', field_type: 'float', description: '电网频率(Hz)', sample_value: '50.02' },
          { field_name: 'temperature', field_type: 'float', description: '环境温度(℃)', sample_value: '32.4' },
          { field_name: 'label', field_type: 'string', description: '异常类型标签', sample_value: 'normal' },
        ],
      },
      {
        name: '停电风险数据集',
        desc: '历史停电事件与设备状态记录',
        format: 'csv',
        fields: [
          { field_name: 'device_id', field_type: 'string', description: '设备编号', sample_value: 'SUB-01' },
          { field_name: 'device_type', field_type: 'string', description: '设备类型', sample_value: 'transformer' },
          { field_name: 'temp_rise', field_type: 'float', description: '温升(℃)', sample_value: '15.6' },
          { field_name: 'vibration', field_type: 'float', description: '振动值(mm/s)', sample_value: '2.3' },
          { field_name: 'partial_discharge', field_type: 'float', description: '局部放电量(pC)', sample_value: '120.0' },
          { field_name: 'oil_pressure', field_type: 'float', description: '油压(MPa)', sample_value: '0.35' },
          { field_name: 'label', field_type: 'string', description: '风险标签', sample_value: 'normal' },
        ],
      },
      {
        name: '仿真电力数据集',
        desc: '基于电网仿真模型生成的综合评估数据',
        format: 'csv',
        fields: [
          { field_name: 'sim_time', field_type: 'float', description: '仿真时间步(s)', sample_value: '0.1' },
          { field_name: 'bus_voltage', field_type: 'float', description: '母线电压(p.u.)', sample_value: '1.02' },
          { field_name: 'power_flow', field_type: 'float', description: '潮流值(MW)', sample_value: '120.0' },
          { field_name: 'load_shed', field_type: 'int', description: '甩负荷量(MW)', sample_value: '0' },
          { field_name: 'fault_type', field_type: 'string', description: '故障类型', sample_value: 'none' },
          { field_name: 'relay_status', field_type: 'string', description: '继电器状态', sample_value: 'closed' },
        ],
      },
    ],
    risk_types: ['Normal', 'Overload', 'VoltageAbnormal', 'EquipmentFault', 'OutageRisk'],
  },
  {
    id: 'flightdeck_operation',
    name: '航母甲板保障作业态势感知',
    description: '识别甲板路径冲突、调度拥堵、设备碰撞风险，提升舰载机调度效率',
    risk_level: 'high',
    datasets: [
      {
        name: '甲板轨迹数据集',
        desc: '舰载机甲板移动轨迹记录与冲突标注',
        format: 'csv',
        fields: [
          { field_name: 'aircraft_id', field_type: 'string', description: '舰载机编号', sample_value: 'J-15-01' },
          { field_name: 'timestamp', field_type: 'datetime', description: '记录时间戳', sample_value: '2024-06-01 08:00:00' },
          { field_name: 'position_x', field_type: 'float', description: '甲板X坐标(m)', sample_value: '45.2' },
          { field_name: 'position_y', field_type: 'float', description: '甲板Y坐标(m)', sample_value: '120.8' },
          { field_name: 'speed', field_type: 'float', description: '速度(m/s)', sample_value: '3.2' },
          { field_name: 'heading', field_type: 'float', description: '航向角(°)', sample_value: '45.0' },
          { field_name: 'status', field_type: 'string', description: '当前状态', sample_value: 'taxiing' },
          { field_name: 'label', field_type: 'string', description: '冲突标签', sample_value: 'safe' },
        ],
      },
      {
        name: '调度仿真数据集',
        desc: '多机调度仿真生成的调度冲突与拥堵数据',
        format: 'csv',
        fields: [
          { field_name: 'schedule_id', field_type: 'string', description: '调度任务编号', sample_value: 'SCH-001' },
          { field_name: 'aircraft_type', field_type: 'string', description: '机型', sample_value: 'J-15' },
          { field_name: 'task_type', field_type: 'string', description: '任务类型', sample_value: 'launch' },
          { field_name: 'parking_pos', field_type: 'string', description: '停机位', sample_value: 'A-03' },
          { field_name: 'runway', field_type: 'string', description: '起飞跑道', sample_value: 'RWY-01' },
          { field_name: 'start_time', field_type: 'datetime', description: '任务开始时间', sample_value: '2024-06-01 08:30:00' },
          { field_name: 'priority', field_type: 'int', description: '任务优先级', sample_value: '1' },
          { field_name: 'conflict_flag', field_type: 'int', description: '是否冲突 0/1', sample_value: '0' },
        ],
      },
      {
        name: '设备状态数据集',
        desc: '甲板保障设备运行状态监测数据',
        format: 'csv',
        fields: [
          { field_name: 'eq_id', field_type: 'string', description: '设备编号', sample_value: 'EQ-TR-01' },
          { field_name: 'eq_type', field_type: 'string', description: '设备类型', sample_value: 'tractor' },
          { field_name: 'working', field_type: 'int', description: '是否工作', sample_value: '1' },
          { field_name: 'position_z', field_type: 'float', description: '坐标Z(m)', sample_value: '0.0' },
          { field_name: 'fuel_level', field_type: 'float', description: '油量(%)', sample_value: '78.5' },
          { field_name: 'battery', field_type: 'float', description: '电量(%)', sample_value: '92.3' },
          { field_name: 'error_code', field_type: 'string', description: '故障码', sample_value: 'E000' },
        ],
      },
    ],
    risk_types: ['Safe', 'CollisionRisk', 'PathConflict', 'DeckCongestion'],
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

/** 生成单个场景卡片数据 */
const generateScenarioCard = (meta: typeof SCENARIO_META[number]): Scenario => ({
  scenario_id: meta.id,
  name: meta.name,
  description: meta.description,
  risk_level: meta.risk_level,
  risk_score: random(45, 92),
  event_count: random(30, 180),
  high_risk_count: random(2, 18),
  dataset_count: meta.datasets.length,
  model_count: random(1, 5),
  status: 'active',
});

/** 生成场景详情态势数据 */
const generateScenarioDetail = (meta: typeof SCENARIO_META[number]): ScenarioDetail => ({
  scenario: generateScenarioCard(meta),
  metrics: [
    { id: 'risk-score', label: '当前风险分数', value: random(45, 92), trend: random(-12, 18) },
    { id: 'event-rate', label: '事件发生率', value: `${random(2, 8)}/h`, trend: random(-8, 10) },
    { id: 'model-accuracy', label: '模型检测率', value: `${random(91, 99)}%`, trend: random(1, 5) },
    { id: 'response-time', label: '平均响应时间', value: `${random(3, 15)} min`, trend: -random(2, 8) },
  ],
  trend_data: Array.from({ length: 12 }, (_, i) => ({
    label: `${String(i * 2).padStart(2, '0')}:00`,
    value: random(15, 95),
    blocked: random(5, 60),
    sources: random(3, 20),
    primaryType: sample(meta.risk_types.filter(t => t !== 'Normal')),
  })),
  risk_distribution: meta.risk_types.map((type, i) => ({
    label: type,
    value: type === 'Normal' ? random(30, 55) : random(8, 25),
    color: ['#5ba6ff', '#53e5c8', '#ffd166', '#ff7b72', '#a78bfa'][i % 5],
  })),
  recent_events: Array.from({ length: 5 }, (_, i) => ({
    event_id: `${meta.id.toUpperCase()}-EVT-${String(i + 1).padStart(4, '0')}`,
    scenario_id: meta.id,
    event_type: sample(meta.risk_types.filter(t => t !== 'Normal')),
    risk_level: sample(['critical', 'high', 'medium'] as const),
    risk_probability: Number((Math.random() * 0.5 + 0.4).toFixed(2)),
    title: `${meta.name}风险事件 #${i + 1}`,
    description: `检测到${meta.risk_types.filter(t => t !== 'Normal')[i % (meta.risk_types.length - 1)]}类型异常`,
    source: `source-${i + 1}`,
    timestamp: `2026-07-${String(20 + i).padStart(2, '0')} ${String(random(8, 20)).padStart(2, '0')}:${String(random(0, 59)).padStart(2, '0')}:00`,
    status: sample(['pending', 'processing', 'resolved'] as const),
    raw_features: { indicator: random(0, 100) },
  })),
});

/** 生成全部数据集列表 */
const generateDatasets = (): Dataset[] =>
  SCENARIO_META.flatMap((meta) =>
    meta.datasets.map((ds, i) => ({
      dataset_id: `${meta.id}-ds-${i + 1}`,
      name: ds.name,
      description: ds.desc,
      scenario_id: meta.id,
      record_count: random(10000, 500000),
      field_count: ds.fields.length,
      fields: ds.fields.map((f) => ({ ...f, nullable: false })),
      created_at: `2026-0${random(3, 6)}-${String(random(1, 28)).padStart(2, '0')}`,
      data_format: ds.format,
    }))
  );

/** 生成全局态势概览 */
const generateGlobalOverview = (scenarios: Scenario[]): GlobalOverview => ({
  global_risk_score: Math.round(scenarios.reduce((sum, s) => sum + s.risk_score, 0) / scenarios.length),
  global_risk_level: 'high',
  scenario_count: scenarios.length,
  high_risk_count: scenarios.reduce((sum, s) => sum + s.high_risk_count, 0),
  active_model_count: scenarios.reduce((sum, s) => sum + s.model_count, 0),
  scenarios,
  global_trend: Array.from({ length: 12 }, (_, i) => ({
    label: `${String(i * 2).padStart(2, '0')}:00`,
    value: random(30, 88),
    blocked: random(10, 55),
    sources: random(5, 30),
    primaryType: sample(['DoS', 'Probe', 'Overload', 'CollisionRisk']),
  })),
});

/** 生成态势分析数据 */
const generateSituationData = (meta: typeof SCENARIO_META[number]): SituationData => ({
  scenario_id: meta.id,
  time_range: '24h',
  score_history: Array.from({ length: 24 }, (_, i) => ({
    label: `${String(i).padStart(2, '0')}:00`,
    value: random(30, 90),
    blocked: random(5, 45),
    sources: random(2, 18),
    primaryType: sample(meta.risk_types.filter(t => t !== 'Normal')),
  })),
  event_distribution: meta.risk_types.map((type, i) => ({
    label: type,
    value: type === 'Normal' ? random(40, 60) : random(5, 20),
    color: ['#5ba6ff', '#53e5c8', '#ffd166', '#ff7b72', '#a78bfa'][i % 5],
  })),
  risk_trend: Array.from({ length: 7 }, (_, i) => ({
    label: `第${i + 1}日`,
    value: random(25, 85),
    blocked: random(8, 40),
    sources: random(3, 15),
    primaryType: sample(meta.risk_types.filter(t => t !== 'Normal')),
  })),
  metrics: [
    { id: 'avg-risk', label: '平均风险分数', value: random(40, 80), trend: -random(1, 10) },
    { id: 'peak-risk', label: '峰值风险', value: random(75, 98), trend: random(1, 8) },
    { id: 'event-total', label: '事件总数', value: random(50, 200), trend: random(2, 15) },
  ],
});

/** 生成报告列表 */
const generateReports = (): Report[] =>
  SCENARIO_META.flatMap((meta) =>
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
  risk_level: string;
  risk_probability: number;
  recommendation: string;
  model_used: string;
}

/** 执行风险推理 */
export const getInferenceResult = async (_input: {
  duration: number;
  protocol: string;
  service: string;
  src_bytes: number;
  dst_bytes: number;
}): Promise<InferenceResult> =>
  simulateLatency({
    risk_level: sample(['严重', '高危', '中危', '低危'] as const),
    risk_probability: Number((Math.random() * 0.6 + 0.2).toFixed(2)),
    recommendation: sample(['立即隔离源地址', '加强访问控制', '持续监控', '无需处理'] as const),
    model_used: `PMWNB-${sample(['v2.1', 'v2.3', 'v3.0'])}`,
  });
