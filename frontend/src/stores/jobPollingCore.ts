/**
 * jobPollingCore.ts — 三个 job store 共用的机械逻辑。
 *
 * 这里只收敛定时器管理、终态任务裁剪和过期清理。各 store 的轮询接口、状态字段、
 * 通知文案与副作用仍留在各自文件里，避免把不同的长任务流程耦合起来。
 */

/** 轮询定时器：任一时刻只有一个（幂等）。每个 store 在模块级创建一个实例。 */
export const createPollTimer = (intervalMs: number, onTick: () => void) => {
  let timer: number | null = null;
  return {
    /** 已在计时则不重复启动；启动后立即跑一拍 */
    start(): void {
      if (timer !== null) return;
      timer = window.setInterval(onTick, intervalMs);
      onTick();
    },
    stop(): void {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    },
    get active(): boolean {
      return timer !== null;
    },
  };
};

/** 终态任务超过上限就丢最旧的，id 和时间字段由调用方提供。 */
export const trimFinished = <TJob>(
  jobs: TJob[],
  isTerminal: (job: TJob) => boolean,
  getId: (job: TJob) => string,
  getStartedAt: (job: TJob) => number,
  maxFinished: number,
): TJob[] => {
  const finished = jobs.filter(isTerminal);
  if (finished.length <= maxFinished) return jobs;
  const drop = new Set(
    finished
      .slice()
      .sort((a, b) => getStartedAt(a) - getStartedAt(b))
      .slice(0, finished.length - maxFinished)
      .map(getId),
  );
  return jobs.filter((job) => !drop.has(getId(job)));
};

/** 丢掉超过保留时长的终态任务；在途任务由各 store 的轮询超时逻辑管理。 */
export const filterExpired = <TJob>(
  jobs: TJob[],
  isTerminal: (job: TJob) => boolean,
  getStartedAt: (job: TJob) => number,
  ttlMs: number,
): TJob[] => {
  const deadline = Date.now() - ttlMs;
  return jobs.filter((job) => !isTerminal(job) || getStartedAt(job) >= deadline);
};
