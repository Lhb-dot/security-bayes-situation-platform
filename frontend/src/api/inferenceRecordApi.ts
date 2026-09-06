/**
 * inferenceRecordApi.ts — 推理记录接口（与后端 /api/v1/inference-records 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8）：执行推理需登录；普通用户仅本人记录。
 */
import request, { unwrapData } from '@/utils/request';
import type { InferenceExplain, InferenceRecord } from '@/types/security';

/** 服务端统一预测入口返回结果（POST /inference-records/predict）。 */
export interface PredictResult {
  id: number;
  user_id: number;
  model_version_id: number;
  input_features: Record<string, unknown>;
  prediction_label: string;
  risk_score: number | null;
  risk_level: string | null;
  is_risk_event: boolean;
  executed_at: string;
  /** 预测为风险类时后端自动生成的风险事件；正常类为 null */
  risk_event: RiskEventResult | null;
}

/** 风险事件最小字段（predict 响应中内嵌） */
export interface RiskEventResult {
  id: number;
  risk_type: string;
  risk_level: string;
  risk_score: number;
  description: string;
  status: string;
}

/**
 * 执行单条推理（POST /inference-records/predict，风险类结果自动生成风险事件）
 *
 * 预测结果（prediction_label / risk_score）由服务端统一预测入口根据
 * model_version_id + input_features 计算，客户端不再提交这两个字段。
 */
export const predictInference = async (params: {
  model_version_id: string | number;
  input_features: Record<string, unknown>;
}): Promise<PredictResult> =>
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

/** 推理记录可解释性信息（GET /inference-records/{record_id}/explain） */
export const getInferenceExplain = async (recordId: string): Promise<{
  inference_record_id: number;
  prediction_label: string;
  explain_data: InferenceExplain;
}> =>
  unwrapData(await request.get(`/api/v1/inference-records/${recordId}/explain`));

/** 删除推理记录（DELETE /inference-records/{record_id}，仅管理员；已生成风险事件的记录后端禁止删除） */
export const removeInferenceRecord = async (recordId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/inference-records/${recordId}`));
