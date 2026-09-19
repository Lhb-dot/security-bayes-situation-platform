import request, { getCsrfToken, unwrapData } from '@/utils/request';

export interface ModelEvaluationResponse {
  model_version_id: number;
  status: string;
  role: 'management' | 'user';
  model_attributes: Record<string, any>;
  evaluation: {
    available: boolean;
    source?: 'ai' | 'fallback' | 'cached' | null;
    markdown?: string | null;
    generated_at?: string | null;
  };
}

export interface ModelEvaluationStreamHandlers {
  onStart?: (data: Record<string, any>) => void;
  onDelta?: (content: string) => void;
  onError?: (data: Record<string, any>) => void;
  onDone?: (data: Record<string, any>) => void;
}

export type ModelEvaluationAudience = 'current' | 'management' | 'user';

export const getModelEvaluation = async (
  modelId: number,
  audience: ModelEvaluationAudience = 'current',
): Promise<ModelEvaluationResponse> =>
  unwrapData(
    await request.get(`/api/v1/model-versions/${modelId}/evaluation`, {
      params: { audience },
    }),
  );

export const streamModelEvaluation = async (
  modelId: number,
  regenerate: boolean,
  handlers: ModelEvaluationStreamHandlers,
  signal?: AbortSignal,
  audience: ModelEvaluationAudience = 'current',
): Promise<void> => {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '';
  const csrf = getCsrfToken();
  const response = await fetch(`${baseUrl}/api/v1/model-versions/${modelId}/evaluation/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
    },
    body: JSON.stringify({ regenerate, audience }),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new Error(`模型评价请求失败（${response.status}）`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  const consume = (raw: string) => {
    buffer += raw;
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || '';
    for (const block of blocks) {
      const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
      const dataText = block.match(/^data:\s*(.+)$/m)?.[1]?.trim();
      if (!event || !dataText) continue;
      let data: Record<string, any> = {};
      try { data = JSON.parse(dataText); } catch { continue; }
      if (event === 'start') handlers.onStart?.(data);
      else if (event === 'delta' && typeof data.content === 'string') handlers.onDelta?.(data.content);
      else if (event === 'error') handlers.onError?.(data);
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
