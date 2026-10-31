<script setup lang="ts">
/**
 * CockpitStack，分段构成条 + 图例（对应管理员首页「事件状态」的 .event-track + .event-status）。
 * 用途：处置状态构成（待处置 / 处理中 / 已处置）这类「几段加起来等于整体」的口径。
 * 分段宽度按合计归一；合计为 0 时整条为空轨道，图例仍如实给出各段 0。
 */
import { computed } from 'vue';
import { fmtInt } from '@/components/dashboard/dashFormat';
import { toneColor, type Tone } from './profileTokens';

export interface CockpitStackItem {
  label: string;
  value: number;
  tone: Tone;
}

const props = withDefaults(defineProps<{ items: CockpitStackItem[] }>(), {});

const total = computed(() => props.items.reduce((sum, item) => sum + Math.max(Number(item.value) || 0, 0), 0));

const widthOf = (value: number): string => {
  if (!total.value) return '0%';
  const ratio = (Math.max(Number(value) || 0, 0) / total.value) * 100;
  return `${Math.max(ratio, ratio > 0 ? 1.5 : 0)}%`;
};
</script>

<template>
  <div class="pf-stack" :aria-label="`合计 ${fmtInt(total)}`">
    <span
      v-for="item in items"
      :key="item.label"
      :style="{ width: widthOf(item.value), background: toneColor(item.tone) }"
      :title="`${item.label}：${fmtInt(item.value)}`"
    ></span>
  </div>
  <div class="pf-stack-legend">
    <div v-for="item in items" :key="`lg-${item.label}`">
      <span><i class="pf-dot" :style="{ background: toneColor(item.tone) }"></i>{{ item.label }}</span>
      <strong>{{ fmtInt(item.value) }}</strong>
    </div>
  </div>
</template>
