/**
 * thresholdStore.ts — 风险阈值配置与变更记录（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/riskThresholdApi.*。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { ScenarioId, ThresholdChangeLog, ThresholdConfig } from '@/types/security';

export const useThresholdStore = defineStore('threshold', {
  state: () => ({
    thresholds: [] as ThresholdConfig[],
    changeLogs: [] as ThresholdChangeLog[],
    loading: false,
  }),
  getters: {
    thresholdByScenario: (state) => (scenarioId: ScenarioId): ThresholdConfig | undefined =>
      state.thresholds.find((t) => t.scenario_id === scenarioId),
  },
  actions: {
    async fetchThresholds(): Promise<void> {
      this.loading = true;
      try {
        this.thresholds = await mockApi.getThresholds();
      } finally {
        this.loading = false;
      }
    },
    async fetchChangeLogs(): Promise<void> {
      this.changeLogs = await mockApi.getThresholdChangeLogs();
    },
    async saveThreshold(
      scenarioId: ScenarioId,
      medium_threshold: number,
      high_threshold: number
    ): Promise<ThresholdConfig> {
      const cfg = await mockApi.saveThreshold(scenarioId, medium_threshold, high_threshold);
      await this.fetchThresholds();
      await this.fetchChangeLogs();
      return cfg;
    },
  },
});
