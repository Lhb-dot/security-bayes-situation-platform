<script setup lang="ts">
/**
 * CockpitPanel，画像驾驶舱面板（对应管理员首页的 .panel）。
 * 标题层级与总览一致：面板序号 + h3，右侧可挂一行口径提示，底部可挂口径脚注。
 * body 默认「放得下居中、放不下顶部对齐」（CSS 用 safe center），表格类内容用 top。
 */
withDefaults(
  defineProps<{
    title: string;
    index?: string;
    hint?: string;
    foot?: string;
    align?: 'center' | 'top';
  }>(),
  { index: '', hint: '', foot: '', align: 'center' },
);
</script>

<template>
  <section class="pf-panel">
    <header class="pf-panel-head">
      <span v-if="index" class="pf-panel-num">{{ index }}</span>
      <h3 :title="title">{{ title }}</h3>
      <span v-if="hint" class="pf-panel-hint">{{ hint }}</span>
    </header>
    <div class="pf-panel-body" :class="{ 'pf-panel-body--top': align === 'top' }">
      <slot />
    </div>
    <p v-if="foot" class="pf-panel-foot">{{ foot }}</p>
  </section>
</template>
