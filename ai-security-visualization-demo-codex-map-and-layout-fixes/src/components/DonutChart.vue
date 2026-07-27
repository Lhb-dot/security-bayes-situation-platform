<script setup lang="ts">
import { computed } from 'vue';
import type { TypeDistribution } from '../types/security';

const props = withDefaults(defineProps<{
  items: TypeDistribution[];
  title?: string;
}>(), {
  title: '攻击类型',
});

const gradient = computed(() => {
  let cursor = 0;

  return props.items
    .map((item) => {
      const start = cursor;
      cursor += item.value;
      return `${item.color} ${start}% ${cursor}%`;
    })
    .join(', ');
});
</script>

<template>
  <div class="donut-layout">
    <div class="donut-chart" :style="{ background: `conic-gradient(${gradient})` }">
      <div class="donut-chart__inner">
        <strong>{{ items.length }}</strong>
        <span>{{ title }}</span>
      </div>
    </div>
    <div class="donut-legend">
      <div v-for="item in items" :key="item.label" class="donut-legend__item">
        <span><i :style="{ backgroundColor: item.color }"></i>{{ item.label }}</span>
        <strong>{{ item.value }}%</strong>
      </div>
    </div>
  </div>
</template>
