<script setup lang="ts">
/**
 * ModelCenter - 模型中心
 *
 * 需求 6.7：模型生命周期状态机（TRAINING/FAILED/DRAFT/PUBLISHED/OFFLINE）
 *  - 管理员：审核发布、下线、重新发布、设置默认推荐模型
 *  - 普通用户：仅能看到已发布模型（需求 6.7.5）
 */
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  getModelVersions,
  getAlgorithms,
  publishModel,
  offlineModel,
  setDefaultModel,
  rePublishModel,
  getCurrentUser,
} from '@/services/mockApi';
import type { ModelVersionRecord, AlgorithmDefinition, ScenarioId, UserAccount, EvaluationMetrics } from '@/types/security';
import ScenarioSelector from '@/components/common/ScenarioSelector.vue';

const models = ref<ModelVersionRecord[]>([]);
const algorithms = ref<AlgorithmDefinition[]>([]);
const currentUser = ref<UserAccount | null>(null);
const loading = ref(true);
const error = ref('');
const selectedScenario = ref<ScenarioId | 'all'>('all');
const selectedDataset = ref<string>('all');

const isAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN' || currentUser.value?.role === 'SCENARIO_ADMIN');
const isSuperAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN');

const algoName = (id: string) => algorithms.value.find((a) => a.algorithm_id === id)?.display_name ?? id;

const statusLabel: Record<string, string> = {
  TRAINING: '训练中',
  FAILED: '训练失败',
  DRAFT: '待发布',
  PUBLISHED: '已发布',
  OFFLINE: '已下线',
};

const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '航母甲板',
};

/** 数据集选项（仅展示当前所选场景的数据集；未选场景时展示全部） */
const datasetOptions = computed(() => {
  const set = new Map<string, string>();
  const base =
    selectedScenario.value === 'all'
      ? models.value
      : models.value.filter((m) => m.scenario_id === selectedScenario.value);
  for (const m of base) {
    if (!set.has(m.dataset_id)) set.set(m.dataset_id, m.dataset_id);
  }
  return Array.from(set, ([id, name]) => ({ id, name }));
});

/** 切换场景时重置数据集筛选 */
watch(selectedScenario, () => {
  selectedDataset.value = 'all';
});

const filteredModels = computed(() => {
  let list = models.value;
  if (selectedScenario.value !== 'all') list = list.filter((m) => m.scenario_id === selectedScenario.value);
  if (selectedDataset.value !== 'all') list = list.filter((m) => m.dataset_id === selectedDataset.value);
  return list;
});

const loadModels = async () => {
  loading.value = true;
  error.value = '';
  try {
    models.value = await getModelVersions();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型数据加载失败';
  } finally {
    loading.value = false;
  }
};

// ===================== 管理员操作 =====================
const handlePublish = async (m: ModelVersionRecord) => {
  try {
    await publishModel(m.model_version_id);
    ElMessage.success(`模型 ${m.model_version_id} 已发布`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '发布失败');
  }
};

const handleOffline = async (m: ModelVersionRecord) => {
  try {
    await offlineModel(m.model_version_id);
    ElMessage.success(`模型 ${m.model_version_id} 已下线`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '下线失败');
  }
};

