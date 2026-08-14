/**
 * situationStore.ts — 全局态势/场景态势（Task 004）
 *
 * 职责边界：仅 state / action，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端态势路由未提供，src/api/situationApi.* 保持占位。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { GlobalOverview, ScenarioId, SituationData } from '@/types/security';

export const useSituationStore = defineStore('situation', {
  state: () => ({
    overview: null as GlobalOverview | null,
    situation: null as SituationData | null,
    loading: false,
  }),
  actions: {
    async fetchGlobalOverview(): Promise<void> {
      this.loading = true;
      try {
        this.overview = await mockApi.getGlobalOverview();
      } finally {
        this.loading = false;
      }
    },
    async fetchSituationData(scenarioId: ScenarioId): Promise<void> {
      this.loading = true;
      try {
        this.situation = await mockApi.getSituationData(scenarioId);
      } finally {
        this.loading = false;
      }
    },
    // TODO Task 007：mockApi.getGlobalCockpit 提供后新增 getGlobalCockpit
  },
});
