<script setup lang="ts">
/**
 * RiskAnalysis - 模型训练
 *
 * 需求 6.3.1（管理员闭环）：选择场景 → 数据集版本 → 算法 → 配置训练参数 → 启动训练
 * 需求 6.6：算法代码注册（A2WNB/MAWNB/EMAWNB/DIWNB/PMWNB）+ 动态参数配置表单
 * 需求 6.7.2：训练成功生成 DRAFT 模型版本（待管理员在模型中心审核发布）
 * 需求 6.5.2：仅管理员可训练；普通用户只能使用已发布模型执行推理
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { ScenarioId, Dataset, AlgorithmDefinition, ModelVersionRecord, UserAccount } from '@/types/security';
import { getDatasetList, getAlgorithms, trainModel, getCurrentUser } from '@/api/index';
import { ElMessage } from 'element-plus';

const router = useRouter();

// ===================== 权限 =====================
const currentUser = ref<UserAccount | null>(null);
const isAdmin = computed(() => currentUser.value?.role === 'ADMIN');

/** 场景名称映射 */
const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板',
};

/** 场景选项（航母甲板第一阶段不可用于训练） */
const scenarioOptions: { value: ScenarioId; label: string }[] = [
  { value: 'network_security', label: '网络安全' },
  { value: 'power_system', label: '电力系统' },
];

// ===================== 状态 =====================
const selectedScenario = ref<ScenarioId | ''>('');
const datasetList = ref<Dataset[]>([]);
const selectedDatasetId = ref<string>('');
const selectedDatasetVersion = ref('');
const algorithms = ref<AlgorithmDefinition[]>([]);
const selectedAlgoId = ref('');
const training = ref(false);
const trainResult = ref<ModelVersionRecord | null>(null);
const loadingDatasets = ref(false);

/** 当前算法定义 */
const currentAlgo = computed(() => algorithms.value.find((a) => a.algorithm_id === selectedAlgoId.value));

/** 训练参数表单（动态生成，默认值来自算法注册定义，需求 6.6.3） */
const paramForm = ref<Record<string, number | string | boolean>>({});

const algoName = (id: string) => algorithms.value.find((a) => a.algorithm_id === id)?.display_name ?? id;

// ===================== 场景切换 → 加载数据集 =====================
watch(selectedScenario, async (scenario) => {
  selectedDatasetId.value = '';
  selectedDatasetVersion.value = '';
  trainResult.value = null;
  if (!scenario) {
    datasetList.value = [];
    return;
  }
  loadingDatasets.value = true;
  try {
    datasetList.value = await getDatasetList(scenario);
  } catch {
    datasetList.value = [];
  } finally {
    loadingDatasets.value = false;
  }
});

// ===================== 算法切换 → 重置参数表单 =====================
watch(selectedAlgoId, () => {
  trainResult.value = null;
  paramForm.value = {};
  const algo = currentAlgo.value;
  if (algo) {
    for (const p of algo.params) {
      paramForm.value[p.param_name] = p.default_value;
    }
  }
});

// ===================== 模型训练 =====================
const handleTrain = async () => {
  if (!selectedScenario.value) {
    ElMessage.warning('请先选择业务场景');
    return;
  }
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择数据集版本');
    return;
  }
  if (!selectedAlgoId.value) {
    ElMessage.warning('请选择训练算法');
    return;
  }

  training.value = true;
  trainResult.value = null;
  try {
    const result = await trainModel({
      scenario_id: selectedScenario.value,
      dataset_id: selectedDatasetId.value,
      dataset_version: selectedDatasetVersion.value,
      algorithm_id: selectedAlgoId.value,
      training_parameters: { ...paramForm.value },
    });
    trainResult.value = result;
    ElMessage.success('训练成功，已生成 DRAFT 模型版本，请在模型中心审核发布');
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '模型训练失败');
  } finally {
    training.value = false;
  }
};

