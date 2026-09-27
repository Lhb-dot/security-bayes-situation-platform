/**
 * batchJobStore.ts — 批量研判后台任务
 *
 * 批量研判逐条串行调 Java 预测服务并落库，200 条最坏可跑十几分钟。提交接口立刻返回
 * job_id，真实执行在服务端 batch_inference_runner 的守护线程里。此前轮询绑在研判页
 * 组件的生命周期上（离开页面就置 abort 静默收尾），结果是：任务一直在跑、用户却收不到
 * 完成通知，回到页面也看不到那张结果表。
 *
 * 状态放在这里而不是组件里，是因为组件会被卸载。与 reportJobStore 同一套做法：
 * 单条轮询链路 + 完成 / 失败统一走 ElNotification；研判页 watch lastResult 回填结果表，
 * App.vue 在会话恢复 / 登录成功时调 resumePending()，刷新后依然能收到通知。
 *
 * 终态任务不立刻丢弃（顶栏面板要展示「已完成未查看」），已读判定见 utils/jobSeen；
 * 已用时间按服务端 created_at 算，刷新后接着算而不是归零。
 */
import { defineStore } from 'pinia';
import { ElNotification } from 'element-plus';
import { getInferenceBatchJob, listInferenceBatchJobs } from '@/api/inferenceRecordApi';
import type { BatchInferenceResult } from '@/api/inferenceRecordApi';
import { markSeenIds, readSeenIds } from '@/utils/jobSeen';
import { useUserStore } from '@/stores/userStore';

type BatchStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED';

const STATUS_DONE = 'DONE';
const STATUS_FAILED = 'FAILED';
const TERMINAL_STATUSES: BatchStatus[] = [STATUS_DONE, STATUS_FAILED];

const POLL_INTERVAL_MS = 1000;
/** 200 条最坏约 16 分钟，留足余量；超时后任务仍在后台继续，结果可在推理记录里查看 */
const POLL_TIMEOUT_MS = 40 * 60 * 1000;
/** 终态任务最多在册多少条（用户一直不打开面板时的兜底） */
const MAX_FINISHED = 20;

/**
 * 终态任务的保留时长。顶栏面板只展示最近一天的任务，超过它的不再列出
 * （由 App.vue 的低频定时器调 purgeExpired —— 空闲时轮询已经停了，
 * 没有别的时机能让到点的行自己消失）。
 *
 * 基准取**提交时刻** `startedAt`（服务端的 created_at）：服务端没有下发完成时间。
 * 一批最长 40 分钟（POLL_TIMEOUT_MS），相对 24 小时可忽略。
 */
const FINISHED_TTL_MS = 24 * 60 * 60 * 1000;

/** 后台批量研判任务（终态任务也留在列表里，供顶栏面板展示） */
export interface BackgroundBatchJob {
  jobId: string;
  modelVersionId: number;
  /** 任务名，用于通知文案与面板行 */
  title: string;
  status: BatchStatus;
  total: number;
  processed: number;
  error: string | null;
  /** 提交时刻（毫秒时间戳；恢复在途任务时取服务端的 created_at） */
  startedAt: number;
  /** 已用秒数（每次轮询按真实时间差重算） */
  elapsed: number;
}

/** 最近一次完成的批量研判结果（研判页据此回填结果表） */
export interface BatchJobResult {
  jobId: string;
  modelVersionId: number;
  title: string;
  result: BatchInferenceResult;
}

let pollTimer: number | null = null;
let polling = false;

const currentUid = (): string | null => useUserStore().currentUser?.user_id ?? null;

const toMillis = (createdAt?: number): number =>
  typeof createdAt === 'number' && Number.isFinite(createdAt) && createdAt > 0
    ? createdAt * 1000
    : Date.now();

const messageOf = (err: unknown, fallback: string) =>
  err instanceof Error && err.message ? err.message : fallback;

const isTerminal = (job: BackgroundBatchJob) => TERMINAL_STATUSES.includes(job.status);

