import { useUserStore } from '@/stores/userStore';

/** 任务已读记录按当前账号隔离；调用时读取账号，避免保留过期快照。 */
export const currentUid = (): string | null => useUserStore().currentUser?.user_id ?? null;
