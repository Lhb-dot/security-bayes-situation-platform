/**
 * AI 模型训练后台任务
 * 训练是「提交 → 后台跑 → 出结果」的长任务：提交后立刻拿到 TRAINING 版本，
 * 真实训练由服务端 training_runner 在后台线程调 Java/Weka 跑完，成功转 DRAFT、
 * 训练其实一直在后台跑，但结果没人通知，回到页面也看不到，只能去模型中心翻。
 */
import { defineStore } from 'pinia';
import { ElNotification } from 'element-plus';
import { getModelVersionDetail, listTrainingJobs } from '@/api/trainingApi';
import type { TrainingJobRow } from '@/api/trainingApi';
import { markSeenIds, readSeenIds } from '@/utils/jobSeen';
import { currentUid } from '@/stores/jobHelpers';
import { parseBeijingNaive } from '@/utils/datetime';
import { createIsTerminal, keepUnexpiredJobs, messageOf, trimFinishedJobs } from '@/utils/job';
import { createStorePoller } from './jobPollingCore';
import type { PollContext } from './jobPollingCore';

const STATUS_TRAINING = 'TRAINING';
const STATUS_DRAFT = 'DRAFT';
const STATUS_FAILED = 'FAILED';
const TERMINAL_STATUSES = [STATUS_DRAFT, STATUS_FAILED];

const POLL_INTERVAL_MS = 1000;
const POLL_TIMEOUT_MS = 65 * 60 * 1000;
const MAX_FINISHED = 20;

const FINISHED_TTL_MS = 24 * 60 * 60 * 1000;

export interface BackgroundTrainingJob {
  modelVersionId: number;
  title: string;
  status: string;
  error: string | null;
  startedAt: number;
  elapsed: number;
}

const pollFor = createStorePoller(POLL_INTERVAL_MS, currentUid);

const settledByStore = new WeakMap<object, Set<number>>();
const settledIdsFor = (store: object) => {
  let ids = settledByStore.get(store);
  if (!ids) {
    ids = new Set<number>();
    settledByStore.set(store, ids);
  }
  return ids;
};

const isTerminalStatus = (status: string) => TERMINAL_STATUSES.includes(status);

const isTerminal = createIsTerminal<BackgroundTrainingJob>(TERMINAL_STATUSES);

export const trainingJobTitle = (row: TrainingJobRow) =>
  [row.scenario_name, row.algorithm_name].filter(Boolean).join(' · ') || '模型训练';

export const useTrainingJobStore = defineStore('trainingJob', {
  state: () => ({
    jobs: [] as BackgroundTrainingJob[],
    seenIds: [] as string[],
  }),

  getters: {
    running: (state): boolean => state.jobs.some((job) => !isTerminal(job)),

    activeJob: (state): BackgroundTrainingJob | null => {
      const running = state.jobs.filter((job) => !isTerminal(job));
      return running.length ? running[running.length - 1] : null;
    },

    runningJobs: (state): BackgroundTrainingJob[] => state.jobs.filter((job) => !isTerminal(job)),

    finishedJobs: (state): BackgroundTrainingJob[] => state.jobs.filter(isTerminal),

    unseenJobs: (state): BackgroundTrainingJob[] => {
      const seen = new Set(state.seenIds);
      return state.jobs.filter((job) => isTerminal(job) && !seen.has(String(job.modelVersionId)));
    },
  },

  actions: {
    track(modelVersionId: number, title: string, status = STATUS_TRAINING, startedAt?: number) {
      const key = String(modelVersionId);
      if (this.jobs.some((job) => String(job.modelVersionId) === key)) return;
      this.jobs.push({
        modelVersionId,
        title,
        status,
        error: null,
        startedAt: startedAt ?? Date.now(),
        elapsed: 0,
      });
      if (!isTerminalStatus(status)) this.startPolling();
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
      settledIdsFor(this).clear();
      this.syncSeen();
    },

    markAllSeen(keys?: string[]) {
      const targets = this.jobs.filter(
        (job) => isTerminal(job) && (!keys || keys.includes(String(job.modelVersionId))),
      );
      if (!targets.length) return;
      this.seenIds = [...markSeenIds(currentUid(), targets.map((job) => String(job.modelVersionId)))];
    },

    /**
     * 恢复「还在训练」以及「已完成但没看过」的任务（由 App.vue 在会话恢复 / 登录成功时调一次）。
     */
    async resumePending() {
      this.reset();
      const context = pollFor(this).capture();
      const seen = new Set(this.seenIds);
      try {
        const rows = await listTrainingJobs(true);
        if (!context.isCurrent()) return;
        for (const row of rows ?? []) {
          const status = String(row?.status ?? '');
          if (!status) continue;
          const id = Number(row.id ?? row.model_version_id);
          if (!Number.isFinite(id)) continue;
          if (isTerminalStatus(status) && seen.has(String(id))) continue;
          this.track(id, trainingJobTitle(row), status, parseBeijingNaive(row.trained_at) ?? undefined);
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
          const row = await getModelVersionDetail(job.modelVersionId);
          if (!context.isCurrent()) return;
          job.status = String(row?.status ?? '');
          if (job.status === STATUS_TRAINING) continue;
          job.error = String(row?.evaluation_metrics?.error ?? '') || null;
          this._settle(job);
        } catch (err) {
          if (!context.isCurrent()) return;
          job.error = messageOf(err, job.error ?? '训练状态查询失败');
        }
      }
      if (context.isCurrent() && !this.running) this.stopPolling();
    },

    _settle(job: BackgroundTrainingJob) {
      const settledIds = settledIdsFor(this);
      if (settledIds.has(job.modelVersionId)) return;
      settledIds.add(job.modelVersionId);
      this._trimFinished();
      if (job.status === STATUS_DRAFT) {
        ElNotification({
          title: '模型训练完成',
          message: `《${job.title}》已训练完成，可在模型中心审核发布`,
          type: 'success',
        });
        return;
      }
      ElNotification({
        title: '模型训练失败',
        message: `《${job.title}》：${job.error || `训练状态 ${job.status}`}`,
        type: 'error',
        duration: 0,
      });
    },

    _trimFinished() {
      this.jobs = trimFinishedJobs(this.jobs, isTerminal, (job) => String(job.modelVersionId), MAX_FINISHED);
    },

    purgeExpired(): boolean {
      const deadline = Date.now() - FINISHED_TTL_MS;
      const kept = keepUnexpiredJobs(this.jobs, isTerminal, deadline);
      if (kept.length === this.jobs.length) return false;
      this.jobs = kept;
      return true;
    },

    _timeout(job: BackgroundTrainingJob) {
      this.jobs = this.jobs.filter((item) => item.modelVersionId !== job.modelVersionId);
      ElNotification({
        title: '模型训练仍在进行',
        message: `《${job.title}》等待超时，训练可能仍在后台继续，可稍后在模型中心查看`,
        type: 'warning',
        duration: 0,
      });
    },
  },
});
