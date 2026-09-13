import request, { unwrapData } from '@/utils/request';

export interface AISetting {
  configured: boolean;
  provider?: string;
  base_url?: string;
  model?: string;
  enabled?: boolean;
  api_key_masked?: string | null;
  updated_at?: string;
}

export const getAISetting = async (): Promise<AISetting> =>
  unwrapData(await request.get('/api/v1/settings/ai'));

export const updateAISetting = async (params: {
  provider: string;
  base_url: string;
  model: string;
  api_key?: string;
  enabled: boolean;
}): Promise<AISetting> =>
  unwrapData(await request.put('/api/v1/settings/ai', params));
