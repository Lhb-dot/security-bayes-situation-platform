/**
 * scenarioStore.ts — 场景列表/详情（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/scenarioApi.*。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { Scenario, ScenarioDetail, ScenarioId } from '@/types/security';

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
        this.scenarios = await mockApi.getScenarioList();
      } finally {
        this.loading = false;
      }
    },
    async fetchScenarioDetail(scenarioId: ScenarioId): Promise<void> {
      this.loading = true;
      try {
        this.detail = await mockApi.getScenarioDetail(scenarioId);
      } finally {
        this.loading = false;
      }
    },
    resetDetail(): void {
      this.detail = null;
    },
  },
});
