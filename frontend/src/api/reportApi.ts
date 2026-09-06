/**
 * reportApi.ts — 报告接口（与后端 /api/v1/reports 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8.5）：普通用户仅本人数据；管理员可全平台或指定用户。
 */
import request, { unwrapData } from '@/utils/request';
import type { Report, ScenarioId } from '@/types/security';

interface ApiReport {
  id: number;
  generated_by: number;
  title: string;
  target_user_id: number | null;
  scenario_id: number | null;
  scenario_code?: ScenarioId;
  scenario_name?: string;
  content: string;
  format: Report['format'];
  scheduled: boolean;
  interval_days: number | null;
  generated_at: string;
  report_id?: string;
  created_at?: string;
  status?: Report['status'];
}

const SCENARIO_BY_ID: Record<number, ScenarioId> = {
  1: 'network_security',
  2: 'power_system',
  3: 'flightdeck_operation',
  4: 'geological_risk',
};

const toReport = (raw: ApiReport): Report => ({
  report_id: raw.report_id ?? String(raw.id),
  title: raw.title,
  scenario_id: raw.scenario_code ?? (raw.scenario_id == null ? 'network_security' : (SCENARIO_BY_ID[raw.scenario_id] ?? 'network_security')),
  scenario_name: raw.scenario_name ?? '',
  summary: raw.content,
  content: raw.content,
  created_at: raw.created_at ?? raw.generated_at,
  format: raw.format,
  status: raw.status ?? 'completed',
  scheduled: raw.scheduled,
  interval_days: raw.interval_days ?? undefined,
  generated_by: String(raw.generated_by),
  target_user_id: raw.target_user_id == null ? undefined : String(raw.target_user_id),
});

/** 报告列表（GET /reports，普通用户：本人生成或定向给自己的报告） */
export const getReportList = async (params?: {
  target_user_id?: string;
  page?: number;
  page_size?: number;
}): Promise<Report[]> => {
  const data = await unwrapData(await request.get('/api/v1/reports', { params }));
  return (data.items ?? []).map(toReport);
};

/** 报告详情（GET /reports/{report_id}） */
export const getReportDetail = async (reportId: string): Promise<Report> =>
  toReport(await unwrapData(await request.get(`/api/v1/reports/${reportId}`)) as ApiReport);

/** 生成态势报告（POST /reports，普通用户仅本人数据） */
export const generateReport = async (params: {
  scenario_id: ScenarioId;
  title: string;
  scope: 'self' | 'all' | 'user';
  target_user_id?: string;
  format?: Report['format'];
  scheduled?: boolean;
  interval_days?: number;
}): Promise<Report> => {
  const { resolveScenarioId } = await import('@/api/scenarioApi');
  const scenarioId = await resolveScenarioId(params.scenario_id);
  const scopeLabel = params.scope === 'all' ? '全平台' : params.scope === 'user' ? `指定用户 ${params.target_user_id}` : '本人';
  const raw = await unwrapData(
    await request.post('/api/v1/reports', {
      title: params.title,
      report_type: params.scope === 'self' ? 'USER_SNAPSHOT' : 'SCENE_SNAPSHOT',
      content: `# ${params.title}\n\n数据范围：${scopeLabel}\n\n报告已创建并保存，后续可根据该配置执行具体定时生成。`,
      target_user_id: params.target_user_id ? Number(params.target_user_id) : undefined,
      scenario_id: scenarioId,
      format: params.format ?? 'markdown',
      scheduled: params.scheduled ?? false,
      interval_days: params.scheduled ? params.interval_days : undefined,
    }),
  );
  return toReport(raw as ApiReport);
};

/** 保存定时设置；当前仅记录配置，不启动调度执行。 */
export const updateReportSchedule = async (
  reportId: string,
  scheduled: boolean,
  intervalDays?: number,
): Promise<Report> => {
  const raw = await unwrapData(
    await request.put(`/api/v1/reports/${reportId}/schedule`, {
      scheduled,
      interval_days: scheduled ? intervalDays : undefined,
    }),
  );
  return toReport(raw as ApiReport);
};

/** 删除报告（DELETE /reports/{report_id}，生成者本人或管理员） */
export const removeReport = async (reportId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/reports/${reportId}`));
