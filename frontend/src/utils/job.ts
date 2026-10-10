/**
 * job.ts — 后台任务 store 共用的纯函数。
 *
 * trainingJobStore / batchJobStore / reportJobStore 三个 store 此前各自定义了一份
 * 完全相同的实现，这里收敛为单一来源。
 */

/** 错误对象 → 可展示文案；取不到 message 时退回 fallback。 */
export const messageOf = (err: unknown, fallback: string): string =>
  err instanceof Error && err.message ? err.message : fallback;

/**
 * 生成「任务是否已到终态」的判定函数。
 * 返回的函数签名与原来的局部 isTerminal 一致，可直接传给 Array.filter。
 */
export const createIsTerminal =
  <T extends { status: string }>(terminalStatuses: readonly string[]) =>
  (job: T): boolean =>
    terminalStatuses.includes(job.status);

/** 保留最新的终态任务，保持在途任务和原列表的展示顺序。 */
export const trimFinishedJobs = <T extends { startedAt: number }>(
  jobs: T[],
  isTerminal: (job: T) => boolean,
  keyOf: (job: T) => string,
  maxFinished: number,
): T[] => {
  const finished = jobs.filter(isTerminal);
  if (finished.length <= maxFinished) return jobs;
  const drop = new Set(
    finished
      .sort((a, b) => a.startedAt - b.startedAt)
      .slice(0, finished.length - maxFinished)
      .map(keyOf),
  );
  return jobs.filter((job) => !drop.has(keyOf(job)));
};

/** 只清理早于截止时间的终态任务，正在运行的任务由各 Store 的超时策略处理。 */
export const keepUnexpiredJobs = <T extends { startedAt: number }>(
  jobs: T[],
  isTerminal: (job: T) => boolean,
  deadline: number,
): T[] => jobs.filter((job) => !isTerminal(job) || job.startedAt >= deadline);

