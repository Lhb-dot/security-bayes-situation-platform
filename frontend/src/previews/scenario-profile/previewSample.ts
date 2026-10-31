/**
 * 仅开发预览用的示例数据，不被任何生产页面导入。用于在没有后端时挂起四个看板看版式，
 * 生产页面一律走 /api/v1/dashboard/scenarios/{id}/profile 与 /workspace 的真实返回。
 */
import type {
  DatasetStat,
  FlightdeckProfile,
  GeologicalProfile,
  NetworkProfile,
  PowerProfile,
  WorkspaceBase,
} from '@/api/dashboardApi';
import type { UserAccount } from '@/types/security';

// 数据集示例条目：只覆盖看板真正读到的字段，其余按后端契约给默认值
const dataset = (
  logicalId: string,
  recordCount: number,
  riskCount: number,
  labelField: string,
  attributeCount: number,
  visibility: string,
  version: number,
  caliberRegistered = true,
): DatasetStat => ({
  dataset_id: version,
  logical_id: logicalId,
  name: logicalId,
  version,
  label_field: labelField,
  is_risk_label: caliberRegistered,
  record_count: recordCount,
  risk_count: riskCount,
  risk_rate: recordCount ? riskCount / recordCount : 0,
  attribute_count: attributeCount,
  field_names: [],
  visibility,
  uploader_role: 'SCENARIO_ADMIN',
  uploaded_at: '2026-09-18T10:24:00',
  source_group: `${recordCount}-${logicalId.slice(0, 8)}`,
  content_fingerprint: `${recordCount}-${logicalId.slice(0, 8)}`,
  positive_labels: caliberRegistered ? ['1'] : [],
  label_values: ['0', '1'],
  label_kind: 'binary',
  caliber_registered: caliberRegistered,
});

// 运行态示例：summary 的字段全部给齐（看板只读 total / pending / processing / resolved 与 activity_trend）
const runtime = (scenarioId: number, key: WorkspaceBase['scenario_key'], name: string, total: number, pending: number, processing: number, resolved: number): WorkspaceBase => ({
  scenario_id: scenarioId,
  scenario_code: key === 'flight_deck' ? 'flightdeck_operation' : key === 'network' ? 'network_security' : key === 'power' ? 'power_system' : 'geological_risk',
  scenario_key: key,
  scenario_name: name,
  risk_type: null,
  summary: {
    total,
    pending,
    processing,
    resolved,
    today: Math.max(Math.round(total / 12), 1),
    high_confidence: Math.round(total * 0.32),
    high_threshold: 0.8,
    medium_threshold: 0.6,
    avg_risk_score: 0.74,
    max_risk_score: 0.97,
    score_bins: [
      { label: '0.5-0.7', count: Math.round(total * 0.41) },
      { label: '0.7-0.9', count: Math.round(total * 0.37) },
      { label: '0.9-1.0', count: Math.round(total * 0.22) },
    ],
    status_funnel: [
      { label: '待处置', status: 'PENDING', count: pending },
      { label: '处理中', status: 'PROCESSING', count: processing },
      { label: '已处置', status: 'RESOLVED', count: resolved },
    ],
    daily_trend: [],
  },
  recent_events: [],
  scope: { self_only: false, user_id: 0 },
  activity_trend: Array.from({ length: 10 }, (_, index) => ({
    date: `2026-10-${String(6 + index).padStart(2, '0')}`,
    total: [6, 11, 4, 15, 9, 13, 7, 18, 12, 16][index],
    risk: [1, 3, 1, 4, 2, 5, 2, 6, 4, 5][index],
  })),
});

const member = (id: number, role: UserAccount['role'], scenarioId: number, code: UserAccount['scenario_code'], status: UserAccount['status'] = 'active'): UserAccount => ({
  id,
  user_id: `u${id}`,
  username: `user${id}`,
  display_name: `用户 ${id}`,
  role,
  status,
  created_at: '2026-08-01T09:00:00',
  created_by: 'system',
  scenario_id: scenarioId,
  scenario_code: code,
});

// 网络安全

const networkDatasets = [
  dataset('nf_uq_netflow_v2', 26543, 3120, 'Label', 49, 'platform', 2),
  dataset('kdd_cup_99_train', 4910, 1345, 'class', 41, 'company', 3),
];

