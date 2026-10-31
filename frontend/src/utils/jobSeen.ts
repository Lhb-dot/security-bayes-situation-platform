/**
 * 顶栏任务面板的「已看过」标记。判据是 id 集合差，不是时间戳：
 * 任务视图没有完成时间字段，id 要么是 uuid 要么是自增主键，天然唯一。
 */
const STORAGE_KEY = 'bayes_seen_job_ids';
const MAX_IDS = 400;
const MAX_ACCOUNTS = 8;

type SeenBuckets = Record<string, string[]>;

const listeners = new Set<() => void>();
let listening = false;

const bucketKey = (uid: string | null): string => uid ?? '__anon__';

const isId = (value: unknown): value is string => typeof value === 'string' && value.length > 0;

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

export const readSeenIds = (uid: string | null): Set<string> => {
  ensureListening();
  return new Set(read()[bucketKey(uid)] ?? []);
};

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
  delete buckets[key];
  buckets[key] = kept;
  write(buckets);
  notify();
  return new Set(kept);
};

export const onSeenIdsChange = (callback: () => void): (() => void) => {
  ensureListening();
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
};
