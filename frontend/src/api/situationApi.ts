/**
 * situationApi.ts — 态势接口（预留占位）
 *
 * 后端当前无态势路由（backend/app/api/v1 下无 situation 端点），
 * 本模块仅定义函数签名，供 Task 004 situationStore 接入时对齐；
 * 真实接口提供前，调用方继续走 mockApi（getSituationData / getGlobalOverview）。
 */
import type { ScenarioId, SituationData } from '@/types/security';

/** 场景态势分析（TODO 后端待提供路由后实现） */
export const getSituationData = async (scenarioId: ScenarioId): Promise<SituationData> => {
  // TODO 后端待提供：GET /api/v1/situation/{scenario_id}（联调前由 mockApi 提供数据）
  throw new Error(`后端态势接口未提供：getSituationData(${scenarioId})`);
};

/** 全局态势驾驶舱（TODO 后端待提供路由后实现；类型待后端契约确认后补 security.ts） */
export const getGlobalCockpit = async (): Promise<unknown> => {
  // TODO 后端待提供：GET /api/v1/situation/global-cockpit
  throw new Error('后端态势接口未提供：getGlobalCockpit()');
};
