/**
 * 报告后台任务（生成 / 导出）。任务状态放在 store 而不是组件里，
 * 用户切页后轮询不中断，结果回来时顶栏仍能提示。
 */
import { defineStore } from 'pinia';
import { ElNotification } from 'element-plus';
import {
  EXPORT_EXT,
  downloadReportExportFile,
  getReportExportJob,
  getReportGenerateJob,
  listReportExportJobs,
  listReportGenerateJobs,
} from '@/api/reportApi';
import type { Report } from '@/types/security';
import { markSeenIds, readSeenIds } from '@/utils/jobSeen';
import { currentUid } from '@/stores/jobHelpers';
import { toMillis } from '@/utils/datetime';
import { createIsTerminal, keepUnexpiredJobs, messageOf, trimFinishedJobs } from '@/utils/job';
import { createStorePoller } from './jobPollingCore';
import type { PollContext } from './jobPollingCore';

export type ReportJobKind = 'generate' | 'export';
export type ReportJobStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';

export interface BackgroundReportJob {
  jobId: string;
  kind: ReportJobKind;
  title: string;
  status: ReportJobStatus;
  error: string | null;
  reportId: string | null;
  filename: string | null;
  sourceReportId?: string;
  format?: Report['format'];
  startedAt: number;
  elapsed: number;
}

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 20 * 60 * 1000;
const MAX_FINISHED = 20;
const TERMINAL_STATUSES: ReportJobStatus[] = ['DONE', 'FAILED'];

/**
 * （由 App.vue 的低频定时器调 purgeExpired，空闲时轮询已经停了，
 * 没有别的时机能让到点的行自己消失）。
 */
const FINISHED_TTL_MS = 24 * 60 * 60 * 1000;

const pollFor = createStorePoller(POLL_INTERVAL_MS, currentUid);

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

const isTerminal = createIsTerminal<BackgroundReportJob>(TERMINAL_STATUSES);

