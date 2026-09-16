<script setup lang="ts">
/**
 * DashKpis —— KPI 卡片组（图标左侧色条 + 大号数值 + 口径副标题）。
 */
import { fmtInt } from './dashFormat';
import { SHOW_DASH_HINTS } from './dashHints';

export interface KpiItem {
  label: string;
  value: number | string | null | undefined;
  unit?: string;
  /** 色条 / 数值配色 */
  tone?: 'primary' | 'danger' | 'warning' | 'success' | 'purple' | 'gray';
  /** 口径说明（展示在标签下方） */
  sub?: string;
  /** 若为 true，value 原样展示（已是格式化字符串） */
  raw?: boolean;
}

withDefaults(defineProps<{ items: KpiItem[]; columns?: number }>(), { columns: 4 });
</script>

<template>
  <section class="d-kpis" :style="columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined">
    <div v-for="item in items" :key="item.label" class="d-kpi" :class="`d-kpi--${item.tone || 'primary'}`">
      <span class="d-kpi-v">
        {{ item.raw ? (item.value ?? '—') : fmtInt(item.value) }}<em v-if="item.unit">{{ item.unit }}</em>
      </span>
      <span class="d-kpi-l">{{ item.label }}</span>
      <span v-if="SHOW_DASH_HINTS && item.sub" class="d-kpi-sub">{{ item.sub }}</span>
    </div>
  </section>
</template>
