import type { CountItem, FlightdeckProfile, GeologicalProfile, NetworkProfile, PowerProfile, ScenarioProfile, WorkspaceBase } from '@/api/dashboardApi';
import type { ChartOption } from '@/components/charts/chartTypes';

export interface ProfileChartSpec {
  title: string;
  tag: string;
  note: string;
  available: boolean;
  emptyText?: string;
  option: ChartOption;
}
const colors = ['#69b7ff', '#4cdac6', '#efc17a', '#a999ee', '#ed8296', '#8ab9c3', '#6584d9', '#c4c88a'];
const base = (): ChartOption => ({
  animation: false, color: colors, textStyle: { fontFamily: 'Microsoft YaHei, sans-serif', fontSize: 10, color: '#a6bdce' },
  tooltip: { trigger: 'axis', confine: true, backgroundColor: '#0b2335', borderColor: '#33556b', textStyle: { color: '#e0edf6', fontSize: 11 } },
});
const axisLabel = { color: '#8ba8bd', fontSize: 10 };
const compact = (value: number) => Math.abs(value) >= 10000 ? `${+(value / 10000).toFixed(1)}万` : Math.abs(value) >= 1000 ? `${+(value / 1000).toFixed(1)}k` : `${+value.toFixed(2)}`;
export const profileNumber = (value: number | null | undefined, digits = 1) => value == null || !Number.isFinite(value) ? '—' : value.toLocaleString('zh-CN', { maximumFractionDigits: digits });
export const profilePercent = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? '—' : `${(value * 100).toFixed(1)}%`;
const shorten = (value: string) => value.length > 22 ? `${value.slice(0, 20)}…` : value;
// 环图必须保留剩余量，不能把 TOP N 重新归一化成全量比例。
export const composition = (items: CountItem[], total: number | undefined, limit = 5): CountItem[] => {
  const shown = items.slice(0, limit);
  const remainder = total === undefined
    ? items.slice(limit).reduce((sum, item) => sum + item.count, 0)
    : Math.max(0, total - shown.reduce((sum, item) => sum + item.count, 0));
  return remainder > 0 ? [...shown, { value: total === undefined ? '其余已返回类别' : '其余 / 缺失', count: remainder }] : shown;
};
export function bars(title: string, items: CountItem[], note: string, color = colors[0]!, percent = false): ProfileChartSpec {
  return {
    title, tag: percent ? 'RATE / %' : 'DISTRIBUTION', note, available: items.length > 0,
    option: {
      ...base(), grid: { top: 10, bottom: 14, left: 8, right: 34, containLabel: true },
      xAxis: { type: 'value', minInterval: !percent && items.every(item => Number.isInteger(item.count)) ? 1 : undefined, splitNumber: 4, max: percent ? 100 : undefined, axisLabel: { ...axisLabel, formatter: compact }, splitLine: { lineStyle: { color: '#82b4cf12' } } },
      yAxis: { type: 'category', inverse: true, data: items.map(i => i.value), axisLabel: { ...axisLabel, interval: 0, formatter: shorten, width: 105, overflow: 'truncate' }, axisTick: { show: false }, axisLine: { show: false } },
      series: [{ type: 'bar', barMaxWidth: 13, data: items.map(i => i.count), showBackground: true, backgroundStyle: { color: '#729eba0b', borderRadius: 2 }, itemStyle: { color, borderRadius: [0, 3, 3, 0] }, label: { show: true, position: 'right', color: '#c4dbea', fontSize: 10, formatter: p => `${compact(Number(p.value))}${percent ? '%' : ''}` } }],
    },
  };
}
export function donut(title: string, items: CountItem[], note: string): ProfileChartSpec {
  const available = items.some(i => i.count > 0);
  return {
    title, tag: 'COMPOSITION', note, available,
    option: {
      ...base(), tooltip: { ...base().tooltip, trigger: 'item' },
      legend: { orient: 'vertical', right: 0, top: 'middle', itemWidth: 6, itemHeight: 6, itemGap: 7, textStyle: { color: '#acc2d3', fontSize: 10 }, formatter: name => `${shorten(name)}  ${profileNumber(items.find(i => i.value === name)?.count)}` },
      series: [{ type: 'pie', radius: ['48%', '70%'], center: ['29%', '50%'], avoidLabelOverlap: true, label: { show: false }, labelLine: { show: false }, itemStyle: { borderColor: '#0b2032', borderWidth: 3 }, data: items.map(i => ({ name: i.value, value: i.count })), emphasis: { label: { show: true, position: 'center', formatter: '{d}%', fontSize: 19, color: '#e0f2ff' } } }],
    },
  };
}
function line(title: string, labels: string[], values: Array<number | null>, note: string, second?: Array<number | null>): ProfileChartSpec {
  return {
    title, tag: second ? 'LAST 10 DAYS' : 'PROFILE CURVE', note, available: values.some(v => v !== null),
    option: {
      ...base(), grid: { left: 12, right: 14, top: second ? 28 : 22, bottom: 10, containLabel: true },
      legend: second ? { top: 0, right: 4, itemHeight: 5, itemWidth: 12, textStyle: axisLabel } : undefined,
      xAxis: { type: 'category', data: labels, boundaryGap: false, axisLabel, axisLine: { lineStyle: { color: '#52799144' } }, axisTick: { show: false } },
      yAxis: { type: 'value', splitNumber: 3, axisLabel: { ...axisLabel, formatter: compact }, splitLine: { lineStyle: { color: '#82b4cf16', type: 'dashed' } } },
      series: [{ type: 'line', name: second ? '推理量' : '平均间距', data: values, smooth: true, symbolSize: 4, showSymbol: values.length < 15, lineStyle: { width: 2 }, areaStyle: { color: '#69b7ff16' }, connectNulls: false }, ...(second ? [{ type: 'line' as const, name: '风险判定', data: second, smooth: true, symbolSize: 4, lineStyle: { width: 2 }, areaStyle: { color: '#4cdac612' } }] : [])],
    },
  };
}

