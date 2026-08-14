/**
 * datasetStore.ts — 数据集列表/字段/版本（Task 004）
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/datasetApi.*。
 */
import { defineStore } from 'pinia';
import * as mockApi from '@/services/mockApi';
import type { DataPreview, Dataset, DatasetField, DatasetVersion, ScenarioId } from '@/types/security';

export const useDatasetStore = defineStore('dataset', {
  state: () => ({
    datasets: [] as Dataset[],
    fields: [] as DatasetField[],
    versions: [] as DatasetVersion[],
    preview: null as DataPreview | null,
    loading: false,
  }),
  getters: {
    datasetsByScenario: (state) => (scenarioId: ScenarioId): Dataset[] =>
      state.datasets.filter((d) => d.scenario_id === scenarioId),
  },
  actions: {
    async fetchDatasets(scenarioId?: ScenarioId): Promise<void> {
      this.loading = true;
      try {
        this.datasets = await mockApi.getDatasetList(scenarioId);
      } finally {
        this.loading = false;
      }
    },
    async fetchFields(datasetId: string, datasetVersion?: string): Promise<void> {
      this.loading = true;
      try {
        this.fields = await mockApi.getDatasetFields(datasetId, datasetVersion);
      } finally {
        this.loading = false;
      }
    },
    async fetchPreview(datasetId: string, params: { page: number; page_size: number }): Promise<void> {
      this.loading = true;
      try {
        this.preview = await mockApi.getDatasetPreview(datasetId, params);
      } finally {
        this.loading = false;
      }
    },
    async fetchVersions(datasetId?: string): Promise<void> {
      this.loading = true;
      try {
        this.versions = await mockApi.getDatasetVersions(datasetId);
      } finally {
        this.loading = false;
      }
    },
    async uploadDataset(params: {
      dataset_id: string;
      name: string;
      scenario_id: ScenarioId;
      data_format: Dataset['data_format'];
      record_count: number;
      fields: DatasetField[];
    }): Promise<DatasetVersion> {
      const version = await mockApi.uploadDataset(params);
      await this.fetchVersions();
      return version;
    },
    async createVersion(datasetId: string, fields: DatasetField[]): Promise<DatasetVersion> {
      const version = await mockApi.createDatasetVersion(datasetId, fields);
      await this.fetchVersions(datasetId);
      return version;
    },
    async disableVersion(versionId: string): Promise<void> {
      await mockApi.disableDatasetVersion(versionId);
      await this.fetchVersions();
    },
    async removeVersion(versionId: string): Promise<void> {
      await mockApi.deleteDatasetVersion(versionId);
      await this.fetchVersions();
    },
  },
});
