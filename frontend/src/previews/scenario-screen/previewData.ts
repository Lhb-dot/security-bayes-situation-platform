/** 独立设计预览的演示数据；字段受现有后端约束，数值仅用于排版，不发出业务请求。 */
import type { DatasetStat, ScenarioProfile, WorkspaceBase } from '@/api/dashboardApi';
const dataset = (logical_id: string, record_count: number, attribute_count: number, risk_rate: number, label_field: string, group: string): DatasetStat => ({
  dataset_id: 0, logical_id, version: 1, label_field, is_risk_label: true, record_count,
  risk_count: Math.round(record_count * risk_rate), risk_rate, attribute_count, field_names: [], visibility: 'platform',
  uploader_role: 'SUPER_ADMIN', uploaded_at: null, source_group: group, content_fingerprint: group,
  positive_labels: ['1'], label_values: ['0', '1'], label_kind: 'binary', caliber_registered: true,
});
const stats = (mean: number, min: number, max: number) => ({ mean, min, max, median: mean, std: (max - min) / 6, range: max - min, count: 2000 });
const count = (pairs: Array<[string, number]>) => pairs.map(([value, count]) => ({ value, count }));
function base(key: string, name: string, datasets: DatasetStat[]) {
  const groups = [...new Set(datasets.map(i => i.source_group))].map(group_id => {
    const files = datasets.filter(i => i.source_group === group_id);
    return { group_id, datasets: files.map(i => i.logical_id), record_count: files[0]!.record_count, deduplicated: files.length > 1, file_count: files.length, fingerprint: group_id };
  });
  const sample_count = groups.reduce((n, g) => n + g.record_count, 0);
  const risk_count = groups.reduce((n, g) => n + datasets.find(i => i.source_group === g.group_id)!.risk_count, 0);
  return { scenario_id: 0, scenario_code: key, scenario_key: key, scenario_name: name, access_status: 'ACTUAL', risk_type: key, dataset_count: groups.length, dataset_file_count: datasets.length, sample_count, risk_count, risk_rate: risk_count / sample_count,
    datasets, groups, modeling: datasets.map((i, index) => ({ logical_id: i.logical_id, published: [2, 1, 0, 1, 0][index] ?? 0, draft: [1, 2, 1, 0, 0][index] ?? 0, total: [3, 3, 1, 1, 0][index] ?? 0 })) };
}
const networkBase = base('network', '网络安全态势', [dataset('kdd_train_20', 7556, 42, .46, 'class', 'kdd'), dataset('nf_unsw_nb15', 23897, 42, .31, 'Label', 'nf')]);
const network = { ...networkBase,
  protocol_distribution: count([['TCP', 16832], ['UDP', 5820], ['ICMP', 1245]]), protocol_total: 23897, distinct_port_count: 1486,
  top_ports: count([['443', 7612], ['80', 5291], ['53', 3428], ['22', 1820], ['445', 1246], ['3389', 863]]),
  flags: count([['SF', 5122], ['S0', 1286], ['REJ', 713]]), services: count([['http', 2834], ['private', 1926], ['domain_u', 1108], ['smtp', 842], ['ftp_data', 416]]), flow_segments: [],
  traffic: { avg_in_bytes: 3824, avg_retrans_in_bytes: 86, retransmission_ratio: .022, in_bytes_stats: null, retrans_stats: null },
  caliber_matrix: networkBase.datasets.map(i => ({ logical_id: i.logical_id, name: i.logical_id, label_field: i.label_field, positive_labels: i.logical_id.startsWith('kdd') ? ['anomaly'] : ['1'], label_values: ['0', '1'], label_kind: 'binary', record_count: i.record_count, risk_count: i.risk_count, risk_rate: i.risk_rate, deviation: i.risk_rate / networkBase.risk_rate, registered: true })),
  dimension_coverage: [{ dimension: '协议', key: 'PROTOCOL', datasets: ['nf_unsw_nb15'] }, { dimension: '目的端口', key: 'L4_DST_PORT', datasets: ['nf_unsw_nb15'] }, { dimension: '包长分布', key: 'NUM_PKTS_UP_TO_128_BYTES', datasets: ['nf_unsw_nb15'] }, { dimension: '连接状态', key: 'flag', datasets: ['kdd_train_20'] }, { dimension: '应用服务', key: 'service', datasets: ['kdd_train_20'] }],
};
const powerBase = base('power', '电力系统态势', [dataset('powergrid_knowledge', 2000, 10, .274, 'Target_Event', 'power'), dataset('powergrid_knowledge_copy', 2000, 10, .274, 'Target_Event', 'power')]);
const powerParams = [
  { key: 'VoltageLevel_kV', name: '电压', unit: 'kV', stats: stats(508.6, 310.2, 696.7) },
  { key: 'CurrentAmp', name: '电流', unit: 'A', stats: stats(940.2, 408.1, 1598.2) },
  { key: 'Temperature_C', name: '温度', unit: '℃', stats: stats(63.4, 31.2, 89.7) },
  { key: 'PowerFrequencyHz', name: '频率', unit: 'Hz', stats: stats(50.02, 49.62, 50.41) },
  { key: 'Sensor_Packet_Loss_%', name: '遥测丢包率', unit: '%', stats: stats(.64, 0, 2.8) },
];
const power = { ...powerBase, params: powerParams, fault_count: 548, fault_rate: .274,
  issues: count([['过载', 516], ['电压波动', 435], ['设备老化', 381], ['通信异常', 346], ['其他', 322]]), components: count([['变压器', 528], ['断路器', 436], ['继电器', 389], ['传感器', 347], ['母线', 300]]), systems: count([['输电系统', 682], ['配电系统', 546], ['变电系统', 432], ['监测系统', 340]]),
  device_fault_rates: [{ value: '变压器', count: 528, risk_count: 180, risk_rate: .341 }, { value: '断路器', count: 436, risk_count: 132, risk_rate: .303 }, { value: '继电器', count: 389, risk_count: 105, risk_rate: .27 }, { value: '传感器', count: 347, risk_count: 76, risk_rate: .219 }, { value: '母线', count: 300, risk_count: 55, risk_rate: .183 }],
  telemetry_by_dataset: powerBase.datasets.map(i => ({ logical_id: i.logical_id, name: i.logical_id, record_count: i.record_count, params: powerParams.map(p => ({ key: p.key, name: p.name, unit: p.unit, mean: p.stats.mean })), frequency_pass_rate: .968, packet_loss_mean: .64, baseline_ok: true, violations: [] })), component_matrix: [],
};
const flightBase = base('flight_deck', '航母甲板保障作业', [dataset('carrier_feature2_biaoqian', 507, 280, .231, 'Collision', 'numeric'), dataset('carrier_feature2_lisan', 507, 280, .231, 'Collision', 'interval'), dataset('carrier_paired_trail', 507, 282, .231, 'Collision', 'paired')]);
const flight = { ...flightBase, collision_count: 117, collision_rate: .231,
  distance: { min: stats(18.72, 1.2, 54.8), mean: stats(43.2, 8.1, 90.2), median: null, std: null, range: null },
  approach: { abs_change_ratio_mean: .36, change_ratio_mean: -.21 }, total_distance: { plane1_mean: 218.6, plane2_mean: 196.3, diff_mean: 22.3 },
  direction: { plane1: { mean: 68.5, std: 12.8, stats: null }, plane2: { mean: 112.4, std: 16.2, stats: null } }, relative_angle: { mean: 43.9, max: 128.3 },
  distance_curve: Array.from({ length: 50 }, (_, i) => ({ step: i + 1, mean: +(72 - 53 * Math.sin(i / 49 * Math.PI) + 3 * Math.cos(i / 5)).toFixed(2) })),
  collision_comparison: { collision: { count: 117, mean_min_distance: 8.3 }, normal: { count: 390, mean_min_distance: 21.8 } },
  encoding_family: flightBase.datasets.map((i, index) => ({ logical_id: i.logical_id, name: i.logical_id, source_group: i.source_group, encoding: ['numeric', 'interval', 'paired'][index], attribute_count: i.attribute_count, record_count: i.record_count, risk_count: i.risk_count, collision_consistent: true, published_model_count: flightBase.modeling[index]!.published })),
  redundancy: { file_count: 3, effective_group_count: 3, redundancy_rate: 0, raw_samples: 1521, deduped_samples: 1521 },
};
const geologicalBase = base('geological', '滑坡灾害态势', [dataset('dis_raw_data', 5000, 20, .314, 'Label', 'raw'), dataset('dis_landslides', 5185, 10, .38, 'LS', 'landslides'), dataset('dis_causative_factors', 5000, 14, .268, 'landslides', 'causative'), { ...dataset('dis_global_catalog', 1000, 13, 0, 'landslide_size', 'catalog'), is_risk_label: false, caliber_registered: false, positive_labels: [] }, dataset('dis_guaruja_random', 200, 9, .19, 'class', 'random')]);
const factors = ['Slope', 'TWI', 'Elevation', 'Relief', 'SPI', 'Dis2roads', 'Dis2fault', 'Dis2river'];
const geological = { ...geologicalBase, factor_count: 8, factors: factors.map(value => ({ value, mean: 1, stats: stats(1, 0, 2) })),
  catalog_distribution: { trigger: count([['降雨', 564], ['持续降雨', 218], ['地震', 92], ['融雪', 64], ['其他', 62]]), category: count([]), size: count([['小型', 486], ['中型', 362], ['大型', 152]]), country: count([['中国', 286], ['印度', 218], ['美国', 174], ['尼泊尔', 142], ['巴西', 98]]) },
  roles: geologicalBase.datasets.map((i, index) => ({ logical_id: i.logical_id, name: i.logical_id, role: ['因子表', '风险标签表', '致灾因子表', '全球编目表', '随机基线集'][index], attribute_count: i.attribute_count, label_field: i.label_field, label_kind: i.label_kind, participates_in_training: geologicalBase.modeling[index]!.total > 0, produces_risk_events: i.caliber_registered, record_count: i.record_count, risk_rate: i.risk_rate })),
  factor_coverage: factors.map((factor, i) => ({ factor, datasets: geologicalBase.datasets.slice(0, [4, 3, 2, 2, 3, 2, 1, 2][i]).filter(d => d.logical_id !== 'dis_global_catalog').map(d => d.logical_id), consistent_binning: i !== 0 && i !== 4 })),
};
export const previewScenes = [network, power, flight, geological] as unknown as ScenarioProfile[];
export const previewRuntime = (index: number): WorkspaceBase => ({
  scenario_id: 0, scenario_code: '', scenario_key: previewScenes[index]!.scenario_key, scenario_name: '', risk_type: null,
  summary: { total: 180 + index * 24, pending: 24 + index * 3, processing: 38 + index * 2, resolved: 118 + index * 19, today: 8, high_confidence: 12, high_threshold: .8, medium_threshold: .5, avg_risk_score: .64, max_risk_score: .96, score_bins: [], status_funnel: [], daily_trend: [] },
  recent_events: [], scope: { self_only: false, user_id: 0 },
  activity_trend: Array.from({ length: 10 }, (_, i) => ({ date: `2026-10-${String(i + 6).padStart(2, '0')}`, total: [18, 26, 23, 38, 32, 47, 41, 55, 48, 61][i]! + index * 3, risk: [4, 8, 6, 12, 9, 17, 13, 19, 16, 22][i]! + index })),
});