const goModelCenter = () => {
  router.push('/models');
};

onMounted(async () => {
  currentUser.value = getCurrentUser();
  algorithms.value = await getAlgorithms();
  selectedAlgoId.value = algorithms.value[0]?.algorithm_id ?? '';
});
</script>

<template>
  <div class="risk-analysis-page">
    <!-- ==================== 页面头部 ==================== -->
    <div class="page-header">
      <div>
        <p class="eyebrow">Model Training</p>
        <h2>模型训练</h2>
        <p class="page-header__desc">
          选择场景、数据集版本和算法 → 配置训练参数 → 启动训练生成 DRAFT 模型
        </p>
      </div>
    </div>

    <!-- 非管理员提示 -->
    <section v-if="!isAdmin" class="card permission-tip">
      <div class="permission-tip__icon">🔒</div>
      <h3>仅管理员可进行模型训练</h3>
      <p>普通用户可在「风险研判」页面选择管理员已发布模型执行单条样本推理。</p>
      <button class="train-btn train-btn--ghost" @click="router.push('/inference')">前往风险研判</button>
    </section>

    <div v-else class="train-flow">
      <!-- ==================== 训练配置 ==================== -->
      <section class="card train-config">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Configuration</p>
            <h3>训练配置</h3>
          </div>
        </div>

        <!-- 业务场景 -->
        <div class="form-group">
          <label class="form-label">业务场景（需求 1.1.2：训练前必须先确定场景）</label>
          <div class="scenario-tabs">
            <button
              v-for="sc in scenarioOptions"
              :key="sc.value"
              class="scenario-tab"
              :class="{ 'is-active': selectedScenario === sc.value }"
              @click="selectedScenario = sc.value"
            >
              {{ sc.label }}
            </button>
          </div>
        </div>

        <!-- 数据集版本 -->
        <div class="form-group">
          <label class="form-label">数据集（版本）</label>
          <select
            v-model="selectedDatasetId"
            class="form-select"
            :disabled="!selectedScenario || loadingDatasets"
            @change="selectedDatasetVersion = datasetList.find(d => d.dataset_id === selectedDatasetId)?.dataset_version ?? ''"
          >
            <option value="" disabled>-- 请选择数据集 --</option>
            <option
              v-for="ds in datasetList"
              :key="ds.dataset_id"
              :value="ds.dataset_id"
            >
              {{ ds.name }}（v{{ ds.dataset_version }} · {{ ds.field_count }} 字段 · {{ ds.record_count }} 样本）{{ ds.enabled ? '' : '【已停用】' }}
            </option>
          </select>
          <p class="form-hint form-hint--muted">仅展示当前场景下的数据集版本；已停用版本不能用于训练</p>
        </div>

        <!-- 算法（需求 6.6.1 五种算法注册） -->
        <div class="form-group">
          <label class="form-label">算法</label>
          <select v-model="selectedAlgoId" class="form-select">
            <option
              v-for="a in algorithms"
              :key="a.algorithm_id"
              :value="a.algorithm_id"
              :disabled="!a.available"
            >
              {{ a.display_name }}（{{ a.algorithm_id }}）
            </option>
          </select>
          <p v-if="currentAlgo" class="form-hint">{{ currentAlgo.description }}｜{{ currentAlgo.input_constraints }}</p>
        </div>

        <!-- 训练参数（需求 6.6.3 动态生成配置表单） -->
        <div v-if="currentAlgo" class="form-group">
          <label class="form-label">训练参数（提供默认值，可修改，须通过类型与范围校验）</label>
          <div class="param-list">
            <div
              v-for="p in currentAlgo.params"
              :key="p.param_name"
              class="param-item"
            >
              <div class="param-item__head">
                <span class="param-item__label">{{ p.label }}（{{ p.param_name }}）</span>
                <span class="param-item__desc">{{ p.description }}</span>
              </div>
              <select
                v-if="p.type === 'select'"
                v-model="paramForm[p.param_name]"
                class="form-select"
              >
                <option v-for="o in p.options" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
              <input
                v-else-if="p.type === 'number'"
                v-model.number="paramForm[p.param_name]"
                type="number"
                class="form-input"
                :min="p.min"
                :max="p.max"
                :step="p.step ?? 'any'"
              />
              <input
                v-else
                v-model="paramForm[p.param_name]"
                type="text"
                class="form-input"
              />
              <p v-if="p.type === 'number' && (p.min !== undefined || p.max !== undefined)" class="param-item__range">
                取值范围：[{{ p.min }} ~ {{ p.max }}]
              </p>
            </div>
          </div>
        </div>

        <!-- 训练按钮 -->
        <button
          class="train-btn"
          :disabled="training || !selectedDatasetId || !selectedAlgoId"
          @click="handleTrain"
        >
          <span v-if="training" class="btn-spinner"></span>
          {{ training ? '训练中...' : '开始训练' }}
        </button>
      </section>

      <!-- ==================== 训练结果 ==================== -->
      <section class="card train-result-panel">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Training Result</p>
            <h3>训练结果</h3>
          </div>
        </div>

        <div v-if="!trainResult" class="infer-placeholder">
          <div class="infer-placeholder__icon">🧠</div>
          <h4>尚未开始训练</h4>
          <p>完成左侧配置后启动训练。训练成功的模型将进入 DRAFT 状态，可在模型中心审核发布。</p>
        </div>

        <template v-else>
          <div class="result-model-id">
            <span class="result-model-id__label">模型版本</span>
            <span class="result-model-id__value">{{ trainResult.model_version_id }}</span>
            <span class="result-model-id__status">DRAFT（待发布）</span>
          </div>

          <div class="train-metrics">
            <div class="metric-card">
              <span class="metric-card__label">Accuracy</span>
              <span class="metric-card__value metric-card__value--acc">{{ (trainResult.evaluation_metrics.accuracy * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">Recall</span>
              <span class="metric-card__value metric-card__value--rec">{{ (trainResult.evaluation_metrics.recall * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">Precision</span>
              <span class="metric-card__value metric-card__value--pre">{{ (trainResult.evaluation_metrics.precision * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">Specificity</span>
              <span class="metric-card__value metric-card__value--spe">{{ (trainResult.evaluation_metrics.specificity * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">F1</span>
              <span class="metric-card__value metric-card__value--f1">{{ (trainResult.evaluation_metrics.f1 * 100).toFixed(1) }}%</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">G-mean</span>
              <span class="metric-card__value metric-card__value--gm">{{ (trainResult.evaluation_metrics.g_mean * 100).toFixed(1) }}%</span>
            </div>
          </div>

          <div class="result-detail">
            <div class="result-detail__row">
              <span>场景</span><strong>{{ scenarioLabel[trainResult.scenario_id] }}</strong>
            </div>
            <div class="result-detail__row">
              <span>数据集</span><strong>{{ trainResult.dataset_id }} v{{ trainResult.dataset_version }}</strong>
            </div>
            <div class="result-detail__row">
              <span>算法</span><strong>{{ algoName(trainResult.algorithm_id) }}</strong>
            </div>
            <div class="result-detail__row">
              <span>训练耗时</span><strong>{{ trainResult.train_time_s }} s</strong>
            </div>
          </div>

          <button class="train-btn train-btn--ghost" @click="goModelCenter">前往模型中心发布</button>
        </template>
      </section>
    </div>
  </div>
</template>

<style scoped>
.risk-analysis-page {
  position: relative;
  z-index: 1;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  color: #c8deff;
}

.page-header__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

/* 权限提示 */
.permission-tip {
  display: grid;
  place-items: center;
  gap: 10px;
  padding: 60px 20px;
  text-align: center;
}

.permission-tip__icon {
  font-size: 2.6rem;
}

.permission-tip h3 {
  margin: 0;
  font-size: 1.15rem;
  color: #e8f1ff;
}

.permission-tip p {
  margin: 0;
  color: rgba(220, 234, 255, 0.6);
  font-size: 0.92rem;
}

/* 两列布局 */
.train-flow {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 24px;
  align-items: start;
}

/* 表单通用 */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.form-hint {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.5);
}

.form-hint--muted {
  color: rgba(220, 234, 255, 0.35);
  font-style: italic;
}

/* 场景选择器 */
.scenario-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.5);
  border: 1px solid rgba(125, 201, 255, 0.12);
  width: fit-content;
}

.scenario-tab {
  border: 0;
  padding: 6px 16px;
  border-radius: 999px;
  color: rgba(220, 234, 255, 0.7);
  background: transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.scenario-tab:hover {
  background: rgba(91, 166, 255, 0.1);
  color: #fff;
}

.scenario-tab.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}

/* 选择框 */
.form-select {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
  appearance: auto;
}

.form-select:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.form-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-select option {
  background: #0b1628;
  color: #e8f1ff;
}

/* 参数列表 */
.param-list {
  display: grid;
  gap: 14px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.param-item__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.param-item__label {
  font-size: 0.85rem;
  color: #d9e8ff;
  font-weight: 600;
}

.param-item__desc {
  font-size: 0.74rem;
  color: rgba(220, 234, 255, 0.45);
  text-align: right;
}

.param-item__range {
  margin: 0;
  font-size: 0.75rem;
  color: rgba(255, 209, 102, 0.7);
}

/* 按钮 */
.train-btn {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  margin: 6px 0;
}

.train-btn:hover {
  opacity: 0.9;
}

.train-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.train-btn--ghost {
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
  border: 1px solid rgba(125, 201, 255, 0.25);
  width: auto;
  padding: 10px 22px;
}

.train-btn--ghost:hover {
  background: rgba(91, 166, 255, 0.2);
}

/* 结果面板 */
.result-model-id {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 209, 102, 0.07);
  border: 1px solid rgba(255, 209, 102, 0.25);
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.result-model-id__label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}

.result-model-id__value {
  font-size: 1rem;
  font-weight: 700;
  color: #e8f1ff;
}

.result-model-id__status {
  margin-left: auto;
  padding: 3px 12px;
  border-radius: 999px;
  background: rgba(255, 209, 102, 0.16);
  color: #ffd166;
  font-size: 0.8rem;
}

/* 训练结果指标 */
.train-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.metric-card__label {
  font-size: 0.72rem;
  color: rgba(220, 234, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.metric-card__value {
  font-size: 1.3rem;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.metric-card__value--acc { color: #53e5c8; }
.metric-card__value--rec { color: #9ad6ff; }
.metric-card__value--pre { color: #ffc37d; }
.metric-card__value--spe { color: #a78bfa; }
.metric-card__value--f1  { color: #ff7b72; }
.metric-card__value--gm  { color: #53e5c8; }

/* 结果详情 */
.result-detail {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
}

.result-detail__row {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  font-size: 0.85rem;
}

.result-detail__row span {
  color: rgba(220, 234, 255, 0.6);
}

.result-detail__row strong {
  color: #d9e8ff;
}

/* 占位 */
.infer-placeholder {
  display: grid;
  place-items: center;
  gap: 12px;
  padding: 60px 20px;
  text-align: center;
  color: rgba(220, 234, 255, 0.4);
}

.infer-placeholder__icon {
  font-size: 3rem;
}

.infer-placeholder h4 {
  margin: 0;
  font-size: 1.1rem;
  color: rgba(220, 234, 255, 0.6);
}

.infer-placeholder p {
  margin: 0;
  max-width: 360px;
  font-size: 0.9rem;
}

/* 加载动画 */
.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 响应式 */
@media (max-width: 1200px) {
  .train-flow {
    grid-template-columns: 1fr;
  }
  .train-metrics {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
