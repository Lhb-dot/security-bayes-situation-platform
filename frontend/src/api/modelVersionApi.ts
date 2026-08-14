/**
 * modelVersionApi.ts — 模型版本接口（与后端 /api/v1/model-versions 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.7/6.5.2）：训练/发布/下线/默认推荐仅 ADMIN。
 */
import request, { unwrapData } from '@/utils/request';
import type { ModelStatus, ModelVersionRecord, ScenarioId } from '@/types/security';

/** 模型版本列表（GET /model-versions，普通用户仅见 PUBLISHED） */
export const getModelVersionList = async (params?: {
  scenario_id?: ScenarioId;
  dataset_id?: string;
  status?: ModelStatus;
  page?: number;
  page_size?: number;
}): Promise<ModelVersionRecord[]> => {
  const data = await unwrapData(await request.get('/api/v1/model-versions', { params }));
  return data.items ?? [];
};

/** 获取场景+数据集的默认推荐模型（GET /model-versions/default；无默认时 data 为 null） */
export const getDefaultModel = async (params: {
  scenario_id: ScenarioId;
  dataset_id: string;
}): Promise<ModelVersionRecord | null> =>
  unwrapData(await request.get('/api/v1/model-versions/default', { params }));

/** 模型版本对比（POST /model-versions/compare，data 为数组） */
export const compareModelVersions = async (modelIds: string[]): Promise<ModelVersionRecord[]> =>
  unwrapData(await request.post('/api/v1/model-versions/compare', { model_ids: modelIds }));

/** 训练并保存模型版本（POST /model-versions/train，仅管理员；PMWNB 真实调用，其余 mock 占位） */
export const trainModel = async (params: {
  scenario_id: ScenarioId;
  dataset_id: string;
  algorithm_id: string;
  training_parameters: Record<string, unknown>;
}): Promise<ModelVersionRecord> => unwrapData(await request.post('/api/v1/model-versions/train', params));

/** 发布模型（POST /model-versions/{model_id}/publish，仅管理员） */
export const publishModel = async (modelId: string): Promise<ModelVersionRecord> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/publish`));

/** 下线模型（POST /model-versions/{model_id}/offline，仅管理员；自动清除默认推荐状态） */
export const offlineModel = async (modelId: string): Promise<ModelVersionRecord> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/offline`));

/** 设为默认推荐模型（POST /model-versions/{model_id}/set-default，仅管理员） */
export const setDefaultModel = async (modelId: string): Promise<ModelVersionRecord> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/set-default`));

/** 取消默认推荐状态（POST /model-versions/{model_id}/clear-default，仅管理员） */
export const clearDefaultModel = async (modelId: string): Promise<ModelVersionRecord> =>
  unwrapData(await request.post(`/api/v1/model-versions/${modelId}/clear-default`));
