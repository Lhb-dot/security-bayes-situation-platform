<script setup lang="ts">
/**
 * DashCard —— 看板区块卡片：标题 + 内容插槽 + 口径来源脚注（对应 demo 的 .src）。
 */
import { SHOW_DASH_HINTS } from './dashHints';

withDefaults(
  defineProps<{
    title: string;
    /** 口径来源说明，支持多行 */
    source?: string | string[];
    wide?: boolean;
    empty?: boolean;
    emptyText?: string;
  }>(),
  { source: '', wide: false, empty: false, emptyText: '暂无数据' },
);

const sources = (value: string | string[]) => (Array.isArray(value) ? value : value ? [value] : []);
</script>

<template>
  <section class="d-card" :class="{ 'd-card--wide': wide }">
    <h3>{{ title }}</h3>
    <p v-if="empty" class="d-empty">{{ emptyText }}</p>
    <template v-else>
      <slot />
    </template>
    <template v-if="SHOW_DASH_HINTS">
      <p v-for="line in sources(source)" :key="line" class="d-src">{{ line }}</p>
    </template>
  </section>
</template>
