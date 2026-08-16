/**
 * modelApi.js — 旧版接口（/api/model/*）
 *
 * @deprecated 已废弃：V3.0 起新代码禁止引用本模块，
 * 请改用 src/api/*.ts（与后端 /api/v1 对齐的模块）或经 store 访问数据。
 * 现有调用方（DashboardView 大屏）暂保留兼容，后续随旧大屏下线移除。
 */
import request from '@/utils/request'

// 1. 获取数据集列表 GET /api/model/dataset-list
export function getDatasetList() {
  return request({
    url: '/api/model/dataset-list',
    method: 'get'
  })
}

// 2. 保存风险阈值 POST /api/model/save-threshold
export function saveThreshold(high, mid, low) {
  return request({
    url: '/api/model/save-threshold',
    method: 'post',
    params: { high, mid, low }
  })
}

// 3. 模型训练 POST /api/model/train
export function trainModel(params) {
  return request({
    url: '/api/model/train',
    method: 'post',
    params: {
      dataset_name: params.dataset_name,
      algo_type: params.algo_type,
      discrete_method: params.discrete_method
    }
  })
}

// 4. 单条流量风险推理 POST /api/model/infer
export function riskInfer(f1, f2, f3) {
  return request({
    url: '/api/model/infer',
    method: 'post',
    params: { flowLength: f1, duration: f2, accessFreq: f3 }
  })
}

// 5. 获取全部实验记录 GET /api/model/exp-records
export function getExpRecords() {
  return request({
    url: '/api/model/exp-records',
    method: 'get'
  })
}

// 6. 删除实验记录 DELETE /api/model/exp/{record_id}
export function delExpRecord(recordId) {
  return request({
    url: `/api/model/exp/${recordId}`,
    method: 'delete'
  })
}

// 大屏用：获取贝叶斯统计数据
export function getBayesStatData() {
  return request({
    url: '/api/model/risk_statistics',
    method: 'get'
  })
}
