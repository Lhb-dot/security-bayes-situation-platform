/**
 * inferenceStore.ts — 推理执行与推理记录（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务逻辑与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/inferenceRecordApi.*。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { InferenceRecord, ScenarioId } from '@/types/security';
// 过渡期：InferenceResult 定义于 mockApi.ts，后续任务建议迁入 security.ts
import type { InferenceResult } from '@/services/mockApi';

export const useInferenceStore = defineStore('inference', {
  state: () => ({
    records: [] as InferenceRecord[],
    lastResult: null as InferenceResult | null,
    loading: false,
  }),
  getters: {
    recordsByScenario: (state) => (scenarioId: ScenarioId): InferenceRecord[] =>
      state.records.filter((r) => r.scenario_id === scenarioId),
  },
  actions: {
    async fetchRecords(scenarioId?: ScenarioId, userId?: string): Promise<void> {
      this.loading = true;
      try {
        this.records = await mockApi.getInferenceRecords(scenarioId, userId);
      } finally {
        this.loading = false;
      }
    },
    async executeInference(params: {
      model_version_id: string;
      input_features: Record<string, unknown>;
    }): Promise<InferenceResult> {
      const result = await mockApi.executeInference(params);
      this.lastResult = result;
      await this.fetchRecords();
      return result;
    },
  },
});
