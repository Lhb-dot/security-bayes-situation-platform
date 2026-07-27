<script setup lang="ts">
/**
 * AlertsView - 告警列表页（带场景/风险等级/状态筛选）
 *
 * 支持前端过滤筛选，AI风险研判跳转
 */
import { computed, ref } from 'vue';
import type { AlertRecord, ScenarioId } from '../types/security';
import { useRouter } from 'vue-router';

// 初始化路由实例
const router = useRouter();

const props = defineProps<{
  alerts: AlertRecord[];
}>();

defineEmits<{
  openAlert: [id: string];
}>();

/** 筛选条件 */
const selectedScenario = ref<ScenarioId | 'all'>('all');
const selectedRiskLevel = ref<string>('all');
const selectedStatus = ref<string>('all');

/** 场景/等级/状态扩展类型（mock数据含scenario_id额外字段） */
interface AlertFilter extends AlertRecord {
  scenario_id?: ScenarioId;
}

/** 筛选后的告警列表 */
const filteredAlerts = computed(() => {
  let result = props.alerts as AlertFilter[];
  if (selectedScenario.value !== 'all') {
    result = result.filter((a) => a.scenario_id === selectedScenario.value);
  }
  if (selectedRiskLevel.value !== 'all') {
    result = result.filter((a) => a.riskLevel === selectedRiskLevel.value);
  }
  if (selectedStatus.value !== 'all') {
    result = result.filter((a) => a.status === selectedStatus.value);
  }
  return result;
});

/** 风险等级选项 */
const riskLevelOptions = [
  { value: 'all', label: '全部等级' },
  { value: 'CRITICAL', label: '严重' },
  { value: 'HIGH', label: '高危' },
  { value: 'MEDIUM', label: '中危' },
];

/** 状态选项 */
const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: '待研判', label: '待研判' },
  { value: '处理中', label: '处理中' },
  { value: '已隔离', label: '已隔离' },
];

/** 场景选项 */
const scenarioOptions: { value: ScenarioId | 'all'; label: string }[] = [
  { value: 'all', label: '全部场景' },
  { value: 'network_security', label: '网络安全' },
  { value: 'power_system', label: '电力系统' },
  { value: 'flightdeck_operation', label: '航母甲板' },
];

/**
 * 告警列表页AI风险研判跳转
 * 通过Vue Router编程式导航携带本条告警三个归一化流量特征，目标页面自动回填推理
 * @param alertItem 当前点击单条告警对象
 */
const jumpBayesAnalyze = (alertItem: AlertRecord) => {
  router.push({
    path: '/risk',
    query: {
      fl: alertItem.flowLength,
      du: alertItem.duration,
      af: alertItem.accessFreq
    }
  });
};
</script>

<template>
  <section class="card alerts-page">
    <div class="section-heading">
      <div>
        <p class="eyebrow">Alert Center</p>
        <h2>告警详情页</h2>
      </div>
      <span class="section-tag">{{ filteredAlerts.length }} 条告警</span>
    </div>

    <!-- 筛选栏 -->
    <div class="alerts-filters">
      <div class="alerts-filters__group">
        <label class="alerts-filters__label">场景</label>
        <div class="alerts-filters__tabs">
          <button
            v-for="opt in scenarioOptions"
            :key="opt.value"
            class="alerts-filters__tab"
            :class="{ 'is-active': selectedScenario === opt.value }"
            @click="selectedScenario = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <div class="alerts-filters__group">
        <label class="alerts-filters__label">风险等级</label>
        <div class="alerts-filters__tabs">
          <button
            v-for="opt in riskLevelOptions"
            :key="opt.value"
            class="alerts-filters__tab"
            :class="{ 'is-active': selectedRiskLevel === opt.value }"
            @click="selectedRiskLevel = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <div class="alerts-filters__group">
        <label class="alerts-filters__label">状态</label>
        <div class="alerts-filters__tabs">
          <button
            v-for="opt in statusOptions"
            :key="opt.value"
            class="alerts-filters__tab"
            :class="{ 'is-active': selectedStatus === opt.value }"
            @click="selectedStatus = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <div class="alerts-table">
      <div class="alerts-table__head">
        <span>告警标题</span>
        <span>攻击类型</span>
        <span>攻击源 IP</span>
        <span>受攻击主机</span>
        <span>风险等级</span>
        <span>时间</span>
        <span>AI操作</span>
      </div>
      <div v-for="alert in filteredAlerts" :key="alert.id" class="alerts-table__row" @click="$emit('openAlert', alert.id)">
        <span>{{ alert.title }}</span>
        <span>{{ alert.attackType }}</span>
        <span>{{ alert.sourceIp }}</span>
        <span>{{ alert.targetHost }}</span>
        <span
          ><i :class="['risk-badge', `risk-${alert.riskLevel.toLowerCase()}`]">{{ alert.riskLevel }}</i></span
        >
        <span>{{ alert.timestamp }}</span>
        <button class="ai-btn" @click.stop="jumpBayesAnalyze(alert)">AI风险研判</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ai-btn {
  background: #407acc;
  color: #fff;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
}

/* 筛选栏 */
.alerts-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08);
  margin-bottom: 16px;
}

.alerts-filters__group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.alerts-filters__label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
  white-space: nowrap;
}

.alerts-filters__tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.5);
  border: 1px solid rgba(125, 201, 255, 0.12);
}

.alerts-filters__tab {
  border: 0;
  padding: 5px 12px;
  border-radius: 999px;
  color: rgba(220, 234, 255, 0.7);
  background: transparent;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.alerts-filters__tab:hover {
  background: rgba(91, 166, 255, 0.1);
  color: #fff;
}

.alerts-filters__tab.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}
</style>
