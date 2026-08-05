<script setup lang="ts">
/**
 * ScenarioCard - 场景卡片组件
 *
 * 展示场景名称、描述、风险等级、数据集/模型/高危事件数量
 * 点击后跳转至对应场景大屏
 */
import type { Scenario } from '@/types/security';
import RiskLevelTag from './RiskLevelTag.vue';

const props = defineProps<{
  /** 场景对象 */
  scenario: Scenario;
}>();

defineEmits<{
  /** 点击卡片进入场景大屏 */
  click: [scenarioId: string];
}>();

/** 场景中文名映射（当 name 字段未提供时回退使用） */
const scenarioNameMap: Record<string, string> = {
  network_security: '网络安全态势感知',
  power_system: '电力系统风险态势感知',
  flightdeck_operation: '航母甲板保障作业态势感知',
};

/** 数据集类型图标 */
const datasetIcon = '📊';
const modelIcon = '🧠';
const eventIcon = '⚡';
</script>

<template>
  <div
    class="scenario-card card"
    :class="{ 'scenario-card--inactive': scenario.status === 'inactive' }"
    @click="$emit('click', scenario.scenario_id)"
  >
    <!-- 场景头部 -->
    <div class="scenario-card__header">
      <div class="scenario-card__title-row">
        <h3 class="scenario-card__name">
          {{ scenario.name || scenarioNameMap[scenario.scenario_id] || scenario.scenario_id }}
        </h3>
        <RiskLevelTag :level="scenario.risk_level" />
      </div>
      <p class="scenario-card__desc">{{ scenario.description }}</p>
    </div>

    <!-- 数据统计行 -->
    <div class="scenario-card__stats">
      <div class="scenario-card__stat">
        <span class="scenario-card__stat-icon">{{ datasetIcon }}</span>
        <div>
          <span class="scenario-card__stat-value">{{ scenario.dataset_count }}</span>
          <span class="scenario-card__stat-label">数据集</span>
        </div>
      </div>
      <div class="scenario-card__divider"></div>
      <div class="scenario-card__stat">
        <span class="scenario-card__stat-icon">{{ modelIcon }}</span>
        <div>
          <span class="scenario-card__stat-value">{{ scenario.model_count }}</span>
          <span class="scenario-card__stat-label">模型</span>
        </div>
      </div>
      <div class="scenario-card__divider"></div>
      <div class="scenario-card__stat">
        <span class="scenario-card__stat-icon">{{ eventIcon }}</span>
        <div>
          <span class="scenario-card__stat-value scenario-card__stat-value--danger">{{ scenario.high_risk_count }}</span>
          <span class="scenario-card__stat-label">高危事件</span>
        </div>
      </div>
    </div>

    <!-- 底部按钮 -->
    <div class="scenario-card__footer">
      <div class="scenario-card__meta">
        <span class="scenario-card__risk-score">
          风险评分：<strong>{{ scenario.risk_score }}</strong>
        </span>
        <span class="scenario-card__status" :class="`scenario-card__status--${scenario.status}`">
          {{ scenario.status === 'active' ? '已接入' : '暂未接入' }}
        </span>
      </div>
      <button
        class="scenario-card__enter-btn"
        :class="{ 'scenario-card__enter-btn--disabled': scenario.status !== 'active' }"
        :disabled="scenario.status !== 'active'"
        :title="scenario.status !== 'active' ? '该场景暂未接入，无法进入' : ''"
        @click.stop="scenario.status === 'active' && $emit('click', scenario.scenario_id)"
      >
        {{ scenario.status === 'active' ? '进入场景' : '暂不可用' }}
        <span v-if="scenario.status === 'active'" class="scenario-card__arrow">→</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.scenario-card {
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
  display: flex;
  flex-direction: column;
}

.scenario-card:hover {
  transform: translateY(-4px);
  border-color: rgba(125, 201, 255, 0.34);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.36);
}

.scenario-card--inactive {
  opacity: 0.55;
}

/* 头部 */
.scenario-card__header {
  padding: 22px 22px 16px;
}

.scenario-card__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.scenario-card__name {
  margin: 0;
  font-size: 1.15rem;
  color: #e8f1ff;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scenario-card__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.68);
  font-size: 0.88rem;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 统计行 */
.scenario-card__stats {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 16px 22px;
  background: rgba(255, 255, 255, 0.03);
  border-top: 1px solid rgba(125, 201, 255, 0.08);
  border-bottom: 1px solid rgba(125, 201, 255, 0.08);
}

.scenario-card__stat {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: center;
}

.scenario-card__stat-icon {
  font-size: 1.25rem;
  line-height: 1;
}

.scenario-card__stat div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.scenario-card__stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: #e8f1ff;
  line-height: 1.2;
}

.scenario-card__stat-value--danger {
  color: #ff8c84;
}

.scenario-card__stat-label {
  font-size: 0.75rem;
  color: rgba(220, 234, 255, 0.56);
  line-height: 1;
}

.scenario-card__divider {
  width: 1px;
  height: 32px;
  background: rgba(125, 201, 255, 0.12);
}

/* 底部 */
.scenario-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 22px;
  gap: 12px;
}

.scenario-card__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.scenario-card__risk-score {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}

.scenario-card__risk-score strong {
  color: #e8f1ff;
}

.scenario-card__status {
  font-size: 0.78rem;
  padding: 2px 8px;
  border-radius: 999px;
  display: inline-block;
  width: fit-content;
}

.scenario-card__status--active {
  color: #53e5c8;
  background: rgba(83, 229, 200, 0.12);
}

.scenario-card__status--inactive {
  color: rgba(220, 234, 255, 0.5);
  background: rgba(255, 255, 255, 0.05);
}

/* 进入按钮 */
.scenario-card__enter-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  padding: 8px 16px;
  border-radius: 12px;
  color: #03101e;
  font-weight: 600;
  font-size: 0.88rem;
  background: linear-gradient(135deg, #53e5c8, #7dc9ff);
  box-shadow: 0 6px 16px rgba(83, 229, 200, 0.2);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  white-space: nowrap;
}

.scenario-card__enter-btn:hover {
  transform: translateX(2px);
  box-shadow: 0 8px 24px rgba(83, 229, 200, 0.35);
}

.scenario-card__enter-btn--disabled {
  background: rgba(220, 234, 255, 0.1) !important;
  color: rgba(220, 234, 255, 0.35) !important;
  box-shadow: none !important;
  cursor: not-allowed !important;
  transform: none !important;
}

.scenario-card__arrow {
  transition: transform 0.2s ease;
}

.scenario-card__enter-btn:hover .scenario-card__arrow {
  transform: translateX(3px);
}
</style>