export function scenarioCharts(data: ScenarioProfile): { left: [ProfileChartSpec, ProfileChartSpec]; main: ProfileChartSpec; right: ProfileChartSpec } {
  if (data.scenario_key === 'network') {
    const d = data as NetworkProfile;
    return {
      left: [donut('网络协议构成', d.protocol_distribution, 'NF-UNSW · 协议字段有效记录'), bars('目的端口 TOP 6', d.top_ports.slice(0, 6), 'NF-UNSW · 按连接样本数排序')],
      main: bars('流量维度 · 数据覆盖全景', d.dimension_coverage.map(i => ({ value: i.dimension, count: i.datasets.length })), '各维度具备对应字段的数据集数；悬停查看覆盖数量', '#69b7ff'),
      right: bars('应用服务 TOP 5', d.services.slice(0, 5), 'KDD · 服务字段有效记录', '#a999ee'),
    };
  }
  if (data.scenario_key === 'power') {
    const d = data as PowerProfile;
    // 量纲各异的电参量采用独立纵轴小图，避免把 V / A / Hz 混在同一刻度。
    const available = d.params.filter(i => i.stats !== null);
    const main: ProfileChartSpec = {
      title: '电参量基线 · 遥测全景', tag: 'TELEMETRY BASELINE', note: '各参量独立刻度 · 柱为均值，横线为最小值与最大值；单位见标题', available: available.length > 0,
      option: {
        ...base(), tooltip: { trigger: 'item', confine: true },
        title: available.map((p, i) => ({ text: `${p.name} / ${p.unit || '无量纲'}`, left: `${(i + .5) / available.length * 100}%`, top: 4, textAlign: 'center', textStyle: { color: '#a9c4d5', fontSize: 10, fontWeight: 'normal' } })),
        grid: available.map((_, i) => ({ left: `${(i + .16) / available.length * 100}%`, width: `${.68 / available.length * 100}%`, top: 40, bottom: 32, containLabel: true })),
        xAxis: available.map((_, i) => ({ type: 'category' as const, gridIndex: i, data: ['均值'], axisLabel, axisTick: { show: false }, axisLine: { lineStyle: { color: '#55758c44' } } })),
        yAxis: available.map((_, i) => ({ type: 'value' as const, gridIndex: i, axisLabel: { ...axisLabel, fontSize: 9, formatter: compact }, splitLine: { lineStyle: { color: '#82b4cf12' } } })),
        series: available.map((p, i) => ({ type: 'bar' as const, name: `${p.name} (${p.unit})`, xAxisIndex: i, yAxisIndex: i, data: [p.stats!.mean], barMaxWidth: 22, itemStyle: { color: colors[i % colors.length], borderRadius: [3, 3, 0, 0] }, label: { show: true, position: 'top' as const, fontSize: 10, color: '#e0edf6', formatter: () => profileNumber(p.stats!.mean, 2) }, markLine: { symbol: 'none', silent: true, label: { show: false }, lineStyle: { color: '#b7ccdc66', type: 'dashed' as const }, data: [{ yAxis: p.stats!.min }, { yAxis: p.stats!.max }] } })),
      },
    };
    return { left: [donut('问题类型构成', composition(d.issues, d.sample_count), '去重全量样本 · IssueType，含非故障样本'), bars('设备故障率', d.device_fault_rates.slice(0, 6).map(i => ({ value: i.value, count: +(i.risk_rate * 100).toFixed(1) })), '各设备登记正类数 / 该设备样本数', '#ed8296', true)], main, right: bars('系统样本分布 TOP 5', d.systems.slice(0, 5), '去重代表数据集 · SystemName', '#4cdac6') };
  }
  if (data.scenario_key === 'flight_deck') {
    const d = data as FlightdeckProfile;
    return {
      left: [bars('最小间距 · 分类对照', [{ value: '碰撞样本', count: d.collision_comparison.collision.mean_min_distance ?? 0 }, { value: '正常样本', count: d.collision_comparison.normal.mean_min_distance ?? 0 }].filter((_, i) => (i === 0 ? d.collision_comparison.collision : d.collision_comparison.normal).mean_min_distance !== null), '数值原始集 · 各类别最小间距均值，原始单位', '#efc17a'), bars('双机航程对照', [{ value: '飞机 1', count: d.total_distance.plane1_mean ?? 0 }, { value: '飞机 2', count: d.total_distance.plane2_mean ?? 0 }].filter((_, i) => (i === 0 ? d.total_distance.plane1_mean : d.total_distance.plane2_mean) !== null), '数值原始集 · 两机总航程均值，原始单位', '#69b7ff')],
      main: line('双机间距 · 50 步全程剖面', d.distance_curve.map(i => `${i.step}`), d.distance_curve.map(i => i.mean), '数值原始集 · 横轴为采样步，纵轴为全样本平均间距（原始单位）；非实时航迹'),
      right: bars('航向与相对角', [{ value: '飞机 1 航向', count: d.direction.plane1.mean ?? 0 }, { value: '飞机 2 航向', count: d.direction.plane2.mean ?? 0 }, { value: '平均相对角', count: d.relative_angle.mean ?? 0 }].filter((_, i) => [d.direction.plane1.mean, d.direction.plane2.mean, d.relative_angle.mean][i] != null), '数值原始集 · 角度算术均值 / °', '#a999ee'),
    };
  }
  const d = data as GeologicalProfile;
  return {
    left: [donut('灾害诱因构成', composition(d.catalog_distribution.trigger, d.datasets.find(i => i.logical_id === 'dis_global_catalog')?.record_count), '全球灾害编目 · 非风险事件统计'), bars('灾害类型 TOP 5', d.catalog_distribution.category.slice(0, 5), '全球灾害编目 · 类型字段有效记录', '#a999ee')],
    main: bars('地形因子 · 跨数据集覆盖', d.factor_coverage.map(i => ({ value: i.factor, count: i.datasets.length })), '每项表示含该因子字段的数据集数；分箱一致性见下方数据职责', '#a999ee'),
    right: bars('编目国家 TOP 5', d.catalog_distribution.country.slice(0, 5), '全球灾害编目 · 国家字段有效记录', '#efc17a'),
  };
}

