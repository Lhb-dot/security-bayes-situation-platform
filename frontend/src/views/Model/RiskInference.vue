<script setup lang="ts">
/**
 * RiskInference - 风险研判（普通用户模型使用闭环，需求 6.3.2 / 6.7.4 / 6.7.5）
 *
 * 选择场景 → 选择数据集 → 展示该范围已发布模型列表（含评估指标）
 * → 自动选中默认推荐模型（无默认则提示手动选择）→ 按模型绑定数据集生成固定字段输入表单
 * （carrier 279 字段按字段族分组折叠）→ 执行单条样本推理 → 风险类结果可跳风险事件详情
 *
 * 数据链路：页面 → scenarioStore / datasetStore / modelStore / inferenceStore（不直连 mockApi）。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useDatasetStore } from '@/stores/datasetStore';
import { useModelStore } from '@/stores/modelStore';
import { useInferenceStore } from '@/stores/inferenceStore';
import { useUserStore } from '@/stores/userStore';
import type {
  AlgorithmDefinition,
  Dataset,
  DatasetField,
  ModelVersionRecord,
  ScenarioId,
} from '@/types/security';
// 过渡期：InferenceResult 类型定义于 mockApi.ts（仅 type import，页面不调用 mockApi 函数）
import type { InferenceResult } from '@/services/mockApi';

const router = useRouter();
const route = useRoute();
const scenarioStore = useScenarioStore();
const datasetStore = useDatasetStore();
const modelStore = useModelStore();
const inferenceStore = useInferenceStore();
const userStore = useUserStore();

/** 需求 6.5.2/6.2：管理员用 tabs 切场景；普通用户用下拉框在感兴趣的场景中选择 */
const isAdmin = computed(() => userStore.currentUser?.role === 'ADMIN');

/** 场景选项：普通用户=感兴趣的场景（设置页自选），管理员=全部场景 */
const scenarioOptions = computed<{ value: ScenarioId; label: string }[]>(() =>
  scenarioStore.activeScenarios.map((s) => ({ value: s.scenario_id, label: s.name }))
);

const selectedScenario = ref<ScenarioId | ''>('');
const selectedDatasetId = ref<string>('');
const loadingDatasets = ref(false);

/** 当前场景的数据集（datasetStore.fetchDatasets(scenarioId) 已按场景/用户过滤） */
const datasetOptions = computed<Dataset[]>(() =>
  selectedScenario.value
    ? datasetStore.datasets.filter((d) => d.scenario_id === selectedScenario.value)
    : []
);

/** 当前范围的已发布模型（modelStore.fetchModelVersions 已过滤） */
const publishedModels = computed<ModelVersionRecord[]>(() =>
  modelStore.modelVersions.filter((m: ModelVersionRecord) => m.status === 'PUBLISHED')
);
const loadingModels = ref(false);
const selectedModelId = ref('');

const algoName = (id: string) =>
  modelStore.algorithms.find((a: AlgorithmDefinition) => a.algorithm_id === id)?.display_name ?? id;

const inputFields = ref<DatasetField[]>([]);
const inputData = ref<Record<string, string | number>>({});
const inferResult = ref<InferenceResult | null>(null);
const hasInferred = ref(false);
const inferring = ref(false);

const selectedModel = computed(() => publishedModels.value.find((m) => m.model_version_id === selectedModelId.value));

// ===================== 场景切换 =====================
watch(selectedScenario, async (scenario) => {
  selectedDatasetId.value = '';
  selectedModelId.value = '';
  inputFields.value = [];
  inputData.value = {};
  inferResult.value = null;
  hasInferred.value = false;
  if (!scenario) {
    datasetStore.datasets = [];
    return;
  }
  loadingDatasets.value = true;
  try {
    await datasetStore.fetchDatasets(scenario);
  } catch {
    datasetStore.datasets = [];
  } finally {
    loadingDatasets.value = false;
  }
});

