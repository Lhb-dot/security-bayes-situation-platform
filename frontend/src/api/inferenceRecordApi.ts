/**
 * inferenceRecordApi.ts — 推理记录接口（与后端 /api/v1/inference-records 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8）：执行推理需登录；普通用户仅本人记录。
 */
import request, { getCsrfToken, unwrapData } from '@/utils/request';
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
  explain_data?: InferenceExplain;
  model_evaluation?: {
    available: boolean;
    source: 'ai' | 'fallback' | null;
    markdown: string | null;
    generated_at: string | null;
  };
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

/** 批量研判单条结果 */
export interface BatchInferenceItem {
  index: number;
  prediction_label: string | null;
  risk_probability: number | null;
  risk_level: string | null;
  is_risk_event: boolean;
  inference_record_id: number | null;
  risk_event_id: number | null;
  /** 该条失败时的原因；成功为 null */
  error: string | null;
}

/** 批量研判汇总结果 */
export interface BatchInferenceResult {
  total: number;
  succeeded: number;
  failed: number;
  risk_count: number;
  items: BatchInferenceItem[];
  /** 样本数超过单批上限、只跑了前面部分时为 true */
  truncated?: boolean;
}

/**
 * 批量研判（POST /inference-records/predict-batch）
 *
 * source='dataset'：由服务端从模型绑定数据集读 offset..offset+limit 条样本；
 * source='samples'：直接提交样本列表。
 * 判为风险类的样本与单条一致，会自动生成 RiskEvent（告警中心可见）。
 */
export const predictInferenceBatch = async (params: {
  model_version_id: string | number;
  source: 'dataset' | 'samples';
  offset?: number;
  limit?: number;
  samples?: Record<string, unknown>[];
}): Promise<BatchInferenceResult> =>
  unwrapData(await request.post('/api/v1/inference-records/predict-batch', params));

/** 上传 CSV 批量研判（表头需覆盖数据集全部输入特征） */
export const predictInferenceBatchUpload = async (params: {
  model_version_id: string | number;
  file: File;
}): Promise<BatchInferenceResult> => {
  const form = new FormData();
  form.append('file', params.file);
  form.append('model_version_id', String(params.model_version_id));
  return unwrapData(
    await request.post('/api/v1/inference-records/predict-batch/upload', form),
  );
};

/** 异步批量研判的提交回执 */
export interface BatchJobReceipt {
  job_id: string;
  total: number;
  /** 样本数超过单批上限、只提交了前面部分时为 true */
  truncated: boolean;
}

/** 批量研判任务视图（GET /inference-records/predict-batch/jobs/{job_id}） */
export interface BatchInferenceJob extends BatchJobReceipt {
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  model_version_id: number;
  /** 已处理条数，用于进度展示 */
  processed: number;
  succeeded: number;
  failed: number;
  risk_count: number;
  /** 任务整体失败时的原因 */
  error: string | null;
  /** 提交时刻（epoch 秒，服务端时钟）：已用时间以它为准，刷新后不会归零 */
  created_at: number;
  /** 终态（DONE / FAILED）才有；进行中为 null */
  result: BatchInferenceResult | null;
}

/**
 * 提交异步批量研判（POST /inference-records/predict-batch/jobs）
 *
 * 200 条最坏可跑十几分钟，超过 nginx 的 proxy_read_timeout（600 秒）：同步接口会让
 * 前端拿到 504 而实际已经落了一半记录，所以页面走这条。模型可见性、数据集区间、
 * CSV 列名等校验仍在提交时同步完成，错误照常抛出。
 */
export const submitInferenceBatch = async (params: {
  model_version_id: string | number;
  source: 'dataset' | 'samples';
  offset?: number;
  limit?: number;
  samples?: Record<string, unknown>[];
}): Promise<BatchJobReceipt> =>
  unwrapData(await request.post('/api/v1/inference-records/predict-batch/jobs', params));

/** 上传 CSV 并提交异步批量研判 */
export const submitInferenceBatchUpload = async (params: {
  model_version_id: string | number;
  file: File;
}): Promise<BatchJobReceipt> => {
  const form = new FormData();
  form.append('file', params.file);
  form.append('model_version_id', String(params.model_version_id));
  return unwrapData(
    await request.post('/api/v1/inference-records/predict-batch/upload/jobs', form),
  );
};

/** 批量研判任务进度（GET /inference-records/predict-batch/jobs/{job_id}，仅发起人） */
export const getInferenceBatchJob = async (jobId: string): Promise<BatchInferenceJob> =>
  unwrapData(await request.get(`/api/v1/inference-records/predict-batch/jobs/${jobId}`));

