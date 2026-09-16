<script setup lang="ts">
/**
 * DashFunnel —— 处置漏斗（条长按 count 比例，对应 demo 的 .funnel）。
 */
import { computed } from 'vue';
import { fmtInt } from './dashFormat';

const props = withDefaults(
  defineProps<{
    items: Array<{ label: string; count: number }>;
  }>(),
  {},
);

const peak = computed(() => Math.max(...props.items.map((item) => item.count), 0));
</script>

<template>
  <div v-if="!items.length" class="d-empty">暂无数据</div>
  <div v-else class="d-funnel">
    <div v-for="item in items" :key="item.label" class="d-fn">
      <span class="d-fn-name">{{ item.label }}</span>
      <span class="d-fn-track">
        <span
          class="d-fn-bar"
          :style="{ width: (peak ? Math.max((item.count / peak) * 100, item.count > 0 ? 3 : 0) : 0) + '%', display: 'block' }"
        ></span>
      </span>
      <span class="d-fn-count">{{ fmtInt(item.count) }}</span>
    </div>
  </div>
</template>
