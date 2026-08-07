<script setup lang="ts">
/**
 * RiskInference - 风险研判（普通用户模型使用闭环，需求 6.3.2 / 6.7.4 / 6.7.5）
 *
 * 选择场景 → 选择数据集 → 展示该范围已发布模型列表（含评估指标）
 * → 自动选中默认推荐模型（无默认则提示手动选择）→ 按模型绑定数据集生成固定字段输入表单
 * → 执行单条样本推理 → 风险类结果转换为统一 RiskEvent
 */
import { computed, ref, watch } from 'vue';
import type { ScenarioId, Dataset, DatasetField, ModelVersionRecord, AlgorithmDefinition } from '@/types/security';
import { getDatasetList, getModelVersions, getDatasetFields, executeInference } from '@/api/index';
import type { InferenceResult } from '@/api/index';
import { ElMessage } from 'element-plus';

/** 场景选项 */
const scenarioOptions: { value: ScenarioId; label: string }[] = [
  { value: 'network_security', label: '网络安全' },
  { value: 'power_system', label: '电力系统' },
];

const selectedScenario = ref<ScenarioId | ''>('');
const datasetList = ref<Dataset[]>([]);
const selectedDatasetId = ref<string>('');
const loadingDatasets = ref(false);

/** 当前范围的已发布模型（普通用户仅可见 PUBLISHED） */
const publishedModels = ref<ModelVersionRecord[]>([]);
const loadingModels = ref(false);
const selectedModelId = ref('');

const algorithms = ref<AlgorithmDefinition[]>([]);
const algoName = (id: string) => algorithms.value.find((a) => a.algorithm_id === id)?.display_name ?? id;

const inputFields = ref<DatasetField[]>([]);
const inputData = ref<Record<string, string | number>>({});
const inferResult = ref<InferenceResult | null>(null);
const hasInferred = ref(false);
const inferring = ref(false);

const selectedModel = computed(() => publishedModels.value.find((m) => m.model_version_id === selectedModelId.value));

