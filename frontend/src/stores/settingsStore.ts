import { defineStore } from 'pinia';

const STORAGE_PREFIX = 'bayes_refresh_settings:';
const DEFAULT_REFRESH_INTERVAL = 30;
const ALLOWED_INTERVALS = [10, 30, 60, 120, 300];

interface StoredRefreshSettings {
  autoRefresh: boolean;
  refreshInterval: number;
}

const storageKey = (userId: string | null | undefined): string =>
  `${STORAGE_PREFIX}${userId || 'anonymous'}`;

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    currentUserId: null as string | null,
    autoRefresh: true,
    refreshInterval: DEFAULT_REFRESH_INTERVAL,
  }),
  actions: {
    loadForUser(userId: string | null | undefined): void {
      this.currentUserId = userId ?? null;
      this.autoRefresh = true;
      this.refreshInterval = DEFAULT_REFRESH_INTERVAL;

      try {
        const raw = window.localStorage.getItem(storageKey(userId));
        if (!raw) return;
        const saved = JSON.parse(raw) as Partial<StoredRefreshSettings>;
        if (typeof saved.autoRefresh === 'boolean') {
          this.autoRefresh = saved.autoRefresh;
        }
        if (typeof saved.refreshInterval === 'number' && ALLOWED_INTERVALS.includes(saved.refreshInterval)) {
          this.refreshInterval = saved.refreshInterval;
        }
      } catch {
        // 使用默认设置，避免本地存储损坏影响页面加载。
      }
    },
    saveRefreshSettings(): void {
      try {
        const settings: StoredRefreshSettings = {
          autoRefresh: this.autoRefresh,
          refreshInterval: this.refreshInterval,
        };
        window.localStorage.setItem(storageKey(this.currentUserId), JSON.stringify(settings));
      } catch {
        // 本地存储不可用时仍保留当前会话内的设置。
      }
    },
  },
});
