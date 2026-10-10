/**
 * trainingJobStore.ts — AI 模型训练后台任务
 *
 * 训练是「提交 → 后台跑 → 出结果」的长任务：提交后立刻拿到 TRAINING 版本，
 * 真实训练由服务端 training_runner 在后台线程调 Java/Weka 跑完，成功转 DRAFT、
 * 失败转 FAILED。此前轮询绑在训练页组件的生命周期上，用户切页就静默收尾 ——
 * 训练其实一直在后台跑，但结果没人通知，回到页面也看不到，只能去模型中心翻。
 *
 * 状态放在这里而不是组件里，是因为组件会被卸载。与 reportJobStore 同一套做法：
 * 单条轮询链路（任一时刻只有一个定时器，一次遍历所有在途任务）+ 完成 / 失败统一走
 * ElNotification；App.vue 在会话恢复 / 登录成功时调 resumePending()，刷新后依然能收到通知。
 * 训练页不再展示结果（结果在模型中心看），所以这里**不暴露完成回调钩子**。
 *
 * 「在途任务」的判定不依赖进程内任务表：状态本身就在 model_version.status 上。
 * 恢复时会带 include_finished，把 DRAFT / FAILED 也接回来 —— 否则「刷新期间训练完成」
 * 的那一次，接口只回 TRAINING、前端永远不知道它结束了（通知直接丢）。
 *
 * 已用时间按服务端的 trained_at 算（提交时刻），不再用本地登记时刻 —— 本地记的话
 * 刷新一次就归零。model_version 没有完成时间字段，所以「已完成未查看」按 id 集合差判
 * （见 utils/jobSeen）。
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

/** 训练中：只要状态还是它，就说明后台线程没推进完 */
const STATUS_TRAINING = 'TRAINING';
/** 训练成功落库后的状态（待管理员审核发布） */
const STATUS_DRAFT = 'DRAFT';
const STATUS_FAILED = 'FAILED';
const TERMINAL_STATUSES = [STATUS_DRAFT, STATUS_FAILED];

const POLL_INTERVAL_MS = 1000;
/**
 * 等待上限。后端 training_runner 的 TRAINING_STALE_MINUTES 默认 60 分钟才把卡住的
 * 版本标记为 FAILED，前端必须比它晚放弃，否则会先弹「等待超时」而真正的完成通知
 * 之后再也收不到。取 65 分钟。
 */
const POLL_TIMEOUT_MS = 65 * 60 * 1000;
/** 终态任务最多在册多少条 */
const MAX_FINISHED = 20;

/**
 * 终态任务的保留时长。顶栏面板只展示最近一天的任务，超过它的不再列出
 * （由 App.vue 的低频定时器调 purgeExpired —— 空闲时轮询已经停了，
 * 没有别的时机能让到点的行自己消失）。
 *
 * 基准取**提交时刻** `startedAt`（服务端的 trained_at）：model_version 没有完成时间字段。
 * 训练最长 65 分钟（POLL_TIMEOUT_MS），相对 24 小时可忽略。
 */
const FINISHED_TTL_MS = 24 * 60 * 60 * 1000;

/** 后台训练任务（终态任务也留在列表里，供顶栏面板展示） */
export interface BackgroundTrainingJob {
  modelVersionId: number;
  /** 任务名（场景 · 算法），用于通知文案与面板行 */
  title: string;
  /** 模型版本状态：TRAINING / DRAFT / FAILED */
  status: string;
  error: string | null;
  /** 提交时刻（毫秒时间戳；恢复时取服务端的 trained_at） */
  startedAt: number;
  /** 已用秒数（每次轮询按真实时间差重算） */
  elapsed: number;
}

const pollFor = createStorePoller(POLL_INTERVAL_MS, currentUid);

/**
 * 已经出过完成 / 失败通知的任务（modelVersionId）。
 *
 * `_tick` 里「状态不再是 TRAINING 就 _settle」的判据比 `isTerminal`（只认 DRAFT / FAILED）
 * 宽：版本在轮询间隔里被管理员改成 PUBLISHED / DISABLED，或者接口返回了空状态时，
 * 任务既不算终态（继续留在在途列表里轮询），又每一拍都满足 _settle 的条件 —— 不拦就会
 * 每秒重复弹一条通知，一直弹到 POLL_TIMEOUT_MS（65 分钟）超时。这里保证一个任务只通知一次。
 * reset() 时清空（换账号 / 重新恢复任务时重建）。
 */
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

/** 判定任务对象是否已到终态（口径同上：只认 DRAFT / FAILED） */
const isTerminal = createIsTerminal<BackgroundTrainingJob>(TERMINAL_STATUSES);

/** 训练任务名：场景 · 算法 */
export const trainingJobTitle = (row: TrainingJobRow) =>
  [row.scenario_name, row.algorithm_name].filter(Boolean).join(' · ') || '模型训练';

