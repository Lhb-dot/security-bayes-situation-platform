<script setup lang="ts">
/**
 * CockpitMatrix —— 跨数据集矩阵表（画像驾驶舱的表格形态，对应管理员首页的 .member-table 语言）。
 *
 * 单元格取值约定（与 components/dashboard/DashTable 一致，便于两处口径互认）：
 *   string / number      → 原样渲染（数值列给 columns[].numeric = true）
 *   { text, tone }       → 带色标签（tone 对应 profileCockpit.css 的 .pf-tag--*）
 *   null / undefined     → 「—」
 * columns[].ellipsis 为 true 时，单元格文本按 ellipsisWidth（设计基准单位）截断并给 title。
 */
import { computed } from 'vue';

/**
 * 标签色号：与 profileCockpit.css 的 .pf-tag--* 一一对应。
 * 与 profileTokens.Tone（KPI / 条形的语义色）是两套词汇：这里表达的是结论状态
 * （达标 / 告警 / 高于基准 / 低于基准 / 中性），不是强调色。
 */
export type CockpitTagTone = 'ok' | 'warn' | 'up' | 'down' | 'muted';

export type CockpitCell = string | number | null | undefined | { text: string; tone?: CockpitTagTone };

export interface CockpitColumn {
  key: string;
  label: string;
  align?: 'left' | 'right' | 'center';
  numeric?: boolean;
  /** 首列/名称列：文本过长时省略号截断 */
  ellipsis?: boolean;
  /** 省略宽度（设计基准单位），默认 150 */
  ellipsisWidth?: number;
  /** 列宽（px，设计基准单位），不传自适应 */
  width?: number;
}

const props = withDefaults(
  defineProps<{
    columns: CockpitColumn[];
    rows: Array<Record<string, unknown>>;
    rowKey?: string;
  }>(),
  { rowKey: '' },
);

const keyOf = (row: Record<string, unknown>, index: number): string =>
  props.rowKey ? String(row[props.rowKey] ?? index) : String(index);

const asTag = (value: unknown): { text: string; tone: CockpitTagTone } | null => {
  if (value === null || typeof value !== 'object') return null;
  const candidate = value as { text?: unknown; tone?: unknown };
  if (typeof candidate.text !== 'string') return null;
  return { text: candidate.text, tone: (candidate.tone as CockpitTagTone) ?? 'muted' };
};

const asText = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '—';
  return String(value);
};

/** 一次算清渲染信息，模板不再重复求值（与 DashTable 同一做法） */
const renders = computed(() =>
  props.rows.map((row, index) =>
    props.columns.map((column) => {
      const raw = row[column.key];
      const tag = asTag(raw);
      return {
        key: `${keyOf(row, index)}-${column.key}`,
        isTag: Boolean(tag),
        tone: tag?.tone ?? 'muted',
        text: tag ? tag.text : asText(raw),
        rawText: asText(raw),
      };
    }),
  ),
);
</script>

<template>
  <p v-if="!rows.length" class="pf-empty">暂无数据</p>
  <div v-else class="pf-table-wrap">
    <table class="pf-table">
      <thead>
        <tr>
          <th
            v-for="column in columns"
            :key="column.key"
            :style="{ textAlign: column.align ?? 'left', width: column.width ? `calc(${column.width} * var(--u))` : undefined }"
          >
            {{ column.label }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(cells, rowIndex) in renders" :key="rowIndex">
          <td
            v-for="(cell, cellIndex) in cells"
            :key="cell.key"
            :class="{ 'is-num': columns[cellIndex].numeric, 'is-name': cellIndex === 0 }"
            :style="{ textAlign: columns[cellIndex].align ?? 'left' }"
          >
            <span v-if="cell.isTag" class="pf-tag" :class="`pf-tag--${cell.tone}`">{{ cell.text }}</span>
            <span
              v-else-if="columns[cellIndex].ellipsis"
              class="pf-ellipsis"
              :style="{ '--pf-ellipsis': String(columns[cellIndex].ellipsisWidth ?? 150) }"
              :title="cell.rawText"
            >{{ cell.text }}</span>
            <template v-else>{{ cell.text }}</template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
