<script setup lang="ts">
withDefaults(defineProps<{
  items?: Array<Record<string, any>>;
  prefix?: string;
  percent?: boolean;
}>(), {
  items: () => [],
  prefix: '',
  percent: false,
});

const labelOf = (item: Record<string, any>) => item.value ?? item.label ?? item.component ?? '—';
const valueOf = (item: Record<string, any>) => Number(item.count ?? item.fault_rate ?? item.mean_risk_score ?? 0);
</script>

<template>
  <div class="home-bars">
    <div v-for="item in (items || []).slice(0, 12)" :key="String(labelOf(item))" class="home-bar">
      <span>{{ prefix }}{{ labelOf(item) }}</span>
      <i :style="{ width: String(Math.max(2, percent ? valueOf(item) * 100 : Math.min(100, valueOf(item)))) + '%' }"></i>
      <b>{{ percent ? (valueOf(item) * 100).toFixed(1) + '%' : (item.count ?? item.fault_rate ?? item.mean_risk_score ?? '—') }}</b>
    </div>
    <p v-if="!(items || []).length" class="home-empty">暂无数据</p>
  </div>
</template>

<style scoped>
.home-bars{display:grid;gap:10px;margin-bottom:17px}.home-bar{display:grid;grid-template-columns:minmax(110px,1fr) minmax(80px,2fr) 72px;gap:10px;align-items:center;font-size:12px}.home-bar span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.home-bar i{display:block;height:8px;background:#5ba6ff;border-radius:2px}.home-bar b{text-align:right;color:#9ad6ff;font-weight:600}.home-empty{color:rgba(220,234,255,.42);font-size:12px;padding:12px 0}@media(max-width:760px){.home-bar{grid-template-columns:minmax(90px,1fr) minmax(60px,1.5fr) 58px}}
</style>
