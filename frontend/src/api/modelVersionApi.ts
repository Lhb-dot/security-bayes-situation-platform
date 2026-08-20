/**
 * modelVersionApi.ts — 模型版本接口（与后端 /api/v1/model-versions 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.7/6.5.2）：训练/发布/禁用/删除/默认推荐仅管理员。
 */
import request, { unwrapData } from '@/utils/request';
import type { ModelStatus, ScenarioId } from '@/types/security';

/** /api/v1/model-versions 返回的数据库模型行。 */
export interface BackendModelVersion {
  id: number;
  model_version_id: number;
  scenario_id: number;
  scenario_code?: string | null;
  scenario_name?: string | null;
  dataset_id: number;
  dataset_logical_id?: string | null;
  dataset_version?: number | null;
  algorithm_id: number;
  algorithm_code?: string | null;
  algorithm_name?: string | null;
  training_parameters: Record<string, unknown>;
  evaluation_metrics: Record<string, number | string>;
  trained_by: number;
  trained_by_name?: string | null;
  trained_at: string;
  status: ModelStatus;
  published_by?: number | null;
  published_by_name?: string | null;
  published_at?: string | null;
  is_default: boolean;
}

/** 模型版本列表（GET /model-versions，普通用户仅见 PUBLISHED） */
export const getModelVersionList = async (params?: {
  scenario_id?: ScenarioId | number;
  dataset_id?: string | number;
  status?: ModelStatus;
  page?: number;
  page_size?: number;
}): Promise<BackendModelVersion[]> => {
  const data = await unwrapData(await request.get('/api/v1/model-versions', { params }));
  return data.items ?? [];
};

/** 获取场景+数据集的默认推荐模型（GET /model-versions/default；无默认时 data 为 null） */
export const getDefaultModel = async (params: {
  scenario_id: ScenarioId | number;
  dataset_id: string | number;
}): Promise<BackendModelVersion | null> =>
  unwrapData(await request.get('/api/v1/model-versions/default', { params }));

/** 模型版本对比（POST /model-versions/compare，data 为数组） */
export const compareModelVersions = async (modelIds: Array<string | number>): Promise<BackendModelVersion[]> =>
  unwrapData(await request.post('/api/v1/model-versions/compare', { model_ids: modelIds }));

/** 训练并保存模型版本（POST /model-versions/train，仅管理员；PMWNB 真实调用，其余 mock 占位） */
export const trainModel = async (params: {
  scenario_id: ScenarioId | number;
  dataset_id: string | number;
  algorithm_id: string | number;
  training_parameters: Record<string, unknown>;
}): Promise<BackendModelVersion> => unwrapData(await request.post('/api/v1/model-versions/train', params));

/** 发布模型（POST /model-versions/{model_id}/publish，仅管理员） */
export const publishModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/publish`));

/** 下线模型（POST /model-versions/{model_id}/offline，仅管理员；自动清除默认推荐状态） */
export const offlineModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/offline`));

/** 禁用模型（POST /model-versions/{model_id}/disable，仅管理员） */
export const disableModel = async (modelId: number | string): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/disable`));

/** 删除禁用中的模型（DELETE /model-versions/{model_id}，仅管理员） */
export const deleteModelVersion = async (modelId: number | string): Promise<void> => {
  await unwrapData(await request.delete(`/api/v1/model-versions/${modelId}`));
};

/** 设为默认推荐模型（POST /model-versions/{model_id}/set-default，仅管理员） */
export const setDefaultModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/set-default`));

/** 取消默认推荐状态（POST /model-versions/{model_id}/clear-default，仅管理员） */
export const clearDefaultModel = async (modelId: string | number): Promise<BackendModelVersion> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/clear-default`));
