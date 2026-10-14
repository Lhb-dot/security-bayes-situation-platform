import type { ScenarioKey } from '@/api/dashboardApi';

export type AdminSceneKey = Exclude<ScenarioKey, 'unknown'>;

export interface AdminOverviewScene {
  key: AdminSceneKey;
  name: string;
  path: string;
  userCount: number | null;
  adminCount: number | null;
  datasets: number;
  samples: number;
  riskRate: number | null;
}

export interface AdminOverviewData {
  scenarioCount: number;
  datasetCount: number;
  sampleCount: number;
  algorithmCount: number;
  trainedModels: number | null;
  publishedModels: number;
  inferenceCount: number;
  reportCount: number | null;
  servedUserCount: number | null;
  eventCount: number;
  pendingCount: number;
  processingCount: number;
  resolvedCount: number;
  userCount: number;
  scenes: AdminOverviewScene[];
}

export const SCENE_STYLES = {
  network: { name: '网络安全', english: 'NETWORK SECURITY', color: '#69b7ff', icon: 'network' },
  power: { name: '电力系统', english: 'POWER SYSTEM', color: '#4cdac6', icon: 'power' },
  flight_deck: { name: '航保作业', english: 'AVIATION SUPPORT', color: '#efc17a', icon: 'flight' },
  geological: { name: '滑坡灾害', english: 'LANDSLIDE DISASTER', color: '#a999ee', icon: 'mountain' },
} satisfies Record<AdminSceneKey, { name: string; english: string; color: string; icon: string }>;

const invalid = (): never => { throw new Error('首页接口返回的数据不完整，请稍后重试'); };
const record = (value: unknown): Record<string, unknown> => {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return invalid();
  return value as Record<string, unknown>;
};
const count = (value: unknown): number => {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) return invalid();
  return value;
};
const optionalCount = (value: unknown): number | null => value == null ? null : count(value);
const rate = (value: unknown): number | null => {
  if (value == null) return null;
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) return invalid();
  return value;
};

/** 仅映射接口数据，禁止使用演示值补齐缺失统计；未知可选字段显示「—」。 */
export const mapAdminOverview = (payload: unknown): AdminOverviewData => {
  const response = record(payload);
  const totals = record(response.totals);
  const runtime = record(response.runtime);
  if (!Array.isArray(response.scenarios)) return invalid();
  const sceneRows = new Map<AdminSceneKey, AdminOverviewScene>();
  for (const item of response.scenarios) {
    const row = record(item);
    if (typeof row.code !== 'string' || !row.code.trim()) return invalid();
    const datasets = count(row.dataset_count);
    const samples = count(row.effective_sample_count);
    if (typeof row.scenario_key !== 'string') return invalid();
    if (!Object.hasOwn(SCENE_STYLES, row.scenario_key)) continue;
    const key = row.scenario_key as AdminSceneKey;
    if (sceneRows.has(key)) return invalid();
    sceneRows.set(key, {
      key,
      name: SCENE_STYLES[key].name,
      path: `/scenarios/${encodeURIComponent(row.code)}/dashboard`,
      userCount: optionalCount(row.user_count),
      adminCount: optionalCount(row.admin_count),
      datasets,
      samples,
      riskRate: rate(row.risk_rate),
    });
  }
  return {
    scenarioCount: count(totals.scenario_count),
    datasetCount: count(totals.effective_dataset_count),
    sampleCount: count(totals.effective_sample_count),
    algorithmCount: count(totals.algorithm_count),
    trainedModels: optionalCount(runtime.trained_model_count),
    publishedModels: count(runtime.published_model_count),
    inferenceCount: count(runtime.inference_count),
    reportCount: optionalCount(runtime.report_count),
    servedUserCount: optionalCount(runtime.served_user_count),
    eventCount: count(runtime.risk_event_count),
    pendingCount: count(runtime.pending_event_count),
    processingCount: count(runtime.processing_event_count),
    resolvedCount: count(runtime.resolved_event_count),
    userCount: count(runtime.user_count),
    scenes: (Object.keys(SCENE_STYLES) as AdminSceneKey[]).flatMap((key) => {
      const scene = sceneRows.get(key);
      return scene ? [scene] : [];
    }),
  };
};

/** 大计数使用中文量级，完整精确值由对应链接的 title / aria-label 保留。 */
export const formatOverviewCount = (value: number | null): string => {
  if (value === null) return '—';
  const unit = value >= 1e12 ? { divisor: 1e12, suffix: '万亿' }
    : value >= 1e8 ? { divisor: 1e8, suffix: '亿' }
      : value >= 1e6 ? { divisor: 1e4, suffix: '万' } : null;
  if (!unit) return value.toLocaleString('zh-CN');
  const scaled = value / unit.divisor;
  const decimals = scaled >= 1000 ? 0 : scaled >= 100 ? 1 : 2;
  return `${scaled.toFixed(decimals)}${unit.suffix}`;
};

export const exactOverviewCount = (value: number | null): string => value === null ? '暂无统计数据' : value.toLocaleString('zh-CN');

export const overviewPercentage = (numerator: number | null, denominator: number): number | null =>
  numerator === null || denominator <= 0 || numerator > denominator
    ? null : Math.round(numerator / denominator * 100);

export const sampleMetric = (value: number): { value: string; unit: string } => {
  const scale = value >= 1e12 ? { divisor: 1e12, unit: '万亿条' }
    : value >= 1e8 ? { divisor: 1e8, unit: '亿条' }
      : value >= 1e4 ? { divisor: 1e4, unit: '万条' } : null;
  if (!scale) return { value: value.toLocaleString('zh-CN'), unit: '条' };
  const scaled = value / scale.divisor;
  return { value: scaled.toFixed(scaled >= 1000 ? 0 : 2), unit: scale.unit };
};
