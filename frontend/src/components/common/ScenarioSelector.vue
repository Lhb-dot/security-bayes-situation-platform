<script setup lang="ts">
/**
 * ScenarioSelector - 场景筛选下拉框
 *
 * 与推理记录（InferenceRecords）完全同源：从 scenarioStore.activeScenarios 取场景。
 * 数据加载：优先用共享 store（与推理记录一致）；若 store 为空再直接调 getScenarioList 兜底。
 * 本地 ref + 双向 watch 保证原生 <select> 一定显示选中值。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { getScenarioList } from '@/services/mockApi';
import { useScenarioStore } from '@/stores/scenarioStore';
import type { ScenarioId } from '@/types/security';

const props = defineProps<{
  /** 当前选中的场景 ID（'all' 表示所有场景） */
  modelValue: ScenarioId | 'all';
  /** 是否显示"所有场景"选项，默认 true */
  showAll?: boolean;
}>();

const emit = defineEmits<{
  /** 选中值变更 */
  'update:modelValue': [value: ScenarioId | 'all'];
}>();

const scenarioStore = useScenarioStore();

/** 场景列表：优先共享 store（与推理记录同源），空时用 getScenarioList 兜底 */
const localScenarios = ref<{ value: ScenarioId; label: string }[]>([]);

const syncScenarios = () => {
  const storeScenarios = scenarioStore.activeScenarios.map((s) => ({ value: s.scenario_id, label: s.name }));
  if (storeScenarios.length > 0) {
    localScenarios.value = storeScenarios;
    return;
  }
  if (localScenarios.value.length === 0) {
    // store 未加载 → 直接拉取
    getScenarioList()
      .then((list) => {
        localScenarios.value = list.map((s) => ({ value: s.scenario_id, label: s.name }));
        console.log('[ScenarioSelector] getScenarioList →', list.length, list.map((s) => s.name));
      })
      .catch((e) => {
        console.warn('[ScenarioSelector] getScenarioList 失败:', e);
      });
  }
};

/** 选项列表："所有场景"恒为第一项 + 场景列表 */
const options = computed<{ value: ScenarioId | 'all'; label: string }[]>(() => {
  const list: { value: ScenarioId | 'all'; label: string }[] = [{ value: 'all', label: '所有场景' }];
  if (props.showAll !== false) {
    for (const s of localScenarios.value) {
      list.push(s);
    }
  }
  return list;
});

/** 本地选中值：默认"所有场景"，与 props 双向同步 */
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
    <select v-model="localValue" class="filter-select">
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </label>
</template>
