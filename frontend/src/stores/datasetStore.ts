/** 数据集查询按资源独立跟踪；页面应消费 action 返回值，避免读取其他调用方的结果。 */
import { defineStore } from 'pinia';
import { computed, reactive, ref, watch } from 'vue';
import * as datasetApi from '@/api/datasetApi';
import { useUserStore } from '@/stores/userStore';
import type { DataPreview, Dataset, DatasetField, DatasetVersion, ScenarioId } from '@/types/security';

export interface DatasetQueryContext {
  /** 页面选择改变或卸载后，不再回写共享状态。请求结果仍返回给调用方自行判断。 */
  isCurrent: () => boolean;
}

type Resource = 'datasets' | 'fields' | 'preview' | 'versions';

export const useDatasetStore = defineStore('dataset', () => {
  const userStore = useUserStore();
  const datasets = ref<Dataset[]>([]);
  const fields = ref<DatasetField[]>([]);
  const versions = ref<DatasetVersion[]>([]);
  const preview = ref<DataPreview | null>(null);
  const queries = reactive<Record<Resource, { key: string | null; loading: boolean }>>({
    datasets: { key: null, loading: false },
    fields: { key: null, loading: false },
    preview: { key: null, loading: false },
    versions: { key: null, loading: false },
  });
  const sequences: Record<Resource, number> = { datasets: 0, fields: 0, preview: 0, versions: 0 };
  const clear: Record<Resource, () => void> = {
    datasets: () => { datasets.value = []; },
    fields: () => { fields.value = []; },
    preview: () => { preview.value = null; },
    versions: () => { versions.value = []; },
  };
  // 保留原 loading 读取接口；不同资源先完成时不能关闭其他资源的等待状态。
  const loading = computed(() => Object.values(queries).some((entry) => entry.loading));
  const datasetsByScenario = (scenarioId: ScenarioId) =>
    datasets.value.filter((dataset) => dataset.scenario_id === scenarioId);

  const resetQueries = () => {
    for (const resource of Object.keys(queries) as Resource[]) {
      sequences[resource] += 1;
      queries[resource].key = null;
      queries[resource].loading = false;
      clear[resource]();
    }
  };
  // 同步失效，涵盖 A → 退出 → A；每个 Pinia 实例都有自己的序号和监听。
  watch(() => userStore.currentUser?.user_id, resetQueries, { flush: 'sync' });

  const query = async <T>(
    resource: Resource,
    key: string,
    fetch: () => Promise<T>,
    commit: (value: T) => void,
    context?: DatasetQueryContext,
  ): Promise<T> => {
    const sequence = ++sequences[resource];
    const owner = userStore.currentUser?.user_id;
    if (queries[resource].key !== key) clear[resource]();
    queries[resource].key = key;
    queries[resource].loading = true;
    try {
      const value = await fetch();
      if (sequence === sequences[resource] && owner === userStore.currentUser?.user_id
        && (context?.isCurrent() ?? true)) commit(value);
      return value;
    } finally {
      if (sequence === sequences[resource]) queries[resource].loading = false;
    }
  };

  const fetchDatasets = (scenarioId?: ScenarioId, context?: DatasetQueryContext): Promise<Dataset[]> =>
    query('datasets', JSON.stringify([scenarioId ?? null]),
      () => datasetApi.getDatasetList(scenarioId
        ? { scenario_id: scenarioId, page_size: 200 } : { page_size: 200 }),
      (value) => { datasets.value = value; }, context);

  const fetchFields = (datasetId: string, datasetVersion?: string, context?: DatasetQueryContext): Promise<DatasetField[]> =>
    query('fields', JSON.stringify([datasetId, datasetVersion ?? null]),
      () => datasetApi.getDatasetFields(datasetId, datasetVersion),
      (value) => { fields.value = value; }, context);

  const fetchPreview = (datasetId: string, params: { page: number; page_size: number }, context?: DatasetQueryContext): Promise<DataPreview> =>
    query('preview', JSON.stringify([datasetId, params.page, params.page_size]),
      () => datasetApi.getDatasetPreview(datasetId, params),
      (value) => { preview.value = value; }, context);

  const fetchVersions = (datasetId?: string, context?: DatasetQueryContext): Promise<DatasetVersion[]> =>
    query('versions', JSON.stringify([datasetId ?? null]),
      () => datasetApi.getDatasetVersions(datasetId),
      (value) => { versions.value = value; }, context);

  const uploadDataset = async (params: {
    dataset_id: string;
    name: string;
    scenario_id: ScenarioId;
    data_format: Dataset['data_format'];
    record_count: number;
    fields: DatasetField[];
    file_path: string;
    label_field?: string;
  }): Promise<DatasetVersion> => {
    const created = await datasetApi.uploadDataset(params);
    await fetchVersions();
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
  };
  const createVersion = async (datasetId: string, definition: DatasetField[]): Promise<DatasetVersion> => {
    const version = await datasetApi.createDatasetVersion(datasetId, definition);
    await fetchVersions(datasetId);
    return version;
  };
  const disableVersion = async (versionId: string): Promise<void> => {
    await datasetApi.disableDatasetVersion(versionId);
    await fetchVersions();
  };
  const removeVersion = async (versionId: string): Promise<void> => {
    await datasetApi.deleteDatasetVersion(versionId);
    await fetchVersions();
  };

  return { datasets, fields, versions, preview, queries, loading, datasetsByScenario, resetQueries,
    fetchDatasets, fetchFields, fetchPreview, fetchVersions, uploadDataset, createVersion, disableVersion, removeVersion };
});
