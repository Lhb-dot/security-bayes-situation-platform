import type { FlightdeckProfile, GeologicalProfile, NetworkProfile, PowerProfile, ProfileBase, ScenarioWorkspace } from '@/api/dashboardApi';
const stats = { mean: 12.5, min: 1, max: 20, median: 12, std: 2, range: 19, count: 28 };
const base = (id: number, scenario_key: ProfileBase['scenario_key'], scenario_code: string): ProfileBase => ({
  scenario_id: id, scenario_key, scenario_code, scenario_name: scenario_code, access_status: 'ACTUAL', risk_type: null,
  dataset_count: 1, dataset_file_count: 1, sample_count: 28, risk_count: 7, risk_rate: .25,
  datasets: [{ dataset_id: 91, logical_id: 'test_source', version: 2, label_field: 'Label', is_risk_label: true,
    record_count: 28, risk_count: 7, risk_rate: .25, attribute_count: 8, field_names: ['Slope'], visibility: 'company',
    uploader_role: 'SCENARIO_ADMIN', uploaded_at: null, source_group: 'group1', content_fingerprint: 'group1', positive_labels: ['1'], label_values: ['0', '1'], label_kind: 'binary', caliber_registered: true }],
  groups: [{ group_id: 'group1', datasets: ['test_source'], record_count: 28, deduplicated: false, file_count: 1, fingerprint: 'group1' }],
  modeling: [{ logical_id: 'test_source', published: 1, draft: 0, total: 1 }],
});
export const networkProfile = (): NetworkProfile => ({ ...base(1, 'network', 'network_security'),
  protocol_distribution: [{ value: 'TCP', count: 28 }], protocol_total: 28, distinct_port_count: 2,
  top_ports: [{ value: '9443', count: 17 }, { value: '80', count: 11 }], flags: [], services: [{ value: 'http', count: 28 }], flow_segments: [],
  traffic: { avg_in_bytes: 0, avg_retrans_in_bytes: 0, retransmission_ratio: 0, in_bytes_stats: null, retrans_stats: null },
  caliber_matrix: [], dimension_coverage: [{ dimension: '目的端口', key: 'port', datasets: ['test_source'] }],
});
export const powerProfile = (): PowerProfile => ({ ...base(2, 'power', 'power_system'),
  params: [{ name: '电压', key: 'VoltageLevel_kV', unit: 'kV', stats }], fault_count: 7, fault_rate: .25,
  issues: [{ value: '过载', count: 7 }], components: [], systems: [{ value: '输电', count: 28 }],
  device_fault_rates: [{ value: '变压器', count: 28, risk_count: 7, risk_rate: .25 }], telemetry_by_dataset: [], component_matrix: [],
});
export const flightProfile = (): FlightdeckProfile => ({ ...base(3, 'flight_deck', 'flightdeck_operation'),
  collision_count: 7, collision_rate: .25, distance: { min: stats }, approach: { abs_change_ratio_mean: .2, change_ratio_mean: .1 },
  total_distance: { plane1_mean: 15, plane2_mean: 20, diff_mean: -5 },
  direction: { plane1: { mean: 15, std: 2, stats }, plane2: { mean: 25, std: 3, stats } }, relative_angle: { mean: 10, max: 30 },
  distance_curve: [{ step: 1, mean: 12 }, { step: 2, mean: 20 }],
  collision_comparison: { collision: { count: 7, mean_min_distance: 5 }, normal: { count: 21, mean_min_distance: 15 } },
  encoding_family: [], redundancy: { file_count: 1, effective_group_count: 1, redundancy_rate: 0, raw_samples: 28, deduped_samples: 28 },
});
export const geologicalProfile = (): GeologicalProfile => ({ ...base(4, 'geological', 'geological_risk'),
  factors: [{ value: 'Slope', mean: 12.5, stats }], factor_count: 1,
  catalog_distribution: { trigger: [{ value: '降雨', count: 28 }], category: [{ value: 'landslide', count: 28 }], size: [{ value: '小型', count: 28 }], country: [] },
  roles: [], factor_coverage: [{ factor: 'Slope', datasets: ['test_source'], consistent_binning: true }],
});
export const scenarioProfiles = () => [networkProfile(), powerProfile(), flightProfile(), geologicalProfile()];
export const scenarioList = () => scenarioProfiles().map(item => ({ id: item.scenario_id, code: item.scenario_code, name: item.scenario_name, description: null, access_status: 'ACTUAL' }));
export const workspaceFixture = (selfOnly = false): ScenarioWorkspace => ({
  scenario_id: 1, scenario_code: 'network_security', scenario_key: 'network', scenario_name: '', risk_type: null,
  summary: { total: 19, pending: 3, processing: 4, resolved: 12, today: 0, high_confidence: 0, high_threshold: .8, medium_threshold: .5, avg_risk_score: .5, max_risk_score: .9, score_bins: [], status_funnel: [], daily_trend: [] },
  recent_events: [], scope: { self_only: selfOnly, user_id: 1 }, activity_trend: [{ date: '2026-10-16', total: 15, risk: 5 }],
  top_ports: [], abnormal_ports: [], port_deviation: [], port_baseline: 0, flow_segments: [],
});
