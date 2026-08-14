/**
 * inferenceRecordApi.ts — 推理记录接口（与后端 /api/v1/inference-records 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8）：执行推理需登录；普通用户仅本人记录。
 */
import request, { unwrapData } from '@/utils/request';
import type { InferenceRecord } from '@/types/security';

/**
 * 执行单条推理（POST /inference-records/predict，风险类结果自动生成风险事件）
 *
 * TODO 联调占位：后端当前要求客户端传 prediction_label / risk_score，
 * 正式版将改为服务端统一预测入口，请求体不再携带这两个字段。
 */
export const predictInference = async (params: {
  model_version_id: string;
  input_features: Record<string, unknown>;
  prediction_label: string;
  risk_score?: number;
}): Promise<InferenceRecord> =>
  unwrapData(await request.post('/api/v1/inference-records/predict', params));

/** 推理记录列表（GET /inference-records，普通用户仅本人；管理员全部） */
export const getInferenceRecordList = async (params?: {
  model_version_id?: string;
  page?: number;
  page_size?: number;
}): Promise<InferenceRecord[]> => {
  const data = await unwrapData(await request.get('/api/v1/inference-records', { params }));
  return data.items ?? [];
};

/** 推理记录详情（GET /inference-records/{record_id}，普通用户仅本人） */
export const getInferenceRecordDetail = async (recordId: string): Promise<InferenceRecord> =>
  unwrapData(await request.get(`/api/v1/inference-records/${recordId}`));

/** 删除推理记录（DELETE /inference-records/{record_id}，仅管理员；已生成风险事件的记录后端禁止删除） */
export const removeInferenceRecord = async (recordId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/inference-records/${recordId}`));
