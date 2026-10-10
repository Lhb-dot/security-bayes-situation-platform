import type { DataPreview, Dataset, DatasetField, ScenarioId, UserAccount } from '@/types/security';
import type { BackendModelVersion } from '@/api/modelVersionApi';

export const deferred = <T>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
};

export const field = (name = 'L4_DST_PORT'): DatasetField => ({
  field_name: name, field_type: 'int', field_role: '输入特征', description: '', sample_value: '80', nullable: false,
});
export const dataset = (id = '1', scenario: ScenarioId = 'network_security'): Dataset => ({
  dataset_id: id, name: `数据集${id}`, description: '', scenario_id: scenario, record_count: 150,
  field_count: 1, fields: [field()], created_at: '2026-10-11 00:00:00', data_format: 'csv',
  dataset_version: 'v1', uploaded_by: 'tester', uploaded_at: '2026-10-11 00:00:00', enabled: true, referenced: true,
});
export const preview = (page = 1, value = page * 100): DataPreview => ({
  total: 150, page, page_size: 50, rows: [{ L4_DST_PORT: value }], label_field: '',
});
export const user = (id = 'a'): UserAccount => ({
  id: 1, user_id: id, username: id, display_name: id, role: 'SUPER_ADMIN', status: 'active',
  created_at: '2026-10-11 00:00:00', created_by: 'test', scenario_id: null, scenario_code: null,
});
export const model = (id = 1, datasetId = 1, extras: Partial<BackendModelVersion> = {}): BackendModelVersion => ({
  id, model_version_id: id, scenario_id: 1, dataset_id: datasetId, dataset_version: 1,
  algorithm_id: 1, algorithm_name: `算法${id}`, training_parameters: {}, evaluation_metrics: {},
  trained_by: 1, trained_at: '2026-10-11 00:00:00', status: 'PUBLISHED', is_default: false, ...extras,
});
