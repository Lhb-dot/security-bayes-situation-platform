<script setup lang="ts">
/**
 * ScenarioSelector - 场景筛选下拉框
 *
 * 第一项恒为"所有场景"，进入页面默认选中它并显示"所有场景"。
 * 使用本地 ref + 双向 watch 保证原生 <select> 一定显示选中值（:value 绑定在 select 上不可靠）。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { getScenarioList } from '@/services/mockApi';
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

/**
 * 场景列表：直接调 mockApi.getScenarioList() 存本地 ref（与推理记录同源：
 * 管理员=全部场景，普通用户=自选场景），不依赖共享 store 的时序/响应式。
 */
const localScenarios = ref<{ value: ScenarioId; label: string }[]>([]);

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

onMounted(async () => {
  try {
    const list = await getScenarioList();
    localScenarios.value = list.map((s) => ({ value: s.scenario_id, label: s.name }));
  } catch {
    localScenarios.value = [];
  }
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
