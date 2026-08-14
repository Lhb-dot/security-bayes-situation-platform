<script setup lang="ts">
/**
 * ScenarioMetricCard.vue — 场景看板指标卡（Task 009）
 *
 * 纯展示组件：暗色态势风格，scenario-* 命名，不承载业务逻辑。
 */
withDefaults(
  defineProps<{
    label: string;
    value: string | number;
    unit?: string;
    tone?: 'primary' | 'danger' | 'warning' | 'success';
    /** 告警高亮（需求 7.4：碰撞风险超阈值时 KPI 卡联动高亮） */
    alert?: boolean;
  }>(),
  {
    unit: '',
    tone: 'primary',
    alert: false,
  }
);
</script>

<template>
  <div class="scenario-metric" :class="[`scenario-metric--${tone}`, { 'scenario-metric--alert': alert }]">
    <span class="scenario-metric__value">
      {{ value }}<em v-if="unit">{{ unit }}</em>
    </span>
    <span class="scenario-metric__label">{{ label }}</span>
  </div>
</template>

<style scoped>
.scenario-metric {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 20px 22px;
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.85), rgba(8, 17, 31, 0.9));
}

.scenario-metric::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
}

.scenario-metric--primary::before { background: #5ba6ff; }
.scenario-metric--danger::before { background: #ff7b72; }
.scenario-metric--warning::before { background: #ffd166; }
.scenario-metric--success::before { background: #53e5c8; }

.scenario-metric--primary .scenario-metric__value { color: #7dc9ff; }
.scenario-metric--danger .scenario-metric__value { color: #ff8c84; }
.scenario-metric--warning .scenario-metric__value { color: #ffd166; }
.scenario-metric--success .scenario-metric__value { color: #53e5c8; }

.scenario-metric--alert {
  border-color: rgba(255, 123, 114, 0.55);
  box-shadow: 0 0 18px rgba(255, 123, 114, 0.25);
  animation: scenario-metric-pulse 1.6s ease-in-out infinite;
}

@keyframes scenario-metric-pulse {
  0%, 100% { box-shadow: 0 0 10px rgba(255, 123, 114, 0.18); }
  50% { box-shadow: 0 0 22px rgba(255, 123, 114, 0.4); }
}

.scenario-metric__value {
  font-size: 2rem;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.scenario-metric__value em {
  font-style: normal;
  font-size: 0.9rem;
  font-weight: 600;
  margin-left: 4px;
  opacity: 0.75;
}

.scenario-metric__label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}
</style>