export const networkSample: NetworkProfile = {
  scenario_id: 1,
  scenario_code: 'network_security',
  scenario_key: 'network',
  scenario_name: '网络安全',
  access_status: 'active',
  risk_type: '网络入侵',
  dataset_count: 2,
  dataset_file_count: 3,
  sample_count: 31453,
  risk_count: 4465,
  risk_rate: 0.142,
  datasets: networkDatasets,
  groups: [
    { group_id: 'g1', datasets: ['nf_uq_netflow_v2'], record_count: 26543, deduplicated: false, file_count: 2, fingerprint: 'g1' },
    { group_id: 'g2', datasets: ['kdd_cup_99_train'], record_count: 4910, deduplicated: false, file_count: 1, fingerprint: 'g2' },
  ],
  modeling: [
    { logical_id: 'nf_uq_netflow_v2', published: 2, draft: 1, total: 3 },
    { logical_id: 'kdd_cup_99_train', published: 1, draft: 1, total: 2 },
  ],
  protocol_distribution: [],
  protocol_total: 0,
  distinct_port_count: 0,
  top_ports: [],
  flags: [],
  services: [],
  flow_segments: [],
  traffic: { avg_in_bytes: 0, avg_retrans_in_bytes: 0, retransmission_ratio: 0, in_bytes_stats: null, retrans_stats: null },
  caliber_matrix: [
    { logical_id: 'nf_uq_netflow_v2', name: 'nf_uq_netflow_v2', label_field: 'Label', positive_labels: ['1'], label_values: ['0', '1'], label_kind: 'binary', record_count: 26543, risk_count: 3120, risk_rate: 0.1176, deviation: 0.83, registered: true },
    { logical_id: 'kdd_cup_99_train', name: 'kdd_cup_99_train', label_field: 'class', positive_labels: [], label_values: ['normal', 'neptune'], label_kind: 'multiclass', record_count: 4910, risk_count: 1345, risk_rate: 0.2739, deviation: 1.93, registered: false },
  ],
  dimension_coverage: [
    { dimension: '协议', key: 'PROTOCOL', datasets: ['nf_uq_netflow_v2'] },
    { dimension: '目的端口', key: 'L4_DST_PORT', datasets: ['nf_uq_netflow_v2'] },
    { dimension: '包长分布', key: 'NUM_PKTS_UP_TO_128_BYTES', datasets: ['nf_uq_netflow_v2'] },
    { dimension: '连接状态', key: 'flag', datasets: ['kdd_cup_99_train'] },
    { dimension: '应用服务', key: 'service', datasets: ['kdd_cup_99_train'] },
  ],
};

export const networkRuntime = runtime(1, 'network', '网络安全', 148, 12, 6, 130);
export const networkMembers: UserAccount[] = [
  member(2, 'SCENARIO_ADMIN', 1, 'network_security'),
  member(3, 'SCENARIO_USER', 1, 'network_security'),
  member(4, 'SCENARIO_USER', 1, 'network_security'),
  member(5, 'SCENARIO_USER', 1, 'network_security', 'disabled'),
];

// 电力系统

const powerDatasets = [dataset('power_grid_telemetry', 2000, 1594, 'Fault_Label', 38, 'platform', 1)];

export const powerSample: PowerProfile = {
  scenario_id: 2,
  scenario_code: 'power_system',
  scenario_key: 'power',
  scenario_name: '电力系统',
  access_status: 'active',
  risk_type: '设备故障',
  dataset_count: 1,
  dataset_file_count: 1,
  sample_count: 2000,
  risk_count: 1594,
  risk_rate: 0.797,
  datasets: powerDatasets,
  groups: [{ group_id: 'g1', datasets: ['power_grid_telemetry'], record_count: 2000, deduplicated: false, file_count: 1, fingerprint: 'g1' }],
  modeling: [{ logical_id: 'power_grid_telemetry', published: 2, draft: 0, total: 2 }],
  params: [],
  fault_count: 1594,
  fault_rate: 0.797,
  issues: [],
  components: [],
  systems: [],
  device_fault_rates: [],
  telemetry_by_dataset: [
    {
      logical_id: 'power_grid_telemetry',
      name: 'power_grid_telemetry',
      record_count: 2000,
      params: [
        { key: 'VoltageLevel_kV', name: '电压等级', unit: 'kV', mean: 512.4 },
        { key: 'CurrentAmp', name: '电流', unit: 'A', mean: 968.2 },
        { key: 'Temperature_C', name: '温度', unit: '℃', mean: 61.8 },
      ],
      frequency_pass_rate: 0.9315,
      packet_loss_mean: 0.42,
      baseline_ok: true,
      violations: [],
    },
  ],
  component_matrix: [
    { value: '变压器 T-01', kind: 'component', counts: [{ logical_id: 'power_grid_telemetry', count: 386, risk_rate: 0.812 }] },
    { value: '断路器 Q-07', kind: 'component', counts: [{ logical_id: 'power_grid_telemetry', count: 254, risk_rate: 0.769 }] },
    { value: '线路 L-12', kind: 'component', counts: [{ logical_id: 'power_grid_telemetry', count: 412, risk_rate: 0.845 }] },
    { value: '保护系统', kind: 'system', counts: [{ logical_id: 'power_grid_telemetry', count: 178, risk_rate: 0.706 }] },
    { value: '调度自动化', kind: 'system', counts: [{ logical_id: 'power_grid_telemetry', count: 96, risk_rate: 0.652 }] },
  ],
};

