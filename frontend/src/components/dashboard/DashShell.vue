<script setup lang="ts">
/**
 * DashShell —— 首页看板外壳：加载/错误/空态 + 顶部标题区 + 内容插槽。
 * 9 个首页共用，保证视觉与交互一致。
 */
import { SHOW_DASH_HINTS } from './dashHints';

withDefaults(
  defineProps<{
    eyebrow: string;
    title: string;
    subtitle?: string;
    badge?: string;
    badgeTone?: 'success' | 'info';
    loading?: boolean;
    error?: string;
  }>(),
  { subtitle: '', badge: '', badgeTone: 'success', loading: false, error: '' },
);

const emit = defineEmits<{ retry: [] }>();
</script>

<template>
  <div class="dash-page">
    <div class="d-wrap">
      <div v-if="loading" class="d-state">正在加载首页数据…</div>

      <div v-else-if="error" class="d-state d-state--error">
        <p>{{ error }}</p>
        <button class="d-btn" @click="emit('retry')">重试</button>
      </div>

      <template v-else>
        <div class="d-top">
          <div>
            <p class="d-eyebrow">{{ eyebrow }}</p>
            <h1>{{ title }}</h1>
            <p v-if="SHOW_DASH_HINTS && subtitle">{{ subtitle }}</p>
          </div>
          <span v-if="badge" class="d-badge" :class="{ 'd-badge--info': badgeTone === 'info' }">{{ badge }}</span>
        </div>
        <slot />
      </template>
    </div>
  </div>
</template>
