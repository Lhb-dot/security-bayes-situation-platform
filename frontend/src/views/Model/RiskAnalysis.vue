<script setup lang="ts">
/**
 * RiskAnalysis - 模型训练（数据库化版）
 *
 * 需求 6.3.1（管理员闭环）：选择场景 → 数据集版本 → 算法 → 配置训练参数 → 启动训练
 * 需求 6.6：算法代码注册（A2WNB/MAWNB/EMAWNB/CAVWNB/PMWNB）+ 动态参数配置表单
 *   - 场景 / 数据集 / 算法 全部从 /api/v1 数据库渲染，不再使用 mock
 *   - 训练参数表单由算法注册的 param_schema 动态生成（需求 6.6.3）
 * 需求 6.7.2：训练成功生成 DRAFT 模型版本（待管理员在模型中心审核发布）
 * 需求 6.5.2：仅管理员可训练；普通用户只能使用已发布模型执行推理
 *
 * 训练执行策略（后端 /api/v1/model-versions/train）：所有已注册算法均调用真实 Java/Weka 服务；
 * 页面参数来自 algorithm.param_schema，并随训练请求传入服务。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import type { AlgorithmParamDef, UserAccount } from '@/types/security';
import { useUserStore } from '@/stores/userStore';
import { getScenarios, getDatasets, getAlgorithms, trainModel } from '@/api/trainingApi';
import { ElMessage } from 'element-plus';

const router = useRouter();
const userStore = useUserStore();

// ===================== 权限 =====================
const currentUser = ref<UserAccount | null>(null);
const isAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN' || currentUser.value?.role === 'SCENARIO_ADMIN');

// ===================== 场景（数据库） =====================
interface DbScenario {
  id: number;
  code: string;
  name: string;
  access_status: string;
}
const scenarios = ref<DbScenario[]>([]);
const scenarioOptions = computed(() =>
  scenarios.value.filter((s) => s.access_status === 'ACTUAL')
);
const selectedScenario = ref<number | ''>('');

// ===================== 数据集（数据库） =====================
interface DbDataset {
  id: number;
  logical_id: string;
  version: number;
  status: string;
  file_path: string;
  fields_schema: unknown[];
}
const datasetList = ref<DbDataset[]>([]);
const selectedDatasetId = ref<number | ''>('');
const selectedDatasetVersion = ref<number | null>(null);
const loadingDatasets = ref(false);

// ===================== 算法（数据库 + param_schema 动态表单） =====================
interface AlgoOption {
  id: number;
  code: string;
  display_name: string;
  description: string;
  available: boolean;
  params: AlgorithmParamDef[];
}
const algorithms = ref<AlgoOption[]>([]);
const selectedAlgoId = ref<number | ''>('');

/** 后端 param_schema（name/type/enum/options）→ 前端 AlgorithmParamDef 渲染模型 */
const mapBackendParams = (schema: unknown[]): AlgorithmParamDef[] => {
  if (!Array.isArray(schema)) return [];
  return schema.map((raw) => {
    const item = (raw ?? {}) as Record<string, unknown>;
    let type: AlgorithmParamDef['type'];
    switch (item.type) {
      case 'int':
      case 'float':
        type = 'number';
        break;
      case 'bool':
        type = 'boolean';
        break;
      case 'enum':
        type = 'select';
        break;
      default:
        type = 'string';
    }
    return {
      param_name: String(item.name ?? ''),
      label: String(item.label ?? item.name ?? ''),
      type,
      default_value: (item.default as AlgorithmParamDef['default_value']) ?? '',
      min: item.min as number | undefined,
      max: item.max as number | undefined,
      step: item.step as number | undefined,
      options: Array.isArray(item.options)
        ? (item.options as { value: string; label: string }[])
        : Array.isArray(item.enum_values)
          ? (item.enum_values as string[]).map((v) => ({ value: v, label: v }))
          : undefined,
      description: String(item.description ?? ''),
    };
  });
};

/** 当前算法定义 */
const currentAlgo = computed(() => algorithms.value.find((a) => a.id === selectedAlgoId.value));

/** 训练参数表单（动态生成，默认值来自算法 param_schema，需求 6.6.3） */
const paramForm = ref<Record<string, number | string | boolean>>({});

const algoNameById = (id: number) => algorithms.value.find((a) => a.id === id)?.display_name ?? String(id);
const scenarioNameById = (id: number) => scenarios.value.find((s) => s.id === id)?.name ?? String(id);

// ===================== 训练结果 =====================
interface TrainOutcome {
  model_version_id: string;
  status: string;
  scenario_id: number;
  dataset_id: number;
  algorithm_id: number;
  evaluation_metrics: Record<string, unknown>;
  training_parameters: Record<string, unknown>;
}
const trainResult = ref<TrainOutcome | null>(null);
const training = ref(false);
// ===== 训练计时（需求：点击训练后实时显示已训练秒数） =====
const trainingElapsed = ref(0);            // 已训练秒数（实时递增）
let trainingTimer: number | null = null;   // setInterval 句柄

