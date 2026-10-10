/**
 * trainingApi.js — AI 模型训练页真实接口（/api/v1 数据库版）
 *
 * 为训练页提供真实后端的 getScenarios / getDatasets / getAlgorithms /
 * trainModelAsync / getModelVersionDetail：
 * - 场景 / 数据集 / 算法 全部从数据库渲染
 * - 训练走 POST /api/v1/model-versions/train-async：提交后立刻返回 TRAINING 版本，
 *   后台线程调用真实 Java/Weka 服务；前端轮询 getModelVersionDetail 等状态流转
 *
 * 同步接口 POST /api/v1/model-versions/train 仍在（trainModel 保留作回退用），
 * 它会在请求线程里等到训练结束，最长占住一个 worker 到 TRAIN_TIMEOUT（600 秒）。
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

/** 训练并保存模型版本（同步）：请求线程等到训练结束，仅作回退用 */
export const trainModel = async (payload) =>
  unwrapData(await request.post('/api/v1/model-versions/train', payload));

/** 提交异步训练：立刻返回 TRAINING 版本，真实训练在后台线程执行 */
export const trainModelAsync = async (payload) =>
  unwrapData(await request.post('/api/v1/model-versions/train-async', payload));

/** 模型版本详情：异步训练轮询用，状态转为 DRAFT / FAILED 即训练结束 */
export const getModelVersionDetail = async (modelId) =>
  unwrapData(await request.get(`/api/v1/model-versions/${modelId}`));

/**
 * 我的训练任务（GET /api/v1/model-versions/training-jobs）
 *
 * 训练没有独立任务表，在途状态就落在 model_version.status 上；刷新 / 切页回来靠它
 * 把还在 TRAINING 的版本接回轮询，这样离开训练页也不会丢掉完成通知。
 *
 * includeFinished=true 时把 DRAFT / FAILED 也带回来（最多 20 条），供顶栏任务面板
 * 判定「已完成但没看过」：model_version 没有完成时间字段，所以按 id 集合差判 ——
 * id 自增，前端把见过的 id 记在 localStorage 里，没见过的就是没看过。
 */
export const listTrainingJobs = async (includeFinished = false) =>
  unwrapData(
    await request.get('/api/v1/model-versions/training-jobs', {
      params: includeFinished ? { include_finished: true } : undefined,
    })
  );
