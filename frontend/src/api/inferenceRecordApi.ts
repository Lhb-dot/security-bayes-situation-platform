// 推理记录接口（后端 /api/v1/inference-records）。这一层只有 request 调用和解包。
// 权限边界由后端强制执行推理要登录，场景用户只看得到自己的记录。
import request, { getCsrfToken, unwrapData } from '@/utils/request';
import type { InferenceExplain, InferenceRecord } from '@/types/security';

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
  risk_event: RiskEventResult | null;
  explain_data?: InferenceExplain;
  model_evaluation?: {
    available: boolean;
    source: 'ai' | 'fallback' | null;
    markdown: string | null;
    generated_at: string | null;
  };
}

export interface RiskEventResult {
  id: number;
  risk_type: string;
  risk_level: string;
  risk_score: number;
  description: string;
  status: string;
}

export const predictInference = async (params: {
  model_version_id: string | number;
  input_features: Record<string, unknown>;
}): Promise<PredictResult> =>
  unwrapData(await request.post('/api/v1/inference-records/predict', params));

export interface BatchInferenceItem {
  index: number;
  prediction_label: string | null;
  risk_probability: number | null;
  risk_level: string | null;
  is_risk_event: boolean;
  inference_record_id: number | null;
  risk_event_id: number | null;
  error: string | null;
}

export interface BatchInferenceResult {
  total: number;
  succeeded: number;
  failed: number;
  risk_count: number;
  items: BatchInferenceItem[];
  truncated?: boolean;
}

export interface BatchJobReceipt {
  job_id: string;
  total: number;
  truncated: boolean;
}

export interface BatchInferenceJob extends BatchJobReceipt {
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  model_version_id: number;
  processed: number;
  succeeded: number;
  failed: number;
  risk_count: number;
  error: string | null;
  // 提交时刻（epoch 秒，服务端时钟）：已用时间以它为准，刷新后不会归零
  created_at: number;
  // 终态（DONE / FAILED）才有；进行中为 null
  result: BatchInferenceResult | null;
}

// 提交异步批量研判（POST /inference-records/predict-batch/jobs）。
// 0 条最坏要跑十几分钟，超过 nginx 的 proxy_read_timeout（600 秒），走同步接口
// 前端会拿到 504，而记录其实已经落了一半。所以页面走异步这条。模型可见性、数据集
// 区间、CSV 列名这些校验还是在提交时同步做完，错了照常抛。
export const submitInferenceBatch = async (params: {
  model_version_id: string | number;
  source: 'dataset' | 'samples';
  offset?: number;
  limit?: number;
  samples?: Record<string, unknown>[];
}): Promise<BatchJobReceipt> =>
  unwrapData(await request.post('/api/v1/inference-records/predict-batch/jobs', params));

// 上传 CSV 并提交异步批量研判
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

// 批量研判任务进度（GET /inference-records/predict-batch/jobs/{job_id}，仅发起人）
export const getInferenceBatchJob = async (jobId: string): Promise<BatchInferenceJob> =>
  unwrapData(await request.get(`/api/v1/inference-records/predict-batch/jobs/${jobId}`));

export type BatchInferenceJobBrief = Omit<BatchInferenceJob, 'result'>;

// 我的批量研判任务列表（GET /inference-records/predict-batch/jobs，最近的在前）。
export const listInferenceBatchJobs = async (): Promise<BatchInferenceJobBrief[]> =>
  unwrapData(await request.get('/api/v1/inference-records/predict-batch/jobs'));

// 推理记录分页列表（带 total，供列表页翻页用）
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
  const data = await unwrapData<Partial<InferenceRecordPage>>(
    await request.get('/api/v1/inference-records', { params }),
  );
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 10,
  };
};

// 推理记录可解释性信息（GET /inference-records/{record_id}/explain）
export const getInferenceExplain = async (recordId: string | number): Promise<{
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

// 删除推理记录（DELETE /inference-records/{record_id}，仅管理员；已生成风险事件的记录后端禁止删除）
export const removeInferenceRecord = async (recordId: string | number): Promise<void> =>
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
  onReasoning?: (content: string) => void;
  onDelta?: (content: string) => void;
  onError?: (message: string) => void;
  onDone?: (data: Record<string, unknown>) => void;
}

// Read model-result Markdown from the backend SSE endpoint. The key stays server-side.
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
