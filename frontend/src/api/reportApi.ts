/**
 * reportApi.ts — 报告接口（与后端 /api/v1/reports 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 * 权限边界由后端强制（需求 6.8.5）：场景用户仅本人数据；
 * 管理员可选全平台/本场景聚合数据或本人个人数据（不支持指定单个用户）。
 */
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

/** 报告分页（GET /reports，带 total，供报告中心的页码条使用） */
export const getReportPage = async (params?: {
  page?: number;
  page_size?: number;
}): Promise<ReportPage> => {
  const data = await unwrapData(await request.get('/api/v1/reports', { params }));
  return {
    items: (data.items ?? []).map(toReport),
    total: data.total ?? 0,
    page: data.page ?? 1,
    page_size: data.page_size ?? 10,
  };
};

/** 本账号配置的定时报告（GET /reports/scheduled，跟随账号，仅本人生成的） */
export const getScheduledReports = async (): Promise<Report[]> => {
  const data = await unwrapData(await request.get('/api/v1/reports/scheduled'));
  return (data ?? []).map(toReport);
};

/** 报告详情（GET /reports/{report_id}） */
export const getReportDetail = async (reportId: string): Promise<Report> =>
  toReport(await unwrapData(await request.get(`/api/v1/reports/${reportId}`)) as ApiReport);

/** 生成入参（同步接口与后台任务提交共用） */
export interface ReportGenerateParams {
  scenario_id: ScenarioId;
  title: string;
  scope: 'self' | 'all';
  format?: Report['format'];
  scheduled?: boolean;
  interval_days?: number;
}

/** 场景 code → 后端整型 scenario_id，并补齐默认值。两个生成入口共用这一条组装。 */
const buildGeneratePayload = async (params: ReportGenerateParams) => ({
  title: params.title,
  scenario_id: await resolveScenarioId(params.scenario_id),
  scope: params.scope,
  format: params.format ?? 'markdown',
  scheduled: params.scheduled ?? false,
  interval_days: params.scheduled ? params.interval_days : undefined,
});

/** 生成任务提交回执（POST /reports/generate/jobs） */
export interface ReportGenerateReceipt {
  job_id: string;
}

/** 生成任务视图（GET /reports/generate/jobs[/{job_id}]） */
export interface ReportGenerateJob {
  job_id: string;
  title: string;
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  error: string | null;
  /** 生成完成后的报告 id，未完成时为 null */
  report_id: string | null;
  /** 产物就绪 */
  ready: boolean;
  /** 提交时刻（epoch 秒，服务端时钟）：已用时间以它为准，刷新后不会归零 */
  created_at: number;
}

/**
 * 提交后台生成任务（POST /reports/generate/jobs）。
 *
 * POST 立刻返回 job_id，真正的生成（数据聚合 + 多视图研判 + NL 分析）由服务端后台线程串行执行；
 * 入参校验仍在提交时同步完成，参数不对照常抛 400 / 403，不会把注定失败的任务丢进队列。
 */
export const submitReportGenerateJob = async (
  params: ReportGenerateParams,
): Promise<ReportGenerateReceipt> =>
  unwrapData(await request.post('/api/v1/reports/generate/jobs', await buildGeneratePayload(params)));

/** 生成任务进度（GET /reports/generate/jobs/{job_id}，仅发起人） */
export const getReportGenerateJob = async (jobId: string): Promise<ReportGenerateJob> =>
  unwrapData(await request.get(`/api/v1/reports/generate/jobs/${jobId}`));

/** 我的生成任务列表（GET /reports/generate/jobs，最近的在前；供刷新后恢复在途状态） */
export const listReportGenerateJobs = async (): Promise<ReportGenerateJob[]> =>
  ((await unwrapData(await request.get('/api/v1/reports/generate/jobs'))) ?? []) as ReportGenerateJob[];

/** 删除报告（DELETE /reports/{report_id}，生成者本人或管理员） */
export const removeReport = async (reportId: string): Promise<void> =>
  unwrapData(await request.delete(`/api/v1/reports/${reportId}`));

/** 导出格式 → 文件扩展名（与后端 report_export.EXTENSIONS 对齐） */
export const EXPORT_EXT: Record<Report['format'], string> = {
  markdown: 'md',
  html: 'html',
  pdf: 'pdf',
};

/** 导出任务提交回执（POST /reports/{report_id}/export/jobs） */
export interface ReportExportReceipt {
  job_id: string;
  report_id: number;
  format: Report['format'];
}

/** 导出任务视图（GET /reports/export/jobs/{job_id}） */
export interface ReportExportJob extends ReportExportReceipt {
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';
  /** 产物就绪，可以取文件 */
  ready: boolean;
  filename: string | null;
  error: string | null;
  /** 提交时刻（epoch 秒，服务端时钟） */
  created_at: number;
}

/**
 * 提交导出任务（POST /reports/{report_id}/export/jobs）。
 *
 * pdf 由后台线程渲染，提交后立刻返回 job_id，前端轮询 getReportExportJob 直到 ready；
 * markdown / html 是毫秒级字符串编码，提交即完成（第一次轮询就 ready）。
 * 权限与格式校验仍在提交时同步完成，错误照常抛出。
 */
export const submitReportExport = async (
  reportId: string,
  format: Report['format'],
): Promise<ReportExportReceipt> =>
  unwrapData(
    await request.post(`/api/v1/reports/${reportId}/export/jobs`, null, {
      params: { format },
    }),
  );

/** 导出任务进度（GET /reports/export/jobs/{job_id}，仅发起人） */
export const getReportExportJob = async (jobId: string): Promise<ReportExportJob> =>
  unwrapData(await request.get(`/api/v1/reports/export/jobs/${jobId}`));

/**
 * 我的导出任务列表（GET /reports/export/jobs，最近的在前）。
 *
 * 服务端的 list_jobs 不按状态过滤，终态任务也在返回里（TTL 900 秒内保留），
 * 所以刷新后能把「还在导出」的接回轮询，也能靠它判定「已完成但没看过」。
 */
export const listReportExportJobs = async (): Promise<ReportExportJob[]> =>
  ((await unwrapData(await request.get('/api/v1/reports/export/jobs'))) ?? []) as ReportExportJob[];

/** 下载导出任务产出的文件（GET /reports/export/jobs/{job_id}/file，成功时直接回文件流） */
export const downloadReportExportFile = async (jobId: string): Promise<Blob> =>
  (await request.get(`/api/v1/reports/export/jobs/${jobId}/file`, {
    responseType: 'blob',
  })) as Blob;
