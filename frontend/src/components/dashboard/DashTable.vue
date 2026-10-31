<script setup lang="ts">
/**
 * 多列数据矩阵表，管理端总览专用。与 DashRows 的分工：
 * DashRows 是「标签 : 值」两列键值列表；本组件是任意列 × 任意行的矩阵，
 * 用于「数据集 × 多个管理口径」这类跨数据集逐行对比。
 */
import { computed } from 'vue';

export type DashTone =
  | 'high'
  | 'medium'
  | 'low'
  | 'ok'
  | 'pending'
  | 'processing'
  | 'resolved'
  | 'up'
  | 'down'
  | 'warn'
  | 'muted';

export type DashCell =
  | string
  | number
  | null
  | undefined
  | { text: string; tone?: DashTone };

export interface DashColumn {
  key: string;
  label: string;
  width?: number;
  align?: 'left' | 'right' | 'center';
  numeric?: boolean;
}

const props = withDefaults(
  defineProps<{
    columns: DashColumn[];
    rows: Array<Record<string, unknown>>;
    rowKey?: string;
    dense?: boolean;
  }>(),
  { rowKey: '', dense: false },
);

const keyOf = (row: Record<string, unknown>, index: number) =>
  props.rowKey ? String(row[props.rowKey] ?? index) : String(index);

const asTag = (value: unknown): { text: string; tone: DashTone } | null => {
  if (value === null || typeof value !== 'object') return null;
  const candidate = value as { text?: unknown; tone?: unknown };
  if (typeof candidate.text !== 'string') return null;
  return { text: candidate.text, tone: (candidate.tone as DashTone) ?? 'muted' };
};

const asText = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '—';
  return String(value);
};

const cellValues = computed(() => props.rows.map((row) => props.columns.map((col) => row[col.key])));

const cellRenders = computed(() =>
  cellValues.value.map((row) =>
    row.map((value) => {
      const tag = asTag(value);
      return tag
        ? { isTag: true, text: tag.text, cls: `d-tag d-tag--${tag.tone}` }
        : { isTag: false, text: asText(value), cls: '' };
    }),
  ),
);
</script>

<template>
  <div v-if="!rows.length" class="d-empty">暂无数据</div>
  <div v-else class="d-table-wrap">
    <table class="d-table" :class="{ 'd-table--dense': dense }">
      <thead>
        <tr>
          <th
            v-for="col in columns"
            :key="col.key"
            :style="{ width: col.width ? col.width + 'px' : undefined, textAlign: col.align || 'left' }"
          >
            {{ col.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="keyOf(row, index)">
          <td
            v-for="(cell, colIndex) in cellRenders[index]"
            :key="columns[colIndex].key"
            :class="{ 'd-table-num': columns[colIndex].numeric }"
            :style="{ textAlign: columns[colIndex].align || 'left' }"
          >
            <slot :name="columns[colIndex].key" :row="row" :value="cellValues[index][colIndex]">
              <span v-if="cell.isTag" :class="cell.cls">{{ cell.text }}</span>
              <template v-else>{{ cell.text }}</template>
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