export const useBatchJobStore = defineStore('batchJob', {
  state: () => ({
    jobs: [] as BackgroundBatchJob[],
    /** 已看过的任务 id（localStorage 持久化，跨刷新 / 跨标签页） */
    seenIds: [] as string[],
    /** 每完成一个任务 +1；研判页 watch 它滚动到结果区 */
    completedTick: 0,
    /** 最近一次成功产出的结果；离开页面再回来仍能展示 */
    lastResult: null as BatchJobResult | null,
  }),

  getters: {
    /** 还有在途任务（页面按钮置灰用；终态任务不算） */
    running: (state): boolean => state.jobs.some((job) => !isTerminal(job)),

    /** 在途任务（顶栏面板用） */
    runningJobs: (state): BackgroundBatchJob[] => state.jobs.filter((job) => !isTerminal(job)),

    /** 已到达终态的（顶栏面板的「已完成」区；含已看过的，那属于任务历史） */
    finishedJobs: (state): BackgroundBatchJob[] => state.jobs.filter(isTerminal),

    /** 页面上展示的那条在途任务（研判页一次只提交一批，取最近登记的） */
    activeJob: (state): BackgroundBatchJob | null => {
      const running = state.jobs.filter((job) => !isTerminal(job));
      return running.length ? running[running.length - 1] : null;
    },

    /** 已完成但没看过的（顶栏徽章的数字） */
    unseenJobs: (state): BackgroundBatchJob[] => {
      const seen = new Set(state.seenIds);
      return state.jobs.filter((job) => isTerminal(job) && !seen.has(job.jobId));
    },
  },

  actions: {
    /** 登记一个后台批量研判任务 */
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

    /** 重新读一遍已读集合（会话恢复 / 别的标签页改动时用） */
    syncSeen() {
      this.seenIds = [...readSeenIds(currentUid())];
    },

    /**
     * 清空任务状态、重新读本账号的已读集合。**换账号 / 登出时必须调**。
     *
     * store 是全局单例，任务列表虽然是后端按 `user_id` 过滤的，但数组本身不会自己清 ——
     * 不重置的话上一个账号的任务会留在列表里，被当成「本账号已完成未查看」列进顶栏面板。
     * `lastResult` 也要清：研判页的结果表靠它回填，留着就会展示上一个账号的研判结果。
     *
     * 注意这里必须跟着 `syncSeen()`：`seenIds` 也得换成当前账号的，
     * 否则 `resumePending` 拿到空集合，会把所有终态任务都判成未读。
     */
    reset() {
      this.stopPolling();
      this.jobs = [];
      this.lastResult = null;
      this.syncSeen();
    },

    /**
     * 把已完成任务标记为已看（面板展开停留够久、或点击某一行时调）。
     *
     * **只记 id，不从 jobs 里删** —— 顶栏面板正在展示这些行，删了会让它们在鼠标底下
     * 消失（展开 1.5 秒后必发生），连点都点不到。清理由 _trimFinished 兜底。
     */
    markAllSeen(jobIds?: string[]) {
      const targets = this.jobs.filter(
        (job) => isTerminal(job) && (!jobIds || jobIds.includes(job.jobId)),
      );
      if (!targets.length) return;
      this.seenIds = [...markSeenIds(currentUid(), targets.map((job) => job.jobId))];
    },

    /**
     * 恢复「还在跑」以及「已完成但没看过」的任务（由 App.vue 在会话恢复 / 登录成功时调一次）。
     *
     * **先 reset 再拉**：这是「按当前账号重建状态」的时机，不先把上一个账号的残留清掉，
     * 就会把它当成本账号的任务挂进顶栏面板。
     *
     * 服务端任务表是进程内的，前端这侧的状态随页面一起没了；列出本账号的任务把
     * 未完成的接回来继续轮询、把没看过的完成项接回来挂徽章。
     * 列表接口是 brief 视图（不带逐条明细），够面板展示；结果表仍走单任务接口。
     */
    async resumePending() {
      this.reset();
      const seen = new Set(this.seenIds);
      try {
        const rows = await listInferenceBatchJobs();
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
        // 恢复失败不影响页面：任务仍在服务端跑，结果可在推理记录里看到
      }
      // 服务端任务表里可能还躺着昨天甚至更早的，接回来之前先丢掉
      this.purgeExpired();
    },

    async _tick() {
      if (polling) return;   // 上一轮还没回来（请求慢），跳过这一拍
      polling = true;
      try {
        const running = this.jobs.filter((job) => !isTerminal(job));
        if (!running.length) {
          this.stopPolling();
          return;
        }
        for (const job of running) {
          job.elapsed = Math.max(0, Math.floor((Date.now() - job.startedAt) / 1000));
          if (Date.now() - job.startedAt >= POLL_TIMEOUT_MS) {
            this._timeout(job);
            continue;
          }
          try {
            const view = await getInferenceBatchJob(job.jobId);
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
            // 单次轮询失败（网络抖动 / 服务端重启导致任务丢失）不立刻判死，交给超时兜底
            job.error = messageOf(err, job.error ?? '任务状态查询失败');
          }
        }
        if (!this.jobs.some((job) => !isTerminal(job))) this.stopPolling();
      } finally {
        polling = false;
      }
    },

    /** 任务到达终态：出通知。**不从列表移除** —— 顶栏面板要展示它。 */
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
      // 失败要人看见，所以不自动消失
      ElNotification({
        title: '批量研判失败',
        message: `《${job.title}》：${job.error || '未知错误'}`,
        type: 'error',
        duration: 0,
      });
    },

    /** 终态任务超过上限就丢最旧的 */
    _trimFinished() {
      const finished = this.jobs.filter(isTerminal);
      if (finished.length <= MAX_FINISHED) return;
      const drop = new Set(
        finished
          .slice()
          .sort((a, b) => a.startedAt - b.startedAt)
          .slice(0, finished.length - MAX_FINISHED)
          .map((job) => job.jobId),
      );
      this.jobs = this.jobs.filter((job) => !drop.has(job.jobId));
    },

    /**
     * 丢掉超过保留时长的**终态**任务，返回是否有变化。
     *
     * 在途任务不碰：它们的时间轴由 POLL_TIMEOUT_MS 管，轮不到这里；而且真删了的话
     * `_tick` 手里那个对象已经不在数组里，会白跑一轮。
     */
    purgeExpired(): boolean {
      const deadline = Date.now() - FINISHED_TTL_MS;
      const kept = this.jobs.filter((job) => !isTerminal(job) || job.startedAt >= deadline);
      if (kept.length === this.jobs.length) return false;
      this.jobs = kept;
      return true;
    },

    /**
     * 等待超时：停止追踪，但不当作失败 —— 服务端仍在逐条跑。
     * 说清楚「结果可在推理记录里查看」比直接报失败更准确。
     */
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