// ===================== 数据集切换 → 加载已发布模型 =====================
watch(selectedDatasetId, async (datasetId) => {
  selectedModelId.value = '';
  inputFields.value = [];
  inputData.value = {};
  inferResult.value = null;
  hasInferred.value = false;
  if (!datasetId) return;
  loadingModels.value = true;
  try {
    await modelStore.fetchModelVersions(selectedScenario.value || undefined, datasetId);
    // 自动选中默认推荐模型（需求 6.7.4.3）；无默认时提示手动选择（需求 6.7.4.6）
    const def = publishedModels.value.find((m) => m.is_default);
    if (def) {
      selectedModelId.value = def.model_version_id;
    } else {
      selectedModelId.value = '';
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
    await datasetStore.fetchFields(model.dataset_id, model.dataset_version);
    const allFields = datasetStore.fields;
    inputFields.value = allFields.filter((f: DatasetField) => f.field_role === '输入特征');
    inputData.value = buildInputData(inputFields.value);
    // 需求 7.1：看板点击端口 → /inference?port= 预填 L4_DST_PORT
    const port = route.query.port;
    if (port && inputData.value.L4_DST_PORT !== undefined) {
      const n = Number(port);
      if (Number.isFinite(n)) inputData.value.L4_DST_PORT = n;
    }
    // 默认仅展开第一组（carrier 279 字段不一次性挂载 279 个 DOM）
    expandedGroups.value = fieldGroups.value.length > 0 ? [fieldGroups.value[0].name] : [];
  } catch {
    inputFields.value = [];
    inputData.value = {};
  }
});

// ===================== carrier 字段族分组（需求 7.4：279 字段折叠防卡顿） =====================
const CARRIER_GROUP_RULES: Array<{ name: string; match: (name: string) => boolean }> = [
  { name: '方向角族', match: (n) => n.startsWith('Plane1_dir_') || n.startsWith('Plane2_dir_') },
  { name: '相对角度族', match: (n) => n.startsWith('relative_angle_') },
  {
    name: '间距族',
    match: (n) =>
      n.startsWith('inter_distance_') || n.startsWith('inter_dist_')
      || n === 'start_dist' || n === 'end_dist' || n === 'dist_change' || n === 'dist_change_ratio',
  },
  {
    name: '距离变化族',
    match: (n) =>
      n.startsWith('dist_change_step_')
      || n.startsWith('dist_change_mean_step') || n.startsWith('dist_change_std_step')
      || n.startsWith('dist_change_max_step') || n.startsWith('dist_change_min_step'),
  },
  {
    name: '航程族',
    match: (n) =>
      n === 'Plane1_total_distance' || n === 'Plane2_total_distance'
      || n === 'total_dist_diff' || n === 'total_dist_ratio',
  },
  { name: '标识族', match: (n) => n === 'PlaneID1' || n === 'PlaneID2' },
];

interface FieldGroup {
  name: string;
  fields: DatasetField[];
}

/** 按字段族前缀分组；未命中任何前缀归入"其它字段"，非 carrier 小字段集归为单组「全部字段」 */
const fieldGroups = computed<FieldGroup[]>(() => {
  const groups: FieldGroup[] = CARRIER_GROUP_RULES.map((r) => ({ name: r.name, fields: [] as DatasetField[] }));
  const other: DatasetField[] = [];
  for (const f of inputFields.value) {
    const idx = CARRIER_GROUP_RULES.findIndex((r) => r.match(f.field_name));
    if (idx >= 0) groups[idx].fields.push(f);
    else other.push(f);
  }
  const matched = groups.filter((g) => g.fields.length > 0);
  if (matched.length === 0) {
    return other.length > 0 ? [{ name: '全部字段', fields: other }] : [];
  }
  if (other.length > 0) matched.push({ name: '其它字段', fields: other });
  return matched;
});

/** el-collapse 展开的组名 */
const expandedGroups = ref<string[]>([]);

const expandAll = () => {
  expandedGroups.value = fieldGroups.value.map((g) => g.name);
};

const collapseAll = () => {
  expandedGroups.value = [];
};

/** 默认值填充：数值取 sample_value（解析失败回退 0）；枚举 string 取合法 sample_value，否则空（由校验提示填写） */
const buildInputData = (fields: DatasetField[]): Record<string, string | number> => {
  const init: Record<string, string | number> = {};
  for (const f of fields) {
    if (f.field_type === 'float' || f.field_type === 'int') {
      const parsed = Number(f.sample_value);
      init[f.field_name] = Number.isFinite(parsed) ? parsed : 0;
    } else if (f.enum_values && f.enum_values.length > 0) {
      init[f.field_name] = f.enum_values.includes(f.sample_value) ? f.sample_value : '';
    } else {
      init[f.field_name] = '';
    }
  }
  return init;
};

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
    const result = await inferenceStore.executeInference({
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

/** 推理结果 → 风险事件详情（Task 012 /events/:id） */
const goEventDetail = (eventId: string) => {
  router.push({ path: `/events/${eventId}` });
};

onMounted(async () => {
  await Promise.all([
    scenarioStore.fetchScenarioList(),
    modelStore.fetchAlgorithms(),
  ]);
  // 自动确定当前场景：普通用户取绑定/自选场景（首个）；管理员默认选中第一个便于直接操作（仍可通过 tabs 切换）。
  if (!selectedScenario.value && scenarioOptions.value.length) {
    selectedScenario.value = scenarioOptions.value[0].value;
  }
});
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
          <div v-if="isAdmin" class="scenario-tabs">
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
          <select
            v-else-if="scenarioOptions.length"
            v-model="selectedScenario"
            class="form-input"
          >
            <option value="" disabled>-- 请选择场景 --</option>
            <option v-for="sc in scenarioOptions" :key="sc.value" :value="sc.value">
              {{ sc.label }}
            </option>
          </select>
          <p v-else class="no-model-tip">当前账号暂无可用场景，请在"设置"中选择感兴趣的场景</p>
        </div>

        <!-- 数据集选择 -->
        <div class="form-group">
          <label class="form-label">数据集</label>
          <select v-model="selectedDatasetId" class="form-input" :disabled="!selectedScenario || loadingDatasets">
            <option value="" disabled>-- 请选择数据集 --</option>
            <option v-for="ds in datasetOptions" :key="ds.dataset_id" :value="ds.dataset_id">
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
          <div class="dynamic-fields__toolbar">
            <span class="dynamic-fields__count">共 {{ inputFields.length }} 个输入特征</span>
            <el-button size="small" plain @click="expandAll">展开全部</el-button>
            <el-button size="small" plain @click="collapseAll">收起全部</el-button>
          </div>

          <el-collapse v-model="expandedGroups" class="field-collapse">
            <el-collapse-item v-for="group in fieldGroups" :key="group.name" :name="group.name">
              <template #title>
                <span class="field-group-title">{{ group.name }}（{{ group.fields.length }} 字段）</span>
              </template>
              <!-- v-if 保证折叠组不挂载内部 input（el-collapse 默认 v-show 仍会挂载子节点） -->
              <div v-if="expandedGroups.includes(group.name)" class="field-group-body">
                <div class="form-group" v-for="field in group.fields" :key="field.field_name">
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
              </div>
            </el-collapse-item>
          </el-collapse>

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
            <el-button
              v-if="inferResult.generated_event_id"
              size="small"
              type="primary"
              plain
              class="event-tip__btn"
              @click="goEventDetail(inferResult.generated_event_id)"
            >
              查看风险事件详情
            </el-button>
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

.dynamic-fields__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.dynamic-fields__count {
  margin-right: auto;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
}

.field-collapse {
  width: 100%;
}

.field-group-title {
  font-size: 0.9rem;
  color: #dbe9ff;
}

.field-group-body {
  display: grid;
  gap: 14px;
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

.user-scenario-hint {
  margin: 0;
  padding: 10px 14px;
  border-radius: 10px;
  background: rgba(91, 166, 255, 0.08);
  border: 1px solid rgba(91, 166, 255, 0.2);
  color: #9ad6ff;
  font-size: 0.86rem;
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
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-radius: 10px;
  background: rgba(255, 123, 114, 0.08);
  border: 1px solid rgba(255, 123, 114, 0.22);
  color: #ff8a83;
  font-size: 0.85rem;
}

.event-tip__btn {
  margin-left: auto;
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

<style>
/* Element Plus 折叠面板暗色覆盖（inference-page 命名空间） */
.inference-page .el-collapse {
  border: none;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
  --el-collapse-border-color: rgba(125, 201, 255, 0.1);
  --el-collapse-header-text-color: #dbe9ff;
  --el-collapse-header-active-text-color: #9ad6ff;
  --el-collapse-content-text-color: rgba(217, 232, 255, 0.85);
}

.inference-page .el-collapse-item__header {
  background: rgba(8, 17, 31, 0.6);
  border-bottom: 1px solid rgba(125, 201, 255, 0.1);
  height: 44px;
  padding: 0 14px;
  border-radius: 8px;
  margin-bottom: 8px;
}

.inference-page .el-collapse-item__header.is-active {
  background: rgba(91, 166, 255, 0.08);
}

.inference-page .el-collapse-item__arrow {
  color: rgba(154, 214, 255, 0.7);
}

.inference-page .el-collapse-item__wrap {
  background: transparent;
  border-bottom: none;
}

.inference-page .el-collapse-item__content {
  padding: 10px 14px 16px;
}

.inference-page .el-button.is-plain {
  --el-button-bg-color: rgba(91, 166, 255, 0.1) !important;
  --el-button-border-color: rgba(91, 166, 255, 0.35) !important;
  --el-button-text-color: #9ad6ff !important;
  --el-button-hover-bg-color: rgba(91, 166, 255, 0.2) !important;
  --el-button-hover-border-color: rgba(91, 166, 255, 0.5) !important;
  --el-button-hover-text-color: #bae3ff !important;
}

.inference-page .el-button--primary {
  --el-button-bg-color: #5ba6ff;
  --el-button-border-color: #5ba6ff;
  --el-button-text-color: #ffffff;
  --el-button-hover-bg-color: #4a94ee;
  --el-button-hover-border-color: #4a94ee;
  --el-button-hover-text-color: #ffffff;
}
</style>
