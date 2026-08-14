<script setup lang="ts">
/**
 * ScenarioSelector - 场景筛选下拉框
 *
 * 第一项恒为"所有场景"，进入页面默认选中它并显示"所有场景"。
 * 使用本地 ref + 双向 watch 保证原生 <select> 一定显示选中值（:value 绑定在 select 上不可靠）。
 */
import { computed, onMounted, ref, watch } from 'vue';
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

/** 选项列表："所有场景"恒为第一项 + 用户可见场景 */
const options = computed<{ value: ScenarioId | 'all'; label: string }[]>(() => {
  const list: { value: ScenarioId | 'all'; label: string }[] = [{ value: 'all', label: '所有场景' }];
  if (props.showAll !== false) {
    for (const s of scenarioStore.activeScenarios) {
      list.push({ value: s.scenario_id, label: s.name });
    }
  }
  return list;
});

/** 本地选中值：默认"所有场景"，与 props 双向同步（保证下拉框加载即显示"所有场景"） */
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
  scenarioStore.fetchScenarioList();
});
</script>

<template>
  <!-- 与推理记录筛选框一致的样式（filter-item/filter-select 全局类） -->
  <label class="filter-item">
    <span class="filter-item__label">场景</span>
    <select v-model="localValue" class="filter-select">
      <option v-for="opt in options" :key="opt.value" :value="opt.value">
        {{ opt.label }}
      </option>
    </select>
  </label>
</template>