export function modelingChart(data: ScenarioProfile): ProfileChartSpec {
  const rows = data.modeling.slice(0, 6);
  const chart = bars('数据集建模覆盖', rows.map(i => ({ value: i.logical_id, count: i.total })), '前 6 个数据集 · 未发布含草稿、训练中及停用等状态');
  chart.tag = 'MODEL COVERAGE';
  chart.option.grid = { left: 8, right: 12, top: 28, bottom: 16, containLabel: true };
  chart.option.legend = { top: 0, right: 0, itemWidth: 7, itemHeight: 7, textStyle: axisLabel };
  chart.option.series = [
    { name: '已发布', type: 'bar', stack: 'models', data: rows.map(i => i.published), barMaxWidth: 13, itemStyle: { color: '#4cdac6' } },
    { name: '未发布', type: 'bar', stack: 'models', data: rows.map(i => i.draft), barMaxWidth: 13, itemStyle: { color: '#6385a7' } },
  ];
  return chart;
}
export function runtimeCharts(runtime: WorkspaceBase | null): [ProfileChartSpec, ProfileChartSpec] {
  const s = runtime?.summary;
  const scope = runtime?.scope.self_only ? '当前账号在本场景' : '当前场景全部';
  const events = donut('风险事件处置分布', s ? [{ value: '待处置', count: s.pending }, { value: '处理中', count: s.processing }, { value: '已处置', count: s.resolved }] : [], `${scope}风险事件 · 按处置状态分组`);
  events.emptyText = runtime ? '暂无风险事件' : '运行数据暂不可用';
  const trend = runtime?.activity_trend ?? [];
  const activity = line('近 10 天推理活动', trend.map(i => i.date.slice(5)), trend.map(i => i.total), `${scope} · UTC 日期 · 风险判定为推理量子集`, trend.map(i => i.risk));
  activity.emptyText = runtime ? '暂无推理活动' : '运行数据暂不可用';
  return [events, activity];
}

