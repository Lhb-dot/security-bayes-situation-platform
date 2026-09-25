/**
 * reportJobStore.ts — 报告后台任务（生成 / 导出）
 *
 * 生成与导出都是「提交 → 后台跑 → 拿结果」的长任务：生成要十几秒（数据聚合 +
 * 多视图研判 + NL 分析），导出 pdf 要等 Chromium 渲染。任务状态放在这里而不是
 * 组件里，是因为组件会被卸载 —— 之前导出的轮询绑在 ReportCenter 的生命周期上，
 * 用户切页就 `if (!job) return` 静默收尾，文件好了也不知道，同一个「挂后台但用户
 * 不知道结果」的问题在生成上更明显（关掉弹窗就彻底没反馈了）。
 *
 * 单条轮询链路：任一时刻只有一个定时器，一次遍历所有在途任务；全部到达终态自动停表。
 * 完成 / 失败统一走 ElNotification，成功额外 bump completedTick，页面 watch 它刷新列表。
 */
import { defineStore } from 'pinia';
import { ElNotification } from 'element-plus';
import {
  EXPORT_EXT,
  downloadReportExportFile,
  getReportExportJob,
  getReportGenerateJob,
  listReportGenerateJobs,
} from '@/api/reportApi';
import type { Report } from '@/types/security';

export type ReportJobKind = 'generate' | 'export';
export type ReportJobStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';

/** 在途的后台任务（已完成的会立刻从列表移除，只留一条通知） */
export interface BackgroundReportJob {
  jobId: string;
  kind: ReportJobKind;
  /** 报告标题，用于通知文案 */
  title: string;
  status: ReportJobStatus;
  error: string | null;
  /** 生成任务完成后的新报告 id */
  reportId: string | null;
  /** 导出任务：产物文件名 */
  filename: string | null;
  /** 导出任务：下载时用来拼文件名 */
  sourceReportId?: string;
  format?: Report['format'];
  /** 已用秒数（由轮询时钟累加） */
  elapsed: number;
  /** 超时时刻（毫秒时间戳），到点按失败处理 */
  deadline: number;
}

const POLL_INTERVAL_MS = 1000;
/** 生成最慢几十秒、pdf 渲染上限 120 秒，留足余量；超时任务在服务端仍在跑，重新提交即可 */
const POLL_TIMEOUT_MS = 3 * 60 * 1000;
const TERMINAL_STATUSES: ReportJobStatus[] = ['DONE', 'FAILED'];

let pollTimer: number | null = null;
let polling = false;