const handleRepublish = async (m: ModelVersionRecord) => {
  try {
    await rePublishModel(m.model_version_id);
    ElMessage.success(`模型 ${m.model_version_id} 已重新发布`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重新发布失败');
  }
};

const handleSetDefault = async (m: ModelVersionRecord) => {
  try {
    await setDefaultModel(m.model_version_id);
    ElMessage.success(`已将 ${m.model_version_id} 设为「${scenarioLabel[m.scenario_id]}」范围的默认推荐模型`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '设置默认模型失败');
  }
};

// ===================== 模型版本对比（需求 6.2 P1；普通用户仅可对比已发布模型） =====================
const compareIds = ref<string[]>([]);

const toggleCompare = (m: ModelVersionRecord) => {
  const idx = compareIds.value.indexOf(m.model_version_id);
  if (idx >= 0) {
    compareIds.value.splice(idx, 1);
  } else {
    if (compareIds.value.length >= 5) {
      ElMessage.warning('最多选择 5 个模型进行对比');
      return;
    }
    compareIds.value.push(m.model_version_id);
  }
};

const compareList = computed(() =>
  models.value.filter((m) => compareIds.value.includes(m.model_version_id))
);

const clearCompare = () => {
  compareIds.value = [];
};

/** 对比指标列定义 */
const metricRows: Array<{ label: string; key: keyof EvaluationMetrics }> = [
  { label: 'Accuracy', key: 'accuracy' },
  { label: 'Recall', key: 'recall' },
  { label: 'Precision', key: 'precision' },
  { label: 'Specificity', key: 'specificity' },
  { label: 'F1', key: 'f1' },
  { label: 'G-mean', key: 'g_mean' },
];

/** 判断某模型在某指标上是否为最优（高亮） */
const isBest = (m: ModelVersionRecord, key: keyof EvaluationMetrics) => {
  if (compareList.value.length < 2) return false;
  const best = Math.max(...compareList.value.map((x) => x.evaluation_metrics[key]));
  return m.evaluation_metrics[key] === best;
};

onMounted(async () => {
  currentUser.value = getCurrentUser();
  // 管理员/用户：默认固定自己场景（不显示场景下拉）
  if (currentUser.value?.role !== 'SUPER_ADMIN') {
    const bound = currentUser.value?.scenario_ids?.[0];
    if (bound) selectedScenario.value = bound;
  }
  algorithms.value = await getAlgorithms();
  await loadModels();
});
</script>

<template>
  <div class="model-center">
    <div class="model-center__header">
      <div>
        <p class="eyebrow">Model Center</p>
        <h2>模型中心</h2>
        <p class="model-center__desc">
          {{ isAdmin ? '全平台模型版本生命周期管理（发布 / 下线 / 默认推荐）' : '仅展示已发布模型及其评估指标' }}
        </p>
      </div>
    </div>

    <!-- 筛选栏：系统管理员可切换场景；管理员/用户固定自己场景（场景名在顶栏头像上方显示） -->
    <div class="model-center__toolbar">
      <div class="model-center__filters">
        <ScenarioSelector v-if="isSuperAdmin" v-model="selectedScenario" />
        <select v-model="selectedDataset" class="model-filter-select">
          <option value="all">全部数据集</option>
          <option v-for="d in datasetOptions" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
      </div>
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

    <!-- 空状态 -->
    <section v-else-if="filteredModels.length === 0" class="state-card">
      <p>当前筛选范围内暂无模型版本</p>
    </section>

    <!-- 模型版本对比（需求 6.2 P1） -->
    <div v-if="compareList.length >= 2" class="compare-panel card">
      <div class="compare-panel__head">
        <h4>模型版本对比</h4>
        <button class="compare-clear" @click="clearCompare">清空对比</button>
      </div>
      <div class="compare-table-wrap">
        <table class="compare-table">
          <thead>
            <tr>
              <th>指标</th>
              <th v-for="m in compareList" :key="m.model_version_id">{{ m.model_version_id }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>算法</td>
              <td v-for="m in compareList" :key="'algo-' + m.model_version_id">{{ algoName(m.algorithm_id) }}</td>
            </tr>
            <tr>
              <td>数据集</td>
              <td v-for="m in compareList" :key="'ds-' + m.model_version_id">{{ m.dataset_id }} v{{ m.dataset_version }}</td>
            </tr>
            <tr>
              <td>状态</td>
              <td v-for="m in compareList" :key="'st-' + m.model_version_id">{{ statusLabel[m.status] ?? m.status }}</td>
            </tr>
            <tr v-for="row in metricRows" :key="row.key">
              <td>{{ row.label }}</td>
              <td
                v-for="m in compareList"
                :key="'m-' + row.key + '-' + m.model_version_id"
                :class="{ 'compare-best': isBest(m, row.key) }"
              >
                {{ (m.evaluation_metrics[row.key] * 100).toFixed(1) }}%
              </td>
            </tr>
            <tr>
              <td>训练时间</td>
              <td v-for="m in compareList" :key="'t-' + m.model_version_id">{{ m.trained_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 模型卡片列表 -->
    <div v-else class="model-center__list">
      <div
        v-for="model in filteredModels"
        :key="model.model_version_id"
        class="model-card card"
      >
        <div class="model-card__header">
          <div class="model-card__titles">
            <h3 class="model-card__id">{{ model.model_version_id }}</h3>
            <span class="model-card__scenario-tag">{{ scenarioLabel[model.scenario_id] || model.scenario_id }}</span>
            <span
              v-if="model.is_default"
              class="model-card__default-tag"
            >默认推荐</span>
          </div>
          <div class="model-card__header-right">
            <button
              class="compare-btn"
              :class="{ 'is-on': compareIds.includes(model.model_version_id) }"
              @click="toggleCompare(model)"
            >
              对比
            </button>
            <span
              class="model-card__status"
              :class="`model-status--${model.status}`"
            >
              {{ statusLabel[model.status] || model.status }}
            </span>
          </div>
        </div>

        <div class="model-card__meta">
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">数据集</span>
            <span class="model-card__meta-value">{{ model.dataset_id }} <em class="model-card__version">v{{ model.dataset_version }}</em></span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">算法</span>
            <span class="model-card__meta-value">{{ algoName(model.algorithm_id) }}</span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">训练人</span>
            <span class="model-card__meta-value">{{ model.trained_by }} · {{ model.trained_at }}</span>
          </div>
          <div v-if="model.published_by" class="model-card__meta-item">
            <span class="model-card__meta-label">发布人</span>
            <span class="model-card__meta-value">{{ model.published_by }} · {{ model.published_at }}</span>
          </div>
        </div>

        <div class="model-card__metrics">
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.evaluation_metrics.accuracy * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Accuracy</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.evaluation_metrics.precision * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Precision</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.evaluation_metrics.recall * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Recall</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.evaluation_metrics.specificity * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">Specificity</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.evaluation_metrics.f1 * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">F1</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ (model.evaluation_metrics.g_mean * 100).toFixed(1) }}%</span>
            <span class="model-card__metric-label">G-mean</span>
          </div>
        </div>

        <!-- 训练参数 -->
        <div class="model-card__params">
          <span
            v-for="(v, k) in model.training_parameters"
            :key="k"
            class="model-card__param"
          >
            {{ k }} = {{ v }}
          </span>
        </div>

        <!-- 管理员操作区 -->
        <div v-if="isAdmin" class="model-card__footer">
          <template v-if="model.status === 'DRAFT'">
            <button class="op-btn op-btn--publish" @click="handlePublish(model)">审核发布</button>
          </template>
          <template v-else-if="model.status === 'PUBLISHED'">
            <button
              class="op-btn"
              :disabled="model.is_default"
              :title="model.is_default ? '当前已是默认推荐模型' : ''"
              @click="handleSetDefault(model)"
            >
              设为默认推荐
            </button>
            <button class="op-btn op-btn--danger" @click="handleOffline(model)">下线</button>
          </template>
          <template v-else-if="model.status === 'OFFLINE'">
            <button class="op-btn op-btn--publish" @click="handleRepublish(model)">重新发布</button>
          </template>
          <span v-if="model.status === 'FAILED'" class="model-card__failed-tip">训练失败，不可发布</span>
          <span v-if="model.status === 'TRAINING'" class="model-card__failed-tip">训练中...</span>
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
  flex-wrap: wrap;
}

.model-center__filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.model-center__scenario-tag {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid rgba(83, 229, 200, 0.3);
  background: rgba(83, 229, 200, 0.08);
  color: #53e5c8;
  font-size: 0.85rem;
  white-space: nowrap;
}

.model-filter-select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
}

