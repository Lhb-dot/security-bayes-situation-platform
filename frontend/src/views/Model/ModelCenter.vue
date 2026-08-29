<script setup lang="ts">
/**
 * ModelCenter - 模型中心
 *
 * 需求 6.7：模型生命周期状态机（TRAINING/FAILED/DRAFT/PUBLISHED/DISABLED）
 *  - 管理员：发布、禁用、删除、设置默认推荐模型
 *  - 普通用户：仅能看到已发布模型（需求 6.7.5）
 */
import { computed, onMounted, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { useUserStore } from '@/stores/userStore';
import { getAlgorithms } from '@/api/algorithmApi';
import { getDatasets, getScenarios } from '@/api/trainingApi';
import {
  deleteModelVersion,
  disableModel,
  enableModel,
  getModelVersionList,
  publishModel,
  setDefaultModel,
} from '@/api/modelVersionApi';
import type { BackendModelVersion } from '@/api/modelVersionApi';
import type { EvaluationMetrics } from '@/types/security';

const userStore = useUserStore();
const models = ref<BackendModelVersion[]>([]);
const algorithms = ref<Array<{ algorithm_id: string; display_name: string }>>([]);
const currentUser = computed(() => userStore.currentUser);
const loading = ref(true);
const error = ref('');
const selectedScenario = ref<string>('all');
const selectedDataset = ref<string>('all');
type ModelStatusFilter = 'all' | 'unpublished' | 'published' | 'disabled';
const selectedStatus = ref<ModelStatusFilter>('all');
interface ScenarioOption {
  id: number;
  code: string;
  name: string;
}
interface DatasetOption {
  id: number;
  logical_id: string;
  version: number;
  scenario_id: number;
  scenario_code: string;
}
const allScenarios = ref<ScenarioOption[]>([]);
const allDatasets = ref<DatasetOption[]>([]);

const isAdmin = computed(() => userStore.isManagement);
const isSuperAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN');

const algoName = (id: string) => algorithms.value.find((a) => a.algorithm_id === id)?.display_name ?? id;

const statusLabel: Record<string, string> = {
  TRAINING: '训练中',
  FAILED: '训练失败',
  DRAFT: '待发布',
  PUBLISHED: '已发布',
  OFFLINE: '禁用中',
  DISABLED: '禁用中',
};

const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '航母甲板',
};

/** 数据集选项只按场景归属联动，不根据当前是否存在模型来生成选项。 */
const datasetOptions = computed(() => {
  return allDatasets.value
    .filter((dataset) => selectedScenario.value === 'all' || dataset.scenario_code === selectedScenario.value)
    .map((dataset) => ({
      id: String(dataset.id),
      name: `${dataset.logical_id}（v${dataset.version}）`,
    }));
});

/** 切换场景时重置数据集筛选 */
watch(selectedScenario, () => {
  selectedDataset.value = 'all';
});

const filteredModels = computed(() => {
  let list = models.value;
  if (selectedScenario.value !== 'all') list = list.filter((m) => m.scenario_code === selectedScenario.value);
  if (selectedDataset.value !== 'all') list = list.filter((m) => String(m.dataset_id) === selectedDataset.value);
  if (isAdmin.value && selectedStatus.value === 'unpublished') {
    list = list.filter((m) => ['TRAINING', 'FAILED', 'DRAFT'].includes(m.status));
  } else if (isAdmin.value && selectedStatus.value === 'published') {
    list = list.filter((m) => m.status === 'PUBLISHED');
  } else if (isAdmin.value && selectedStatus.value === 'disabled') {
    list = list.filter((m) => m.status === 'DISABLED');
  }
  return list;
});

const scenarioOptions = computed(() => {
  return allScenarios.value;
});

const loadModels = async () => {
  loading.value = true;
  error.value = '';
  try {
    models.value = await getModelVersionList({ page: 1, page_size: 200 });
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型数据加载失败';
  } finally {
    loading.value = false;
  }
};

// ===================== 管理员操作 =====================
const handlePublish = async (m: BackendModelVersion) => {
  try {
    await publishModel(m.id);
    ElMessage.success(`模型 ${m.id} 已发布`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '发布失败');
  }
};

const handleDisable = async (m: BackendModelVersion) => {
  try {
    await disableModel(m.id);
    ElMessage.success(`模型 ${m.id} 已禁用`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '下线失败');
  }
};

