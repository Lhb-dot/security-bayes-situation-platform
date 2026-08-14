<script setup lang="ts">
/**
 * ScenarioSelector - 场景筛选器组件
 *
 * 支持筛选全部场景或当前用户可见场景（Task 016：场景选项从 scenarioStore.activeScenarios 注入）
 * 使用 v-model 绑定选中值
 */
import { computed, onMounted } from 'vue';
import { useScenarioStore } from '@/stores/scenarioStore';
import type { ScenarioId } from '@/types/security';

defineProps<{
  /** 当前选中的场景 ID（'all' 表示全部场景） */
  modelValue: ScenarioId | 'all';
  /** 是否显示"全部场景"选项，默认 true */
  showAll?: boolean;
}>();

defineEmits<{
  /** 选中值变更 */
  'update:modelValue': [value: ScenarioId | 'all'];
}>();

const scenarioStore = useScenarioStore();

/** 场景选项列表（"全部场景" + 当前用户可见场景，Task 006 已按绑定过滤） */
const options = computed<{ value: ScenarioId | 'all'; label: string }[]>(() => [
  { value: 'all', label: '全部场景' },
  ...scenarioStore.activeScenarios.map((s) => ({ value: s.scenario_id, label: s.name })),
]);

onMounted(() => {
  scenarioStore.fetchScenarioList();
});
</script>

<template>
  <div class="scenario-selector">
    <!-- 使用现有 nav-tabs 风格 -->
    <div class="scenario-selector__tabs" role="tablist">
      <button
        v-for="opt in options"
        :key="opt.value"
        v-show="showAll || opt.value !== 'all'"
        class="scenario-selector__tab"
        :class="{ 'is-active': modelValue === opt.value }"
        role="tab"
        :aria-selected="modelValue === opt.value"
        @click="$emit('update:modelValue', opt.value)"
      >
        {{ opt.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.scenario-selector {
  display: flex;
  align-items: center;
}

.scenario-selector__tabs {
  display: inline-flex;
  padding: 4px;
  border: 1px solid rgba(125, 201, 255, 0.18);
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.7);
  backdrop-filter: blur(18px);
  gap: 2px;
}

.scenario-selector__tab {
  border: 0;
  padding: 8px 18px;
  border-radius: 999px;
  color: #d9e8ff;
  background: transparent;
  font-size: 0.88rem;
  transition: background 0.25s ease, color 0.25s ease;
  cursor: pointer;
  white-space: nowrap;
}

.scenario-selector__tab:hover {
  background: rgba(91, 166, 255, 0.12);
  color: #fff;
}

.scenario-selector__tab.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}
</style>