.model-filter-select option {
  background: #0b1628;
  color: #e8f1ff;
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

.model-card__titles {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
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

.model-card__default-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  background: rgba(255, 209, 102, 0.16);
  color: #ffd166;
}

.model-card__status {
  font-size: 0.82rem;
  padding: 4px 12px;
  border-radius: 999px;
  font-weight: 500;
}

.model-status--TRAINING {
  background: rgba(91, 166, 255, 0.16);
  color: #9ad6ff;
}

.model-status--FAILED {
  background: rgba(255, 123, 114, 0.16);
  color: #ff8c84;
}

.model-status--DRAFT {
  background: rgba(255, 209, 102, 0.15);
  color: #ffd166;
}

.model-status--PUBLISHED {
  background: rgba(83, 229, 200, 0.15);
  color: #53e5c8;
}

.model-status--OFFLINE {
  background: rgba(220, 234, 255, 0.08);
  color: rgba(220, 234, 255, 0.55);
}

.model-card__meta {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08);
  flex-wrap: wrap;
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

.model-card__version {
  font-style: normal;
  color: rgba(154, 214, 255, 0.6);
  font-size: 0.8rem;
}

.model-card__metrics {
  display: flex;
  gap: 14px;
  margin-bottom: 14px;
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
  font-size: 1.05rem;
  font-weight: 700;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

.model-card__metric-label {
  font-size: 0.72rem;
  color: rgba(220, 234, 255, 0.5);
}

.model-card__params {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.model-card__param {
  padding: 3px 10px;
  border-radius: 6px;
  background: rgba(8, 17, 31, 0.7);
  border: 1px solid rgba(125, 201, 255, 0.12);
  color: rgba(154, 214, 255, 0.8);
  font-size: 0.78rem;
}

.model-card__footer {
  display: flex;
  gap: 10px;
  align-items: center;
}

.model-card__failed-tip {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.5);
}

.op-btn {
  padding: 7px 16px;
  border: 1px solid rgba(125, 201, 255, 0.28);
  border-radius: 8px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.2s;
}

.op-btn:hover:not(:disabled) {
  background: rgba(91, 166, 255, 0.2);
}

.op-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.op-btn--publish {
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  border: none;
  font-weight: 600;
}

.op-btn--danger {
  color: #ff7b72;
  border-color: rgba(255, 123, 114, 0.3);
}

.model-card__header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.compare-btn {
  padding: 4px 12px;
  border: 1px solid rgba(125, 201, 255, 0.28);
  border-radius: 999px;
  background: transparent;
  color: rgba(154, 214, 255, 0.7);
  font-size: 0.78rem;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.compare-btn:hover {
  background: rgba(91, 166, 255, 0.15);
}

.compare-btn.is-on {
  background: rgba(91, 166, 255, 0.2);
  color: #fff;
  border-color: rgba(91, 166, 255, 0.55);
}

/* 对比面板 */
.compare-panel {
  padding: 20px 24px;
  margin-bottom: 18px;
}

.compare-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.compare-panel__head h4 {
  margin: 0;
  font-size: 1.05rem;
  color: #d9e8ff;
}

.compare-clear {
  padding: 6px 14px;
  border: 1px solid rgba(125, 201, 255, 0.25);
  border-radius: 8px;
  background: transparent;
  color: #9ad6ff;
  font-size: 0.82rem;
  cursor: pointer;
}

.compare-clear:hover {
  background: rgba(91, 166, 255, 0.12);
}

.compare-table-wrap {
  overflow-x: auto;
}

.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.compare-table th {
  text-align: left;
  padding: 10px 12px;
  color: rgba(154, 214, 255, 0.85);
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.15);
  white-space: nowrap;
}

.compare-table td {
  padding: 10px 12px;
  color: rgba(217, 232, 255, 0.9);
  border-bottom: 1px solid rgba(125, 201, 255, 0.06);
  white-space: nowrap;
}

.compare-table tbody tr td:first-child {
  color: rgba(220, 234, 255, 0.6);
}

.compare-best {
  color: #53e5c8 !important;
  font-weight: 700;
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
