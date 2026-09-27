<script setup lang="ts">
/**
 * DashTable —— 多列数据矩阵表（管理端总览专用）。
 *
 * 与 DashRows 的分工：
 *   DashRows  = 「标签 : 值」两列键值列表，适合单一口径的少量指标；
 *   本组件    = 任意列 × 任意行的矩阵，适合「数据集 × 多个管理口径」这类对比
 *              （风险口径可比性矩阵、数据集角色分工矩阵、统计维度覆盖矩阵…）。
 *   管理端首页的特色块本质都是「跨数据集逐行对比」，两列键值列表表达不了，故新增本组件。
 *
 * 单元格取值约定（DashCell）：
 *   - 字符串 / 数字 → 原样渲染（数值列请给 columns[].numeric = true）
 *   - { text, tone } → 渲染为带色标签，tone 复用 dash.css 的 .d-tag--* 语义
 *   - null / undefined → 渲染为「—」
 *   - 需要自定义 DOM 时，用与 columns[].key 同名的具名插槽覆盖（slot props: row / value）
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
  /** 与 row 对象的字段名一致；同时作为具名插槽名 */
  key: string;
  label: string;
  /** 列宽（px）；不传自适应 */
  width?: number;
  align?: 'left' | 'right' | 'center';
  /** 数值列：等宽数字 + 高亮色 */
  numeric?: boolean;
}

const props = withDefaults(
  defineProps<{
    columns: DashColumn[];
    rows: Array<Record<string, unknown>>;
    /** 行主键字段名；不传用索引 */
    rowKey?: string;
    /** 紧凑模式：列数多时用，压缩行高 */
    dense?: boolean;
  }>(),
  { rowKey: '', dense: false },
);

const keyOf = (row: Record<string, unknown>, index: number) =>
  props.rowKey ? String(row[props.rowKey] ?? index) : String(index);

/** 带色标签单元格 */
const asTag = (value: unknown): { text: string; tone: DashTone } | null => {
  if (value === null || typeof value !== 'object') return null;
  const candidate = value as { text?: unknown; tone?: unknown };
  if (typeof candidate.text !== 'string') return null;
  return { text: candidate.text, tone: (candidate.tone as DashTone) ?? 'muted' };
};

/** 纯文本单元格 */
const asText = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '—';
  return String(value);
};

const cellValues = computed(() => props.rows.map((row) => props.columns.map((col) => row[col.key])));
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
            v-for="(col, colIndex) in columns"
            :key="col.key"
            :class="{ 'd-table-num': col.numeric }"
            :style="{ textAlign: col.align || 'left' }"
          >
            <slot :name="col.key" :row="row" :value="cellValues[index][colIndex]">
              <span
                v-if="asTag(cellValues[index][colIndex])"
                class="d-tag"
                :class="`d-tag--${asTag(cellValues[index][colIndex])!.tone}`"
              >{{ asTag(cellValues[index][colIndex])!.text }}</span>
              <template v-else>{{ asText(cellValues[index][colIndex]) }}</template>
            </slot>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
