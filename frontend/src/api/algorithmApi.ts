/**
 * algorithmApi.ts — 算法接口（与后端 /api/v1/algorithms 对齐）
 *
 * 薄封装：仅 request 调用 + unwrapData 解包，不含业务逻辑。
 */
import request, { unwrapData } from '@/utils/request';
import type { AlgorithmDefinition } from '@/types/security';

/** 已注册算法列表（GET /algorithms，data 为数组） */
export const getAlgorithms = async (): Promise<AlgorithmDefinition[]> =>
  unwrapData(await request.get('/api/v1/algorithms'));