export const powerRuntime = runtime(2, 'power', '电力系统', 312, 41, 18, 253);
export const powerMembers: UserAccount[] = [
  member(6, 'SCENARIO_ADMIN', 2, 'power_system'),
  member(7, 'SCENARIO_USER', 2, 'power_system'),
  member(8, 'SCENARIO_USER', 2, 'power_system'),
];

// 舰面调度态势

const flightdeckDatasets = [dataset('carrier_landing_pairs', 507, 129, 'Collision', 27, 'company', 2)];

export const flightdeckSample: FlightdeckProfile = {
  scenario_id: 3,
  scenario_code: 'flightdeck_operation',
  scenario_key: 'flight_deck',
  scenario_name: '舰面调度态势',
  access_status: 'active',
  risk_type: '舰面碰撞',
  dataset_count: 1,
  dataset_file_count: 2,
  sample_count: 507,
  risk_count: 129,
  risk_rate: 0.254,
  datasets: flightdeckDatasets,
  groups: [
    { group_id: 'g1', datasets: ['carrier_landing_pairs', 'carrier_landing_pairs_copy'], record_count: 507, deduplicated: true, file_count: 2, fingerprint: 'g1' },
  ],
  modeling: [{ logical_id: 'carrier_landing_pairs', published: 1, draft: 1, total: 2 }],
  collision_count: 129,
  collision_rate: 0.254,
  distance: {},
  approach: { abs_change_ratio_mean: null, change_ratio_mean: null },
  total_distance: { plane1_mean: null, plane2_mean: null, diff_mean: null },
  direction: {
    plane1: { mean: null, std: null, stats: null },
    plane2: { mean: null, std: null, stats: null },
  },
  relative_angle: { mean: null, max: null },
  distance_curve: [],
  collision_comparison: { collision: { count: 0, mean_min_distance: null }, normal: { count: 0, mean_min_distance: null } },
  encoding_family: [
    { logical_id: 'carrier_landing_pairs', name: 'carrier_landing_pairs', source_group: 'g1', encoding: 'paired', attribute_count: 27, record_count: 507, risk_count: 129, collision_consistent: true, published_model_count: 1 },
    { logical_id: 'carrier_landing_pairs_copy', name: 'carrier_landing_pairs_copy', source_group: 'g1', encoding: 'paired', attribute_count: 27, record_count: 507, risk_count: 118, collision_consistent: false, published_model_count: 0 },
  ],
  redundancy: { file_count: 2, effective_group_count: 1, redundancy_rate: 0.5, raw_samples: 1014, deduped_samples: 507 },
};

export const flightdeckRuntime = runtime(3, 'flight_deck', '舰面调度态势', 76, 9, 5, 62);
export const flightdeckMembers: UserAccount[] = [
  member(9, 'SCENARIO_ADMIN', 3, 'flightdeck_operation'),
  member(10, 'SCENARIO_USER', 3, 'flightdeck_operation'),
];

// 地质风险

const geologicalDatasets = [
  dataset('dis_raw_data', 9860, 2760, 'Landslide', 24, 'platform', 3),
  dataset('dis_risk_label', 3120, 1084, 'label', 12, 'platform', 2),
  dataset('dis_hazard_factor', 2140, 512, 'hazard', 18, 'company', 1),
  dataset('dis_global_catalog', 1105, 0, 'size', 9, 'platform', 1, false),
  dataset('garuja_random', 160, 48, 'class', 8, 'personal', 1, false),
];