/** 下载文件名：去掉文件系统不接受的字符（与后端 report_export.safe_filename 一致） */
const safeFileName = (title: string, reportId: string) => {
  const cleaned = (title ?? '')
    .replace(/[\\/:*?"<>|\u0000-\u001f]/g, '_')
    .replace(/^[.\s]+|[.\s]+$/g, '')
    .slice(0, 60);
  return cleaned || `report_${reportId}`;
};

const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
};

const messageOf = (err: unknown, fallback: string) =>
  err instanceof Error && err.message ? err.message : fallback;

export const useReportJobStore = defineStore('reportJob', {
  state: () => ({
    jobs: [] as BackgroundReportJob[],
    /** 每完成一个任务 +1；页面 watch 它重新拉报告列表 */
    completedTick: 0,
  }),

  getters: {
    runningJobs: (state): BackgroundReportJob[] =>
      state.jobs.filter((job) => !TERMINAL_STATUSES.includes(job.status)),

    /** 有导出任务在跑的 report_id（列表里把「下载」置灰成「导出中」） */
    runningExportIds: (state): Set<string> =>
      new Set(
        state.jobs
          .filter((job) => job.kind === 'export' && job.sourceReportId)
          .map((job) => job.sourceReportId as string),
      ),

    /** 有生成任务在跑的标题（列表里把「重新生成」置灰） */
    runningTitles: (state): Set<string> =>
      new Set(state.jobs.filter((job) => job.kind === 'generate').map((job) => job.title)),
  },

  actions: {
    /** 登记一个后台生成任务 */
    trackGenerate(jobId: string, title: string) {
      this._track({
        jobId,
        kind: 'generate',
        title,
        status: 'PENDING',
        error: null,
        reportId: null,
        filename: null,
      });
    },

    /** 登记一个后台导出任务 */
    trackExport(jobId: string, report: Report) {
      this._track({
        jobId,
        kind: 'export',
        title: report.title,
        status: 'PENDING',
        error: null,
        reportId: null,
        filename: null,
        sourceReportId: report.report_id,
        format: report.format,
      });
    },

    _track(partial: Omit<BackgroundReportJob, 'elapsed' | 'deadline'>) {
      if (this.jobs.some((job) => job.jobId === partial.jobId)) return;
      this.jobs.push({ ...partial, elapsed: 0, deadline: Date.now() + POLL_TIMEOUT_MS });
      this.startPolling();
    },

    startPolling() {
      if (pollTimer !== null) return;
      pollTimer = window.setInterval(() => void this._tick(), POLL_INTERVAL_MS);
      void this._tick();
    },

    stopPolling() {
      if (pollTimer !== null) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    },

    /**
     * 恢复「还在跑」的生成任务（由 App.vue 在会话恢复 / 登录成功时调一次）。
     *
     * 服务端任务表是进程内的，前端这侧的状态随页面一起没了；列出本账号的任务把
     * 未完成的接回来继续轮询，这样刷新一下不会让通知彻底丢失。
     * 已完成的不再接（报告列表本来就会拉到）。
     */
    async resumePending() {
      try {
        const views = await listReportGenerateJobs();
        for (const view of views) {
          if (TERMINAL_STATUSES.includes(view.status as ReportJobStatus)) continue;
          this._track({
            jobId: view.job_id,
            kind: 'generate',
            title: view.title,
            status: view.status as ReportJobStatus,
            error: view.error,
            reportId: view.report_id,
            filename: null,
          });
        }
      } catch {
        // 恢复失败不影响页面：任务仍在服务端跑，产物最终会出现在报告列表里
      }
    },

    async _tick() {
      if (polling) return;   // 上一轮还没回来（请求慢），跳过这一拍
      polling = true;
      try {
        const running = this.runningJobs;
        if (!running.length) {
          this.stopPolling();
          return;
        }
        for (const job of running) {
          job.elapsed += 1;
          if (Date.now() >= job.deadline) {
            job.status = 'FAILED';
            job.error = '任务超时，请稍后重试';
            this._settle(job);
            continue;
          }
          try {
            if (job.kind === 'generate') {
              const view = await getReportGenerateJob(job.jobId);
              job.status = view.status;
              job.error = view.error;
              job.reportId = view.report_id;
            } else {
              const view = await getReportExportJob(job.jobId);
              job.status = view.status;
              job.error = view.error;
              job.filename = view.filename;
            }
          } catch (err) {
            // 单次轮询失败（网络抖动 / 服务端重启导致任务丢失）不立刻判死，交给 deadline 兜底
            job.error = messageOf(err, job.error ?? '任务状态查询失败');
            continue;
          }
          if (TERMINAL_STATUSES.includes(job.status)) this._settle(job);
        }
      } finally {
        polling = false;
      }
    },

    /** 任务到达终态：出通知、必要时取产物，然后从列表移除 */
    _settle(job: BackgroundReportJob) {
      this.jobs = this.jobs.filter((item) => item.jobId !== job.jobId);
      const label = job.kind === 'generate' ? '报告生成' : '报告导出';
      if (job.status === 'FAILED') {
        // 失败要人看见，所以不自动消失
        ElNotification({
          title: `${label}失败`,
          message: `《${job.title}》：${job.error || '未知错误'}`,
          type: 'error',
          duration: 0,
        });
        return;
      }
      if (job.kind === 'generate') {
        this.completedTick += 1;
        ElNotification({
          title: '报告已生成',
          message: `《${job.title}》已生成完成，可在报告中心查看`,
          type: 'success',
        });
        return;
      }
      void this._downloadExport(job);
    },

    /** 导出产物就绪：取文件流并触发下载 */
    async _downloadExport(job: BackgroundReportJob) {
      try {
        const blob = await downloadReportExportFile(job.jobId);
        const ext = EXPORT_EXT[job.format ?? 'markdown'] ?? 'txt';
        saveBlob(blob, `${safeFileName(job.title, job.sourceReportId ?? job.jobId)}.${ext}`);
        ElNotification({
          title: '报告已导出',
          message: `《${job.title}》已下载`,
          type: 'success',
        });
      } catch (err) {
        ElNotification({
          title: '报告导出失败',
          message: `《${job.title}》：${messageOf(err, '文件下载失败')}`,
          type: 'error',
          duration: 0,
        });
      }
    },
  },
});
