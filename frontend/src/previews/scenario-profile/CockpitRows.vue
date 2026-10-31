<script setup lang="ts">
/**
 * CockpitRows，键值行列表（对应管理员首页的 .model-stat-grid / .user-stats 语族）。
 * columns=2 时两列排布，适合「成员 + 角色」这类短行。
 * value 为 null 渲染「—」：调用方用 null 表达「未取到」，不能写成 0。
 */
import { toneColor, type Tone } from './profileTokens';

export interface CockpitRow {
  label: string;
  value: string | number | null;
  tone?: Tone;
}

withDefaults(defineProps<{ rows: CockpitRow[]; columns?: number }>(), { columns: 1 });

const valueText = (row: CockpitRow): string =>
  row.value === null || row.value === undefined || row.value === '' ? '—' : String(row.value);
</script>

<template>
  <p v-if="!rows.length" class="pf-empty">暂无数据</p>
  <div v-else class="pf-rows" :class="{ 'pf-rows--2': columns === 2 }">
    <div v-for="row in rows" :key="row.label" class="pf-row">
      <span>{{ row.label }}</span>
      <strong :style="{ color: toneColor(row.tone) }">{{ valueText(row) }}</strong>
    </div>
  </div>
</template>
