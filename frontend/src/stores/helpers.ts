/**
 * helpers.ts — store 层共用的小工具。
 */
import { useUserStore } from '@/stores/userStore';

/** 当前登录用户的 user_id；未登录时为 null。 */
export const currentUid = (): string | null =>
  useUserStore().currentUser?.user_id ?? null;