export interface GovernanceRow { name: string; detail: string; status: string; warn: boolean }
export function governanceRows(data: ScenarioProfile): GovernanceRow[] {
  if (data.scenario_key === 'network') return (data as NetworkProfile).caliber_matrix.map(i => ({ name: i.logical_id, detail: `${i.label_field} → ${i.positive_labels.join(' / ') || '未登记正类'}`, status: i.registered ? `已登记${i.deviation == null ? '' : ` · 偏离 ×${i.deviation.toFixed(2)}`}` : '未登记 · 不产事件', warn: !i.registered }));
  if (data.scenario_key === 'power') return (data as PowerProfile).telemetry_by_dataset.map(i => ({ name: i.logical_id, detail: `工频合格 ${profilePercent(i.frequency_pass_rate)} · 遥测丢包 ${i.packet_loss_mean == null ? '—' : `${profileNumber(i.packet_loss_mean, 2)}%`}`, status: i.baseline_ok ? '均值基线通过' : i.violations.join(' / '), warn: !i.baseline_ok }));
  if (data.scenario_key === 'flight_deck') {
    const labels = { numeric: '数值连续', interval: '离散区间', paired: '配对轨迹', unknown: '未知编码' };
    return (data as FlightdeckProfile).encoding_family.map(i => ({ name: i.logical_id, detail: `${labels[i.encoding]} · 内容组 ${data.groups.findIndex(g => g.group_id === i.source_group) + 1 || '未分组'}`, status: i.collision_consistent ? '正类与组代表一致' : '正类不一致', warn: !i.collision_consistent }));
  }
  return (data as GeologicalProfile).roles.map(i => ({ name: i.logical_id, detail: `${i.role} · ${i.label_field}`, status: i.produces_risk_events ? '已登记风险口径' : '背景数据 · 不产事件', warn: !i.produces_risk_events && !['全球编目表', '随机基线集'].includes(i.role) }));
}
