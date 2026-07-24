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
  };
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
