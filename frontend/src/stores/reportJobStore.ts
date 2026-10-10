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
 *
 * **终态任务不再立刻从数组里删掉** —— 顶栏任务面板要能列出「已完成但没看过」的，
 * 「看过」由 utils/jobSeen 的 id 集合差判定（见那个文件的说明）。
 * 「已用时间」也不再靠 tick 累加（切后台被节流会严重偏小），改成按服务端下发的
 * created_at 算时间差，刷新后接着算而不是归零。
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

/** 后台任务（终态任务也留在列表里，供顶栏面板展示「已完成未查看」） */
export interface BackgroundReportJob {
  jobId: string;
  kind: ReportJobKind;
  /** 报告标题，用于通知文案与面板行 */
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
  /** 提交时刻（毫秒时间戳；恢复在途任务时取服务端的 created_at） */
  startedAt: number;
  /** 已用秒数（每次轮询按真实时间差重算） */
  elapsed: number;
}

const POLL_INTERVAL_MS = 1000;
/**
 * 等待上限。原先是 3 分钟，比后端短太多：后端生成没有硬超时、任务表保留 900 秒，
 * 前端先放弃就会弹「任务超时」而后端其实还在跑、报告最后照样出现。改成 20 分钟，
 * 并且超时只出 warning（不再当 FAILED），口径与训练 / 批量研判一致。
 */
const POLL_TIMEOUT_MS = 20 * 60 * 1000;
/** 终态任务最多在册多少条（用户一直不打开面板时的兜底） */
const MAX_FINISHED = 20;
const TERMINAL_STATUSES: ReportJobStatus[] = ['DONE', 'FAILED'];

/**
 * 终态任务的保留时长。顶栏面板只展示最近一天的任务，超过它的不再列出
 * （由 App.vue 的低频定时器调 purgeExpired —— 空闲时轮询已经停了，
 * 没有别的时机能让到点的行自己消失）。
 *
 * 基准取**提交时刻** `startedAt`：服务端只下发 created_at，没有完成时间字段。
 * 单个任务最长也就 20 分钟（POLL_TIMEOUT_MS），相对 24 小时可忽略。
 */
const FINISHED_TTL_MS = 24 * 60 * 60 * 1000;

const pollFor = createStorePoller(POLL_INTERVAL_MS, currentUid);

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

const isTerminal = createIsTerminal<BackgroundReportJob>(TERMINAL_STATUSES);

export const useReportJobStore = defineStore('reportJob', {
  state: () => ({
    jobs: [] as BackgroundReportJob[],
    /** 已看过的任务 id（localStorage 持久化，跨刷新 / 跨标签页） */
    seenIds: [] as string[],
    /** 每完成一个任务 +1；页面 watch 它重新拉报告列表 */
    completedTick: 0,
  }),

  getters: {
    runningJobs: (state): BackgroundReportJob[] => state.jobs.filter((job) => !isTerminal(job)),

    /** 已到达终态的（顶栏面板的「已完成」区；含已看过的，那属于任务历史） */
    finishedJobs: (state): BackgroundReportJob[] => state.jobs.filter(isTerminal),

    /** 已完成但没看过的（顶栏徽章的数字） */
    unseenJobs: (state): BackgroundReportJob[] => {
      const seen = new Set(state.seenIds);
      return state.jobs.filter((job) => isTerminal(job) && !seen.has(job.jobId));
    },

    /** 有下载任务在跑的 report_id（列表里把「下载」置灰成「下载中」） */
    runningExportIds: (state): Set<string> =>
      new Set(
        state.jobs
          .filter((job) => job.kind === 'export' && job.sourceReportId && !isTerminal(job))
          .map((job) => job.sourceReportId as string),
      ),

    /** 有生成任务在跑的标题（列表里把「重新生成」置灰） */
    runningTitles: (state): Set<string> =>
      new Set(
        state.jobs
          .filter((job) => job.kind === 'generate' && !isTerminal(job))
          .map((job) => job.title),
      ),
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

    /** 重新读一遍已读集合（会话恢复 / 别的标签页改动时用） */
    syncSeen() {
      this.seenIds = [...readSeenIds(currentUid())];
    },

    /**
     * 清空任务状态、重新读本账号的已读集合。**换账号 / 登出时必须调**。
     *
     * store 是全局单例，任务列表虽然是后端按 `user_id` 过滤的，但数组本身不会自己清 ——
     * 不重置的话上一个账号的任务会留在列表里，被当成「本账号已完成未查看」列进顶栏面板
     * （徽章数字也会把它们算进去）。见 `App.vue` 的 watch 与 `resumePending`。
     *
     * 注意这里必须跟着 `syncSeen()`：`seenIds` 也得换成当前账号的，
     * 否则 `resumePending` 拿到空集合，会把所有终态任务都判成未读。
     */
    reset() {
      pollFor(this).reset();
      this.jobs = [];
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
     * 未完成的接回来继续轮询、把没看过的完成项接回来挂徽章。**导出也要接** ——
     * 之前只调了 listReportGenerateJobs，刷新后导出任务就彻底丢了。
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
        // 恢复失败不影响页面：任务仍在服务端跑，产物最终会出现在报告列表里
      }
      // 服务端任务表里可能还躺着昨天甚至更早的，接回来之前先丢掉
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
          // 单次轮询失败（网络抖动 / 服务端重启导致任务丢失）不立刻判死，交给超时兜底
          job.error = messageOf(err, job.error ?? '任务状态查询失败');
          continue;
        }
        if (isTerminal(job)) this._settle(job);
      }
      if (context.isCurrent() && !this.runningJobs.length) this.stopPolling();
    },

    /** 任务到达终态：出通知、必要时取产物。**不从列表移除** —— 顶栏面板要展示它。 */
    _settle(job: BackgroundReportJob) {
      this._trimFinished();
      const label = job.kind === 'generate' ? '报告生成' : '报告下载';
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

    /** 终态任务超过上限就丢最旧的（正常情况下 markAllSeen 会先清掉） */
    _trimFinished() {
      this.jobs = trimFinishedJobs(this.jobs, isTerminal, (job) => job.jobId, MAX_FINISHED);
    },

    /**
     * 丢掉超过保留时长的**终态**任务，返回是否有变化。
     *
     * 在途任务不碰：它们的时间轴由 POLL_TIMEOUT_MS 管，轮不到这里；而且真删了的话
     * `_tick` 手里那个对象已经不在数组里，会白跑一轮。
     */
    purgeExpired(): boolean {
      const deadline = Date.now() - FINISHED_TTL_MS;
      const kept = keepUnexpiredJobs(this.jobs, isTerminal, deadline);
      if (kept.length === this.jobs.length) return false;
      this.jobs = kept;
      return true;
    },

    /** 下载产物就绪：取文件流并触发下载 */
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

    /**
     * 等待超时：停止追踪，但不当作失败 —— 服务端可能还在跑。
     * 说清楚「还在后台继续」比直接报失败更准确。
     */
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