// ===================== 场景切换 =====================
watch(selectedScenario, async (scenario) => {
  selectedDatasetId.value = '';
  publishedModels.value = [];
  selectedModelId.value = '';
  inputFields.value = [];
  inputData.value = {};
  inferResult.value = null;
  hasInferred.value = false;
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

// ===================== 数据集切换 → 加载已发布模型 =====================
watch(selectedDatasetId, async (datasetId) => {
  publishedModels.value = [];
  selectedModelId.value = '';
  inputFields.value = [];
  inputData.value = {};
  inferResult.value = null;
  hasInferred.value = false;
  if (!datasetId) return;
  loadingModels.value = true;
  try {
    const all = await getModelVersions(selectedScenario.value || undefined, datasetId);
    publishedModels.value = all.filter((m) => m.status === 'PUBLISHED');
    // 自动选中默认推荐模型（需求 6.7.4.3）；无默认时提示手动选择（需求 6.7.4.6）
    const def = publishedModels.value.find((m) => m.is_default);
    if (def) {
      selectedModelId.value = def.model_version_id;
    }
  } finally {
    loadingModels.value = false;
  }
});

// ===================== 模型切换 → 加载绑定数据集字段 =====================
watch(selectedModelId, async (modelId) => {
  inputFields.value = [];
  inputData.value = {};
  inferResult.value = null;
  hasInferred.value = false;
  if (!modelId) return;
  const model = publishedModels.value.find((m) => m.model_version_id === modelId);
  if (!model) return;
  try {
    const allFields = await getDatasetFields(model.dataset_id);
    inputFields.value = allFields.filter((f) => f.field_role === '输入特征');
    const init: Record<string, string | number> = {};
    for (const f of inputFields.value) {
      init[f.field_name] = f.field_type === 'string' ? '' : 0;
    }
    inputData.value = init;
  } catch {
    inputFields.value = [];
  }
});

// ===================== 执行推理 =====================
const handleInfer = async () => {
  if (!selectedModelId.value) {
    ElMessage.warning('请先选择一个已发布模型');
    return;
  }
  for (const f of inputFields.value) {
    if (f.field_type === 'string' && !inputData.value[f.field_name]) {
      ElMessage.warning(`请输入 ${f.description || f.field_name}`);
      return;
    }
  }
  inferring.value = true;
  inferResult.value = null;
  hasInferred.value = false;
  try {
    const result = await executeInference({
      model_version_id: selectedModelId.value,
      input_features: { ...inputData.value },
    });
    inferResult.value = result;
    hasInferred.value = true;
    if (result.is_risk) {
      ElMessage.success(`检测到风险，已生成风险事件 ${result.generated_event_id ?? ''}，可在「推理记录 / 告警中心」查看`);
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '推理请求失败');
  } finally {
    inferring.value = false;
  }
};
</script>

<template>
  <div class="inference-page">
    <div class="inference-page__header">
      <div>
        <p class="eyebrow">Risk Inference</p>
        <h2>风险研判</h2>
        <p class="inference-page__desc">选择已发布模型，按模型绑定数据集字段执行单条样本推理</p>
      </div>
    </div>

    <div class="inference-layout">
      <!-- 左侧：输入区域 -->
      <section class="card inference-input">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Input</p>
            <h3>推理输入</h3>
          </div>
        </div>

        <!-- 场景选择 -->
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
        </div>

        <!-- 数据集选择 -->
        <div class="form-group">
          <label class="form-label">数据集</label>
          <select v-model="selectedDatasetId" class="form-input" :disabled="!selectedScenario || loadingDatasets">
            <option value="" disabled>-- 请选择数据集 --</option>
            <option v-for="ds in datasetList" :key="ds.dataset_id" :value="ds.dataset_id">
              {{ ds.name }}（{{ ds.field_count }} 字段）
            </option>
          </select>
        </div>

        <!-- 已发布模型列表（需求 6.7.5.3） -->
        <div v-if="selectedDatasetId" class="form-group">
          <label class="form-label">已发布模型（默认选中推荐模型，可改选）</label>
          <div v-if="loadingModels" class="inference-placeholder"><p>正在加载模型...</p></div>
          <div v-else-if="publishedModels.length === 0" class="no-model-tip">
            暂无可用模型：该范围下管理员尚未发布模型，请等待管理员发布后重试
          </div>
          <div v-else class="model-options">
            <label
              v-for="m in publishedModels"
              :key="m.model_version_id"
              class="model-option"
              :class="{ 'is-selected': selectedModelId === m.model_version_id }"
            >
              <input
                v-model="selectedModelId"
                type="radio"
                :value="m.model_version_id"
                class="model-option__radio"
              />
              <div class="model-option__body">
                <div class="model-option__head">
                  <span class="model-option__id">{{ m.model_version_id }}</span>
                  <span v-if="m.is_default" class="model-option__default">默认推荐</span>
                </div>
                <div class="model-option__algo">{{ algoName(m.algorithm_id) }}</div>
                <div class="model-option__metrics">
                  <span>Acc {{ (m.evaluation_metrics.accuracy * 100).toFixed(1) }}%</span>
                  <span>Rec {{ (m.evaluation_metrics.recall * 100).toFixed(1) }}%</span>
                  <span>F1 {{ (m.evaluation_metrics.f1 * 100).toFixed(1) }}%</span>
                  <span>G-mean {{ (m.evaluation_metrics.g_mean * 100).toFixed(1) }}%</span>
                </div>
              </div>
            </label>
            <p v-if="publishedModels.length > 0 && !selectedModelId" class="no-model-tip">
              当前范围暂无默认推荐模型，请手动选择一个已发布模型
            </p>
          </div>
        </div>

        <!-- 动态输入字段 -->
        <div v-if="selectedModel && inputFields.length > 0" class="dynamic-fields">
          <div class="form-group" v-for="field in inputFields" :key="field.field_name">
            <label class="form-label">
              {{ field.field_name }}
              <span class="form-label__type">（{{ field.field_type }}）</span>
              <span class="form-label__hint">{{ field.description }}</span>
            </label>
            <input
              v-if="field.field_type === 'float'"
              v-model.number="inputData[field.field_name]"
              type="number"
              step="0.01"
              class="form-input"
              :placeholder="field.sample_value"
            />
            <input
              v-else-if="field.field_type === 'int'"
              v-model.number="inputData[field.field_name]"
              type="number"
              step="1"
              class="form-input"
              :placeholder="field.sample_value"
            />
            <select
              v-else-if="field.enum_values && field.enum_values.length > 0"
              v-model="inputData[field.field_name]"
              class="form-input"
            >
              <option value="" disabled>-- 请选择 --</option>
              <option v-for="opt in field.enum_values" :key="opt" :value="opt">{{ opt }}</option>
            </select>
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

        <div v-else-if="selectedDatasetId && publishedModels.length === 0" class="inference-placeholder">
          <p>该范围暂无已发布模型，暂不可执行推理</p>
        </div>
      </section>

      <!-- 右侧：推理结果 -->
      <section class="card inference-result">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Result</p>
            <h3>推理结果</h3>
          </div>
        </div>

        <div v-if="!hasInferred" class="inference-placeholder">
          <div class="inference-placeholder__icon">🔍</div>
          <p>选择已发布模型并输入特征后点击「执行风险推理」</p>
        </div>

        <div v-else-if="inferResult" class="inference-result__content">
          <div class="result-item result-item--level">
            <span class="result-item__label">分类结果</span>
            <span
              class="result-item__value result-level-badge"
              :class="`level--${inferResult.risk_level}`"
            >
              {{ inferResult.is_risk ? '风险类' : '正常类' }}
            </span>
          </div>
          <div class="result-item">
            <span class="result-item__label">风险等级</span>
            <span class="result-item__value">
              {{ inferResult.risk_level === 'HIGH' ? '高' : inferResult.risk_level === 'MEDIUM' ? '中' : '低' }}
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
            <span class="result-item__value">{{ inferResult.risk_type || '—' }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">推荐措施</span>
            <span class="result-item__value">{{ inferResult.recommendation }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">使用模型</span>
            <span class="result-item__value">{{ inferResult.model_used }}</span>
          </div>
          <div v-if="inferResult.is_risk" class="event-tip">
            已生成风险事件：{{ inferResult.generated_event_id }}（状态：待处置）
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.inference-page {
  position: relative;
  z-index: 1;
}

.inference-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.inference-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.inference-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.inference-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

/* 场景选择标签 */
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

/* 表单 */
.dynamic-fields {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

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
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.4);
  font-weight: normal;
  margin-left: auto;
}

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

.form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

select.form-input option {
  background: #0b1628;
  color: #e8f1ff;
}

/* 模型选项列表 */
.model-options {
  display: grid;
  gap: 10px;
}

.model-option {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.15);
  background: rgba(255, 255, 255, 0.02);
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}

.model-option:hover {
  border-color: rgba(91, 166, 255, 0.4);
}

.model-option.is-selected {
  border-color: rgba(91, 166, 255, 0.65);
  background: rgba(91, 166, 255, 0.08);
}

.model-option__radio {
  margin-top: 4px;
  accent-color: #5ba6ff;
}

.model-option__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
}

.model-option__head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.model-option__id {
  font-weight: 700;
  color: #e8f1ff;
  font-size: 0.92rem;
}

.model-option__default {
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(255, 209, 102, 0.16);
  color: #ffd166;
  font-size: 0.74rem;
}

.model-option__algo {
  font-size: 0.8rem;
  color: rgba(154, 214, 255, 0.8);
}

.model-option__metrics {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.76rem;
  color: rgba(220, 234, 255, 0.55);
}

.no-model-tip {
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(255, 209, 102, 0.08);
  border: 1px solid rgba(255, 209, 102, 0.22);
  color: rgba(255, 209, 102, 0.9);
  font-size: 0.84rem;
  line-height: 1.5;
}

.infer-btn {
  padding: 12px 24px;
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
  margin-top: 4px;
}

.infer-btn:hover {
  opacity: 0.9;
}

.infer-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

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

/* 右侧结果 */
.inference-result__content {
  display: grid;
  gap: 20px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.result-item__label {
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.65);
}

.result-item__value {
  font-size: 1rem;
  font-weight: 600;
  color: #e8f1ff;
}

.result-item__value--num {
  font-size: 1.4rem;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

.result-level-badge {
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 0.95rem;
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

.event-tip {
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(255, 123, 114, 0.08);
  border: 1px solid rgba(255, 123, 114, 0.22);
  color: #ff8a83;
  font-size: 0.85rem;
}

.inference-placeholder {
  display: grid;
  place-items: center;
  gap: 16px;
  padding: 40px 0;
  color: rgba(220, 234, 255, 0.4);
}

.inference-placeholder p {
  margin: 0;
}

.inference-placeholder__icon {
  font-size: 3rem;
}

@media (max-width: 768px) {
  .inference-layout {
    grid-template-columns: 1fr;
  }
}
</style>
