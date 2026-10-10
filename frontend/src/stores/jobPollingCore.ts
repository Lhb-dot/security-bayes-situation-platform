/** 会话重置或轮询停止后，异步响应必须先确认自己仍属于当前轮次。 */
export interface PollContext {
  isCurrent(): boolean;
}

/** 只管理调度与失效响应；查询接口、终态、通知和下载由各 Store 决定。 */
export const createJobPoller = (
  intervalMs: number,
  onTick: (context: PollContext) => Promise<void>,
  getOwner: () => string | null,
) => {
  let timer: ReturnType<typeof setInterval> | null = null;
  let session = 0;
  let round = 0;
  let pending: Promise<void> | null = null;

  // 恢复列表与下载属于会话，不因所有任务完成后自动停表而失效。
  const capture = (): PollContext => {
    const version = session;
    const owner = getOwner();
    return { isCurrent: () => session === version && getOwner() === owner };
  };

  const tick = (): Promise<void> => {
    if (pending) return pending;
    const context = capture();
    const version = round;
    const task = Promise.resolve()
      .then(() => onTick({ isCurrent: () => context.isCurrent() && round === version }))
      .finally(() => {
        // 旧请求返回时不能解除新轮次的防重入锁。
        if (pending === task) pending = null;
      });
    pending = task;
    return task;
  };

  const stop = () => {
    if (timer !== null) clearInterval(timer);
    timer = null;
    round += 1;
    pending = null;
  };

  return {
    start() {
      if (timer !== null) return;
      timer = setInterval(() => void tick(), intervalMs);
      void tick();
    },
    stop,
    tick,
    capture,
    reset() {
      stop();
      session += 1;
    },
    get active() { return timer !== null; },
  };
};

/** 每个 Pinia Store 实例独立持有调度器，避免测试或多应用共享模块级锁。 */
export const createStorePoller = (intervalMs: number, getOwner: () => string | null) => {
  const pollers = new WeakMap<object, ReturnType<typeof createJobPoller>>();
  return (store: { _poll(context: PollContext): Promise<void> }) => {
    let poller = pollers.get(store);
    if (!poller) {
      poller = createJobPoller(intervalMs, (context) => store._poll(context), getOwner);
      pollers.set(store, poller);
    }
    return poller;
  };
};
