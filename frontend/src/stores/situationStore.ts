/**
 * situationStore.ts — 全局态势/场景态势
 *
 * 全局总览（fetchGlobalOverview）与场景态势（fetchSituationData）均已接入真实后端 /api/v1。
 */
import { defineStore } from 'pinia';
import { getGlobalOverview, getSituationData } from '@/api/situationApi';
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
        this.overview = await getGlobalOverview();
      } finally {
        this.loading = false;
      }
    },
    async fetchSituationData(scenarioId: ScenarioId): Promise<void> {
      this.loading = true;
      try {
        this.situation = await getSituationData(scenarioId);
      } finally {
        this.loading = false;
      }
    },
  },
});