const startTrainingTimer = () => {
  trainingElapsed.value = 0;
  if (trainingTimer !== null) window.clearInterval(trainingTimer);
  trainingTimer = window.setInterval(() => {
    trainingElapsed.value += 1;
  }, 1000);
};

const stopTrainingTimer = () => {
  if (trainingTimer !== null) {
    window.clearInterval(trainingTimer);
    trainingTimer = null;
  }
};

const trainMetrics = computed(() => trainResult.value?.evaluation_metrics ?? {});
const isRealTrain = computed(() => String(trainMetrics.value.source ?? '').startsWith('java_'));
const isMockTrain = computed(() => String(trainMetrics.value.source ?? '').startsWith('mock'));

/** 百分比指标展示：缺字段（如 PMWNB 无 specificity/g_mean）显示 — */
const metricText = (key: string) => {
  const v = trainMetrics.value[key];
  return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—';
};
const trainTimeText = () => {
  const v = trainMetrics.value.train_time_s;
  return typeof v === 'number' ? `${v} s` : '—';
};
const datasetText = () => {
  const ds = datasetList.value.find((d) => d.id === trainResult.value?.dataset_id);
  return ds ? `${ds.logical_id}（v${ds.version}）` : String(trainResult.value?.dataset_id);
};

// ===================== 场景切换 → 加载数据集 =====================
watch(selectedScenario, async (scenario) => {
  selectedDatasetId.value = '';
  selectedDatasetVersion.value = null;
  trainResult.value = null;
  if (!scenario) {
    datasetList.value = [];
    return;
  }
  loadingDatasets.value = true;
  try {
    datasetList.value = await getDatasets(scenario);
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
  startTrainingTimer();
  try {
    const row = await trainModel({
      scenario_id: selectedScenario.value,
      dataset_id: selectedDatasetId.value,
      algorithm_id: selectedAlgoId.value,
      training_parameters: { ...paramForm.value },
    });
    trainResult.value = {
      model_version_id: String(row.id),
      status: row.status,
      scenario_id: row.scenario_id,
      dataset_id: row.dataset_id,
      algorithm_id: row.algorithm_id,
      evaluation_metrics: row.evaluation_metrics ?? {},
      training_parameters: row.training_parameters ?? {},
    };
    const done = row.status === 'DRAFT';
    ElMessage.success(done ? '训练完成，已生成 DRAFT 模型版本，请在模型中心审核发布' : `训练状态：${row.status}`);
  } catch (err) {
    const e = err as { response?: { data?: { message?: string } }; message?: string };
    ElMessage.error(e.response?.data?.message || e.message || '模型训练失败');
  } finally {
    stopTrainingTimer();
    training.value = false;
  }
};

const goModelCenter = () => {
  router.push('/models');
};

/** /api/v1/algorithms 返回的算法行（trainingApi 为 JS 模块无类型，此处显式声明） */
interface ApiAlgorithmRow {
  id: number;
  code: string;
  display_name: string;
  description?: string | null;
  status: string;
  param_schema?: unknown[];
}

onMounted(async () => {
  currentUser.value = userStore.currentUser;
  try {
    scenarios.value = await getScenarios();
    algorithms.value = ((await getAlgorithms()) as ApiAlgorithmRow[]).map((a) => ({
      id: a.id,
      code: a.code,
      display_name: a.display_name,
      description: a.description ?? '',
      available: a.status === 'AVAILABLE',
      params: mapBackendParams(a.param_schema ?? []),
    }));
  } catch (err) {
    const e = err as { response?: { data?: { message?: string } }; message?: string };
    ElMessage.warning(`加载算法/场景数据失败：${e.response?.data?.message || e.message || '请确认后端已启动'}`);
  }
  // 默认选中第一个 ACTUAL 场景与第一个可用算法
  if (scenarioOptions.value.length) {
    selectedScenario.value = scenarioOptions.value[0].id;
  }
  selectedAlgoId.value = algorithms.value.find((a) => a.available)?.id ?? '';
});

// 离开页面时清理训练计时器，防止内存泄漏
onBeforeUnmount(() => {
  stopTrainingTimer();
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

        <!-- 业务场景（数据库注册）：系统管理员可选全部；管理员场景已固定（账号绑定），直接选数据集 -->
        <div v-if="currentUser?.role !== 'SCENARIO_ADMIN'" class="form-group">
          <label class="form-label">业务场景（需求 1.1.2：训练前必须先确定场景）</label>
          <!-- 系统管理员（或用户信息未加载时兜底）：显示全部场景可选 -->
          <div class="scenario-tabs">
            <button
              v-for="sc in scenarioOptions"
              :key="sc.id"
              class="scenario-tab"
              :class="{ 'is-active': selectedScenario === sc.id }"
              @click="selectedScenario = sc.id"
            >
              {{ sc.name }}
            </button>
          </div>
          <p v-if="!scenarioOptions.length" class="form-hint form-hint--muted">
            暂无可训练场景（请确认后端已启动且数据库已初始化）
          </p>
        </div>

        <!-- 数据集版本（数据库） -->
        <div class="form-group">
          <label class="form-label">数据集（版本）</label>
          <select
            v-model="selectedDatasetId"
            class="form-select"
            :disabled="!selectedScenario || loadingDatasets"
            @change="selectedDatasetVersion = datasetList.find(d => d.id === selectedDatasetId)?.version ?? null"
          >
            <option value="" disabled>-- 请选择数据集 --</option>
            <option
              v-for="ds in datasetList"
              :key="ds.id"
              :value="ds.id"
            >
              {{ ds.logical_id }}（v{{ ds.version }} · {{ ds.fields_schema?.length ?? 0 }} 字段）{{ ds.status === 'ACTIVE' ? '' : '【已停用】' }}
            </option>
          </select>
          <p class="form-hint form-hint--muted">仅展示当前场景下已注册的数据集版本；已停用版本不能用于训练</p>
        </div>

        <!-- 算法（需求 6.6.1 五种算法注册） -->
        <div class="form-group">
          <label class="form-label">算法</label>
          <select v-model="selectedAlgoId" class="form-select">
            <option
              v-for="a in algorithms"
              :key="a.id"
              :value="a.id"
              :disabled="!a.available"
            >
              {{ a.display_name }}
            </option>
          </select>
          <p v-if="currentAlgo" class="form-hint">{{ currentAlgo.description }}</p>
        </div>

        <!-- 训练参数（需求 6.6.3 由 param_schema 动态生成） -->
        <div v-if="currentAlgo" class="form-group">
          <label class="form-label">训练参数（提供默认值，可修改，须通过类型与范围校验）</label>
          <div v-if="currentAlgo.params.length" class="param-list">
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
          <p v-else class="form-hint">
            当前算法没有注册可公开调整的训练参数，使用 Java/Weka 实现的内置默认配置训练。
          </p>
        </div>

        <!-- 训练按钮 -->
        <button
          class="train-btn"
          :disabled="training || !selectedDatasetId || !selectedAlgoId"
          @click="handleTrain"
        >
          <span v-if="training" class="btn-spinner"></span>
          {{ training ? `训练中... ${trainingElapsed}s` : '开始训练' }}
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
          <div class="infer-placeholder__icon">{{ training ? '⏳' : '🧠' }}</div>
          <h4>{{ training ? `训练中... 已用时 ${trainingElapsed} 秒` : '尚未开始训练' }}</h4>
          <p>
            {{
              training
              ? '正在执行真实 Java/Weka 算法训练，大样本数据集可能需要数十秒。'
                : '完成左侧配置后启动训练。训练成功的模型将进入 DRAFT 状态，可在模型中心审核发布。'
            }}
          </p>
        </div>

        <template v-else>
          <div class="result-model-id">
            <span class="result-model-id__label">模型版本</span>
            <span class="result-model-id__value">{{ trainResult.model_version_id }}</span>
            <span class="result-model-id__status">
            <template v-if="isRealTrain">真实训练（Java/Weka）</template>
              <template v-else-if="isMockTrain">占位训练（模拟数据）</template>
              <template v-else>DRAFT（待发布）</template>
            </span>
          </div>

          <div class="train-metrics">
            <div class="metric-card">
              <span class="metric-card__label">Accuracy</span>
              <span class="metric-card__value metric-card__value--acc">{{ metricText('accuracy') }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">Recall</span>
              <span class="metric-card__value metric-card__value--rec">{{ metricText('recall') }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">Precision</span>
              <span class="metric-card__value metric-card__value--pre">{{ metricText('precision') }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">Specificity</span>
              <span class="metric-card__value metric-card__value--spe">{{ metricText('specificity') }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">F1</span>
              <span class="metric-card__value metric-card__value--f1">{{ metricText('f1') }}</span>
            </div>
            <div class="metric-card">
              <span class="metric-card__label">G-mean</span>
              <span class="metric-card__value metric-card__value--gm">{{ metricText('g_mean') }}</span>
            </div>
          </div>

          <div class="result-detail">
            <div class="result-detail__row">
              <span>场景</span><strong>{{ scenarioNameById(trainResult.scenario_id) }}</strong>
            </div>
            <div class="result-detail__row">
              <span>数据集</span><strong>{{ datasetText() }}</strong>
            </div>
            <div class="result-detail__row">
              <span>算法</span><strong>{{ algoNameById(trainResult.algorithm_id) }}</strong>
            </div>
            <div class="result-detail__row">
              <span>训练耗时</span><strong>{{ trainTimeText() }}</strong>
            </div>
            <template v-if="isRealTrain">
              <div class="result-detail__row">
                <span>训练样本 / 特征 / 类别</span><strong>{{ trainMetrics.num_instances }} / {{ trainMetrics.num_attributes }} / {{ trainMetrics.num_classes }}</strong>
              </div>
              <div class="result-detail__row">
                <span>模型文件</span><strong class="result-detail__mono">{{ trainMetrics.model_saved_to }}</strong>
              </div>
            </template>
            <template v-else-if="isMockTrain">
              <div class="result-detail__row">
                <span>提示</span><strong>算法实现待算法组交付，当前为模拟占位指标</strong>
              </div>
            </template>
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

.result-detail__mono {
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.75rem;
  word-break: break-all;
  text-align: right;
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
