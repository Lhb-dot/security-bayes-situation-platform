/**
 * riskEventStore.ts — 风险事件列表/处置（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/riskEventApi.*。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { RiskEvent, ScenarioId } from '@/types/security';

export const useRiskEventStore = defineStore('riskEvent', {
  state: () => ({
    events: [] as RiskEvent[],
    detail: null as RiskEvent | null,
    loading: false,
  }),
  getters: {
    eventsByScenario: (state) => (scenarioId: ScenarioId): RiskEvent[] =>
      state.events.filter((e) => e.scenario_id === scenarioId),
    highRiskCount: (state): number => state.events.filter((e) => e.risk_level === 'HIGH').length,
  },
  actions: {
    async fetchEvents(scenarioId?: ScenarioId): Promise<void> {
      this.loading = true;
      try {
        this.events = await mockApi.getRiskEvents(scenarioId);
      } finally {
        this.loading = false;
      }
    },
    async fetchDetail(eventId: string): Promise<void> {
      this.loading = true;
      try {
        this.detail = await mockApi.getRiskEventById(eventId);
      } finally {
        this.loading = false;
      }
    },
    clearDetail(): void {
      this.detail = null;
    },
    async updateStatus(eventId: string, status: RiskEvent['status']): Promise<void> {
      await mockApi.updateRiskEventStatus(eventId, status);
      const target = this.events.find((e) => e.event_id === eventId);
      if (target) target.status = status;
      if (this.detail?.event_id === eventId) this.detail.status = status;
    },
  },
});