/** 任务列表视图：不含逐条明细（明细走单任务接口，列表只用来恢复在途状态） */
export type BatchInferenceJobBrief = Omit<BatchInferenceJob, 'result'>;

/**
 * 我的批量研判任务列表（GET /inference-records/predict-batch/jobs，最近的在前）
 *
 * 任务表在服务端进程内，前端这侧的状态随页面一起没；刷新 / 切页回来靠它把未完成的
 * 任务接回轮询，这样离开研判页也不会丢掉完成通知。
 */
export const listInferenceBatchJobs = async (): Promise<BatchInferenceJobBrief[]> =>
  unwrapData(await request.get('/api/v1/inference-records/predict-batch/jobs'));

/** 推理记录分页列表（带 total，供列表页翻页用；后端分页结构与 getInferenceRecordList 同一接口） */
export interface InferenceRecordPage {
  items: InferenceRecord[];
  total: number;
  page: number;
  page_size: number;
}

export const getInferenceRecordPage = async (params?: {
  model_version_id?: string;
  page?: number;
  page_size?: number;
}): Promise<InferenceRecordPage> => {
  const data = await unwrapData(await request.get('/api/v1/inference-records', { params }));
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 20,
  };
};

/** 推理记录列表（GET /inference-records，普通用户仅本人；管理员全部；取分页结果的 items） */
export const getInferenceRecordList = async (params?: {
  model_version_id?: string;
  page?: number;
  page_size?: number;
}): Promise<InferenceRecord[]> => (await getInferenceRecordPage(params)).items;

/** 推理记录详情（GET /inference-records/{record_id}，普通用户仅本人） */
export const getInferenceRecordDetail = async (recordId: string): Promise<InferenceRecord> =>
  unwrapData(await request.get(`/api/v1/inference-records/${recordId}`));

/** 推理记录可解释性信息（GET /inference-records/{record_id}/explain） */
export const getInferenceExplain = async (recordId: string): Promise<{
  inference_record_id: number;
  prediction_label: string;
  explain_data: InferenceExplain;
  generated_explanation?: {
    available: boolean;
    markdown?: string;
    source?: 'ai' | 'fallback' | null;
    generated_at?: string | null;
    data_snapshot?: Record<string, unknown>;
  };
}> =>
  unwrapData(await request.get(`/api/v1/inference-records/${recordId}/explain`));

/** 删除推理记录（DELETE /inference-records/{record_id}，仅管理员；已生成风险事件的记录后端禁止删除） */
export const removeInferenceRecord = async (recordId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/inference-records/${recordId}`));

export interface ExplanationStreamParams {
  scenario: Record<string, unknown>;
  sample: Record<string, unknown>;
  model_result: Record<string, unknown>;
  algorithm_details: Record<string, unknown>;
  recommended_actions: string[];
  inference_record_id?: number;
  model_version_id?: string | number;
}

export interface ExplanationStreamHandlers {
  onStart?: (data: Record<string, unknown>) => void;
  /** 推理型模型的思维链，只用于展示「确实在生成」，不落库 */
  onReasoning?: (content: string) => void;
  onDelta?: (content: string) => void;
  onError?: (message: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
}

/** Read model-result Markdown from the backend SSE endpoint. The key stays server-side. */
export const streamInferenceExplanation = async (
  params: ExplanationStreamParams,
  handlers: ExplanationStreamHandlers,
  signal?: AbortSignal,
): Promise<void> => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const csrf = getCsrfToken();
  const response = await fetch(`${baseUrl}/api/v1/inference/explanation/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
    },
    body: JSON.stringify(params),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`AI 分析请求失败（${response.status}）`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const consume = (raw: string) => {
    buffer += raw;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? '';
    for (const block of blocks) {
      const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
      const dataText = block.match(/^data:\s*(.+)$/m)?.[1]?.trim();
      if (!event || !dataText) continue;
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(dataText) as Record<string, unknown>; } catch { continue; }
      if (event === 'start') handlers.onStart?.(data);
      else if (event === 'reasoning' && typeof data.content === 'string') handlers.onReasoning?.(data.content);
      else if (event === 'delta' && typeof data.content === 'string') handlers.onDelta?.(data.content);
      else if (event === 'error') handlers.onError?.(String(data.message ?? 'AI 分析失败'));
      else if (event === 'done') handlers.onDone?.(data);
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    consume(decoder.decode(value, { stream: true }));
  }
  consume(decoder.decode());
};
