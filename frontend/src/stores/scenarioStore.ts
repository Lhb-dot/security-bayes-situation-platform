/**
 * scenarioStore.ts — 场景列表/详情
 *
 * 数据源：src/api/scenarioApi（真实后端）+ situationApi（真实态势统计）。
 * 后端场景用数字 ID、编码 code；页面沿用 code 作为 scenario_id，详情补充真实统计与近期事件。
 */
import { defineStore } from 'pinia';
import { getScenarioList, getScenarioDetail, resolveScenarioId, type ApiScenario } from '@/api/scenarioApi';
import { getSceneSituation, mapRiskEvent } from '@/api/situationApi';
import type { MetricItem, Scenario, ScenarioDetail, ScenarioId, TypeDistribution } from '@/types/security';

function mapScenario(raw: ApiScenario): Scenario {
  return {
    scenario_id: raw.code as ScenarioId,
    name: raw.name,
    description: raw.description ?? '',
    risk_level: 'low',
    risk_score: 0,
    event_count: 0,
    high_risk_count: 0,
    dataset_count: 0,
    model_count: 0,
    status: raw.access_status === 'ACTUAL' ? 'active' : 'inactive',
  };
}

export const useScenarioStore = defineStore('scenario', {
  state: () => ({
    scenarios: [] as Scenario[],
    detail: null as ScenarioDetail | null,
    loading: false,
  }),
  getters: {
    activeScenarios: (state): Scenario[] => state.scenarios.filter((s) => s.status === 'active'),
    scenarioById: (state) => (scenarioId: ScenarioId): Scenario | undefined =>
      state.scenarios.find((s) => s.scenario_id === scenarioId),
  },
  actions: {
    async fetchScenarioList(): Promise<void> {
      this.loading = true;
      try {
        const raw = await getScenarioList();
        this.scenarios = raw.map(mapScenario);
      } finally {
        this.loading = false;
      }
    },
    async fetchScenarioDetail(scenarioId: ScenarioId): Promise<void> {
      this.loading = true;
      try {
        const numericId = await resolveScenarioId(scenarioId);
        const [raw, sit] = await Promise.all([
          getScenarioDetail(numericId),
          getSceneSituation(numericId),
        ]);
        const scenario: Scenario = {
          ...mapScenario(raw),
          event_count: sit.stats.total_events,
          high_risk_count: sit.stats.high_count,
          risk_level: sit.stats.high_count > 0 ? 'high' : sit.stats.medium_count > 0 ? 'medium' : 'low',
        };
        const metrics: MetricItem[] = [
          { id: 'total-events', label: '风险事件', value: sit.stats.total_events, trend: 0 },
          { id: 'high-risk', label: '高危', value: sit.stats.high_count, trend: 0 },
          { id: 'medium-risk', label: '中危', value: sit.stats.medium_count, trend: 0 },
          { id: 'low-risk', label: '低危', value: sit.stats.low_count, trend: 0 },
          { id: 'pending', label: '待处置', value: sit.stats.pending_count, trend: 0 },
          { id: 'resolved', label: '已处置', value: sit.stats.resolved_count, trend: 0 },
        ];
        const risk_distribution: TypeDistribution[] = [
          { label: '高危', value: sit.stats.high_count, color: '#ff7b72' },
          { label: '中危', value: sit.stats.medium_count, color: '#ffd166' },
          { label: '低危', value: sit.stats.low_count, color: '#53e5c8' },
        ];
        this.detail = {
          scenario,
          metrics,
          trend_data: [],
          risk_distribution,
          recent_events: sit.recent_events.map((e) => mapRiskEvent(e)),
        };
      } finally {
        this.loading = false;
      }
    },
    resetDetail(): void {
      this.detail = null;
    },
  },
});