const handleEnable = async (m: BackendModelVersion) => {
  try {
    await enableModel(m.id);
    ElMessage.success(`模型 ${m.id} 已重新启用`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重新启用失败');
  }
};

const handleDelete = async (m: BackendModelVersion) => {
  if (!window.confirm(`确定删除禁用中的模型 ${m.id} 吗？删除后不可恢复。`)) return;
  try {
    await deleteModelVersion(m.id);
    ElMessage.success(`模型 ${m.id} 已删除`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败');
  }
};

const handleSetDefault = async (m: BackendModelVersion) => {
  try {
    await setDefaultModel(m.id);
    ElMessage.success(`已将模型 ${m.id} 设为默认推荐模型`);
    await loadModels();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '设置默认模型失败');
  }
};

// ===================== 模型版本对比（需求 6.2 P1；普通用户仅可对比已发布模型） =====================
const compareIds = ref<number[]>([]);

const toggleCompare = (m: BackendModelVersion) => {
  const idx = compareIds.value.indexOf(m.id);
  if (idx >= 0) {
    compareIds.value.splice(idx, 1);
  } else {
    if (compareIds.value.length >= 5) {
      ElMessage.warning('最多选择 5 个模型进行对比');
      return;
    }
    compareIds.value.push(m.id);
  }
};

const compareList = computed(() =>
  models.value.filter((m) => compareIds.value.includes(m.id))
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
const isBest = (m: BackendModelVersion, key: keyof EvaluationMetrics) => {
  if (compareList.value.length < 2) return false;
  const best = Math.max(...compareList.value.map((x) => Number(x.evaluation_metrics[key]) || 0));
  return Number(m.evaluation_metrics[key]) === best;
};

const metricValue = (model: BackendModelVersion, key: keyof EvaluationMetrics) => {
  const value = Number(model.evaluation_metrics?.[key]);
  return Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : '—';
};

const canPublish = (model: BackendModelVersion) => currentUser.value?.id === model.trained_by;

onMounted(async () => {
  await userStore.bootstrap();
  if (currentUser.value?.role !== 'SUPER_ADMIN' && currentUser.value?.scenario_code) {
    selectedScenario.value = currentUser.value.scenario_code;
  }
  const rows = await getAlgorithms() as unknown as Array<{ id: number; code: string; display_name: string }>;
  algorithms.value = rows.map((a) => ({ algorithm_id: String(a.id), display_name: a.display_name || a.code }));
  const scenarioRows = await getScenarios() as Array<{ id: number; code: string; name: string; access_status: string }>;
  allScenarios.value = scenarioRows
    .filter((scenario) => scenario.access_status === 'ACTUAL')
    .map((scenario) => ({ id: scenario.id, code: scenario.code, name: scenario.name }));
  const datasetRows = await Promise.all(allScenarios.value.map((scenario) => getDatasets(scenario.id)));
  allDatasets.value = datasetRows.flatMap((rows) =>
    (rows as Array<{ id: number; logical_id: string; version: number; scenario_id: number }>).map((dataset) => ({
      ...dataset,
      scenario_code: allScenarios.value.find((scenario) => scenario.id === dataset.scenario_id)?.code || '',
    }))
  );
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
          {{ isAdmin ? '模型版本管理（发布 / 禁用 / 删除）' : '仅展示已发布模型及其评估指标' }}
        </p>
      </div>
    </div>

    <!-- 筛选栏：管理员可按模型状态查看；普通用户只显示已发布模型 -->
    <div class="model-center__toolbar">
      <div class="model-center__filters">
        <select v-if="isSuperAdmin" v-model="selectedScenario" class="model-filter-select">
          <option value="all">所有场景</option>
          <option v-for="s in scenarioOptions" :key="s.code" :value="s.code">{{ s.name }}</option>
        </select>
        <select v-model="selectedDataset" class="model-filter-select">
          <option value="all">全部数据集</option>
          <option v-for="d in datasetOptions" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
        <select v-if="isAdmin" v-model="selectedStatus" class="model-filter-select">
          <option value="all">全部状态</option>
          <option value="unpublished">未发布</option>
          <option value="published">已发布</option>
          <option value="disabled">禁用中</option>
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
              <th v-for="m in compareList" :key="m.id">{{ m.id }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>算法</td>
              <td v-for="m in compareList" :key="'algo-' + m.id">{{ algoName(String(m.algorithm_id)) }}</td>
            </tr>
            <tr>
              <td>数据集</td>
              <td v-for="m in compareList" :key="'ds-' + m.id">{{ m.dataset_logical_id || m.dataset_id }} v{{ m.dataset_version || '—' }}</td>
            </tr>
            <tr>
              <td>状态</td>
              <td v-for="m in compareList" :key="'st-' + m.id">{{ statusLabel[m.status] ?? m.status }}</td>
            </tr>
            <tr v-for="row in metricRows" :key="row.key">
              <td>{{ row.label }}</td>
              <td
                v-for="m in compareList"
                :key="'m-' + row.key + '-' + m.id"
                :class="{ 'compare-best': isBest(m, row.key) }"
              >
                {{ metricValue(m, row.key) }}
              </td>
            </tr>
            <tr>
              <td>训练时间</td>
              <td v-for="m in compareList" :key="'t-' + m.id">{{ m.trained_at }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 模型卡片列表 -->
    <div v-else class="model-center__list">
      <div
        v-for="model in filteredModels"
        :key="model.id"
        class="model-card card"
      >
        <div class="model-card__header">
          <div class="model-card__titles">
            <h3 class="model-card__id">模型 #{{ model.id }}</h3>
            <span class="model-card__scenario-tag">{{ model.scenario_name || scenarioLabel[model.scenario_code || ''] || model.scenario_code || model.scenario_id }}</span>
            <span
              v-if="model.is_default"
              class="model-card__default-tag"
            >默认推荐</span>
          </div>
          <div class="model-card__header-right">
            <button
              class="compare-btn"
              :class="{ 'is-on': compareIds.includes(model.id) }"
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
            <span class="model-card__meta-value">{{ model.dataset_logical_id || '未知数据集' }} <em class="model-card__version">v{{ model.dataset_version || '—' }}</em></span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">算法</span>
            <span class="model-card__meta-value">{{ model.algorithm_name || algoName(String(model.algorithm_id)) }}</span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">训练人</span>
            <span class="model-card__meta-value">{{ model.trained_by_name || model.trained_by }}</span>
          </div>
          <div class="model-card__meta-item">
            <span class="model-card__meta-label">训练时间</span>
            <span class="model-card__meta-value">{{ model.trained_at }}</span>
          </div>
          <div v-if="model.published_by" class="model-card__meta-item">
            <span class="model-card__meta-label">发布人</span>
            <span class="model-card__meta-value">{{ model.published_by_name || model.published_by }}</span>
          </div>
          <div v-if="model.published_at" class="model-card__meta-item">
            <span class="model-card__meta-label">发布时间</span>
            <span class="model-card__meta-value">{{ model.published_at }}</span>
          </div>
        </div>

        <div class="model-card__metrics">
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ metricValue(model, 'accuracy') }}</span>
            <span class="model-card__metric-label">Accuracy</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ metricValue(model, 'precision') }}</span>
            <span class="model-card__metric-label">Precision</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ metricValue(model, 'recall') }}</span>
            <span class="model-card__metric-label">Recall</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ metricValue(model, 'specificity') }}</span>
            <span class="model-card__metric-label">Specificity</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ metricValue(model, 'f1') }}</span>
            <span class="model-card__metric-label">F1</span>
          </div>
          <div class="model-card__metric">
            <span class="model-card__metric-value">{{ metricValue(model, 'g_mean') }}</span>
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
          <template v-if="model.status === 'DRAFT' && canPublish(model)">
            <button class="op-btn op-btn--publish" @click="handlePublish(model)">发布模型</button>
          </template>
          <template v-else-if="model.status === 'DRAFT'">
            <span class="model-card__failed-tip">仅训练人可发布</span>
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
            <button class="op-btn op-btn--danger" @click="handleDisable(model)">禁用</button>
          </template>
          <template v-else-if="model.status === 'DISABLED'">
            <button class="op-btn op-btn--publish" @click="handleEnable(model)">重新启用</button>
            <button class="op-btn op-btn--danger" @click="handleDelete(model)">删除</button>
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

.model-status--DISABLED {
  background: rgba(255, 123, 114, 0.14);
  color: #ff8c84;
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
