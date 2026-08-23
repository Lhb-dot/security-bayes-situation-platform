/**
 * trainingApi.js — AI 模型训练页真实接口（/api/v1 数据库版）
 *
 * 替代 mockApi 的 getDatasetList / getAlgorithms / trainModel：
 * - 场景 / 数据集 / 算法 全部从数据库渲染
 * - 训练走 POST /api/v1/model-versions/train，参数按 param_schema 传入真实 Java/Weka 服务
 *
 * request.js 响应拦截器已剥掉 axios 外层，直接返回后端统一结构
 * {code, data, message}；非零 code 时后端以对应 HTTP 状态码返回，由 axios 抛错。
 */
import request, { unwrapData } from '@/utils/request';

/** 已注册场景（需求 1.1：训练前必须先选场景） */
export const getScenarios = async () => unwrapData(await request.get('/api/v1/scenarios'));

/** 指定场景下的数据集（需求 2.2：数据集必须属于所选场景） */
export const getDatasets = async (scenarioId, pageSize = 200) => {
  const data = unwrapData(
    await request.get('/api/v1/datasets', {
      params: { scenario_id: scenarioId, page: 1, page_size: pageSize },
    })
  );
  return data.items ?? [];
};

/** 已注册算法（含 param_schema，供训练参数表单动态生成） */
export const getAlgorithms = async () => unwrapData(await request.get('/api/v1/algorithms'));

/** 训练并保存模型版本：所有已注册算法均执行真实训练 */
export const trainModel = async (payload) =>
  unwrapData(await request.post('/api/v1/model-versions/train', payload));
