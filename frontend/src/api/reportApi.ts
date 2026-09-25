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
  next_run_at: raw.next_run_at ?? undefined,
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
const buildGeneratePayload = async (params: ReportGenerateParams) => {
  const { resolveScenarioId } = await import('@/api/scenarioApi');
  return {
    title: params.title,
    scenario_id: await resolveScenarioId(params.scenario_id),
    scope: params.scope,
    format: params.format ?? 'markdown',
    scheduled: params.scheduled ?? false,
    interval_days: params.scheduled ? params.interval_days : undefined,
  };
};

/** 生成态势报告（POST /reports/generate，同步；服务端基于真实数据 + 算法解释自动组装内容）
 *
 * scheduled=true 时同一条报告会登记为定时报告：立刻产出内容并记录下次生成时间，
 * 到期由服务端调度器原地重新生成。
 *
 * 页面已改走下面的任务接口（生成要十几秒起步，同步会把界面钉住）；
 * 这个同步封装保留作回退用。
 */
export const generateReport = async (params: ReportGenerateParams): Promise<Report> => {
  const raw = await unwrapData(
    await request.post('/api/v1/reports/generate', await buildGeneratePayload(params)),
  );
  return toReport(raw as ApiReport);
};

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

/**
 * 下载报告文件（GET /reports/{report_id}/export，同步）。
 *
 * 服务端把 Markdown 正文转成目标格式：markdown 原样、html 套打印模板、
 * pdf 再由 Chromium 渲染；三种格式共用同一份正文，不会出现内容不一致。
 * 传 responseType: 'blob' 是因为该接口成功时直接回文件流，不走统一 JSON 结构。
 *
 * PDF 渲染会让请求线程等到渲染结束（上限 120 秒），页面已改走下面的任务接口；
 * 这个同步封装保留作回退用。
 */
export const downloadReportFile = async (
  reportId: string,
  format: Report['format'],
): Promise<Blob> =>
  (await request.get(`/api/v1/reports/${reportId}/export`, {
    params: { format },
    responseType: 'blob',
  })) as Blob;

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

/** 下载导出任务产出的文件（GET /reports/export/jobs/{job_id}/file，成功时直接回文件流） */
export const downloadReportExportFile = async (jobId: string): Promise<Blob> =>
  (await request.get(`/api/v1/reports/export/jobs/${jobId}/file`, {
    responseType: 'blob',
  })) as Blob;
