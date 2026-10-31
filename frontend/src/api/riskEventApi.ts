/**
 * 风险事件接口（与后端 /api/v1/risk-events 对齐）
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制场景用户仅本人事件。
 */
import request, { unwrapData } from '@/utils/request';
import type { RiskEvent, ScenarioId } from '@/types/security';

export type RiskEventStatus = 'PENDING' | 'PROCESSING' | 'RESOLVED';

export const getRiskEventList = async (params?: {
  scenario_id?: ScenarioId;
  status?: RiskEvent['status'];
  page?: number;
  page_size?: number;
}): Promise<RiskEvent[]> => {
  const data = await unwrapData<{ items?: RiskEvent[] }>(
    await request.get('/api/v1/risk-events', { params }),
  );
  return data.items ?? [];
};

export interface RiskEventPage {
  items: RiskEvent[];
  total: number;
  page: number;
  page_size: number;
}

export const getRiskEventPage = async (params?: {
  scenario_id?: number;
  status?: 'PENDING' | 'PROCESSING' | 'RESOLVED';
  risk_level?: 'HIGH' | 'MEDIUM' | 'LOW';
  include_hidden?: boolean;
  page?: number;
  page_size?: number;
}): Promise<RiskEventPage> => {
  const data = await unwrapData<Partial<RiskEventPage>>(
    await request.get('/api/v1/risk-events', { params }),
  );
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 20,
  };
};

export const getRiskEventDetail = async (eventId: string): Promise<RiskEvent> =>
  unwrapData(await request.get(`/api/v1/risk-events/${eventId}`));

export const updateRiskEventStatus = async (
  eventId: string,
  params: { new_status: RiskEventStatus; comment?: string }
): Promise<RiskEvent> => unwrapData(await request.put(`/api/v1/risk-events/${eventId}/handle`, params));

export const hideRiskEvent = async (eventId: string): Promise<void> =>
  unwrapData(await request.post(`/api/v1/risk-events/${eventId}/hide`));

export const unhideRiskEvent = async (eventId: string): Promise<void> =>
  unwrapData(await request.post(`/api/v1/risk-events/${eventId}/unhide`));
