// 报告接口（后端 /api/v1/reports）。薄封装，只有 request + unwrapData。
// 权限在后端强制场景用户仅本人数据；管理员可选全平台 / 本场景聚合
// 或本人数据，不支持指定单个用户。
import request, { unwrapData } from '@/utils/request';
import { SCENARIO_CODE_BY_ID, resolveScenarioId } from '@/api/scenarioApi';
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
  next_run_at?: string | null;
  generated_at: string;
  report_id?: string;
  created_at?: string;
  status?: Report['status'];
}

interface ReportPage {
  items: Report[];
  total: number;
  page: number;
  page_size: number;
}

const toReport = (raw: ApiReport): Report => ({
  report_id: raw.report_id ?? String(raw.id),
  title: raw.title,
  scenario_id:
    raw.scenario_code ??
    (raw.scenario_id == null ? '' : (SCENARIO_CODE_BY_ID[raw.scenario_id] ?? '')),
  scenario_name: raw.scenario_name ?? '',
  content: raw.content,
  report_data: raw.report_data,
  created_at: raw.created_at ?? raw.generated_at,
  format: raw.format,
  status: raw.status ?? 'completed',
  scheduled: raw.scheduled,
  interval_days: raw.interval_days ?? undefined,
  next_run_at: raw.next_run_at ?? undefined,
  generated_by: String(raw.generated_by),
});

export const getReportPage = async (params?: {
  page?: number;
  page_size?: number;
}): Promise<ReportPage> => {
  const data = await unwrapData<{
    items?: ApiReport[];
    total?: number;
    page?: number;
    page_size?: number;
  }>(await request.get('/api/v1/reports', { params }));
  return {
    items: (data.items ?? []).map(toReport),
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 10,
  };
};

export const getScheduledReports = async (): Promise<Report[]> => {
  const data = await unwrapData<ApiReport[]>(await request.get('/api/v1/reports/scheduled'));
  return (data ?? []).map(toReport);
};

export const getReportDetail = async (reportId: string): Promise<Report> =>
  toReport(await unwrapData(await request.get(`/api/v1/reports/${reportId}`)) as ApiReport);

export interface ReportGenerateParams {
  scenario_id: ScenarioId | null;
  title: string;
  scope: 'self' | 'all';
  format?: Report['format'];
  scheduled?: boolean;
  interval_days?: number;
}

const buildGeneratePayload = async (params: ReportGenerateParams) => ({
  title: params.title,
  scenario_id: params.scenario_id == null ? null : await resolveScenarioId(params.scenario_id),
  scope: params.scope,
  format: params.format ?? 'markdown',
  scheduled: params.scheduled ?? false,
  interval_days: params.scheduled ? params.interval_days : undefined,
});

export interface ReportGenerateReceipt {
  job_id: string;
}

export interface ReportGenerateJob {
  job_id: string;
  title: string;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  error: string | null;
  report_id: string | null;
  ready: boolean;
  created_at: number;
}

// 线程串行跑。入参校验仍在提交时同步做，参数不对照常抛 400 / 403，
export const submitReportGenerateJob = async (
  params: ReportGenerateParams,
): Promise<ReportGenerateReceipt> =>
  unwrapData(await request.post('/api/v1/reports/generate/jobs', await buildGeneratePayload(params)));

export const getReportGenerateJob = async (jobId: string): Promise<ReportGenerateJob> =>
  unwrapData(await request.get(`/api/v1/reports/generate/jobs/${jobId}`));

export const listReportGenerateJobs = async (): Promise<ReportGenerateJob[]> =>
  ((await unwrapData(await request.get('/api/v1/reports/generate/jobs'))) ?? []) as ReportGenerateJob[];

export const removeReport = async (reportId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/reports/${reportId}`));

export const EXPORT_EXT: Record<Report['format'], string> = {
  markdown: 'md',
  html: 'html',
  pdf: 'pdf',
};

export interface ReportExportReceipt {
  job_id: string;
  report_id: number;
  format: Report['format'];
}

export interface ReportExportJob extends ReportExportReceipt {
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  ready: boolean;
  filename: string | null;
  error: string | null;
  created_at: number;
}

// 提交导出任务（POST /reports/{report_id}/export/jobs）。
// pdf 由后台线程渲染，提交后立刻拿到 job_id，前端轮询 getReportExportJob 到 ready 为止；
// markdown / html 是毫秒级字符串编码，提交即完成，第一次轮询就 ready。
export const submitReportExport = async (
  reportId: string,
  format: Report['format'],
): Promise<ReportExportReceipt> =>
  unwrapData(
    await request.post(`/api/v1/reports/${reportId}/export/jobs`, null, {
      params: { format },
    }),
  );

// 导出任务进度（GET /reports/export/jobs/{job_id}，仅发起人）
export const getReportExportJob = async (jobId: string): Promise<ReportExportJob> =>
  unwrapData(await request.get(`/api/v1/reports/export/jobs/${jobId}`));

// 我的导出任务列表（GET /reports/export/jobs，最近的在前）。
// 服务端 list_jobs 不按状态过滤，终态任务也在返回里（TTL 900 秒），所以刷新后既能把
export const listReportExportJobs = async (): Promise<ReportExportJob[]> =>
  ((await unwrapData(await request.get('/api/v1/reports/export/jobs'))) ?? []) as ReportExportJob[];

// 下载导出任务产出的文件（GET /reports/export/jobs/{job_id}/file，成功时直接回文件流）
export const downloadReportExportFile = async (jobId: string): Promise<Blob> =>
  (await request.get(`/api/v1/reports/export/jobs/${jobId}/file`, {
    responseType: 'blob',
  })) as Blob;
