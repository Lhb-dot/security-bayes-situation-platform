<script setup lang="ts">
import { computed } from 'vue';
import type { MetricHistory } from '../types/security';
import LineTrendChart from './LineTrendChart.vue';

const props = defineProps<{
  metric: MetricHistory;
}>();

defineEmits<{
  close: [];
}>();

const headline = computed(() => {
  const last = props.metric.points[props.metric.points.length - 1]?.value ?? 0;
  return `${last}${props.metric.unit}`;
});
</script>

<template>
  <div class="overlay-modal">
    <div class="overlay-modal__backdrop" @click="$emit('close')"></div>
    <section class="card overlay-modal__panel">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Metric Drilldown</p>
          <h3>{{ metric.label }}近 30 天趋势</h3>
        </div>
        <button class="ghost-button" @click="$emit('close')">关闭</button>
      </div>

      <div class="metric-modal__summary">
        <div>
          <span>最新值</span>
          <strong>{{ headline }}</strong>
        </div>
        <p>{{ metric.insight }}</p>
      </div>

      <LineTrendChart :points="metric.points" :label-step="3" />
    </section>
  </div>
</template>
