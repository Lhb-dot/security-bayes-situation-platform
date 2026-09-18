/**
 * thresholdStore.ts — 风险阈值配置与变更记录（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 数据源：src/api/riskThresholdApi.*（真实后端 /api/v1/risk-thresholds）。
 *
 * 2026-09-18：原先走 mockApi，取到的是写死的前端假值（网络安全 0.45/0.75、其余 0.5/0.8），
 * 与设置页保存的真实阈值无关 —— 导致管理端总览「场景运行状态」卡的 danger/warn 判定用的是假数。
 * 后端早已就绪，这里完成当年注释里写的切换。
 */
import { defineStore } from 'pinia';
import {
  getRiskThresholdAuditLogs,
  getRiskThresholds,
  updateRiskThreshold,
} from '@/api/riskThresholdApi';
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
        this.thresholds = await getRiskThresholds();
      } finally {
        this.loading = false;
      }
    },
    async fetchChangeLogs(): Promise<void> {
      this.changeLogs = await getRiskThresholdAuditLogs();
    },
    async saveThreshold(
      scenarioId: ScenarioId,
      medium_threshold: number,
      high_threshold: number
    ): Promise<ThresholdConfig> {
      const cfg = await updateRiskThreshold(scenarioId, { medium_threshold, high_threshold });
      await this.fetchThresholds();
      await this.fetchChangeLogs();
      return cfg;
    },
  },
});
