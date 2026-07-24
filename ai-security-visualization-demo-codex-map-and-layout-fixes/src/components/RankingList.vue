<script setup lang="ts">
import type { RankingItem } from '../types/security';

defineProps<{
  items: RankingItem[];
  accent: 'danger' | 'safe';
}>();
</script>

<template>
  <div class="ranking-list">
    <div v-for="(item, index) in items" :key="item.name" class="ranking-list__item">
      <div class="ranking-list__label">
        <span class="ranking-list__index">{{ String(index + 1).padStart(2, '0') }}</span>
        <strong>{{ item.name }}</strong>
      </div>
      <div class="ranking-list__bar">
        <div class="ranking-list__fill" :class="accent" :style="{ width: `${item.score}%` }"></div>
      </div>
      <span class="ranking-list__score">{{ item.score }}</span>
    </div>
  </div>
</template>
