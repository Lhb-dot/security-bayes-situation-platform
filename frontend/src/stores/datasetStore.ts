/**
 * datasetStore.ts — 数据集列表/字段/版本/预览
 *
 * 职责边界：仅 state / action / getter，不含业务过滤与页面逻辑。
 * 数据源：src/api/datasetApi（PostgreSQL 真实数据）。
 */
import { defineStore } from 'pinia';
import * as datasetApi from '@/api/datasetApi';
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
        this.datasets = await datasetApi.getDatasetList(
          scenarioId ? { scenario_id: scenarioId, page_size: 200 } : { page_size: 200 }
        );
      } finally {
        this.loading = false;
      }
    },
    async fetchFields(datasetId: string, datasetVersion?: string): Promise<void> {
      this.loading = true;
      try {
        this.fields = await datasetApi.getDatasetFields(datasetId, datasetVersion);
      } finally {
        this.loading = false;
      }
    },
    async fetchPreview(datasetId: string, params: { page: number; page_size: number }): Promise<void> {
      this.loading = true;
      try {
        this.preview = await datasetApi.getDatasetPreview(datasetId, params);
      } finally {
        this.loading = false;
      }
    },
    async fetchVersions(datasetId?: string): Promise<void> {
      this.loading = true;
      try {
        this.versions = await datasetApi.getDatasetVersions(datasetId);
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
      file_path: string;
      label_field?: string;
    }): Promise<DatasetVersion> {
      const created = await datasetApi.uploadDataset(params);
      await this.fetchVersions();
      return {
        dataset_version_id: created.dataset_id,
        dataset_id: params.dataset_id,
        dataset_version: created.dataset_version,
        name: created.name,
        scenario_id: created.scenario_id,
        data_format: created.data_format,
        file_path: params.file_path,
        record_count: created.record_count,
        field_count: created.field_count,
        fields: created.fields,
        uploaded_by: created.uploaded_by,
        uploaded_at: created.uploaded_at,
        enabled: created.enabled,
        referenced: created.referenced,
      };
    },
    async createVersion(datasetId: string, fields: DatasetField[]): Promise<DatasetVersion> {
      const version = await datasetApi.createDatasetVersion(datasetId, fields);
      await this.fetchVersions(datasetId);
      return version;
    },
    async disableVersion(versionId: string): Promise<void> {
      await datasetApi.disableDatasetVersion(versionId);
      await this.fetchVersions();
    },
    async removeVersion(versionId: string): Promise<void> {
      await datasetApi.deleteDatasetVersion(versionId);
      await this.fetchVersions();
    },
  },
});
