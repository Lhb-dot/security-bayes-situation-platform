/**
 * situationStore.ts — 全局态势/场景态势
 *
 * 场景态势（fetchSituationData）接入真实后端 /api/v1/situation；
 * 全局总览（fetchGlobalOverview）仍走 mockApi（对应 OverviewView，另行改造）。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import { getSituationData } from '@/api/situationApi';
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
        this.situation = await getSituationData(scenarioId);
      } finally {
        this.loading = false;
      }
    },
  },
});
