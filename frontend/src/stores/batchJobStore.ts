/**
 * 批量研判后台任务
 * 批量研判逐条串行调 Java 预测服务并落库，200 条最坏可跑十几分钟。提交接口立刻返回
 * 组件的生命周期上（离开页面就置 abort 静默收尾），结果是：任务一直在跑、用户却收不到
 * 完成通知，回到页面也看不到那张结果表。
 */
import { defineStore } from 'pinia';
import { ElNotification } from 'element-plus';
import { getInferenceBatchJob, listInferenceBatchJobs } from '@/api/inferenceRecordApi';
import type { BatchInferenceResult } from '@/api/inferenceRecordApi';
import { markSeenIds, readSeenIds } from '@/utils/jobSeen';
import { currentUid } from '@/stores/jobHelpers';
import { toMillis } from '@/utils/datetime';
import { createIsTerminal, keepUnexpiredJobs, messageOf, trimFinishedJobs } from '@/utils/job';
import { createStorePoller } from './jobPollingCore';
import type { PollContext } from './jobPollingCore';

type BatchStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';

const STATUS_DONE = 'DONE';
const STATUS_FAILED = 'FAILED';
const TERMINAL_STATUSES: BatchStatus[] = [STATUS_DONE, STATUS_FAILED];

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 40 * 60 * 1000;
const MAX_FINISHED = 20;

/**
 * （由 App.vue 的低频定时器调 purgeExpired，空闲时轮询已经停了，
 * 没有别的时机能让到点的行自己消失）。
 */
const FINISHED_TTL_MS = 24 * 60 * 60 * 1000;

export interface BackgroundBatchJob {
  jobId: string;
  modelVersionId: number;
  title: string;
  status: BatchStatus;
  total: number;
  processed: number;
  error: string | null;
  startedAt: number;
  elapsed: number;
}

export interface BatchJobResult {
  jobId: string;
  modelVersionId: number;
  title: string;
  result: BatchInferenceResult;
}

const pollFor = createStorePoller(POLL_INTERVAL_MS, currentUid);

const isTerminal = createIsTerminal<BackgroundBatchJob>(TERMINAL_STATUSES);

export const useBatchJobStore = defineStore('batchJob', {
  state: () => ({
    jobs: [] as BackgroundBatchJob[],
    seenIds: [] as string[],
    // 每完成一个任务 +1；研判页 watch 它滚动到结果区
    completedTick: 0,
    lastResult: null as BatchJobResult | null,
  }),

  getters: {
    running: (state): boolean => state.jobs.some((job) => !isTerminal(job)),

    runningJobs: (state): BackgroundBatchJob[] => state.jobs.filter((job) => !isTerminal(job)),

    finishedJobs: (state): BackgroundBatchJob[] => state.jobs.filter(isTerminal),

    activeJob: (state): BackgroundBatchJob | null => {
      const running = state.jobs.filter((job) => !isTerminal(job));
      return running.length ? running[running.length - 1] : null;
    },

    unseenJobs: (state): BackgroundBatchJob[] => {
      const seen = new Set(state.seenIds);
      return state.jobs.filter((job) => isTerminal(job) && !seen.has(job.jobId));
    },
  },

  actions: {
    track(jobId: string, modelVersionId: number, title: string, total: number) {
      if (this.jobs.some((job) => job.jobId === jobId)) return;
      this.jobs.push({
        jobId,
        modelVersionId,
        title,
        status: 'PENDING',
        total,
        processed: 0,
        error: null,
        startedAt: Date.now(),
        elapsed: 0,
      });
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
      this.lastResult = null;
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
        const rows = await listInferenceBatchJobs();
        if (!context.isCurrent()) return;
        for (const row of rows ?? []) {
          const status = row.status as BatchStatus;
          if (TERMINAL_STATUSES.includes(status) && seen.has(row.job_id)) continue;
          if (this.jobs.some((job) => job.jobId === row.job_id)) continue;
          this.jobs.push({
            jobId: row.job_id,
            modelVersionId: Number(row.model_version_id),
            title: `模型版本 #${row.model_version_id}`,
            status,
            total: Number(row.total ?? 0),
            processed: Number(row.processed ?? 0),
            error: row.error ?? null,
            startedAt: toMillis(row.created_at),
            elapsed: 0,
          });
          if (!TERMINAL_STATUSES.includes(status)) this.startPolling();
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
          const view = await getInferenceBatchJob(job.jobId);
          if (!context.isCurrent()) return;
          job.status = view.status as BatchStatus;
          job.error = view.error;
          job.processed = view.processed;
          job.total = view.total;
          if (job.status === STATUS_DONE && view.result) {
            this.lastResult = {
              jobId: job.jobId,
              modelVersionId: job.modelVersionId,
              title: job.title,
              result: view.result,
            };
            this._settle(job);
          } else if (job.status === STATUS_FAILED) {
            this._settle(job);
          }
        } catch (err) {
          if (!context.isCurrent()) return;
          job.error = messageOf(err, job.error ?? '任务状态查询失败');
        }
      }
      if (context.isCurrent() && !this.running) this.stopPolling();
    },

    _settle(job: BackgroundBatchJob) {
      this._trimFinished();
      if (job.status === STATUS_DONE) {
        const res = this.lastResult?.result;
        this.completedTick += 1;
        ElNotification({
          title: '批量研判完成',
          message: res
            ? `《${job.title}》：成功 ${res.succeeded} 条、风险 ${res.risk_count} 条`
              + (res.failed ? `、失败 ${res.failed} 条` : '')
            : `《${job.title}》已完成`,
          type: 'success',
        });
        return;
      }
      ElNotification({
        title: '批量研判失败',
        message: `《${job.title}》：${job.error || '未知错误'}`,
        type: 'error',
        duration: 0,
      });
    },

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

    _timeout(job: BackgroundBatchJob) {
      this.jobs = this.jobs.filter((item) => item.jobId !== job.jobId);
      ElNotification({
        title: '批量研判仍在进行',
        message: `《${job.title}》等待超时，任务仍在后台继续，结果可在推理记录中查看`,
        type: 'warning',
        duration: 0,
      });
    },
  },
});
