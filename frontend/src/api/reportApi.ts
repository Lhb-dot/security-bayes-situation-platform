/**
 * reportApi.ts — 报告接口（与后端 /api/v1/reports 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8.5）：场景用户仅本人数据；
 * 管理员可选全平台/本场景聚合数据或本人个人数据（不支持指定单个用户）。
 */
import request, { unwrapData } from '@/utils/request';
import type { Report, ReportData, ScenarioId } from '@/types/security';

interface ApiReport {
  id: number;
  generated_by: number;
  title: string;
  scenario_id: number | null;
  scenario_code?: ScenarioId;
  scenario_name?: string;
  content: string;
  report_data?: ReportData;
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
  report_data: raw.report_data,
  created_at: raw.created_at ?? raw.generated_at,
  format: raw.format,
  status: raw.status ?? 'completed',
  scheduled: raw.scheduled,
  interval_days: raw.interval_days ?? undefined,
  generated_by: String(raw.generated_by),
});

/** 报告列表（GET /reports，场景用户：本人生成的报告） */
export const getReportList = async (params?: {
  page?: number;
  page_size?: number;
}): Promise<Report[]> => {
  const data = await unwrapData(await request.get('/api/v1/reports', { params }));
  return (data.items ?? []).map(toReport);
};

/** 报告详情（GET /reports/{report_id}） */
export const getReportDetail = async (reportId: string): Promise<Report> =>
  toReport(await unwrapData(await request.get(`/api/v1/reports/${reportId}`)) as ApiReport);

/** 生成态势报告（POST /reports/generate，服务端基于真实数据 + 算法解释自动组装内容） */
export const generateReport = async (params: {
  scenario_id: ScenarioId;
  title: string;
  scope: 'self' | 'all';
  format?: Report['format'];
  scheduled?: boolean;
  interval_days?: number;
}): Promise<Report> => {
  const { resolveScenarioId } = await import('@/api/scenarioApi');
  const scenarioId = await resolveScenarioId(params.scenario_id);
  const raw = await unwrapData(
    await request.post('/api/v1/reports/generate', {
      title: params.title,
      scenario_id: scenarioId,
      scope: params.scope,
      format: params.format ?? 'markdown',
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
