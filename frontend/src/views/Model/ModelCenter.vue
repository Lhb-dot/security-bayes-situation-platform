<script setup lang="ts">
/**
 * ModelCenter - 模型中心页面
 *
 * 模型版本列表管理
 * 展示场景、算法、指标（Accuracy/Precision/Recall/F1/G-mean）、状态、时间
 */
import { onMounted, ref } from 'vue';
import type { ModelVersionRecord } from '@/services/mockApi';
import { getModelVersions } from '@/services/mockApi';
import ScenarioSelector from '@/components/common/ScenarioSelector.vue';
import type { ScenarioId } from '@/types/security';

/** 模型版本列表 */
const models = ref<ModelVersionRecord[]>([]);
const filteredModels = ref<ModelVersionRecord[]>([]);
const loading = ref(true);
const error = ref('');
const selectedScenario = ref<ScenarioId | 'all'>('all');

/** 算法中文映射 */
const algoLabel: Record<string, string> = {
  PMWNB: 'PMWNB 矩阵加权贝叶斯',
  naive_bayes: '朴素贝叶斯',
  bayesian_network: '贝叶斯网络',
};

/** 离散方式中文映射 */
const discreteLabel: Record<string, string> = {
  equal_width: '等宽离散',
  equal_freq: '等频离散',
};

/** 状态中文映射 */
const statusLabel: Record<string, string> = {
  running: '运行中',
  stopped: '已停止',
  error: '异常',
};

/** 场景中文映射 */
const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板',
};

const loadModels = async () => {
  loading.value = true;
  error.value = '';
  try {
    models.value = await getModelVersions();
    applyFilter();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型数据加载失败';
  } finally {
    loading.value = false;
  }
};

const applyFilter = () => {
  if (selectedScenario.value === 'all') {
    filteredModels.value = models.value;
  } else {
    filteredModels.value = models.value.filter((m) => m.scenario_id === selectedScenario.value);
  }
};

onMounted(() => {
  loadModels();
});
</script>

<template>
  <div class="model-center">
    <div class="model-center__header">
      <div>
        <p class="eyebrow">Model Center</p>
        <h2>模型中心</h2>
        <p class="model-center__desc">全平台模型版本统一管理，支持按场景筛选</p>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="model-center__toolbar">
      <ScenarioSelector v-model="selectedScenario" />
      <span class="model-center__count">
        共 <strong>{{ filteredModels.length }}</strong> 个模型版本
      </span>
    </div>

    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载模型数据...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadModels">重试</button>
    </section>

    <!-- 模型卡片列表 -->
    <div v-else class="model-center__list">
      <div
        v-for="model in filteredModels"
        :key="model.model_id"
        class="model-card card"
      >
        <div class="model-card__header">
          <div>
            <h3 class="model-card__id">{{ model.model_id }}</h3>
            <span class="model-card__scenario-tag">{{ scenarioLabel[model.scenario_id] || model.scenario_id }}</span>
          </div>
          <span
            class="model-card__status"
            :class="`model-status--${model.status}`"
          >
            {{ statusLabel[model.status] || model.status }}
          </span>
        </div>

        <div class="model-card__meta">
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">数据集</span>
            <span class="model-card__meta-value">{{ model.dataset_name }}</span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">算法</span>
            <span class="model-card__meta-value">{{ algoLabel[model.algo_type] || model.algo_type }}</span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">离散方式</span>
            <span class="model-card__meta-value">{{ discreteLabel[model.discrete_method] || model.discrete_method }}</span>
          </div>
        </div>

        <div class="model-card__metrics">
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.accuracy * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Accuracy</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.precision * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Precision</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.recall * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Recall</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.f1 * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">F1</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.g_mean * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">G-mean</span>
          </div>
        </div>

        <div class="model-card__footer">
          <span class="model-card__time">创建：{{ model.created_at }}</span>
          <span class="model-card__time">更新：{{ model.updated_at }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-center {
  position: relative;
  z-index: 1;
}

.model-center__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.model-center__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.model-center__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.model-center__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.model-center__count {
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.6);
  white-space: nowrap;
}

.model-center__count strong {
  color: #9ad6ff;
}

.model-center__list {
  display: grid;
  gap: 18px;
}

.model-card {
  padding: 20px 24px;
}

.model-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.model-card__header > div {
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-card__id {
  margin: 0;
  font-size: 1.05rem;
  color: #e8f1ff;
}

.model-card__scenario-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  background: rgba(91, 166, 255, 0.14);
  color: #9ad6ff;
}

.model-card__status {
  font-size: 0.82rem;
  padding: 4px 12px;
  border-radius: 999px;
  font-weight: 500;
}

.model-status--running {
  background: rgba(83, 229, 200, 0.15);
  color: #53e5c8;
}

.model-status--stopped {
  background: rgba(220, 234, 255, 0.08);
  color: rgba(220, 234, 255, 0.6);
}

.model-status--error {
  background: rgba(255, 123, 114, 0.15);
  color: #ff8c84;
}

.model-card__meta {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08);
}

.model-card__meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-card__meta-label {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
}

.model-card__meta-value {
  font-size: 0.9rem;
  color: #d9e8ff;
}

.model-card__metrics {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.model-card__metric {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px 8px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
}

.model-card__metric-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

.model-card__metric-label {
  font-size: 0.75rem;
  color: rgba(220, 234, 255, 0.5);
}

.model-card__footer {
  display: flex;
  gap: 20px;
}

.model-card__time {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.45);
}

@media (max-width: 768px) {
  .model-card__meta {
    flex-direction: column;
    gap: 8px;
  }
  .model-card__metrics {
    flex-wrap: wrap;
  }
}
</style>
