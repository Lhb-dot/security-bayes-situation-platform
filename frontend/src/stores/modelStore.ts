/**
 * modelStore.ts — 模型版本/算法/训练生命周期（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/modelVersionApi.*。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { AlgorithmDefinition, ModelVersionRecord, ScenarioId } from '@/types/security';

export const useModelStore = defineStore('model', {
  state: () => ({
    modelVersions: [] as ModelVersionRecord[],
    algorithms: [] as AlgorithmDefinition[],
    loading: false,
  }),
  getters: {
    publishedModels: (state): ModelVersionRecord[] =>
      state.modelVersions.filter((m) => m.status === 'PUBLISHED'),
    modelsByScenario: (state) => (scenarioId: ScenarioId): ModelVersionRecord[] =>
      state.modelVersions.filter((m) => m.scenario_id === scenarioId),
    defaultModelFor: (state) => (scenarioId: ScenarioId, datasetId: string): ModelVersionRecord | undefined =>
      state.modelVersions.find(
        (m) => m.scenario_id === scenarioId && m.dataset_id === datasetId && m.is_default
      ),
  },
  actions: {
    async fetchModelVersions(scenarioId?: ScenarioId, datasetId?: string): Promise<void> {
      this.loading = true;
      try {
        this.modelVersions = await mockApi.getModelVersions(scenarioId, datasetId);
      } finally {
        this.loading = false;
      }
    },
    async fetchAlgorithms(): Promise<void> {
      this.algorithms = await mockApi.getAlgorithms();
    },
    async trainModel(params: {
      scenario_id: ScenarioId;
      dataset_id: string;
      dataset_version: string;
      algorithm_id: string;
      training_parameters: Record<string, unknown>;
    }): Promise<ModelVersionRecord & { train_time_s: number }> {
      const model = await mockApi.trainModel(params);
      await this.fetchModelVersions();
      return model;
    },
    async publishModel(modelVersionId: string): Promise<void> {
      await mockApi.publishModel(modelVersionId);
      await this.fetchModelVersions();
    },
    async offlineModel(modelVersionId: string): Promise<void> {
      await mockApi.offlineModel(modelVersionId);
      await this.fetchModelVersions();
    },
    async rePublishModel(modelVersionId: string): Promise<void> {
      await mockApi.rePublishModel(modelVersionId);
      await this.fetchModelVersions();
    },
    async setDefaultModel(modelVersionId: string): Promise<void> {
      await mockApi.setDefaultModel(modelVersionId);
      await this.fetchModelVersions();
    },
  },
});
