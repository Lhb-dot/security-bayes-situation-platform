<script setup lang="ts">
/**
 * CockpitColumns，纵向柱状对比（纯 CSS，柱高按本组最大值归一）。
 * 用 flex + 百分比高度而不是 SVG：在面板里自适应宽度，不需要测量容器，
 * 也不会出现文字被横向拉伸的问题。数值标注在柱顶、类别名在柱底，均随 --u 缩放。
 */
import { computed } from 'vue';
import { fmtInt } from '@/components/dashboard/dashFormat';
import { toneColor, type Tone } from './profileTokens';

export interface CockpitColumnItem {
  label: string;
  value: number | null;
  tone?: Tone;
  caption?: string;
}

const props = withDefaults(
  defineProps<{ items: CockpitColumnItem[]; unit?: string }>(),
  { unit: '' },
);

const peak = computed(() =>
  props.items.reduce((acc, item) => Math.max(acc, Math.abs(Number(item.value ?? 0))), 0),
);

const heightOf = (value: number | null): string => {
  if (value === null || !Number.isFinite(Number(value)) || !peak.value) return '0%';
  return `${Math.max((Math.abs(Number(value)) / peak.value) * 100, value > 0 ? 3 : 0)}%`;
};

const valueText = (value: number | null): string =>
  value === null || !Number.isFinite(Number(value)) ? '—' : fmtInt(value);
</script>

<template>
  <p v-if="!items.length" class="pf-empty">暂无数据</p>
  <div v-else class="pf-columns">
    <div
      v-for="item in items"
      :key="item.label"
      class="pf-column"
      :style="{ '--accent': toneColor(item.tone) }"
      :title="`${item.label}：${valueText(item.value)}${unit}`"
    >
      <span class="pf-column-value">{{ valueText(item.value) }}</span>
      <span class="pf-column-track"><span class="pf-column-fill" :style="{ height: heightOf(item.value) }"></span></span>
      <span class="pf-column-label">{{ item.label }}</span>
      <span v-if="item.caption" class="pf-column-label">{{ item.caption }}</span>
    </div>
  </div>
</template>
