<script setup lang="ts">
/**
 * RiskAnalysis - 模型训练与风险预测
 *
 * P0 业务闭环：选择场景 → 选择数据集 → 贝叶斯模型训练（输出 Acc/Rec/F1/G-mean）
 *              → 根据数据集固定字段生成输入项 → 执行风险推理
 * 数据来源：mockApi（trainModel / getInferenceResult）
 */
import { ref, watch } from 'vue';
import type { ScenarioId, Dataset, DatasetField } from '@/types/security';
import { getDatasetList, getDatasetFields, getInferenceResult, trainModel } from '@/services/mockApi';
import type { InferenceResult, TrainResult } from '@/services/mockApi';
import { ElMessage } from 'element-plus';

// ===================== 状态 =====================

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

/** 算法选项 */
const algoOptions = [
  { value: 'PMWNB', label: 'PMWNB（矩阵加权贝叶斯）' },
  { value: 'naive_bayes', label: '朴素贝叶斯' },
  { value: 'bayesian_network', label: '贝叶斯网络' },
];

/** 离散方式选项 */
const discreteOptions = [
  { value: 'equal_width', label: '等宽离散' },
  { value: 'equal_freq', label: '等频离散' },
];

// ----- 训练 -----
const selectedScenario = ref<ScenarioId | ''>('');
const datasetList = ref<Dataset[]>([]);
const selectedDatasetId = ref<string>('');
const algoType = ref('PMWNB');
const discreteMethod = ref('equal_width');
const training = ref(false);
const trainResult = ref<TrainResult | null>(null);
const trainCompleted = ref(false);
const loadingDatasets = ref(false);

// ----- 推理 -----
const inputFields = ref<DatasetField[]>([]);
const inputData = ref<Record<string, string | number>>({});
const inferring = ref(false);
const inferResult = ref<InferenceResult | null>(null);

