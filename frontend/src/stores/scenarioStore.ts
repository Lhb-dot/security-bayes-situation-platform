/**
 * scenarioStore.ts — 场景列表/详情
 *
 * 数据源：src/api/scenarioApi（真实后端）+ situationApi（真实态势统计）。
 * 后端场景用数字 ID、编码 code；页面沿用 code 作为 scenario_id，详情补充真实统计与近期事件。
 */
import { defineStore } from 'pinia';
import {
  getScenarioList,
  getScenarioOverview,
  toScenarioCard,
  type ApiScenario,
} from '@/api/scenarioApi';
import type { Scenario, ScenarioId } from '@/types/security';

/**
 * 场景元数据映射（`GET /scenarios`）。
 *
 * ⚠️ 该接口**不含任何统计字段**，所以这里的 dataset_count / model_count /
 * high_risk_count / risk_score 只能是 0 —— 需要真实指标请用 `fetchScenarioOverview()`。
 */
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
    /**
     * 场景卡片列表（真实聚合：去重口径数据集数 / 有效样本量 / 已发布模型数 / 风险分）。
     * 场景中心必须用这个，`fetchScenarioList` 不含统计字段。
     */
    async fetchScenarioOverview(): Promise<void> {
      this.loading = true;
      try {
        const overview = await getScenarioOverview();
        this.scenarios = overview.scenarios.map(toScenarioCard);
      } finally {
        this.loading = false;
      }
    },
  },
});
