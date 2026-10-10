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
