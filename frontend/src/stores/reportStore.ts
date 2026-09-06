/**
 * reportStore.ts — 报告列表/生成（Task 004）
 *
 * 职责边界：仅 state / action，不含业务过滤与页面逻辑。
 * 过渡期数据源：mockApi；后端就绪后切换至 src/api/reportApi.*。
 */
import { defineStore } from 'pinia';
import { getReportList, generateReport } from '@/api/reportApi';
import type { Report, ScenarioId } from '@/types/security';

export const useReportStore = defineStore('report', {
  state: () => ({
    reports: [] as Report[],
    loading: false,
  }),
  actions: {
    async fetchReports(): Promise<void> {
      this.loading = true;
      try {
        this.reports = await getReportList({ page: 1, page_size: 200 });
      } finally {
        this.loading = false;
      }
    },
    async generateReport(params: {
      scenario_id: ScenarioId;
      title: string;
      scope: 'self' | 'all' | 'user';
      target_user_id?: string;
      format?: Report['format'];
      scheduled?: boolean;
      interval_days?: number;
    }): Promise<Report> {
      const report = await generateReport(params);
      await this.fetchReports();
      return report;
    },
  },
});
