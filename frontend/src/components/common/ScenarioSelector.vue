<script setup lang="ts">
/**
 * ScenarioSelector - 场景筛选下拉框
 *
 * 支持"全部场景"或当前用户可见场景（Task 016：场景选项从 scenarioStore.activeScenarios 注入）
 * 使用 v-model 绑定选中值；默认"全部场景"，避免筛选条件堆叠过长。
 */
import { computed, onMounted } from 'vue';
import { useScenarioStore } from '@/stores/scenarioStore';
import type { ScenarioId } from '@/types/security';

const props = defineProps<{
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

/** 根据 showAll 过滤"全部场景"选项 */
const visibleOptions = computed(() =>
  props.showAll === false ? options.value.filter((o) => o.value !== 'all') : options.value
);

onMounted(() => {
  scenarioStore.fetchScenarioList();
});
</script>

<template>
  <select
    class="scenario-selector__select"
    :value="modelValue"
    @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value as ScenarioId | 'all')"
  >
    <option v-for="opt in visibleOptions" :key="opt.value" :value="opt.value">
      {{ opt.label }}
    </option>
  </select>
</template>

<style scoped>
.scenario-selector__select {
  padding: 7px 12px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
  cursor: pointer;
  min-width: 130px;
}

.scenario-selector__select:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.scenario-selector__select option {
  background: #0b1628;
  color: #e8f1ff;
}
</style>
