// 模型版本接口（后端 /api/v1/model-versions）。只有 request 调用和 unwrapData 解包。
// 权限边界由后端强制：训练、发布、禁用、删除、推荐都只对管理级角色开放。
import request, { unwrapData } from '@/utils/request';
import type { EvaluationMetrics, ModelStatus, ScenarioId } from '@/types/security';

// /api/v1/model-versions 返回的数据库模型行。
export interface BackendModelVersion {
  id: number;
  model_version_id: number;
  scenario_id: number;
  scenario_code?: string | null;
  scenario_name?: string | null;
  dataset_id: number;
  dataset_logical_id?: string | null;
  dataset_name?: string | null;
  dataset_version?: number | null;
  algorithm_id: number;
  algorithm_code?: string | null;
  algorithm_name?: string | null;
  training_parameters: Record<string, unknown>;
  evaluation_metrics: EvaluationMetrics;
  trained_by: number;
  trained_by_name?: string | null;
  trained_at: string;
  status: ModelStatus;
  published_by?: number | null;
  published_by_name?: string | null;
  published_at?: string | null;
  is_recommended: boolean;
  model_evaluation_available?: boolean;
  model_attributes?: Record<string, unknown>;
}

export interface ModelVersionPage {
  items: BackendModelVersion[];
  total: number;
  page: number;
  page_size: number;
}

export const getModelVersionPage = async (params?: {
  scenario_id?: ScenarioId | number;
  dataset_id?: string | number;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<ModelVersionPage> => {
  const data = await unwrapData<Partial<ModelVersionPage>>(
    await request.get('/api/v1/model-versions', { params }),
  );
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 10,
  };
};

export const getModelVersionList = async (params?: {
  scenario_id?: ScenarioId | number;
  dataset_id?: string | number;
  status?: ModelStatus;
  page?: number;
  page_size?: number;
}): Promise<BackendModelVersion[]> => (await getModelVersionPage(params)).items;

export const trainModel = async (params: {
  scenario_id: ScenarioId | number;
  dataset_id: string | number;
  algorithm_id: string | number;
  training_parameters: Record<string, unknown>;
}): Promise<BackendModelVersion> => unwrapData(await request.post('/api/v1/model-versions/train', params));

export const publishModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/publish`));

export const disableModel = async (modelId: number | string): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/disable`));

export const enableModel = async (modelId: number | string): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/enable`));

// 删除禁用中的模型（DELETE /model-versions/{model_id}，仅管理员）
export const deleteModelVersion = async (modelId: number | string): Promise<void> => {
  await unwrapData(await request.delete(`/api/v1/model-versions/${modelId}`));
};

// 设为推荐模型（POST /model-versions/{model_id}/recommend，仅管理员；推荐不唯一）
export const recommendModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/recommend`));

// 取消推荐状态（POST /model-versions/{model_id}/unrecommend，仅管理员）
export const unrecommendModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/unrecommend`));
