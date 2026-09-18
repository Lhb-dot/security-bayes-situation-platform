<script setup lang="ts">
/**
 * DashRows —— 键值行列表（对应 demo 的 .row）。
 */
withDefaults(
  defineProps<{
    rows: Array<{ label: string; value: unknown }>;
  }>(),
  {},
);
</script>

<template>
  <div v-if="!rows.length" class="d-empty">暂无数据</div>
  <div v-else class="d-rows">
    <div v-for="row in rows" :key="row.label" class="d-row">
      <span>{{ row.label }}</span>
      <b>{{ row.value ?? '—' }}</b>
    </div>
  </div>
</template>
