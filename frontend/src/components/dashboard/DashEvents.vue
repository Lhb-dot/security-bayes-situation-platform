<script setup lang="ts">
/**
 * DashEvents —— 最近告警列表（描述 + 时间 + 风险分 + 处置状态）。
 */
import type { RiskEventRow } from '@/api/dashboardApi';
import { fmtDateTime, fmtNum, tagClass, tagText } from './dashFormat';

withDefaults(
  defineProps<{
    items: RiskEventRow[];
    emptyText?: string;
  }>(),
  { emptyText: '暂无风险事件 —— 完成风险研判并判定为风险后，事件会出现在这里' },
);
</script>

<template>
  <p v-if="!items.length" class="d-empty">{{ emptyText }}</p>
  <div v-else class="d-evs">
    <div v-for="event in items" :key="event.id" class="d-ev">
      <div class="d-evb">
        <strong :title="event.description">{{ event.description || '风险事件' }}</strong>
        <span class="d-evm">{{ fmtDateTime(event.occurred_at) }}</span>
      </div>
      <span class="d-ev-score">{{ fmtNum(event.risk_score, 2) }}</span>
      <span class="d-tag" :class="tagClass(event.status)">{{ tagText(event.status) }}</span>
    </div>
  </div>
</template>
