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
        const items = await getInferenceRecordList({ page_size: 200 });
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
