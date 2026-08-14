<script setup lang="ts">
/**
 * ScenariosQuickNav.vue — 业务场景概览快捷入口（需求 7.0 第三入口）
 *
 * 场景看板顶部内嵌其它已接入场景的快捷卡片，一键跳转对应场景态势页。
 */
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import type { Scenario } from '@/types/security';

const props = defineProps<{
  scenarios: Scenario[];
  currentId: string;
}>();

const router = useRouter();

const others = computed(() => props.scenarios.filter((s) => s.scenario_id !== props.currentId));

const goDashboard = (scenarioId: string) => {
  router.push({ path: `/scenarios/${scenarioId}/dashboard` });
};
</script>

<template>
  <div v-if="others.length" class="scenario-quicknav">
    <span class="scenario-quicknav__label">业务场景概览（快捷入口）</span>
    <button
      v-for="s in others"
      :key="s.scenario_id"
      class="scenario-quicknav__item"
      @click="goDashboard(s.scenario_id)"
    >
      <span class="scenario-quicknav__name">{{ s.name }}</span>
      <span class="scenario-quicknav__meta">{{ s.event_count }} 事件 · {{ s.dataset_count }} 数据集</span>
    </button>
  </div>
</template>

<style scoped>
.scenario-quicknav {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px dashed rgba(125, 201, 255, 0.22);
  background: rgba(8, 17, 31, 0.55);
}

.scenario-quicknav__label {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.5);
  white-space: nowrap;
}

.scenario-quicknav__item {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid rgba(91, 166, 255, 0.3);
  background: rgba(91, 166, 255, 0.08);
  color: #9ad6ff;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.scenario-quicknav__item:hover {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.5);
}

.scenario-quicknav__name {
  font-weight: 600;
}

.scenario-quicknav__meta {
  font-size: 0.7rem;
  color: rgba(220, 234, 255, 0.55);
}
</style>
