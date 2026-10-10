/**
 * riskEventApi.ts — 风险事件接口（与后端 /api/v1/risk-events 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 5.2）：场景用户仅本人事件。
 */
import request, { unwrapData } from '@/utils/request';
import type { RiskEvent, ScenarioId } from '@/types/security';

/** 风险事件列表（GET /risk-events，场景用户仅本人事件；管理员可按场景/状态过滤） */
export const getRiskEventList = async (params?: {
  scenario_id?: ScenarioId;
  status?: RiskEvent['status'];
  page?: number;
  page_size?: number;
}): Promise<RiskEvent[]> => {
  // 声明返回已映射的 RiskEvent[]，实际是后端原始行（status 为 PENDING/PROCESSING/RESOLVED 枚举，非中文）
  const data = await unwrapData<{ items?: RiskEvent[] }>(
    await request.get('/api/v1/risk-events', { params }),
  );
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
 * include_hidden 为 true 时连已隐藏的事件一起返回（默认不带）。
 */
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

/** 风险事件详情（GET /risk-events/{event_id}，场景用户仅本人事件） */
export const getRiskEventDetail = async (eventId: string): Promise<RiskEvent> =>
  unwrapData(await request.get(`/api/v1/risk-events/${eventId}`));

/** 处置风险事件（PUT /risk-events/{event_id}/handle，更新状态并写入处置记录） */
export const updateRiskEventStatus = async (
  eventId: string,
  params: { new_status: RiskEvent['status']; comment?: string }
): Promise<RiskEvent> => unwrapData(await request.put(`/api/v1/risk-events/${eventId}/handle`, params));

/**
 * 隐藏风险事件（POST /risk-events/{event_id}/hide）。
 *
 * 是**软隐藏**不是删除 —— 需求 5.2 访问控制第 4 条要求历史事件不得被无痕删除，
 * 后端的 DELETE 接口因此永远返回 400。隐藏只切可见性开关，数据与处置记录一行不动。
 */
export const hideRiskEvent = async (eventId: string): Promise<void> =>
  unwrapData(await request.post(`/api/v1/risk-events/${eventId}/hide`));

/** 取消隐藏风险事件（POST /risk-events/{event_id}/unhide，置回可见） */
export const unhideRiskEvent = async (eventId: string): Promise<void> =>
  unwrapData(await request.post(`/api/v1/risk-events/${eventId}/unhide`));
