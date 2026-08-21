/**
 * scenarioApi.ts — 场景接口（与后端 /api/v1/scenarios 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 */
import request, { unwrapData } from '@/utils/request';

/** 后端 scenario 行 */
export interface ApiScenario {
  id: number;
  code: string;
  name: string;
  description: string | null;
  access_status: string;
}

/** 场景列表（GET /scenarios，data 为数组） */
export const getScenarioList = async (): Promise<ApiScenario[]> =>
  unwrapData(await request.get('/api/v1/scenarios'));

/** 场景详情（GET /scenarios/{scenario_id}，scenario_id 为数字 ID） */
export const getScenarioDetail = async (scenarioId: number): Promise<ApiScenario> =>
  unwrapData(await request.get(`/api/v1/scenarios/${scenarioId}`));

// 场景编码 → 数字 ID 缓存（前端路由用编码，后端接口用数字 ID）
let _idByCodeCache: Record<string, number> | null = null;

/** 把场景编码（如 network_security）解析为后端数字 ID；传数字则原样返回 */
export const resolveScenarioId = async (codeOrId: string | number): Promise<number> => {
  if (typeof codeOrId === 'number') return codeOrId;
  if (!_idByCodeCache) {
    const list = await getScenarioList();
    _idByCodeCache = {};
    for (const s of list) _idByCodeCache[s.code] = s.id;
  }
  const id = _idByCodeCache[codeOrId];
  if (id == null) throw new Error(`场景不存在: ${codeOrId}`);
  return id;
};
