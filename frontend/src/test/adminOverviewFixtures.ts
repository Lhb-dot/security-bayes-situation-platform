import type { DashboardOverview } from '@/api/dashboardApi';

// 回归测试接口数据，数值刻意与设计预览不同。
export const adminOverviewPayload = (): DashboardOverview => ({
  totals: {
    scenario_count: 4, effective_dataset_count: 9, effective_sample_count: 4000,
    risk_sample_count: 100, risk_rate: .025, algorithm_count: 6,
    published_model_count: 9, inference_count: 42, risk_event_count: 11,
    pending_event_count: 3, user_count: 25,
  },
  runtime: {
    trained_model_count: 17, published_model_count: 9, inference_count: 42,
    report_count: 8, served_user_count: 10, user_count: 25, algorithm_count: 6,
    risk_event_count: 11, pending_event_count: 3, processing_event_count: 2, resolved_event_count: 6,
  },
  scenarios: [
    { id: 1, key: 'network', code: 'network_security', name: '网络安全', samples: 1000, datasets: 2 },
    { id: 2, key: 'power', code: 'power_system', name: '电力系统', samples: 300, datasets: 1 },
    { id: 3, key: 'flight_deck', code: 'flightdeck_operation', name: '舰面调度', samples: 30, datasets: 1 },
    { id: 4, key: 'geological', code: 'geological_risk', name: '地质风险', samples: 670, datasets: 5 },
  ].map((scene) => ({
    scenario_id: scene.id, scenario_key: scene.key as DashboardOverview['scenarios'][number]['scenario_key'],
    code: scene.code, name: scene.name, access_status: 'ACTUAL',
    user_count: scene.id, admin_count: 1, dataset_count: scene.datasets,
    effective_sample_count: scene.samples, risk_count: 0, risk_rate: 0,
    published_model_count: 1, model_count: 2, inference_count: 0, event_count: 0, pending_count: 0,
  })),
});
