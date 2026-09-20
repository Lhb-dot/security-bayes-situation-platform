/**
 * riskEventApi.ts — 风险事件接口（与后端 /api/v1/risk-events 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 5.2）：普通用户仅本人事件。
 */
import request, { unwrapData } from '@/utils/request';
import type { RiskEvent, ScenarioId } from '@/types/security';

/** 风险事件列表（GET /risk-events，普通用户仅本人事件；管理员可按场景/状态过滤） */
export const getRiskEventList = async (params?: {
  scenario_id?: ScenarioId;
  status?: RiskEvent['status'];
  page?: number;
  page_size?: number;
}): Promise<RiskEvent[]> => {
  // TODO 联调对齐：后端处置状态为 PENDING/PROCESSING/RESOLVED，前端为 待处置/处理中/已处置
  const data = await unwrapData(await request.get('/api/v1/risk-events', { params }));
  return data.items ?? [];
};

/** 风险事件分页列表（带 total，供列表页翻页与后端筛选用） */
export interface RiskEventPage {
  items: RiskEvent[];
  total: number;
  page: number;
  page_size: number;
}

/**
 * 风险事件分页查询。筛选在后端执行，因此翻页时筛选条件跨全量数据生效。
 * scenario_id 为后端场景数字 ID；status 为后端枚举；risk_level 按查看者阈值判级。
 */
export const getRiskEventPage = async (params?: {
  scenario_id?: number;
  status?: 'PENDING' | 'PROCESSING' | 'RESOLVED';
  risk_level?: 'HIGH' | 'MEDIUM' | 'LOW';
  page?: number;
  page_size?: number;
}): Promise<RiskEventPage> => {
  const data = await unwrapData(await request.get('/api/v1/risk-events', { params }));
  return {
    items: data.items ?? [],
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 20,
  };
};

/** 风险事件详情（GET /risk-events/{event_id}，普通用户仅本人事件） */
export const getRiskEventDetail = async (eventId: string): Promise<RiskEvent> =>
  unwrapData(await request.get(`/api/v1/risk-events/${eventId}`));

/** 处置风险事件（PUT /risk-events/{event_id}/handle，更新状态并写入处置记录） */
export const updateRiskEventStatus = async (
  eventId: string,
  params: { new_status: RiskEvent['status']; comment?: string }
): Promise<RiskEvent> => unwrapData(await request.put(`/api/v1/risk-events/${eventId}/handle`, params));

/** 追加处置说明（POST /risk-events/{event_id}/comment，不改变状态） */
export const commentRiskEvent = async (eventId: string, comment: string): Promise<void> =>
  unwrapData(await request.post(`/api/v1/risk-events/${eventId}/comment`, { comment }));
