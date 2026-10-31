<script setup lang="ts">
/**
 * 场景数据画像驾驶舱外壳，四场景共用：页面头 + KPI 行 + 3×2 面板矩阵。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { PROFILE_ICONS, type ProfileIconKey } from './profileTokens';

export interface CockpitMetaChip {
  label: string;
  value: string;
  icon?: ProfileIconKey;
}

const props = withDefaults(
  defineProps<{
    title: string;
    eyebrow: string;
    // 顶部口径 chips（数据集数 / 样本量 / 风险占比…）
    meta?: CockpitMetaChip[];
    statusText?: string;
    loading?: boolean;
    error?: string;
    empty?: boolean;
    emptyText?: string;
  }>(),
  { meta: () => [], statusText: '', loading: false, error: '', empty: false, emptyText: '该场景暂未配置数据画像' },
);

const emit = defineEmits<{ retry: [] }>();

const rootRef = ref<HTMLElement | null>(null);
const wide = ref(true);
const unit = ref(1);
const height = ref(697);

// 设计基准：1440×900 视口下本组件的可用内容盒（见文件头说明）
const DESIGN_WIDTH = 1352;
const DESIGN_HEIGHT = 697;

const measure = () => {
  const root = rootRef.value;
  if (!root) return;
  wide.value = window.matchMedia('(min-width: 1024px)').matches;
  if (!wide.value) return;
  const rect = root.getBoundingClientRect();
  const available = window.innerHeight - rect.top - 50;
  const nextUnit = Math.min(rect.width / DESIGN_WIDTH, available / DESIGN_HEIGHT);
  unit.value = Number.isFinite(nextUnit) && nextUnit > 0 ? Math.round(nextUnit * 1000) / 1000 : 1;
  height.value = Math.max(Math.round(available), 320);
};

const rootStyle = computed(() =>
  wide.value ? { '--u': `${unit.value}px`, height: `${height.value}px` } : undefined,
);

let resizeFrame = 0;
const onResize = () => {
  if (resizeFrame) cancelAnimationFrame(resizeFrame);
  resizeFrame = requestAnimationFrame(measure);
};

onMounted(() => {
  measure();
  window.addEventListener('resize', onResize);
});

onBeforeUnmount(() => {
  if (resizeFrame) cancelAnimationFrame(resizeFrame);
  window.removeEventListener('resize', onResize);
});

const badgeText = computed(() => {
  if (props.loading) return '读取数据';
  if (props.error) return props.empty ? '连接失败' : '更新失败';
  return '实时数据';
});
const badgeClass = computed(() => ({
  'pf-badge--error': Boolean(props.error),
  'pf-badge--loading': props.loading,
}));
</script>

<template>
  <div ref="rootRef" class="pf-cockpit" :style="rootStyle">
    <header class="pf-head">
      <div>
        <p class="pf-eyebrow">{{ eyebrow }}</p>
        <h2 :title="title">{{ title }}</h2>
      </div>
      <div class="pf-head-meta">
        <span v-for="item in meta" :key="item.label" class="pf-chip">
          <svg v-if="item.icon" viewBox="0 0 24 24" aria-hidden="true"><path :d="PROFILE_ICONS[item.icon]" /></svg>
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </span>
        <span class="pf-badge" :class="badgeClass" :title="statusText || undefined">{{ badgeText }}</span>
      </div>
    </header>

    <div class="pf-body">
      <div v-if="loading" class="pf-state" role="status" aria-live="polite">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="PROFILE_ICONS.data" /></svg>
        <strong>正在读取场景画像…</strong>
        <p>正在汇总数据集、模型版本与运行情况</p>
      </div>

      <div v-else-if="error" class="pf-state pf-state--error" role="status" aria-live="polite">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="PROFILE_ICONS.alert" /></svg>
        <strong>场景画像读取失败</strong>
        <p>{{ error }}</p>
        <button type="button" @click="emit('retry')">重试</button>
      </div>

      <div v-else-if="empty" class="pf-state" role="status">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="PROFILE_ICONS.matrix" /></svg>
        <strong>{{ emptyText }}</strong>
      </div>

      <slot v-else />
    </div>
  </div>
</template>

<style src="./profileCockpit.css"></style>
