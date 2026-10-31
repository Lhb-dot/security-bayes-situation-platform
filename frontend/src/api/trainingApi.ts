/**
 * 模型训练页接口：场景 / 数据集 / 算法全部从数据库渲染。
 * 训练走 POST /api/v1/model-versions/train-async，提交后立刻返回 TRAINING 版本，
 * 后台线程调用 Java/Weka 服务，前端轮询 getModelVersionDetail 等状态流转。
 */
import request, { unwrapData } from '@/utils/request';

export interface ScenarioRow {
  id: number;
  code: string;
  name: string;
  access_status: string;
}

export interface DatasetRow {
  id: number;
  logical_id: string;
  name: string;
  version: number;
  scenario_id: number;
  status: string;
  file_path: string;
  fields_schema: unknown[];
  record_count?: number;
  field_count?: number;
}

export interface AlgorithmRow {
  id: number;
  code: string;
  display_name: string;
  description?: string | null;
  status: string;
  param_schema?: unknown[];
}

export interface ModelVersionRow {
  id: number;
  status?: string;
  evaluation_metrics?: { error?: string } | null;
}

export interface TrainingPayload {
  scenario_id: number;
  dataset_id: number;
  algorithm_id: number;
  training_parameters: Record<string, unknown>;
}

export interface TrainingJobRow {
  id?: number;
  model_version_id?: number;
  status?: string;
  scenario_name?: string;
  algorithm_name?: string;
  trained_at?: string;
  evaluation_metrics?: { error?: string } | null;
}

export const getScenarios = async (): Promise<ScenarioRow[]> =>
  unwrapData<ScenarioRow[]>(await request.get('/api/v1/scenarios'));

export const getDatasets = async (scenarioId: number, pageSize = 200): Promise<DatasetRow[]> => {
  const data = unwrapData<{ items?: DatasetRow[] }>(
    await request.get('/api/v1/datasets', {
      params: { scenario_id: scenarioId, page: 1, page_size: pageSize },
    })
  );
  return data.items ?? [];
};

export const getAlgorithms = async (): Promise<AlgorithmRow[]> =>
  unwrapData<AlgorithmRow[]>(await request.get('/api/v1/algorithms'));

export const trainModel = async (payload: TrainingPayload): Promise<ModelVersionRow> =>
  unwrapData<ModelVersionRow>(await request.post('/api/v1/model-versions/train', payload));

export const trainModelAsync = async (payload: TrainingPayload): Promise<ModelVersionRow> =>
  unwrapData<ModelVersionRow>(await request.post('/api/v1/model-versions/train-async', payload));

export const getModelVersionDetail = async (modelId: number | string): Promise<ModelVersionRow> =>
  unwrapData<ModelVersionRow>(await request.get(`/api/v1/model-versions/${modelId}`));

export const listTrainingJobs = async (includeFinished = false): Promise<TrainingJobRow[]> =>
  unwrapData<TrainingJobRow[]>(
    await request.get('/api/v1/model-versions/training-jobs', {
      params: includeFinished ? { include_finished: true } : undefined,
    })
  );
