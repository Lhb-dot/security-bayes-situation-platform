/**
 * jobSeen.ts — 顶栏任务面板的「已看过」标记
 *
 * 判据是 **id 集合差**，不是时间戳。原因：model_version 表没有完成时间字段
 * （只有 trained_at，那是提交时刻），report / export / batch 三个任务视图也不下发
 * finished_at，所以没法按「上次已读时间」筛。改成记「见过的 id」—— 后端返回的终态
 * 任务里，id 不在集合内的就是「已完成未查看」。任务 id 要么是 uuid、要么是自增主键，
 * 天然唯一，够用。
 *
 * 存 localStorage 所以跨刷新有效；监听 storage 事件让多个标签页互相同步
 * （storage 事件只在**其他**标签页触发，正好是我们要的方向）。
 *
 * **按 user_id 分桶**：`{"1": [id...], "2": [id...]}`。同一台机器上换账号登录，
 * 各自的已读记录互不影响，也不会把上一个账号的顶掉。旧版本存的是单槽
 * `{uid, ids}`，读的时候就地升级（见 migrate）。
 */
const STORAGE_KEY = 'bayes_seen_job_ids';
/** 单个账号的上限：id 会无限增长，超过就丢最旧的 */
const MAX_IDS = 400;
/** 最多保留几个账号的桶，防止长期切账号把 localStorage 撑大 */
const MAX_ACCOUNTS = 8;

/** 按账号分桶：{ "1": ["job-a", ...], "2": [...] } */
type SeenBuckets = Record<string, string[]>;

const listeners = new Set<() => void>();
let listening = false;

const bucketKey = (uid: string | null): string => uid ?? '__anon__';

const isId = (value: unknown): value is string => typeof value === 'string' && value.length > 0;

/** 兼容旧的单槽结构 `{uid, ids}` → 分桶结构 */
const migrate = (raw: unknown): SeenBuckets => {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const obj = raw as Record<string, unknown>;
  if ('uid' in obj || 'ids' in obj) {
    const ids = Array.isArray(obj.ids) ? obj.ids.filter(isId) : [];
    const uid = obj.uid;
    return typeof uid === 'string' && uid ? { [uid]: ids } : {};
  }
  const buckets: SeenBuckets = {};
  for (const [uid, ids] of Object.entries(obj)) {
    if (uid && Array.isArray(ids)) buckets[uid] = ids.filter(isId);
  }
  return buckets;
};

const read = (): SeenBuckets => {
  try {
    return migrate(JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? 'null'));
  } catch {
    return {};
  }
};

const write = (buckets: SeenBuckets) => {
  try {
    const entries = Object.entries(buckets);
    const kept = entries.length > MAX_ACCOUNTS ? entries.slice(-MAX_ACCOUNTS) : entries;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(kept)));
  } catch {
    // 隐私模式 / 配额满：标记写不进去不影响主流程，退化成「本次会话内有效」
  }
};

const notify = () => {
  for (const callback of [...listeners]) callback();
};

const ensureListening = () => {
  if (listening) return;
  listening = true;
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY) notify();
  });
};

/** 某个账号「已看过」的 id 集合；没有这个账号的桶就是空集合 */
export const readSeenIds = (uid: string | null): Set<string> => {
  ensureListening();
  return new Set(read()[bucketKey(uid)] ?? []);
};

/** 把一批 id 记为已看过，返回该账号更新后的集合 */
export const markSeenIds = (uid: string | null, ids: string[]): Set<string> => {
  ensureListening();
  const key = bucketKey(uid);
  const buckets = read();
  const base = buckets[key] ?? [];
  const known = new Set(base);
  const merged = [...base];
  for (const id of ids) {
    if (known.has(id)) continue;
    known.add(id);
    merged.push(id);
  }
  const kept = merged.slice(-MAX_IDS);
  // 先删再写：让「最近用过的账号」排到末尾，写满 MAX_ACCOUNTS 时优先保留它
  delete buckets[key];
  buckets[key] = kept;
  write(buckets);
  notify();
  return new Set(kept);
};

/** 订阅变更（含其他标签页的改动），返回取消订阅函数 */
export const onSeenIdsChange = (callback: () => void): (() => void) => {
  ensureListening();
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
};