// ===================== 场景切换 → 加载数据集 =====================
watch(selectedScenario, async (scenario) => {
  selectedDatasetId.value = '';
  inputFields.value = [];
  inputData.value = {};
  trainResult.value = null;
  trainCompleted.value = false;
  inferResult.value = null;
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

// ===================== 数据集切换 → 加载字段 =====================
watch(selectedDatasetId, async (datasetId) => {
  inputData.value = {};
  inputFields.value = [];
  inferResult.value = null;
  if (!datasetId) return;
  try {
    const allFields = await getDatasetFields(datasetId);
    // 只保留输入特征（排除分类标签字段）
    inputFields.value = allFields.filter((f) => f.field_role === '输入特征');
    // 初始化输入数据：数值型默认 0，字符串默认空
    const init: Record<string, string | number> = {};
    for (const f of inputFields.value) {
      init[f.field_name] = f.field_type === 'string' ? '' : 0;
    }
    inputData.value = init;
  } catch {
    inputFields.value = [];
  }
});

// ===================== 模型训练 =====================
const handleTrain = async () => {
  if (!selectedScenario.value) {
    ElMessage.warning('请先选择业务场景');
    return;
  }
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择数据集');
    return;
  }

  training.value = true;
  trainResult.value = null;
  trainCompleted.value = false;
  try {
    const result = await trainModel({
      scenario_id: selectedScenario.value,
      dataset_id: selectedDatasetId.value,
      algo_type: algoType.value,
      discrete_method: discreteMethod.value,
    });
    trainResult.value = result;
    trainCompleted.value = true;
    ElMessage.success(`训练完成！准确率：${(result.accuracy * 100).toFixed(1)}%`);
  } catch (err) {
    ElMessage.error('模型训练失败');
    console.error(err);
  } finally {
    training.value = false;
  }
};

// ===================== 风险推理 =====================
const handleInfer = async () => {
  if (!trainCompleted.value) {
    ElMessage.warning('请先完成模型训练再执行推理');
    return;
  }

  inferring.value = true;
  inferResult.value = null;
  try {
    const result = await getInferenceResult({ ...inputData.value });
    inferResult.value = result;
  } catch {
    ElMessage.error('推理请求失败');
  } finally {
    inferring.value = false;
  }
};
</script>

<template>
  <div class="risk-analysis-page">
    <!-- ==================== 页面头部 ==================== -->
    <div class="page-header">
      <div>
        <p class="eyebrow">Model Training</p>
        <h2>模型训练与风险预测</h2>
        <p class="page-header__desc">
          选择场景和数据集 → 训练贝叶斯模型 → 使用数据集固定字段完成单条风险推理
        </p>
      </div>
    </div>

    <div class="analysis-flow">
      <!-- ==================== 左侧：模型训练 ==================== -->
      <section class="card analysis-train">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Training</p>
            <h3>模型训练</h3>
          </div>
        </div>

        <!-- 业务场景 -->
        <div class="form-group">
          <label class="form-label">业务场景</label>
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
          <p v-if="selectedScenario" class="form-hint">
            当前已绑定：<strong>{{ scenarioLabel[selectedScenario] }}</strong>
          </p>
        </div>

        <!-- 数据集 -->
        <div class="form-group">
          <label class="form-label">选择数据集</label>
          <select
            v-model="selectedDatasetId"
            class="form-select"
            :disabled="!selectedScenario || loadingDatasets"
          >
            <option value="" disabled>-- 请选择数据集 --</option>
            <option
              v-for="ds in datasetList"
              :key="ds.dataset_id"
              :value="ds.dataset_id"
            >
              {{ ds.name }}（{{ ds.field_count }} 字段 · {{ (ds.record_count / 1000).toFixed(0) }}k 样本）
            </option>
          </select>
          <p v-if="!selectedScenario" class="form-hint form-hint--muted">
            请先选择场景以加载数据集
          </p>
        </div>

        <!-- 算法 + 离散方式 -->
        <div class="form-row">
          <div class="form-group">
            <label class="form-label">算法</label>
            <select v-model="algoType" class="form-select">
              <option v-for="opt in algoOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">离散方式</label>
            <select v-model="discreteMethod" class="form-select">
              <option v-for="opt in discreteOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
        </div>

        <!-- 训练按钮 -->
        <button
          class="train-btn"
          :disabled="training || !selectedDatasetId"
          @click="handleTrain"
        >
          <span v-if="training" class="btn-spinner"></span>
          {{ training ? '训练中...' : '开始训练' }}
        </button>

        <!-- 训练结果指标 -->
        <div v-if="trainResult" class="train-metrics">
          <div class="metric-card">
            <span class="metric-card__label">Accuracy</span>
            <span class="metric-card__value metric-card__value--acc">
              {{ (trainResult.accuracy * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="metric-card">
            <span class="metric-card__label">Recall</span>
            <span class="metric-card__value metric-card__value--rec">
              {{ (trainResult.recall * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="metric-card">
            <span class="metric-card__label">F1</span>
            <span class="metric-card__value metric-card__value--f1">
              {{ (trainResult.f1 * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="metric-card">
            <span class="metric-card__label">G-mean</span>
            <span class="metric-card__value metric-card__value--gm">
              {{ (trainResult.g_mean * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="metric-card metric-card--span">
            <span class="metric-card__label">训练耗时</span>
            <span class="metric-card__value metric-card__value--time">
              {{ trainResult.train_time_s }} s
            </span>
          </div>
        </div>
      </section>

      <!-- ==================== 右侧：风险推理 ==================== -->
      <section class="card analysis-infer">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Inference</p>
            <h3>风险推理</h3>
          </div>
        </div>

        <!-- 未训练 → 占位提示 -->
        <div v-if="!trainCompleted" class="infer-placeholder">
          <div class="infer-placeholder__icon">🧠</div>
          <h4>等待模型训练完成</h4>
          <p>请在左侧完成场景选择、数据集绑定和模型训练后，此处将展示对应数据集的字段输入项</p>
        </div>

        <!-- 训练完成 → 动态字段 -->
        <template v-else>
          <div v-if="inputFields.length === 0" class="infer-placeholder">
            <p>该数据集无可用的输入特征字段</p>
          </div>

          <div v-else class="dynamic-fields">
            <p class="infer-hint">
              数据集：<strong>{{ datasetList.find(d => d.dataset_id === selectedDatasetId)?.name }}</strong>
              ｜ 输入 {{ inputFields.length }} 个特征字段
            </p>

            <div v-for="field in inputFields" :key="field.field_name" class="form-group">
              <label class="form-label">
                {{ field.field_name }}
                <span class="form-label__type">（{{ field.field_type }}）</span>
                <span class="form-label__hint">{{ field.description }}</span>
              </label>
              <!-- 浮点输入 -->
              <input
                v-if="field.field_type === 'float'"
                v-model.number="inputData[field.field_name]"
                type="number"
                step="0.01"
                class="form-input"
                :placeholder="field.sample_value"
              />
              <!-- 整数输入 -->
              <input
                v-else-if="field.field_type === 'int'"
                v-model.number="inputData[field.field_name]"
                type="number"
                step="1"
                class="form-input"
                :placeholder="field.sample_value"
              />
              <!-- 字符串/枚举输入 -->
              <input
                v-else
                v-model="inputData[field.field_name]"
                type="text"
                class="form-input"
                :placeholder="field.sample_value"
              />
            </div>

            <button
              class="infer-btn"
              :disabled="inferring"
              @click="handleInfer"
            >
              <span v-if="inferring" class="btn-spinner"></span>
              {{ inferring ? '推理中...' : '执行风险推理' }}
            </button>
          </div>
        </template>

        <!-- 推理结果 -->
        <div v-if="inferResult" class="infer-result">
          <div class="result-item result-item--level">
            <span class="result-item__label">风险等级</span>
            <span
              class="result-item__value result-level-badge"
              :class="`level--${inferResult.risk_level}`"
            >
              {{ inferResult.risk_level === 'HIGH' ? '高危' : inferResult.risk_level === 'MEDIUM' ? '中危' : '低危' }}
            </span>
          </div>
          <div class="result-item">
            <span class="result-item__label">风险概率</span>
            <span class="result-item__value result-item__value--num">
              {{ (inferResult.risk_probability * 100).toFixed(1) }}%
            </span>
          </div>
          <div class="result-item">
            <span class="result-item__label">原始预测标签</span>
            <span class="result-item__value">{{ inferResult.original_label }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">风险类型</span>
            <span class="result-item__value">{{ inferResult.risk_type }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">推荐措施</span>
            <span class="result-item__value">{{ inferResult.recommendation }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">使用模型</span>
            <span class="result-item__value">{{ inferResult.model_used }}</span>
          </div>
        </div>
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

/* ===== 两列布局 ===== */
.analysis-flow {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 24px;
  align-items: start;
}

/* ===== 表单通用 ===== */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px;
}

.form-label__type {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.4);
}

.form-label__hint {
  font-size: 0.75rem;
  color: rgba(220, 234, 255, 0.35);
  font-weight: normal;
  margin-left: auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.form-hint {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
}

.form-hint strong {
  color: #9ad6ff;
}

.form-hint--muted {
  color: rgba(220, 234, 255, 0.35);
  font-style: italic;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* ===== 场景选择器 ===== */
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

/* ===== 选择框 ===== */
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

/* ===== 训练按钮 ===== */
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

/* ===== 训练结果指标 ===== */
.train-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 18px;
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

.metric-card--span {
  grid-column: 1 / -1;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.metric-card__label {
  font-size: 0.75rem;
  color: rgba(220, 234, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.metric-card__value {
  font-size: 1.4rem;
  font-weight: 700;
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.metric-card__value--time {
  font-size: 1.1rem;
  color: rgba(220, 234, 255, 0.7);
}

.metric-card__value--acc { color: #53e5c8; }
.metric-card__value--rec { color: #9ad6ff; }
.metric-card__value--f1  { color: #ffc37d; }
.metric-card__value--gm  { color: #a78bfa; }

/* ===== 推理占位 ===== */
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

/* ===== 动态字段 ===== */
.dynamic-fields {
  display: grid;
  gap: 14px;
}

.infer-hint {
  margin: 0 0 4px;
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.5);
}

.infer-hint strong {
  color: #9ad6ff;
}

/* ===== 输入框 ===== */
.form-input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.form-input::placeholder {
  color: rgba(220, 234, 255, 0.3);
}

/* ===== 推理按钮 ===== */
.infer-btn {
  padding: 12px 24px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #407acc, #2a5ca8);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  margin-top: 4px;
}

.infer-btn:hover {
  opacity: 0.9;
}

.infer-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ===== 加载动画 ===== */
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

/* ===== 推理结果 ===== */
.infer-result {
  display: grid;
  gap: 10px;
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid rgba(125, 201, 255, 0.08);
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 18px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.result-item__label {
  font-size: 0.84rem;
  color: rgba(220, 234, 255, 0.6);
}

.result-item__value {
  font-size: 0.95rem;
  font-weight: 600;
  color: #e8f1ff;
}

.result-item__value--num {
  font-size: 1.3rem;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

.result-level-badge {
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 0.9rem;
}

.level--HIGH {
  background: rgba(255, 123, 114, 0.18);
  color: #ff8c84;
}

.level--MEDIUM {
  background: rgba(91, 166, 255, 0.18);
  color: #9ad6ff;
}

.level--LOW {
  background: rgba(83, 229, 200, 0.18);
  color: #53e5c8;
}

/* ===== 响应式 ===== */
@media (max-width: 1200px) {
  .analysis-flow {
    grid-template-columns: 1fr;
  }
  .form-row {
    grid-template-columns: 1fr;
  }
}
</style>