export const useReportJobStore = defineStore('reportJob', {
  state: () => ({
    jobs: [] as BackgroundReportJob[],
    // 已看过的任务 id（localStorage 持久化，跨刷新 / 跨标签页）
    seenIds: [] as string[],
    // 每完成一个任务 +1；页面 watch 它重新拉报告列表
    completedTick: 0,
  }),

  getters: {
    runningJobs: (state): BackgroundReportJob[] => state.jobs.filter((job) => !isTerminal(job)),

    finishedJobs: (state): BackgroundReportJob[] => state.jobs.filter(isTerminal),

    unseenJobs: (state): BackgroundReportJob[] => {
      const seen = new Set(state.seenIds);
      return state.jobs.filter((job) => isTerminal(job) && !seen.has(job.jobId));
    },

    runningExportIds: (state): Set<string> =>
      new Set(
        state.jobs
          .filter((job) => job.kind === 'export' && job.sourceReportId && !isTerminal(job))
          .map((job) => job.sourceReportId as string),
      ),

    runningTitles: (state): Set<string> =>
      new Set(
        state.jobs
          .filter((job) => job.kind === 'generate' && !isTerminal(job))
          .map((job) => job.title),
      ),
  },

  actions: {
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

    _track(partial: Omit<BackgroundReportJob, 'elapsed' | 'startedAt'> & { startedAt?: number }) {
      if (this.jobs.some((job) => job.jobId === partial.jobId)) return;
      this.jobs.push({ ...partial, startedAt: partial.startedAt ?? Date.now(), elapsed: 0 });
      this.startPolling();
    },

    startPolling() {
      pollFor(this).start();
    },

    stopPolling() {
      pollFor(this).stop();
    },

    syncSeen() {
      this.seenIds = [...readSeenIds(currentUid())];
    },

    reset() {
      pollFor(this).reset();
      this.jobs = [];
      this.syncSeen();
    },

    markAllSeen(jobIds?: string[]) {
      const targets = this.jobs.filter(
        (job) => isTerminal(job) && (!jobIds || jobIds.includes(job.jobId)),
      );
      if (!targets.length) return;
      this.seenIds = [...markSeenIds(currentUid(), targets.map((job) => job.jobId))];
    },

    /**
     * 恢复「还在跑」以及「已完成但没看过」的任务（由 App.vue 在会话恢复 / 登录成功时调一次）。
     */
    async resumePending() {
      this.reset();
      const context = pollFor(this).capture();
      const seen = new Set(this.seenIds);
      try {
        const [generates, exports] = await Promise.all([
          listReportGenerateJobs(),
          listReportExportJobs(),
        ]);
        if (!context.isCurrent()) return;
        for (const view of generates ?? []) {
          const status = view.status as ReportJobStatus;
          if (TERMINAL_STATUSES.includes(status) && seen.has(view.job_id)) continue;
          this._track({
            jobId: view.job_id,
            kind: 'generate',
            title: view.title,
            status,
            error: view.error,
            reportId: view.report_id,
            filename: null,
            startedAt: toMillis(view.created_at),
          });
        }
        for (const view of exports ?? []) {
          const status = view.status as ReportJobStatus;
          if (TERMINAL_STATUSES.includes(status) && seen.has(view.job_id)) continue;
          this._track({
            jobId: view.job_id,
            kind: 'export',
            title: `报告 #${view.report_id}`,
            status,
            error: view.error,
            reportId: null,
            filename: view.filename,
            sourceReportId: String(view.report_id),
            format: view.format,
            startedAt: toMillis(view.created_at),
          });
        }
      } catch {
      }
      if (context.isCurrent()) this.purgeExpired();
    },

    _tick(): Promise<void> {
      return pollFor(this).tick();
    },

    async _poll(context: PollContext) {
      if (!context.isCurrent()) return;
      const running = this.runningJobs;
      if (!running.length) {
        this.stopPolling();
        return;
      }
      for (const job of running) {
        if (!context.isCurrent()) return;
        job.elapsed = Math.max(0, Math.floor((Date.now() - job.startedAt) / 1000));
        if (Date.now() - job.startedAt >= POLL_TIMEOUT_MS) {
          this._timeout(job);
          continue;
        }
        try {
          if (job.kind === 'generate') {
            const view = await getReportGenerateJob(job.jobId);
            if (!context.isCurrent()) return;
            job.status = view.status;
            job.error = view.error;
            job.reportId = view.report_id;
          } else {
            const view = await getReportExportJob(job.jobId);
            if (!context.isCurrent()) return;
            job.status = view.status;
            job.error = view.error;
            job.filename = view.filename;
          }
        } catch (err) {
          if (!context.isCurrent()) return;
          job.error = messageOf(err, job.error ?? '任务状态查询失败');
          continue;
        }
        if (isTerminal(job)) this._settle(job);
      }
      if (context.isCurrent() && !this.runningJobs.length) this.stopPolling();
    },

    _settle(job: BackgroundReportJob) {
      this._trimFinished();
      const label = job.kind === 'generate' ? '报告生成' : '报告下载';
      if (job.status === 'FAILED') {
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

    // 终态任务超过上限就丢最旧的（正常情况下 markAllSeen 会先清掉）
    _trimFinished() {
      this.jobs = trimFinishedJobs(this.jobs, isTerminal, (job) => job.jobId, MAX_FINISHED);
    },

    purgeExpired(): boolean {
      const deadline = Date.now() - FINISHED_TTL_MS;
      const kept = keepUnexpiredJobs(this.jobs, isTerminal, deadline);
      if (kept.length === this.jobs.length) return false;
      this.jobs = kept;
      return true;
    },

    async _downloadExport(job: BackgroundReportJob) {
      const context = pollFor(this).capture();
      try {
        const blob = await downloadReportExportFile(job.jobId);
        if (!context.isCurrent()) return;
        const ext = EXPORT_EXT[job.format ?? 'markdown'] ?? 'txt';
        saveBlob(blob, `${safeFileName(job.title, job.sourceReportId ?? job.jobId)}.${ext}`);
        ElNotification({
          title: '报告已下载',
          message: `《${job.title}》已下载`,
          type: 'success',
        });
      } catch (err) {
        if (!context.isCurrent()) return;
        ElNotification({
          title: '报告下载失败',
          message: `《${job.title}》：${messageOf(err, '文件下载失败')}`,
          type: 'error',
          duration: 0,
        });
      }
    },

    _timeout(job: BackgroundReportJob) {
      this.jobs = this.jobs.filter((item) => item.jobId !== job.jobId);
      ElNotification({
        title: job.kind === 'generate' ? '报告生成仍在进行' : '报告下载仍在进行',
        message: `《${job.title}》等待超时，任务可能仍在后台继续，可稍后在报告中心查看`,
        type: 'warning',
        duration: 0,
      });
    },
  },
});
