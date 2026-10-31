// 算法接口（后端 /api/v1/algorithms）。只有 request 调用和 unwrapData 解包。
import request, { unwrapData } from '@/utils/request';
import type { AlgorithmDefinition } from '@/types/security';

export const getAlgorithms = async (): Promise<AlgorithmDefinition[]> =>
  unwrapData(await request.get('/api/v1/algorithms'));
