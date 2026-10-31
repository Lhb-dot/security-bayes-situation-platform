<script setup lang="ts">
/**
 * ScenarioSelector - 场景筛选下拉框
 * 与推理记录（InferenceRecords）完全同源：从 scenarioStore.activeScenarios 取场景。
 * 数据加载：优先用共享 store（与推理记录一致）；若 store 为空再直接调 getScenarioList 兜底。
 * 本地 ref + 双向 watch 保证原生 <select> 一定显示选中值。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { getScenarioList } from '@/api/scenarioApi';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useUserStore } from '@/stores/userStore';
import type { ScenarioId } from '@/types/security';

const props = withDefaults(
  defineProps<{
    modelValue: ScenarioId | 'all';
    showAll?: boolean;
  }>(),
  { showAll: true }
);

const emit = defineEmits<{
  'update:modelValue': [value: ScenarioId | 'all'];
}>();

const scenarioStore = useScenarioStore();
const userStore = useUserStore();

const localScenarios = ref<{ value: ScenarioId; label: string }[]>([]);

const syncScenarios = () => {
  const storeScenarios = scenarioStore.activeScenarios.map((s) => ({ value: s.scenario_id, label: s.name }));
  if (storeScenarios.length > 0) {
    localScenarios.value = storeScenarios;
    return;
  }
  if (localScenarios.value.length === 0) {
    getScenarioList()
      .then((list) => {
        localScenarios.value = list.map((s) => ({ value: s.code as ScenarioId, label: s.name }));
      })
      .catch(() => {
        localScenarios.value = [];
      });
  }
};

const options = computed<{ value: ScenarioId | 'all'; label: string }[]>(() => {
  const list: { value: ScenarioId | 'all'; label: string }[] = [];
  if (props.showAll !== false && userStore.isSuperAdmin) {
    list.push({ value: 'all', label: '所有场景' });
  }
  if (props.showAll !== false) {
    for (const s of localScenarios.value) {
      list.push(s);
    }
  }
  return list;
});

const localValue = ref<ScenarioId | 'all'>(props.modelValue ?? 'all');
watch(
  () => props.modelValue,
  (v) => {
    localValue.value = v ?? 'all';
  }
);
watch(localValue, (v) => {
  emit('update:modelValue', v);
});

onMounted(() => {
  syncScenarios();
});
</script>

<template>
  <label class="filter-item">
    <span class="filter-item__label">场景</span>
    <!-- :key 绑定选项数量 -->
    <select v-model="localValue" class="filter-select" :key="options.length">
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </label>
</template>
