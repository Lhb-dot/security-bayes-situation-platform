/**
 * riskEventStore.ts — 风险事件详情/处置
 *
 * 数据源：src/api/riskEventApi（真实后端），字段映射复用 situationApi.mapRiskEvent。
 * 处置状态前端用中文（待处置/处理中/已处置），后端用枚举（PENDING/PROCESSING/RESOLVED），此处转换。
 */
import { defineStore } from 'pinia';
import { getRiskEventDetail, getRiskEventList, updateRiskEventStatus } from '@/api/riskEventApi';
import { mapRiskEvent } from '@/api/situationApi';
import type { RiskEvent, ScenarioId } from '@/types/security';

/**
 * 前端展示口径（中文）→ 后端处置枚举。
 *
 * 用 `Record<RiskEvent['status'], string>` 而不是 `Record<string, string>` 声明：
 * `RiskEvent['status']` 的取值一旦增删，这里会直接编译报错，不会静默漏掉一种状态
 * （原写法还带 `?? status` 兜底，在穷举后是不可达分支）。
 */
const STATUS_VALUE: Record<RiskEvent['status'], string> = {
  '待处置': 'PENDING',
  '处理中': 'PROCESSING',
  '已处置': 'RESOLVED',
};

export const useRiskEventStore = defineStore('riskEvent', {
  state: () => ({
    events: [] as RiskEvent[],
    detail: null as RiskEvent | null,
    loading: false,
  }),
  getters: {
    eventsByScenario: (state) => (scenarioId: ScenarioId): RiskEvent[] =>
      state.events.filter((e) => e.scenario_id === scenarioId),
    highRiskCount: (state): number => state.events.filter((e) => e.risk_level === 'HIGH').length,
  },
  actions: {
    async fetchEvents(): Promise<void> {
      this.loading = true;
      try {
        const items = await getRiskEventList({ page_size: 200 });
        this.events = (items as unknown as Array<Record<string, unknown>>).map(mapRiskEvent);
      } finally {
        this.loading = false;
      }
    },
    async fetchDetail(eventId: string): Promise<void> {
      this.loading = true;
      try {
        const raw = await getRiskEventDetail(eventId);
        this.detail = mapRiskEvent(raw as unknown as Record<string, unknown>);
      } finally {
        this.loading = false;
      }
    },
    clearDetail(): void {
      this.detail = null;
    },
    async updateStatus(eventId: string, status: RiskEvent['status']): Promise<void> {
      // ⚠️ 后端 handle 接口收的是英文枚举，但 updateRiskEventStatus 的参数类型声明成了
      // RiskEvent['status']（中文口径）—— 这个断言是为 api 层的错误类型打的补丁，
      // 修好 riskEventApi.ts 的参数类型后应当删掉（见报告「跨区提案」）。
      const newStatus = STATUS_VALUE[status] as RiskEvent['status'];
      const raw = await updateRiskEventStatus(eventId, { new_status: newStatus });
      this.detail = mapRiskEvent(raw as unknown as Record<string, unknown>);
      const target = this.events.find((e) => e.event_id === eventId);
      if (target) target.status = status;
    },
  },
});
