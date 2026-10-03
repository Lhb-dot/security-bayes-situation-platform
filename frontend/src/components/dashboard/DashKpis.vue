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

/**
 * 非 raw 值的展示文本。
 *
 * 必须先拦 null/undefined/空串：`fmtInt` 内部走 `Number(value)`，而 `Number(null)` 与
 * `Number('')` 都是 0（有限数），会被渲染成「0」而不是「—」。调用点用 null 表达的正是
 * 「无数据」（见各 Profile 页 runtimeKpis 的 `item ? item.pending : null` 分支，
 * 以及 ProfileFlightdeck「分母为 0 时不下结论，交给 DashKpis 渲染「—」」的注释），
 * 渲染成 0 会被读成「一件都没有」，与「拿不到数据」混淆。
 */
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
