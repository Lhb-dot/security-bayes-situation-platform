/**
 * scenarioAlgorithms.ts — 场景差异化轻量算法（需求第 8 节 / Task 015）
 *
 * 定位（需求 8.5）：贝叶斯二分类"之前 / 之后"的辅助判断层。
 * - 之前（预判）：网络流量 Z-score 突变检测，先筛可疑窗口，减少无效推理调用；
 * - 之后（解释）：设备健康分、滑坡易发性评分、碰撞风险评分，给二分类结果增加可解释的业务上下文。
 *
 * 约定：
 * - 全部为纯函数、确定性计算，无 any / ts-ignore，不依赖 UI；
 * - 输入字段名与 mockApi 数据集正式字段保持一致（大小写兼容变体）；
 * - 这些评分是前端演示用辅助指标，真实判定仍以后端模型输出（risk_score / original_label）为准。
 */
import type { RiskEvent } from '@/types/security';

const toFinite = (value: unknown, fallback = 0): number => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const clamp = (value: number, min: number, max: number): number =>
  Math.min(max, Math.max(min, value));

// ===================== 8.1 网络安全 =====================

export interface ZScoreResult {
  /** 窗口下标 */
  index: number;
  /** 窗口原始值 */
  value: number;
  /** Z 分数（保留 2 位） */
  zScore: number;
  /** |z| >= threshold 判定为突变窗口 */
  anomaly: boolean;
}

/**
 * 滑动窗口 Z-score 突变检测（需求 8.1 流量异常检测）。
 * 对每个窗口，用"除自身外的其余窗口"计算均值与标准差（留一法），
 * 偏离超过 threshold 个标准差即判定为突变。
 */
export function zScoreAnomaly(values: number[], threshold = 2): ZScoreResult[] {
  if (values.length < 3) {
    return values.map((value, index) => ({ index, value, zScore: 0, anomaly: false }));
  }
  return values.map((value, index) => {
    const others = values.filter((_, i) => i !== index);
    const mean = others.reduce((sum, v) => sum + v, 0) / others.length;
    const variance =
      others.reduce((sum, v) => sum + (v - mean) ** 2, 0) / others.length;
    const std = Math.sqrt(variance);
    const zScore = std === 0 ? 0 : (value - mean) / std;
    return {
      index,
      value,
      zScore: Number(zScore.toFixed(2)),
      anomaly: Math.abs(zScore) >= threshold,
    };
  });
}

export interface PortDeviationItem {
  /** 目标端口（L4_DST_PORT） */
  port: string;
  /** 该端口事件条数 */
  count: number;
  /** 均匀基线期望条数（总条数 / 端口数） */
  expected: number;
  /** 偏离倍数（count / expected） */
  deviation: number;
  /** 偏离度评分 0-100（1 倍 = 0 分，>=3 倍 = 100 分） */
  score: number;
  /** 偏离倍数 >= threshold 视为异常端口 */
  anomaly: boolean;
}

/**
 * 协议 / 端口偏离度评分（需求 8.1）。
 * 以当前事件集合中目标端口出现次数相对均匀基线的偏离程度衡量端口异常度，
 * 偏离越大的端口优先进入人工研判。
 */
