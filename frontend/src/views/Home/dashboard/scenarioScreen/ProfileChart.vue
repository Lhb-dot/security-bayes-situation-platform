<script setup lang="ts">
import EChartBase from '@/components/charts/EChartBase.vue';
import type { ProfileChartSpec } from './profileCharts';
import { use } from 'echarts/core';
import { MarkLineComponent } from 'echarts/components';
import { computed, onMounted, onUnmounted, ref } from 'vue';
use([MarkLineComponent]);
const props = defineProps<{ spec: ProfileChartSpec; index: string; error?: string }>();
const scale = ref(1);
const resize = () => { scale.value = Math.min(window.innerWidth / 1440, window.innerHeight / 900); };
const pixelKeys = new Set(['fontSize', 'itemHeight', 'itemWidth', 'itemGap', 'symbolSize', 'barMaxWidth']);
const option = computed(() => {
  const adapt = (value: unknown, key = '', parent = ''): unknown => {
    if (typeof value === 'number' && (pixelKeys.has(key) || (parent === 'grid' && ['top', 'bottom', 'left', 'right'].includes(key)))) return value * scale.value;
    if (Array.isArray(value)) return value.map(item => adapt(item, key, parent));
    if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([name, item]) => [name, adapt(item, name, key)]));
    return value;
  };
  return adapt(props.spec.option) as ProfileChartSpec['option'];
});
onMounted(() => { resize(); window.addEventListener('resize', resize); });
onUnmounted(() => window.removeEventListener('resize', resize));
</script>

<template>
  <section class="sp-panel sp-chart-panel" :aria-label="spec.title">
    <header class="sp-panel-heading"><span>{{ index }}</span><h3>{{ spec.title }}</h3><small>{{ spec.tag }}</small></header>
    <div class="sp-chart-area">
      <EChartBase v-if="spec.available && !error" :option="option" not-merge />
      <div v-else-if="error" class="sp-empty sp-chart-error" :title="error"><span>—</span>运行数据读取失败，请点击顶部重试</div>
      <div v-else class="sp-empty"><span>—</span>{{ spec.emptyText || '暂无可用数据' }}</div>
    </div>
    <p class="sp-chart-note">{{ spec.note }}</p>
  </section>
</template>