export const useTrainingJobStore = defineStore('trainingJob', {
  state: () => ({
    jobs: [] as BackgroundTrainingJob[],
    /** 已看过的任务 id（localStorage 持久化，跨刷新 / 跨标签页） */
    seenIds: [] as string[],
  }),

  getters: {
    /** 还有在途训练（终态任务不算） */
    running: (state): boolean => state.jobs.some((job) => !isTerminal(job)),

    /** 页面上展示的那条在途任务（训练页一次只提交一个，取最近登记的） */
    activeJob: (state): BackgroundTrainingJob | null => {
      const running = state.jobs.filter((job) => !isTerminal(job));
      return running.length ? running[running.length - 1] : null;
    },

    /** 在途训练（顶栏面板用） */
    runningJobs: (state): BackgroundTrainingJob[] => state.jobs.filter((job) => !isTerminal(job)),

    /** 已到达终态的（顶栏面板的「已完成」区；含已看过的，那属于任务历史） */
    finishedJobs: (state): BackgroundTrainingJob[] => state.jobs.filter(isTerminal),

    /** 已完成但没看过的（顶栏徽章的数字） */
    unseenJobs: (state): BackgroundTrainingJob[] => {
      const seen = new Set(state.seenIds);
      return state.jobs.filter((job) => isTerminal(job) && !seen.has(String(job.modelVersionId)));
    },
  },

  actions: {
    /** 登记一个后台训练任务（status 传终态时只登记不轮询，用于恢复「已完成未查看」的） */
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

    /** 重新读一遍已读集合（会话恢复 / 别的标签页改动时用） */
    syncSeen() {
      this.seenIds = [...readSeenIds(currentUid())];
    },

    /**
     * 清空任务状态、重新读本账号的已读集合。**换账号 / 登出时必须调**。
     *
     * store 是全局单例，任务列表虽然是后端按 `trained_by = me` 过滤的，但数组本身不会
     * 自己清 —— 不重置的话上一个账号的训练会留在列表里，被当成「本账号已完成未查看」
     * 列进顶栏面板。
     *
     * 注意这里必须跟着 `syncSeen()`：`seenIds` 也得换成当前账号的，
     * 否则 `resumePending` 拿到空集合，会把所有终态任务都判成未读。
     */
    reset() {
      pollFor(this).reset();
      this.jobs = [];
      settledIdsFor(this).clear();
      this.syncSeen();
    },

    /**
     * 把已完成任务标记为已看（面板展开停留够久、或点击某一行时调）。
     *
     * **只记 id，不从 jobs 里删** —— 顶栏面板正在展示这些行，删了会让它们在鼠标底下
     * 消失（展开 1.5 秒后必发生），连点都点不到。清理由 _trimFinished 兜底。
     */
    markAllSeen(keys?: string[]) {
      const targets = this.jobs.filter(
        (job) => isTerminal(job) && (!keys || keys.includes(String(job.modelVersionId))),
      );
      if (!targets.length) return;
      this.seenIds = [...markSeenIds(currentUid(), targets.map((job) => String(job.modelVersionId)))];
    },

    /**
     * 恢复「还在训练」以及「已完成但没看过」的任务（由 App.vue 在会话恢复 / 登录成功时调一次）。
     *
     * **先 reset 再拉**：这是「按当前账号重建状态」的时机，不先把上一个账号的残留清掉，
     * 就会把它当成本账号的训练挂进顶栏面板。
     *
     * 前端这侧的状态随页面一起没了；列出本人仍在 TRAINING 的版本接回轮询、
     * 把 DRAFT / FAILED 的接回来挂徽章 —— 否则刷新期间完成的那些，通知永远收不到。
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
        // 恢复失败不影响页面：训练仍在后台跑，结果可在模型中心看到
      }
      // 接口带 include_finished 会把更早的终态也捞回来，超过保留时长的先丢掉
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
          // 单次轮询失败（网络抖动 / 服务端重启）不立刻判死，交给超时兜底
          job.error = messageOf(err, job.error ?? '训练状态查询失败');
        }
      }
      if (context.isCurrent() && !this.running) this.stopPolling();
    },

    /** 任务到达终态：出通知。**不从列表移除** —— 顶栏面板要展示它。 */
    _settle(job: BackgroundTrainingJob) {
      const settledIds = settledIdsFor(this);
      // 一个任务只通知一次，理由见 settledIds 的说明
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
      // 失败要人看见，所以不自动消失
      ElNotification({
        title: '模型训练失败',
        message: `《${job.title}》：${job.error || `训练状态 ${job.status}`}`,
        type: 'error',
        duration: 0,
      });
    },

    /** 终态任务超过上限就丢最旧的 */
    _trimFinished() {
      this.jobs = trimFinishedJobs(this.jobs, isTerminal, (job) => String(job.modelVersionId), MAX_FINISHED);
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

    /**
     * 等待超时：停止轮询，但不当作失败 —— 服务端可能还在跑。
     * 说清楚「还在后台继续」比直接报失败更准确。
     */
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
