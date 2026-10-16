<script setup lang="ts">
/**
 * CockpitKpis —— 指标卡片组（与管理员首页 .metric-card 同一形态：左侧色条 + 大号等宽数字）。
 * size="sm" 时收成面板内的小号统计行（如运行态势的三项、去重收益的三项）。
 *
 * 数值口径：null / undefined / 空串一律渲染「—」，绝不回落成 0 —— 调用方用 null 表达的
 * 正是「拿不到数据」，渲染成 0 会被读成「一件都没有」。
 */
import { fmtInt } from '@/components/dashboard/dashFormat';
import { PROFILE_ICONS, toneColor, type ProfileIconKey, type Tone } from './profileTokens';

export interface CockpitKpi {
  label: string;
  /** 数字走千分位；字符串按原样展示（已是格式化结果，如 '12.3%'） */
  value: number | string | null;
  unit?: string;
  tone?: Tone;
  sub?: string;
  icon?: ProfileIconKey;
}

withDefaults(defineProps<{ items: CockpitKpi[]; columns?: number; size?: 'lg' | 'sm' }>(), {
  columns: 4,
  size: 'lg',
});

const valueText = (item: CockpitKpi): string => {
  if (item.value === null || item.value === undefined || item.value === '') return '—';
  return typeof item.value === 'number' ? fmtInt(item.value) : item.value;
};
</script>

<template>
  <section
    class="pf-kpis"
    :class="{ 'pf-kpis--sm': size === 'sm' }"
    :style="{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }"
  >
    <article
      v-for="item in items"
      :key="item.label"
      class="pf-kpi"
      :style="{ '--accent': toneColor(item.tone) }"
      :title="item.sub ? `${item.label}：${valueText(item)}${item.unit ?? ''}（${item.sub}）` : undefined"
    >
      <div class="pf-kpi-top">
        <span>{{ item.label }}</span>
        <svg v-if="item.icon" viewBox="0 0 24 24" aria-hidden="true"><path :d="PROFILE_ICONS[item.icon]" /></svg>
      </div>
      <div class="pf-kpi-value">
        <strong>{{ valueText(item) }}</strong>
        <span v-if="item.unit">{{ item.unit }}</span>
      </div>
      <p v-if="size === 'lg' && item.sub" class="pf-kpi-sub">{{ item.sub }}</p>
    </article>
  </section>
</template>