export const geologicalSample: GeologicalProfile = {
  scenario_id: 4,
  scenario_code: 'geological_risk',
  scenario_key: 'geological',
  scenario_name: '地质风险',
  access_status: 'active',
  risk_type: '滑坡灾害',
  dataset_count: 5,
  dataset_file_count: 6,
  sample_count: 16385,
  risk_count: 4588,
  risk_rate: 0.28,
  datasets: geologicalDatasets,
  groups: [
    { group_id: 'g1', datasets: ['dis_raw_data'], record_count: 9860, deduplicated: false, file_count: 1, fingerprint: 'g1' },
    { group_id: 'g2', datasets: ['dis_risk_label'], record_count: 3120, deduplicated: false, file_count: 1, fingerprint: 'g2' },
    { group_id: 'g3', datasets: ['dis_hazard_factor'], record_count: 2140, deduplicated: false, file_count: 1, fingerprint: 'g3' },
    { group_id: 'g4', datasets: ['dis_global_catalog'], record_count: 1105, deduplicated: false, file_count: 1, fingerprint: 'g4' },
    { group_id: 'g5', datasets: ['garuja_random'], record_count: 160, deduplicated: false, file_count: 1, fingerprint: 'g5' },
  ],
  modeling: [
    { logical_id: 'dis_raw_data', published: 2, draft: 1, total: 3 },
    { logical_id: 'dis_risk_label', published: 1, draft: 1, total: 2 },
    { logical_id: 'dis_hazard_factor', published: 1, draft: 0, total: 1 },
    { logical_id: 'dis_global_catalog', published: 0, draft: 0, total: 0 },
    { logical_id: 'garuja_random', published: 0, draft: 0, total: 0 },
  ],
  factors: [],
  factor_count: 0,
  catalog_distribution: { trigger: [], category: [], size: [], country: [] },
  roles: [
    { logical_id: 'dis_raw_data', name: 'dis_raw_data', role: '因子表', attribute_count: 24, label_field: 'Landslide', label_kind: 'binary', participates_in_training: true, produces_risk_events: true, record_count: 9860, risk_rate: 0.28 },
    { logical_id: 'dis_risk_label', name: 'dis_risk_label', role: '风险标签表', attribute_count: 12, label_field: 'label', label_kind: 'binary', participates_in_training: true, produces_risk_events: true, record_count: 3120, risk_rate: 0.347 },
    { logical_id: 'dis_hazard_factor', name: 'dis_hazard_factor', role: '致灾因子表', attribute_count: 18, label_field: 'hazard', label_kind: 'multiclass', participates_in_training: true, produces_risk_events: true, record_count: 2140, risk_rate: 0.239 },
    { logical_id: 'dis_global_catalog', name: 'dis_global_catalog', role: '全球编目表', attribute_count: 9, label_field: 'size', label_kind: 'numeric', participates_in_training: false, produces_risk_events: false, record_count: 1105, risk_rate: 0 },
    { logical_id: 'garuja_random', name: 'garuja_random', role: '随机基线集', attribute_count: 8, label_field: 'class', label_kind: 'binary', participates_in_training: false, produces_risk_events: false, record_count: 160, risk_rate: 0.3 },
  ],
  factor_coverage: [
    { factor: 'Slope', datasets: ['dis_raw_data', 'dis_hazard_factor', 'garuja_random'], consistent_binning: true },
    { factor: 'TWI', datasets: ['dis_raw_data', 'garuja_random'], consistent_binning: false },
    { factor: 'Elevation', datasets: ['dis_raw_data', 'dis_hazard_factor', 'garuja_random'], consistent_binning: true },
    { factor: 'Relief', datasets: ['dis_raw_data', 'dis_hazard_factor'], consistent_binning: true },
    { factor: 'SPI', datasets: ['dis_raw_data'], consistent_binning: true },
    { factor: 'Dis2roads', datasets: ['dis_raw_data', 'dis_hazard_factor'], consistent_binning: true },
    { factor: 'Dis2fault', datasets: ['dis_raw_data', 'dis_hazard_factor'], consistent_binning: false },
    { factor: 'Dis2river', datasets: ['dis_raw_data'], consistent_binning: true },
  ],
};

export const geologicalRuntime = runtime(4, 'geological', '地质风险', 206, 23, 14, 169);
export const geologicalMembers: UserAccount[] = [
  member(11, 'SCENARIO_ADMIN', 4, 'geological_risk'),
  member(12, 'SCENARIO_USER', 4, 'geological_risk'),
  member(13, 'SCENARIO_USER', 4, 'geological_risk'),
  member(14, 'SCENARIO_USER', 4, 'geological_risk'),
  member(15, 'SCENARIO_USER', 4, 'geological_risk'),
];
