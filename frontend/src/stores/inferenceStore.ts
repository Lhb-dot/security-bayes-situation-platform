/**
 * inferenceStore.ts — 推理执行与推理记录
 *
 * 数据源：src/api/inferenceRecordApi（真实后端，服务端统一预测入口）。
 * 预测结果 prediction_label / risk_score 由后端按 model_version_id + input_features 计算。
 */
import { defineStore } from 'pinia';
import { getInferenceRecordList, predictInference, type PredictResult } from '@/api/inferenceRecordApi';

export const useInferenceStore = defineStore('inference', {
  state: () => ({
    records: [] as Array<Record<string, unknown>>,
    lastResult: null as PredictResult | null,
    loading: false,
  }),
  actions: {
    async fetchRecords(): Promise<void> {
      this.loading = true;
      try {
        // 200 条会拉到十几 MB（单条含 explain_data），这里只留最近 20 条摘要。
        // 注意：目前没有任何页面读 this.records，这个请求纯属「执行推理后刷新列表」的历史设计。
        const items = await getInferenceRecordList({ page_size: 20 });
        this.records = items as unknown as Array<Record<string, unknown>>;
      } finally {
        this.loading = false;
      }
    },
    async executeInference(params: {
      model_version_id: string | number;
      input_features: Record<string, unknown>;
    }): Promise<PredictResult> {
      const result = await predictInference(params);
      this.lastResult = result;
      await this.fetchRecords();
      return result;
    },
  },
});
