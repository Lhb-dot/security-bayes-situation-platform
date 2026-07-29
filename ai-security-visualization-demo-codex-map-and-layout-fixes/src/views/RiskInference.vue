<script setup lang="ts">
/**
 * RiskInference - 风险研判页面（动态输入字段版）
 *
 * 左侧：选择场景 → 选择数据集 → 根据数据集固定字段生成输入项
 * 右侧：推理结果展示
 */
import { ref, watch } from 'vue';
import type { ScenarioId, Dataset, DatasetField } from '@/types/security';
import { getDatasetList, getDatasetFields, getInferenceResult } from '@/services/mockApi';
import type { InferenceResult } from '@/services/mockApi';
import { ElMessage } from 'element-plus';

/** 场景选项 */
const scenarioOptions: { value: ScenarioId; label: string }[] = [
  { value: 'network_security', label: '网络安全' },
  { value: 'power_system', label: '电力系统' },
];

/** 当前选中的场景 */
const selectedScenario = ref<ScenarioId | ''>('');

/** 数据集列表 */
const datasetList = ref<Dataset[]>([]);

/** 当前选中的数据集ID */
const selectedDatasetId = ref<string>('');

/** 当前数据集的字段列表（不含标签字段） */
const inputFields = ref<DatasetField[]>([]);

/** 输入数据（动态 key-value） */
const inputData = ref<Record<string, string | number>>({});

const inferResult = ref<InferenceResult | null>(null);
const inferring = ref(false);
const hasInferred = ref(false);
const loadingDatasets = ref(false);

/** 场景切换 -> 加载数据集 */
watch(selectedScenario, async (scenario) => {
  selectedDatasetId.value = '';
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

/** 数据集切换 -> 加载字段 */
watch(selectedDatasetId, async (datasetId) => {
  inputData.value = {};
  inputFields.value = [];
  inferResult.value = null;
  hasInferred.value = false;
  if (!datasetId) return;
  try {
    const allFields = await getDatasetFields(datasetId);
    // 只保留输入特征（排除分类标签字段）
    inputFields.value = allFields.filter((f) => f.field_role === '输入特征');
    // 初始化输入数据：数值型给默认0，字符串给空
    const init: Record<string, string | number> = {};
    for (const f of inputFields.value) {
      if (f.field_type === 'string') {
        init[f.field_name] = '';
      } else {
        init[f.field_name] = 0;
      }
    }
    inputData.value = init;
  } catch {
    inputFields.value = [];
  }
});

/** 执行推理 */
const handleInfer = async () => {
  if (!selectedScenario.value) {
    ElMessage.warning('请先选择业务场景');
    return;
  }
  if (!selectedDatasetId.value) {
    ElMessage.warning('请先选择数据集');
    return;
  }
  // 检查必填字段
  for (const f of inputFields.value) {
    if (f.field_type === 'string' && !inputData.value[f.field_name]) {
      ElMessage.warning(`请输入${f.description || f.field_name}`);
      return;
    }
  }

  inferring.value = true;
  inferResult.value = null;
  hasInferred.value = false;
  try {
    const result = await getInferenceResult({ ...inputData.value });
    inferResult.value = result;
    hasInferred.value = true;
  } catch {
    ElMessage.error('推理请求失败');
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
        <p class="inference-page__desc">选择场景和数据集，使用对应固定字段执行实时风险推理</p>
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

        <!-- 动态输入字段 -->
        <div v-if="inputFields.length > 0" class="dynamic-fields">
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

        <!-- 无字段提示 -->
        <div v-else-if="selectedDatasetId && inputFields.length === 0" class="inference-placeholder">
          <p>该数据集无可用的输入特征字段</p>
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
          <p>选择数据集并输入特征后点击「执行风险推理」</p>
        </div>

        <div v-else-if="inferResult" class="inference-result__content">
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
  border: 2px solid rgba(255,255,255,0.3);
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

.inference-placeholder {
  display: grid;
  place-items: center;
  gap: 16px;
  padding: 60px 0;
  color: rgba(220, 234, 255, 0.4);
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
