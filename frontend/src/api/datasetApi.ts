/**
 * datasetApi.ts — 数据集接口（与后端 /api/v1/datasets 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含权限/过滤逻辑。
 * 权限边界由后端强制（需求 2.3/6.5.2）：普通用户仅见已发布模型关联数据集。
 */
import request, { unwrapData } from '@/utils/request';
import type { Dataset, DatasetField, DatasetVersion, ScenarioId } from '@/types/security';

/** 数据集列表（GET /datasets，支持按场景过滤与分页） */
export const getDatasetList = async (params?: {
  scenario_id?: ScenarioId;
  page?: number;
  page_size?: number;
}): Promise<Dataset[]> => {
  const data = await unwrapData(await request.get('/api/v1/datasets', { params }));
  return data.items ?? [];
};

/** 数据集详情（GET /datasets/{dataset_id}，含字段结构） */
export const getDatasetDetail = async (datasetId: string): Promise<Dataset> =>
  unwrapData(await request.get(`/api/v1/datasets/${datasetId}`));

/** 字段预览（GET /datasets/{dataset_id}/fields-schema，供推理表单生成） */
export const getDatasetFieldsSchema = async (datasetId: string): Promise<DatasetField[]> => {
  const data = await unwrapData(await request.get(`/api/v1/datasets/${datasetId}/fields-schema`));
  return data.fields_schema ?? [];
};

/** 上传数据集（POST /datasets，仅管理员；后端为 JSON 契约，版本号自动生成） */
export const uploadDataset = async (params: {
  logical_id: string;
  scenario_id: ScenarioId;
  file_path: string;
  fields_schema: DatasetField[];
  label_field: string;
}): Promise<Dataset> => unwrapData(await request.post('/api/v1/datasets', params));

/** 创建数据集版本（PUT /datasets/{dataset_id}，仅管理员；被模型引用时后端自动创建新版本） */
export const createDatasetVersion = async (
  datasetId: string,
  params?: { file_path?: string; fields_schema?: DatasetField[]; label_field?: string }
): Promise<DatasetVersion> => unwrapData(await request.put(`/api/v1/datasets/${datasetId}`, params));

/** 停用数据集（POST /datasets/{dataset_id}/disable，仅管理员；停用后不得用于新训练） */
export const disableDataset = async (datasetId: string): Promise<void> =>
  unwrapData(await request.post(`/api/v1/datasets/${datasetId}/disable`));

/** 删除数据集（DELETE /datasets/{dataset_id}，仅管理员；被引用时后端禁止物理删除） */
export const removeDataset = async (datasetId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/datasets/${datasetId}`));
