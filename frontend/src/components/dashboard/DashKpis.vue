<script setup lang="ts">
/**
 * DashKpis，KPI 卡片组（图标左侧色条 + 大号数值 + 口径副标题）。
 */
import { fmtInt } from './dashFormat';
import { SHOW_DASH_HINTS } from './dashHints';

export interface KpiItem {
  label: string;
  value: number | string | null | undefined;
  unit?: string;
  tone?: 'primary' | 'danger' | 'warning' | 'success' | 'purple' | 'gray';
  sub?: string;
  raw?: boolean;
}

withDefaults(defineProps<{ items: KpiItem[]; columns?: number }>(), { columns: 4 });

const valueText = (item: KpiItem): string => {
  if (item.raw) return String(item.value ?? '—');
  if (item.value === null || item.value === undefined || item.value === '') return '—';
  return fmtInt(item.value);
};
</script>

<template>
  <section class="d-kpis" :style="columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined">
    <div v-for="item in items" :key="item.label" class="d-kpi" :class="`d-kpi--${item.tone || 'primary'}`">
      <span class="d-kpi-v">
        {{ valueText(item) }}<em v-if="item.unit">{{ item.unit }}</em>
      </span>
      <span class="d-kpi-l">{{ item.label }}</span>
      <span v-if="SHOW_DASH_HINTS && item.sub" class="d-kpi-sub">{{ item.sub }}</span>
    </div>
  </section>
</template>