export function networkPortDeviation(events: RiskEvent[], threshold = 2): PortDeviationItem[] {
  const counts = new Map<string, number>();
  for (const ev of events) {
    const port = ev.raw_features.L4_DST_PORT;
    if (port === undefined || port === null || port === '') continue;
    const key = String(port);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const total = [...counts.values()].reduce((sum, v) => sum + v, 0);
  const distinct = counts.size;
  if (total === 0 || distinct === 0) return [];
  const expected = total / distinct;
  return [...counts.entries()]
    .map(([port, count]) => {
      const deviation = expected === 0 ? 0 : count / expected;
      const score = Math.round(clamp(((deviation - 1) / 2) * 100, 0, 100));
      return {
        port,
        count,
        expected: Number(expected.toFixed(1)),
        deviation: Number(deviation.toFixed(2)),
        score,
        anomaly: deviation >= threshold,
      };
    })
    .sort((a, b) => b.score - a.score);
}

// ===================== 8.2 电力系统 =====================

export type HealthLevel = '优' | '良' | '中' | '差';

export interface DeviceHealthItem {
  /** 设备名（Component） */
  component: string;
  /** 越限事件数 */
  eventCount: number;
  /** 越限率（该设备事件占全部事件比例，%） */
  riskShare: number;
  /** 平均风险评分（risk_score 均值，0-1） */
  avgRiskScore: number;
  /** 健康分 0-100 */
  healthScore: number;
  level: HealthLevel;
}

/**
 * 设备健康度评估（需求 8.2：基于越限率与偏移量的 0-100 健康分）。
 * 健康分 = 100 - 越限率权重(70) - 平均风险评分权重(30)，越高越健康。
 */
export function powerDeviceHealth(events: RiskEvent[]): DeviceHealthItem[] {
  const byComponent = new Map<string, RiskEvent[]>();
  for (const ev of events) {
    const component = ev.raw_features.Component;
    if (component === undefined || component === null || component === '') continue;
    const key = String(component);
    const list = byComponent.get(key) ?? [];
    list.push(ev);
    byComponent.set(key, list);
  }
  const total = events.length;
  return [...byComponent.entries()]
    .map(([component, list]) => {
      const riskShare = total > 0 ? (list.length / total) * 100 : 0;
      const avgRiskScore =
        list.reduce((sum, ev) => sum + toFinite(ev.risk_score), 0) / Math.max(1, list.length);
      const healthScore = Math.round(clamp(100 - riskShare * 0.7 - avgRiskScore * 100 * 0.3, 0, 100));
      const level: HealthLevel =
        healthScore >= 80 ? '优' : healthScore >= 60 ? '良' : healthScore >= 40 ? '中' : '差';
      return {
        component,
        eventCount: list.length,
        riskShare: Number(riskShare.toFixed(1)),
        avgRiskScore: Number(avgRiskScore.toFixed(3)),
        healthScore,
        level,
      };
    })
    .sort((a, b) => b.healthScore - a.healthScore);
}

export interface PowerRiskDetail {
  /** 遥测包丢失率（Sensor_Packet_Loss_%，0-100） */
  packetLoss: number;
  /** 与名义值相对偏差（%，保留 1 位） */
  voltageDeviation: number;
  currentDeviation: number;
  temperatureDeviation: number;
  frequencyDeviation: number;
  /** 加权风险评分 0-100 */
  score: number;
}

/** 电力设备经验名义值（无事件基线时的兜底；实际额定值以后端设备台账为准） */
const POWER_NOMINAL = {
  VoltageLevel_kV: 750,
  CurrentAmp: 180,
  Temperature_C: 32,
  PowerFrequencyHz: 50,
};

/**
 * 电力风险评分模型（需求 8.2：对 Sensor_Packet_Loss_% 与电参量异常做加权风险评分）。
 * 权重：遥测包丢失 30% + 电压偏差 25% + 电流偏差 20% + 温度偏差 15% + 频率偏差 10%。
 * 偏差基准优先取事件集合基线均值（均值偏移口径），集合为空时回退经验名义值。
 */
export function powerRiskScore(ev: RiskEvent, events: RiskEvent[] = []): PowerRiskDetail {
  const baseline = (key: keyof typeof POWER_NOMINAL): number => {
    const values = events
      .map((e) => toFinite(e.raw_features[key]))
      .filter((v) => v > 0);
    if (values.length === 0) return POWER_NOMINAL[key];
    return values.reduce((sum, v) => sum + v, 0) / values.length;
  };
  const deviation = (key: keyof typeof POWER_NOMINAL): number => {
    const reference = baseline(key);
    if (reference === 0) return 0;
    return Math.abs(toFinite(ev.raw_features[key]) - reference) / reference;
  };
  const packetLoss = toFinite(ev.raw_features['Sensor_Packet_Loss_%']);
  const voltageDeviation = deviation('VoltageLevel_kV');
  const currentDeviation = deviation('CurrentAmp');
  const temperatureDeviation = deviation('Temperature_C');
  const frequencyDeviation = deviation('PowerFrequencyHz');
  // 偏差因子：10% 相对偏差即让该因子饱和（100 分），保证典型漂移量级下有区分度
  const factorScore = (deviationPercent: number, weight: number): number =>
    clamp(deviationPercent * 10, 0, 100) * weight;
  const raw =
    clamp(packetLoss, 0, 100) * 0.3 +
    factorScore(voltageDeviation * 100, 0.25) +
    factorScore(currentDeviation * 100, 0.2) +
    factorScore(temperatureDeviation * 100, 0.15) +
    factorScore(frequencyDeviation * 100, 0.1);
  return {
    packetLoss,
    voltageDeviation: Number((voltageDeviation * 100).toFixed(1)),
    currentDeviation: Number((currentDeviation * 100).toFixed(1)),
    temperatureDeviation: Number((temperatureDeviation * 100).toFixed(1)),
    frequencyDeviation: Number((frequencyDeviation * 100).toFixed(1)),
    score: Math.round(clamp(raw, 0, 100)),
  };
}

// ===================== 8.3 地质风险 =====================

export interface GeoSusceptibilityDetail {
  slope: number;
  twi: number;
  spi: number;
  elevation: number;
  dis2fault: number;
  dis2river: number;
  dis2roads: number;
  /** 易发性指数 0-100 */
  score: number;
}

const pickNumber = (features: Record<string, unknown>, keys: string[]): number => {
  for (const key of keys) {
    const value = features[key];
    if (value !== undefined && value !== null && value !== '') {
      const n = Number(value);
      if (Number.isFinite(n)) return n;
    }
  }
  return 0;
};

/**
 * 滑坡易发性评分（需求 8.3：基于地形因子标准化叠加的 0-100 易发性指数）。
 * 兼容多套地质数据集字段命名（dis_raw_data / dis_landslides / dis_causative_factors）。
 */
export function geoSusceptibilityScore(
  features: Record<string, unknown>
): GeoSusceptibilityDetail {
  const slope = pickNumber(features, ['Slope', 'slope']);
  const twi = pickNumber(features, ['TWI', 'twi']);
  const spi = pickNumber(features, ['SPI', 'spi']);
  const elevation = pickNumber(features, ['Elevation', 'elevation', 'DEM']);
  const dis2fault = pickNumber(features, ['Dis2fault', 'dis2fault', 'DF']);
  const dis2river = pickNumber(features, ['Dis2river', 'dis2river', 'DW']);
  const dis2roads = pickNumber(features, ['Dis2roads', 'dis2roads', 'DR']);

  const norm = (value: number, max: number): number => clamp(value / max, 0, 1);
  // 距离因子：越近风险越高（指数衰减）
  const distanceTerm = (distance: number, scale: number): number => 1 - Math.exp(-distance / scale);

  const slopeN = norm(slope, 45) * 0.35;
  const twiN = norm(twi, 15) * 0.25;
  const spiN = norm(spi, 20) * 0.15;
  const elevN = norm(elevation, 3000) * 0.1;
  const faultN = distanceTerm(dis2fault, 500) * 0.1;
  const riverN = distanceTerm(dis2river, 800) * 0.03;
  const roadN = distanceTerm(dis2roads, 800) * 0.02;

  return {
    slope,
    twi,
    spi,
    elevation,
    dis2fault,
    dis2river,
    dis2roads,
    score: Math.round(clamp((slopeN + twiN + spiN + elevN + faultN + riverN + roadN) * 100, 0, 100)),
  };
}

export interface RegionRiskItem {
  eventId: string;
  occurredAt: string;
  /** 易发性评分 0-100 */
  score: number;
  riskLevel: RiskEvent['risk_level'];
}

/** 区域风险排序（需求 8.3：对区域按易发性评分排序，供前端着色 / 排名展示） */
export function geoRegionRanking(events: RiskEvent[]): RegionRiskItem[] {
  return events
    .map((ev) => ({
      eventId: ev.event_id,
      occurredAt: ev.occurred_at,
      score: geoSusceptibilityScore(ev.raw_features).score,
      riskLevel: ev.risk_level,
    }))
    .sort((a, b) => b.score - a.score);
}

// ===================== 8.4 航母甲板作业 =====================

export interface CollisionRiskDetail {
  /** 最小间距（m） */
  minDistance: number;
  /** 接近率（dist_change_ratio 绝对值） */
  closureRate: number;
  /** 碰撞风险评分 0-100 */
  score: number;
}

/**
 * 碰撞风险评分（需求 8.4：基于最小间距与接近率的 0-100 风险分）。
 * - 间距项：<=20m 满分、>=100m 为 0，线性映射；
 * - 接近率项：>=0.25（即 25% 距离变化率）满分；
 * - 综合分 = 间距 60% + 接近率 40%。
 */
export function collisionRiskScore(minDistance: number, closureRate: number): CollisionRiskDetail {
  const distScore = clamp(((100 - minDistance) / 80) * 100, 0, 100);
  const closureScore = clamp((closureRate / 0.25) * 100, 0, 100);
  return {
    minDistance,
    closureRate,
    score: Math.round(distScore * 0.6 + closureScore * 0.4),
  };
}

export interface TrajectoryDeviationDetail {
  plane1Std: number;
  plane2Std: number;
  relativeStd: number;
  distStd: number;
  /** 轨迹偏差评分 0-100 */
  score: number;
}

/**
 * 轨迹偏差检测（需求 8.4：与正常轨迹基线统计量的偏差评分）。
 * 以方向角 / 相对角 / 间距统计标准差相对经验基线的占比加权。
 */
export function trajectoryDeviationScore(ev: RiskEvent): TrajectoryDeviationDetail {
  const plane1Std = toFinite(ev.raw_features.Plane1_dir_std_deg);
  const plane2Std = toFinite(ev.raw_features.Plane2_dir_std_deg);
  const relativeStd = toFinite(ev.raw_features.relative_angle_std_deg);
  const distStd = toFinite(ev.raw_features.inter_dist_std);
  const norm = (value: number, max: number): number => clamp(value / max, 0, 1);
  const raw =
    norm(plane1Std, 20) * 0.25 +
    norm(plane2Std, 20) * 0.25 +
    norm(relativeStd, 20) * 0.25 +
    norm(distStd, 30) * 0.25;
  return {
    plane1Std,
    plane2Std,
    relativeStd,
    distStd,
    score: Math.round(clamp(raw * 100, 0, 100)),
  };
}
