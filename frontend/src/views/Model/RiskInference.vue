<script setup lang="ts">
/**
 * RiskInference - 风险研判
 *
 * 三段纵向：
 *   1 选范围   —— 场景 / 数据集 / 模型（一行搞定，模型不再铺卡片列表）
 *   2 选数据来源 —— 样本库（默认）/ 手工录入 / 批量导入
 *   3 结果     —— 单条结果卡 + 批量结果表，完成后自动滚入视口
 *
 * 单条推理（需求 6.3.2 / 6.7.4 / 6.7.5）：选已发布模型 → 按模型绑定数据集字段
 * 生成输入 → 执行推理 → 风险类结果转 RiskEvent。
 *
 * 批量研判：从数据集样本区间或上传 CSV 批量跑，逐条与单条行为一致
 * （风险类照常生成 RiskEvent，保证告警中心/态势大屏/看板都能看到）。
 *
 * 数据链路：页面 → scenarioApi / datasetApi / modelVersionApi / inferenceRecordApi。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import DOMPurify from 'dompurify';
import { ElMessage } from 'element-plus';
import { marked } from 'marked';
import { useDatasetStore } from '@/stores/datasetStore';
import { useUserStore } from '@/stores/userStore';
import { useBatchJobStore } from '@/stores/batchJobStore';
import { getScenarioList, type ApiScenario } from '@/api/scenarioApi';
import { getDatasetPreview } from '@/api/datasetApi';
import { keepScroll } from '@/utils/scrollAnchor';
import { stripArffQuotes } from '@/utils/arffValue';
import { getModelVersionList, type BackendModelVersion } from '@/api/modelVersionApi';
import type { Dataset, DatasetField, ScenarioId } from '@/types/security';
import {
  predictInference,
  submitInferenceBatch,
  submitInferenceBatchUpload,
  streamInferenceExplanation,
  type BatchInferenceResult,
  type PredictResult,
} from '@/api/inferenceRecordApi';

const router = useRouter();
const route = useRoute();
const datasetStore = useDatasetStore();
const userStore = useUserStore();
let pageActive = true;
let sessionRevision = 0;
watch(() => userStore.currentUser?.user_id, () => { sessionRevision += 1; }, { flush: 'sync' });

// ===================== 具名常量（原先散在代码里的魔法值） =====================
/** 模型下拉一次拉全量：单个数据集下的模型版本数远小于这个上限 */
const MODEL_LIST_PAGE_SIZE = 200;
/** 样本表最多展示的输入特征列数（够判断这行是什么样本） */
const SAMPLE_TABLE_COLUMN_COUNT = 5;
/** 单条结果里展示的主要影响字段条数 */
const TOP_FEATURE_COUNT = 3;
/** 批量研判默认条数与单批上限（上限与后端 predict-batch 的校验一致） */
const DEFAULT_BATCH_LIMIT = 50;
const MAX_BATCH_LIMIT = 200;
/** 概率（0~1）→ 百分比的换算系数，以及「小于该值就不报具体数字」的阈值（%） */
const PERCENT_SCALE = 100;
const PERCENT_MIN_VISIBLE = 0.01;
/** 数值输入框步长：浮点留两位小数，整数按 1 递增 */
const FLOAT_INPUT_STEP = '0.01';
const INT_INPUT_STEP = '1';
/** 占位文案：指标 / 等级 / 事件号缺失时统一显示它 */
const UNKNOWN_TEXT = '—';
/** 后端约定的场景可用状态与模型已发布状态 */
const SCENARIO_ACCESS_ACTUAL = 'ACTUAL';
const MODEL_STATUS_PUBLISHED = 'PUBLISHED';
/** 数据集字段角色与类型（与后端字段定义一致） */
const FIELD_ROLE_INPUT = '输入特征';
const FIELD_ROLE_LABEL = '分类标签';
const FIELD_TYPE_FLOAT = 'float';
const FIELD_TYPE_INT = 'int';
const FIELD_TYPE_STRING = 'string';
/** 风险等级（大写枚举）→ 中文，键与 types/security 的 RiskLevelUpper 对齐 */
const RISK_LEVEL_TEXT: Record<string, string> = { HIGH: '高', MEDIUM: '中', LOW: '低' };
/** 未选模型时三个执行入口共用的提示 */
const MODEL_REQUIRED_MESSAGE = '请先选择一个已发布模型';

/** 真实场景列表（直接调 /api/v1/scenarios，行类型复用 scenarioApi 的定义） */
const scenarios = ref<ApiScenario[]>([]);
/** 真实模型版本列表（直接调 /api/v1/model-versions） */
const modelVersions = ref<BackendModelVersion[]>([]);

const isSuperAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN');
const isManager = computed(() => ['SUPER_ADMIN', 'SCENARIO_ADMIN'].includes(userStore.currentUser?.role ?? ''));

const scenarioOptions = computed<{ value: ScenarioId; label: string }[]>(() =>
  scenarios.value
    .filter((s) => s.access_status === SCENARIO_ACCESS_ACTUAL)
    .map((s) => ({ value: s.code as ScenarioId, label: s.name }))
);

// ===================== 1 选范围 =====================
const selectedScenario = ref<ScenarioId | ''>('');
const selectedDatasetId = ref<string>('');
const loadingDatasets = ref(false);
const datasets = ref<Dataset[]>([]);

const datasetOptions = computed<Dataset[]>(() =>
  selectedScenario.value
    ? datasets.value.filter((d) => d.scenario_id === selectedScenario.value)
    : []
);

const publishedModels = computed<BackendModelVersion[]>(() =>
  modelVersions.value.filter((m) => m.status === MODEL_STATUS_PUBLISHED)
);
const loadingModels = ref(false);
const selectedModelId = ref<string | number>('');
const selectedModel = computed(() =>
  publishedModels.value.find((m) => String(m.model_version_id) === String(selectedModelId.value))
);

const modelLabel = (m: BackendModelVersion) =>
  `#${m.model_version_id} ${m.algorithm_name ?? m.algorithm_id}${m.is_recommended ? '（推荐）' : ''}`;

/** 模型下拉旁展示的指标口径 */
type MetricKey = 'accuracy' | 'recall' | 'f1' | 'g_mean';

/** 指标展示：缺失（undefined / null / 非数值）一律显示占位符，不能折算成 0% */
const metricText = (key: MetricKey) => {
  const raw = selectedModel.value?.evaluation_metrics?.[key];
  if (raw === null || raw === undefined) return UNKNOWN_TEXT;
  const value = Number(raw);
  return Number.isFinite(value) ? `${(value * PERCENT_SCALE).toFixed(1)}%` : UNKNOWN_TEXT;
};

// ===================== 2 数据来源 =====================
/** 两类来源：手工录入（自己输入 / 批量上传）、样本库（勾选若干项 / 前 N 项） */
type SourceTab = 'manual' | 'sample';
const sourceTab = ref<SourceTab>('manual');
/** 手工录入内部的两种方式 */
type ManualMode = 'input' | 'upload';
const manualMode = ref<ManualMode>('input');

/** 手工录入：字段与取值 */
const inputFields = ref<DatasetField[]>([]);
const inputData = ref<Record<string, string | number>>({});

/** 样本库 */
const samples = ref<Record<string, string | number>[]>([]);
const sampleLoading = ref(false);
const sampleTotal = ref(0);
const samplePage = ref(1);
const SAMPLE_PAGE_SIZE = 50;
/** 已勾选的样本：键是全局序号（1 起），值是整行取值 —— 跨页勾选也能带全数据 */
const selectedSamples = ref<Record<number, Record<string, string | number>>>({});
const selectedCount = computed(() => Object.keys(selectedSamples.value).length);
let sampleSequence = 0;

/** 第 index 行（当前页）对应的全局序号 */
const ordinalOf = (index: number) => (samplePage.value - 1) * SAMPLE_PAGE_SIZE + index + 1;
const isRowSelected = (index: number) => ordinalOf(index) in selectedSamples.value;
const pageAllSelected = computed(
  () => samples.value.length > 0 && samples.value.every((_, i) => isRowSelected(i))
);

/** 勾选 / 取消一行（整行取值一起带走，翻页后仍能提交） */
const toggleSample = (index: number) => {
  const row = samples.value[index];
  if (!row) return;
  const ordinal = ordinalOf(index);
  if (ordinal in selectedSamples.value) delete selectedSamples.value[ordinal];
  else selectedSamples.value[ordinal] = { ...row };
};

/** 表头全选：勾中 / 取消当前页 */
const toggleSelectPage = () => {
  if (pageAllSelected.value) {
    samples.value.forEach((_, i) => { delete selectedSamples.value[ordinalOf(i)]; });
  } else {
    samples.value.forEach((row, i) => { selectedSamples.value[ordinalOf(i)] = { ...row }; });
  }
};

/** 反选：当前页内已选的取消、未选的勾上 */
const invertSelection = () => {
  samples.value.forEach((row, i) => {
    const ordinal = ordinalOf(i);
    if (ordinal in selectedSamples.value) delete selectedSamples.value[ordinal];
    else selectedSamples.value[ordinal] = { ...row };
  });
};

/** 清空全部勾选（含其它页） */
const clearSelection = () => { selectedSamples.value = {}; };

const totalSamplePages = computed(() =>
  Math.max(1, Math.ceil(sampleTotal.value / SAMPLE_PAGE_SIZE))
);

/** 样本表里展示的列（输入特征前 N 个，够判断这行是什么样本） */
const sampleColumns = computed(() =>
  inputFields.value.slice(0, SAMPLE_TABLE_COLUMN_COUNT).map((f) => f.field_name)
);
const labelField = computed(
  () => inputFields.value.find((f) => f.field_role === FIELD_ROLE_LABEL)?.field_name ?? ''
);

/** 批量研判：样本库的「前 N 项 / 勾选项」与手工录入的「上传 CSV」共用这套状态 */
const batchLimit = ref(DEFAULT_BATCH_LIMIT);
const batchResult = ref<BatchInferenceResult | null>(null);
/** 提交请求在途（按钮立刻置灰，避免连点提交两批） */
const batchSubmitting = ref(false);
/** 正在跑的是哪个批量入口（进度文案只显示在对应的按钮上） */
type BatchAction = 'head' | 'selected' | 'upload';
const batchAction = ref<BatchAction | null>(null);

// ===== 批量研判任务（数据源在 store：离开页面后台照样跑，完成时全局通知） =====
// 进度取自 store 里最近登记的那条任务；完成通知与超时兜底都在 store，不随组件卸载。
const batchJobStore = useBatchJobStore();
const activeBatchJob = computed(() => batchJobStore.activeJob);
const batchRunning = computed(() => Boolean(activeBatchJob.value));
const batchProgressText = computed(() => {
  const job = activeBatchJob.value;
  return job?.total ? `研判中… ${job.processed}/${job.total}` : '研判中…';
});
const uploadFile = ref<File | null>(null);
/** 隐藏的原生 file input：由云上传图标按钮触发 */
const fileInputRef = ref<HTMLInputElement | null>(null);
const pickCsvFile = () => {
  const input = fileInputRef.value;
  if (!input) return;
  input.value = ''; // 清空后重选同一个文件也能触发 change
  input.click();
};

// ===================== 3 单条推理结果 =====================
const inferResult = ref<PredictResult | null>(null);
const inferring = ref(false);
const resultRef = ref<HTMLElement | null>(null);

const explanationMarkdown = ref('');
const explanationLoading = ref(false);
const explanationError = ref('');
const explanationFallback = ref(false);
const explanationStatus = ref<'idle' | 'generating' | 'completed' | 'failed' | 'fallback' | 'stopped'>('idle');
let explanationController: AbortController | null = null;

const safeExplanationHtml = computed(() => {
  if (!explanationMarkdown.value) return '';
  return DOMPurify.sanitize(marked.parse(explanationMarkdown.value, { async: false }) as string);
});

const adminExplanationJson = computed(() => {
  const explanation = inferResult.value?.explain_data;
  if (!explanation) return '';
  return JSON.stringify({
    model_quality: explanation.model_quality,
    algorithm_details: explanation.algorithm_details,
    input_snapshot: explanation.input_snapshot,
  }, null, 2);
});

// ===================== carrier 字段族分组（279 字段折叠防卡顿） =====================
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

interface FieldGroup { name: string; fields: DatasetField[]; }

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

/** 只有一个分组时，折叠头（「全部字段」）不带信息，直接平铺字段 */
const singleFieldGroup = computed(() => fieldGroups.value.length === 1);

const expandedGroups = ref<string[]>([]);
const expandAll = () => { expandedGroups.value = fieldGroups.value.map((g) => g.name); };
const collapseAll = () => { expandedGroups.value = []; };

/** 数值型字段（float / int）：输入框与默认值填充都按数值处理 */
const isNumericField = (field: DatasetField) =>
  field.field_type === FIELD_TYPE_FLOAT || field.field_type === FIELD_TYPE_INT;

/** 默认值填充：数值取 sample_value（解析失败回退 0）；枚举 string 取合法 sample_value */
const buildInputData = (fields: DatasetField[]): Record<string, string | number> => {
  const init: Record<string, string | number> = {};
  for (const f of fields) {
    if (isNumericField(f)) {
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

// ===================== 级联加载 =====================
/** 丢弃上一轮 AI 分析：中止在途的流式请求并清空正文与状态 */
const resetExplanation = () => {
  explanationMarkdown.value = '';
  explanationError.value = '';
  explanationFallback.value = false;
  explanationStatus.value = 'idle';
  explanationController?.abort();
  explanationController = null;
};

/**
 * 结果的归属标签：只展示在"发起它的那一类"里。
 *
 * 切换标签（含手工录入内部的两种方式）会把 resultScope 清空，所以上一类的结果
 * 不会残留在页面下方；后台跑完的批量任务回填时也要先过这一关。
 */
const resultScope = ref<SourceTab | null>(null);

/** 结果区是否展示：结果归属当前标签，且确有内容 */
const resultVisible = computed(
  () => resultScope.value === sourceTab.value && Boolean(batchResult.value || inferResult.value)
);

/** 丢弃当前展示的结果（单条 / 批量 / AI 分析），不动勾选状态 */
const clearResultState = () => {
  inferResult.value = null;
  batchResult.value = null;
  resultScope.value = null;
  resetExplanation();
};

/** 丢弃上一轮结果与勾选（换场景 / 换数据集 / 换模型时用） */
const resetResults = () => {
  clearResultState();
  selectedSamples.value = {};
};

// 切换标签：上一类的结果立即作废，不再残留
watch([sourceTab, manualMode], () => { clearResultState(); });

/** 换场景 / 换数据集 / 换模型时统一清空输入区（字段、取值、样本，并丢弃上一轮结果） */
const resetInputState = () => {
  sampleSequence += 1;
  sampleLoading.value = false;
  samplePage.value = 1;
  inputFields.value = [];
  inputData.value = {};
  samples.value = [];
  sampleTotal.value = 0;
  expandedGroups.value = [];
  resetResults();
};

/** 每层只校验自身和上游选择，子层变化不会使仍有效的父层查询失效。 */
const captureSelection = (level: 'scenario' | 'dataset' | 'model') => {
  const session = sessionRevision;
  const owner = userStore.currentUser?.user_id;
  const scenario = selectedScenario.value;
  const datasetId = selectedDatasetId.value;
  const modelId = selectedModelId.value;
  return () => pageActive && session === sessionRevision && owner === userStore.currentUser?.user_id
    && scenario === selectedScenario.value
    && (level === 'scenario' || datasetId === selectedDatasetId.value)
    && (level !== 'model' || modelId === selectedModelId.value);
};

/**
 * 默认选中哪个数据集：优先挑第一个「有已发布模型」的。
 *
 * 场景下的第一个数据集不一定有已发布模型（本地库里 nf_unsw_nb15_v2 就没有），
 * 直接取第一个会让用户照样得手点一次，所以这里并发探一遍；一个都没有才退回第一个。
 */
const pickDatasetWithPublishedModel = async (
  candidates: Dataset[],
  isCurrent: () => boolean,
): Promise<string | null> => {
  const scenarioNumeric = scenarios.value.find((s) => s.code === selectedScenario.value)?.id;
  const hits = await Promise.all(
    candidates.map(async (ds) => {
      try {
        const list = await getModelVersionList({
          scenario_id: scenarioNumeric,
          dataset_id: ds.dataset_id,
          page_size: MODEL_LIST_PAGE_SIZE,
        });
        return list.some((m) => m.status === MODEL_STATUS_PUBLISHED) ? ds.dataset_id : null;
      } catch {
        return null;
      }
    }),
  );
  if (!isCurrent()) return null;
  return hits.find((id) => id !== null) ?? null;
};

watch([selectedScenario, () => userStore.currentUser?.user_id], async ([scenario, owner], _, onCleanup) => {
  let active = true;
  onCleanup(() => { active = false; });
  selectedDatasetId.value = '';
  selectedModelId.value = '';
  resetInputState();
  datasets.value = [];
  modelVersions.value = [];
  loadingDatasets.value = false;
  loadingModels.value = false;
  if (!scenario || !owner) return;
  const selectionIsCurrent = captureSelection('scenario');
  const isCurrent = () => active && selectionIsCurrent();
  loadingDatasets.value = true;
  try {
    const list = await datasetStore.fetchDatasets(scenario, { isCurrent });
    if (!isCurrent()) return;
    datasets.value = list;
    const candidates = datasetOptions.value;
    if (candidates.length) {
      // 数据集没必要让用户每次手点：默认落在有已发布模型的那个上
      const preferred = await pickDatasetWithPublishedModel(candidates, isCurrent);
      if (!isCurrent()) return;
      selectedDatasetId.value = preferred ?? candidates[0].dataset_id;
    }
  } catch {
    if (isCurrent()) datasets.value = [];
  } finally {
    if (isCurrent()) loadingDatasets.value = false;
  }
}, { flush: 'sync' });

watch(selectedDatasetId, async (datasetId, _, onCleanup) => {
  let active = true;
  onCleanup(() => { active = false; });
  selectedModelId.value = '';
  resetInputState();
  modelVersions.value = [];
  loadingModels.value = false;
  if (!datasetId) return;
  const selectionIsCurrent = captureSelection('dataset');
  const isCurrent = () => active && selectionIsCurrent();
  loadingModels.value = true;
  try {
    const scenarioNumeric = scenarios.value.find((s) => s.code === selectedScenario.value)?.id;
    const list = await getModelVersionList({
      scenario_id: scenarioNumeric,
      dataset_id: datasetId,
      page_size: MODEL_LIST_PAGE_SIZE,
    });
    if (!isCurrent()) return;
    modelVersions.value = list;
    // 有推荐模型的优先选推荐，否则取第一个 —— 同样省掉用户手点
    const preferred = publishedModels.value.find((m) => m.is_recommended) ?? publishedModels.value[0];
    selectedModelId.value = preferred ? preferred.model_version_id : '';
  } catch {
    // 拉取失败必须清空：留着上一个数据集的模型列表会按旧列表自动选中模型
    if (isCurrent()) modelVersions.value = [];
  } finally {
    if (isCurrent()) loadingModels.value = false;
  }
}, { flush: 'sync' });

watch(selectedModelId, async (modelId, _, onCleanup) => {
  let active = true;
  onCleanup(() => { active = false; });
  resetInputState();
  if (!modelId) return;
  const model = selectedModel.value;
  if (!model) return;
  const selectionIsCurrent = captureSelection('model');
  const isCurrent = () => active && selectionIsCurrent();
  try {
    const definition = await datasetStore.fetchFields(String(model.dataset_id), String(model.dataset_version ?? ''), { isCurrent });
    if (!isCurrent()) return;
    inputFields.value = definition.filter((f) => f.field_role === FIELD_ROLE_INPUT);
    inputData.value = buildInputData(inputFields.value);
    // 需求 7.1：看板点击端口 → /inference?port= 预填 L4_DST_PORT
    const port = route.query.port;
    if (port && inputData.value.L4_DST_PORT !== undefined) {
      const n = Number(port);
      if (Number.isFinite(n)) inputData.value.L4_DST_PORT = n;
    }
    expandedGroups.value = fieldGroups.value.length > 0 ? [fieldGroups.value[0].name] : [];
    await loadSamples(1);
  } catch {
    if (isCurrent()) {
      inputFields.value = [];
      inputData.value = {};
    }
  }
}, { flush: 'sync' });

const loadSamples = async (page: number) => {
  const model = selectedModel.value;
  if (!model) return;
  const sequence = ++sampleSequence;
  const selectionIsCurrent = captureSelection('model');
  const isCurrent = () => sequence === sampleSequence && selectionIsCurrent();
  sampleLoading.value = true;
  try {
    const preview = await getDatasetPreview(String(model.dataset_id), {
      page,
      page_size: SAMPLE_PAGE_SIZE,
    });
    if (!isCurrent()) return;
    samples.value = preview.rows;
    sampleTotal.value = preview.total;
    samplePage.value = preview.page;
  } catch {
    if (isCurrent()) {
      samples.value = [];
      sampleTotal.value = 0;
    }
  } finally {
    if (isCurrent()) sampleLoading.value = false;
  }
};

/** 样本区的滚动容器（.pane 自身可滚，翻页要锚住它，见 utils/scrollAnchor.ts） */
const samplePaneRef = ref<HTMLElement | null>(null);

/** 样本翻页：包一层滚动锚定，换页后视口停在原处 */
const changeSamplePage = (target: number) => {
  const selectionIsCurrent = captureSelection('model');
  let sequence = sampleSequence;
  return keepScroll(() => {
    const request = loadSamples(target);
    sequence = sampleSequence;
    return request;
  }, samplePaneRef.value, () => sequence === sampleSequence && selectionIsCurrent());
};

// ===================== 执行单条推理 =====================
/** 未选已发布模型时的统一拦截（单条推理 / 批量研判 / 上传 CSV 三个入口共用） */
const ensureModelSelected = () => {
  if (selectedModelId.value) return true;
  ElMessage.warning(MODEL_REQUIRED_MESSAGE);
  return false;
};

const handleInfer = async () => {
  if (!ensureModelSelected()) return;
  for (const f of inputFields.value) {
    if (f.field_type === FIELD_TYPE_STRING && !inputData.value[f.field_name]) {
      ElMessage.warning(`请输入 ${f.description || f.field_name}`);
      return;
    }
  }
  const scope = sourceTab.value;
  inferring.value = true;
  // 新一轮推理：上一轮结果与它的 AI 分析一并作废（含在途的流式请求）
  clearResultState();
  resultScope.value = scope;
  try {
    const result = await predictInference({
      model_version_id: selectedModelId.value,
      input_features: { ...inputData.value },
    });
    // 请求期间切了标签：这一轮结果不再展示（resultScope 已被清空）
    if (resultScope.value !== scope) return;
    inferResult.value = result;
    await scrollToResult();
    if (result.is_risk_event) {
      ElMessage.success(`检测到风险，已生成风险事件 ${result.risk_event?.id ?? ''}`);
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '推理请求失败');
  } finally {
    inferring.value = false;
  }
};

// ===================== 批量研判 =====================
const canBatch = computed(
  () => Boolean(selectedModelId.value) && !batchRunning.value && !batchSubmitting.value
);
/** 任一批量入口在途（提交中或后台跑着） */
const batchBusy = computed(() => batchRunning.value || batchSubmitting.value);
/** 进度文案只显示在真正触发的那个按钮上 */
const busyOn = (action: BatchAction) => batchBusy.value && batchAction.value === action;
// 任务收尾（完成 / 失败）后清掉"正在跑哪个入口"，按钮恢复常态文案
watch(batchBusy, (busy) => { if (!busy) batchAction.value = null; });

/** 批量研判完成（可能在别的页面）：结果表由 store 的 lastResult 驱动回填 */
const showBatchResult = async (res: BatchInferenceResult) => {
  batchResult.value = res;
  await scrollToResult();
};

/**
 * 提交后的公共收尾：提交 → 登记到 store → 立刻返回。
 *
 * 轮询、完成通知、超时兜底都在 batchJobStore 里 —— 那里不随组件卸载，所以用户
 * 离开本页任务照跑、完成时照样弹通知。结果要不要展示由 resultScope 决定：
 * 提交后切过标签就不再回填。
 */
const runBatchJob = async (
  action: BatchAction,
  submit: () => Promise<{ job_id: string; total: number }>,
  title: string,
) => {
  // 批量开始：单条结果与它的 AI 分析一并作废
  clearResultState();
  resultScope.value = sourceTab.value;
  batchAction.value = action;
  batchSubmitting.value = true;
  try {
    const receipt = await submit();
    batchJobStore.track(receipt.job_id, Number(selectedModelId.value), title, receipt.total);
    ElMessage.success(`批量研判任务已生成，共 ${receipt.total} 条，完成后会通知你`);
  } finally {
    batchSubmitting.value = false;
  }
};

// 批量研判完成：store 记下结果，这里回填结果表并滚入视口
watch(
  [() => batchJobStore.lastResult, selectedModelId],
  async ([payload]) => {
    if (!payload || batchResult.value) return;
    // 结果只回填到"发起它的那一类"：切换过标签就不再展示
    if (resultScope.value !== sourceTab.value) return;
    if (String(payload.modelVersionId) !== String(selectedModelId.value)) return;
    await showBatchResult(payload.result);
  },
);

/** 通知文案里的任务名（与模型下拉的标签一致） */
const batchJobTitle = () =>
  selectedModel.value ? modelLabel(selectedModel.value) : `模型版本 #${selectedModelId.value}`;

/** 批量入口的公共外壳：统一拦截未选模型、统一错误提示，返回是否提交成功 */
const runBatchAction = async (
  action: BatchAction,
  submit: () => Promise<{ job_id: string; total: number }>,
  failureText: string,
) => {
  if (!ensureModelSelected()) return false;
  try {
    await runBatchJob(action, submit, batchJobTitle());
    return true;
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : failureText);
    return false;
  }
};

/** 样本库：研判数据集前 N 项 */
const handleBatchHead = async () => {
  const raw = Math.floor(Number(batchLimit.value));
  const limit = Math.max(1, Math.min(MAX_BATCH_LIMIT, Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_BATCH_LIMIT));
  batchLimit.value = limit;
  await runBatchAction('head', () => submitInferenceBatch({
    model_version_id: selectedModelId.value,
    source: 'dataset',
    offset: 0,
    limit,
  }), '批量研判失败');
};

/** 样本库：研判勾选的若干项 */
const handleBatchSelected = async () => {
  const rows = Object.values(selectedSamples.value);
  if (!rows.length) {
    ElMessage.warning('请先勾选要研判的样本');
    return;
  }
  if (rows.length > MAX_BATCH_LIMIT) {
    ElMessage.warning(`一次最多研判 ${MAX_BATCH_LIMIT} 条`);
    return;
  }
  const submitted = await runBatchAction('selected', () => submitInferenceBatch({
    model_version_id: selectedModelId.value,
    source: 'samples',
    samples: rows,
  }), '批量研判失败');
  if (submitted) selectedSamples.value = {};
};

const onFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement;
  uploadFile.value = input.files?.[0] ?? null;
};

/** 手工录入：上传 CSV 批量研判 */
const handleUpload = async () => {
  if (!uploadFile.value) {
    ElMessage.warning('请先选择 CSV 文件');
    return;
  }
  await runBatchAction('upload', () => submitInferenceBatchUpload({
    model_version_id: selectedModelId.value,
    file: uploadFile.value as File,
  }), 'CSV 批量研判失败');
};

// ===================== 结果展示辅助 =====================
const formatPercent = (raw: number | null | undefined) => {
  if (raw === null || raw === undefined || !Number.isFinite(Number(raw))) return UNKNOWN_TEXT;
  const percent = Number(raw) * PERCENT_SCALE;
  if (percent === 0) return '0%';
  if (percent < PERCENT_MIN_VISIBLE) return `<${PERCENT_MIN_VISIBLE}%`;
  return `${percent.toFixed(2)}%`;
};

const riskPercent = (item: { risk_probability: number | null }) => formatPercent(item.risk_probability);

const singleRiskPercent = computed(() =>
  formatPercent(
    inferResult.value?.explain_data?.risk_probability ?? inferResult.value?.risk_score
  )
);

/** 风险等级 → 中文；未知/缺失等级显示占位符（等级枚举见 types/security） */
const levelText = (level?: string | null) =>
  (level && RISK_LEVEL_TEXT[level]) || UNKNOWN_TEXT;

const exportBatchCsv = () => {
  const items = batchResult.value?.items ?? [];
  const rows: string[][] = [['序号', '分类结果', '风险概率', '风险等级', '风险事件ID', '失败原因']];
  for (const item of items) {
    rows.push([
      String(item.index + 1),
      item.error ? '失败' : item.is_risk_event ? '风险类' : '正常类',
      riskPercent(item),
      levelText(item.risk_level),
      item.risk_event_id ? String(item.risk_event_id) : '',
      item.error ?? '',
    ]);
  }
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\r\n');
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `批量研判结果_${Date.now()}.csv`;
  link.click();
  URL.revokeObjectURL(url);
};

const scrollToResult = async () => {
  await nextTick();
  resultRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const goEventDetail = (eventId?: string | number | null) => {
  if (eventId == null) return;
  router.push({ path: `/events/${eventId}` });
};

// ===================== AI 场景化分析 =====================
const generateExplanation = async (result: PredictResult) => {
  resetExplanation();
  explanationController = new AbortController();
  explanationLoading.value = true;
  explanationStatus.value = 'generating';
  const explanation = result.explain_data ?? {};
  const scenario = scenarios.value.find((item) => item.code === selectedScenario.value);
  try {
    await streamInferenceExplanation(
      {
        scenario: {
          code: selectedScenario.value,
          scenario_code: selectedScenario.value,
          name: scenario?.name,
        },
        sample: { ...inputData.value },
        model_result: { ...explanation, prediction_label: result.prediction_label },
        algorithm_details: explanation.algorithm_details ?? {},
        recommended_actions: explanation.recommended_actions ?? [],
        inference_record_id: result.id,
        model_version_id: result.model_version_id,
      },
      {
        onStart: () => { explanationStatus.value = 'generating'; },
        onDelta: (content) => { explanationMarkdown.value += content; },
        onError: (message) => {
          explanationError.value = message;
          explanationFallback.value = true;
          explanationStatus.value = 'fallback';
          // 流式中途失败时先丢弃半截正文，避免「半句 AI 文本 + 规则模板」拼在一起。
          explanationMarkdown.value = '';
        },
        onDone: (data) => {
          explanationLoading.value = false;
          explanationStatus.value = data.source === 'fallback' ? 'fallback' : 'completed';
        },
      },
      explanationController.signal,
    );
  } catch (err) {
    if ((err as Error)?.name !== 'AbortError') {
      explanationError.value = err instanceof Error ? err.message : 'AI 分析请求失败';
      explanationFallback.value = true;
      explanationStatus.value = 'failed';
    }
  } finally {
    explanationLoading.value = false;
  }
};

const stopExplanation = () => {
  explanationController?.abort();
  explanationController = null;
  explanationLoading.value = false;
  explanationStatus.value = 'stopped';
};

onMounted(async () => {
  const session = sessionRevision;
  const owner = userStore.currentUser?.user_id;
  try {
    const list = await getScenarioList();
    if (!pageActive || session !== sessionRevision || owner !== userStore.currentUser?.user_id) return;
    scenarios.value = list;
    if (!selectedScenario.value && scenarioOptions.value.length) {
      selectedScenario.value = scenarioOptions.value[0].value;
    }
  } catch {
    // 场景查询失败保持空范围，不继续发起数据集或模型请求。
  }
});

onBeforeUnmount(() => {
  pageActive = false;
  sampleSequence += 1;
});

/**
 * 离开页面时中止在途的 AI 分析流。
 *
 * 流式请求的 AbortController 原先只由「重新生成 / 停止生成 / 级联切换」触发中止，
 * 组件卸载这条路径没人管：SSE 连接会一直挂到服务端自然结束，回调还在往已卸载组件的
 * ref 上追加正文。
 */
onUnmounted(() => {
  explanationController?.abort();
  explanationController = null;
});

</script>

<template>
  <div class="inference-page">
    <div class="inference-page__header">
      <p class="eyebrow">Risk Inference</p>
      <h2>风险研判</h2>
      <p class="inference-page__desc">样本推理与风险等级判定</p>
    </div>

    <!-- ============ 1 选范围 ============ -->
    <section class="card scope-bar">
      <div v-if="isSuperAdmin" class="scope-field scope-field--scenario">
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

      <div class="scope-field">
        <label class="form-label">数据集</label>
        <select
          v-model="selectedDatasetId"
          class="form-input"
          :disabled="!selectedScenario || loadingDatasets"
        >
          <option value="" disabled>请选择数据集</option>
          <option v-for="ds in datasetOptions" :key="ds.dataset_id" :value="ds.dataset_id">
            {{ ds.name }}（{{ ds.field_count }} 字段）
          </option>
        </select>
      </div>

      <div class="scope-field">
        <label class="form-label">模型</label>
        <select
          v-model="selectedModelId"
          class="form-input"
          :disabled="!selectedDatasetId || loadingModels || publishedModels.length === 0"
        >
          <option value="" disabled>
            {{ loadingModels ? '加载中' : publishedModels.length ? '请选择模型' : '该范围暂无已发布模型' }}
          </option>
          <option v-for="m in publishedModels" :key="m.model_version_id" :value="m.model_version_id">
            {{ modelLabel(m) }}
          </option>
        </select>
        <div v-if="selectedModel" class="model-metrics">
          <span>Acc {{ metricText('accuracy') }}</span>
          <span>Rec {{ metricText('recall') }}</span>
          <span>F1 {{ metricText('f1') }}</span>
          <span>G-mean {{ metricText('g_mean') }}</span>
        </div>
      </div>
    </section>

    <!-- ============ 2 选数据来源 ============ -->
    <section v-if="selectedModelId" class="card source-card">
      <div class="source-tabs">
        <button
          class="source-tab"
          :class="{ 'is-active': sourceTab === 'manual' }"
          @click="sourceTab = 'manual'"
        >手工录入</button>
        <button
          class="source-tab"
          :class="{ 'is-active': sourceTab === 'sample' }"
          @click="sourceTab = 'sample'"
        >样本库</button>
      </div>

      <!-- 手工录入：自己输入数据 / 批量上传 -->
      <div v-if="sourceTab === 'manual'" class="source-body">
        <div class="sub-tabs">
          <button
            class="sub-tab"
            :class="{ 'is-active': manualMode === 'input' }"
            @click="manualMode = 'input'"
          >输入数据</button>
          <button
            class="sub-tab"
            :class="{ 'is-active': manualMode === 'upload' }"
            @click="manualMode = 'upload'"
          >批量上传</button>
        </div>

        <!-- 自己输入数据 -->
        <div v-if="manualMode === 'input'" class="pane">
          <div class="pane-toolbar">
            <span class="pane-toolbar__count">共 {{ inputFields.length }} 个输入特征</span>
            <template v-if="!singleFieldGroup">
              <button class="ghost-btn" @click="expandAll">展开全部</button>
              <button class="ghost-btn" @click="collapseAll">收起全部</button>
            </template>
          </div>

          <!-- 只有一个分组：直接平铺，不要那行没有信息量的折叠头 -->
          <div v-if="singleFieldGroup" class="field-group-body">
            <div v-for="field in fieldGroups[0].fields" :key="field.field_name" class="form-group">
              <label class="form-label">
                {{ field.field_name }}
                <span v-if="field.description" class="form-label__hint">{{ field.description }}</span>
              </label>
              <input
                v-if="isNumericField(field)"
                v-model.number="inputData[field.field_name]"
                type="number"
                :step="field.field_type === FIELD_TYPE_FLOAT ? FLOAT_INPUT_STEP : INT_INPUT_STEP"
                class="form-input"
                :placeholder="stripArffQuotes(field.sample_value)"
              />
              <select
                v-else-if="field.enum_values && field.enum_values.length > 0"
                v-model="inputData[field.field_name]"
                class="form-input"
              >
                <option value="" disabled>请选择</option>
                <option v-for="opt in field.enum_values" :key="opt" :value="opt">{{ stripArffQuotes(opt) }}</option>
              </select>
              <input
                v-else
                v-model="inputData[field.field_name]"
                type="text"
                class="form-input"
                :placeholder="stripArffQuotes(field.sample_value)"
              />
            </div>
          </div>

          <el-collapse v-else v-model="expandedGroups" class="field-collapse">
            <el-collapse-item v-for="group in fieldGroups" :key="group.name" :name="group.name">
              <template #title>
                <span class="field-group-title">{{ group.name }}（{{ group.fields.length }} 字段）</span>
              </template>
              <div v-if="expandedGroups.includes(group.name)" class="field-group-body">
                <div v-for="field in group.fields" :key="field.field_name" class="form-group">
                  <label class="form-label">
                    {{ field.field_name }}
                    <span v-if="field.description" class="form-label__hint">{{ field.description }}</span>
                  </label>
                  <input
                    v-if="isNumericField(field)"
                    v-model.number="inputData[field.field_name]"
                    type="number"
                    :step="field.field_type === FIELD_TYPE_FLOAT ? FLOAT_INPUT_STEP : INT_INPUT_STEP"
                    class="form-input"
                    :placeholder="stripArffQuotes(field.sample_value)"
                  />
                  <select
                    v-else-if="field.enum_values && field.enum_values.length > 0"
                    v-model="inputData[field.field_name]"
                    class="form-input"
                  >
                    <option value="" disabled>请选择</option>
                    <option v-for="opt in field.enum_values" :key="opt" :value="opt">{{ stripArffQuotes(opt) }}</option>
                  </select>
                  <input
                    v-else
                    v-model="inputData[field.field_name]"
                    type="text"
                    class="form-input"
                    :placeholder="stripArffQuotes(field.sample_value)"
                  />
                </div>
              </div>
            </el-collapse-item>
          </el-collapse>
        </div>

        <!-- 批量上传 -->
        <div v-else class="batch-grid">
          <div class="batch-row">
            <label class="form-label">上传 CSV</label>
            <input
              ref="fileInputRef"
              type="file"
              accept=".csv"
              class="batch-row__file-input"
              @change="onFileChange"
            />
            <button
              class="upload-icon-btn"
              type="button"
              aria-label="选择 CSV 文件"
              @click="pickCsvFile"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.7"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
              >
                <path d="M12 13v8" />
                <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
                <path d="m8 17 4-4 4 4" />
              </svg>
            </button>
            <span
              class="batch-file-name"
              :class="{ 'is-empty': !uploadFile }"
              :title="uploadFile?.name"
            >{{ uploadFile ? uploadFile.name : '未选择文件' }}</span>
            <button class="infer-btn infer-btn--sm" :disabled="!canBatch || !uploadFile" @click="handleUpload">
              <span v-if="busyOn('upload')" class="btn-spinner"></span>
              {{ busyOn('upload') ? batchProgressText : '上传并研判' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 样本库：勾选若干项 / 直接前 N 项 -->
      <div v-else class="source-body">
        <div class="sample-toolbar">
          <div class="sample-toolbar__left">
            <span class="sample-toolbar__count">已选 {{ selectedCount }} 项</span>
            <button class="ghost-btn" :disabled="!samples.length" @click="invertSelection">反选</button>
            <button class="ghost-btn" :disabled="selectedCount === 0" @click="clearSelection">清空</button>
          </div>
          <div class="sample-toolbar__right">
            <span class="sample-toolbar__head">
              <span class="sample-toolbar__label">前</span>
              <input
                v-model.number="batchLimit"
                type="number"
                min="1"
                :max="MAX_BATCH_LIMIT"
                class="form-input sample-toolbar__num"
              />
              <span class="sample-toolbar__label">项</span>
            </span>
            <button class="infer-btn infer-btn--sm" :disabled="!canBatch" @click="handleBatchHead">
              <span v-if="busyOn('head')" class="btn-spinner"></span>
              {{ busyOn('head') ? batchProgressText : '研判' }}
            </button>
            <button
              class="infer-btn infer-btn--sm"
              :disabled="!canBatch || selectedCount === 0"
              @click="handleBatchSelected"
            >
              <span v-if="busyOn('selected')" class="btn-spinner"></span>
              {{ busyOn('selected') ? batchProgressText : '研判选中项' }}
            </button>
          </div>
        </div>

        <div ref="samplePaneRef" class="pane">
          <template v-if="samples.length">
            <div class="sample-table__wrap">
              <div v-if="sampleLoading" class="pane-loading"><div class="loader"></div></div>
              <table class="sample-table">
                <thead>
                  <tr>
                    <th class="sample-table__pick">
                      <input type="checkbox" :checked="pageAllSelected" @change="toggleSelectPage" />
                    </th>
                    <th class="sample-table__idx">序号</th>
                    <th v-if="labelField">{{ labelField }}</th>
                    <th v-for="col in sampleColumns" :key="col">{{ col }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, index) in samples"
                    :key="index"
                    :class="{ 'is-selected': isRowSelected(index) }"
                    @click="toggleSample(index)"
                  >
                    <td class="sample-table__pick">
                      <input type="checkbox" :checked="isRowSelected(index)" tabindex="-1" />
                    </td>
                    <td class="sample-table__idx">{{ ordinalOf(index) }}</td>
                    <td v-if="labelField">{{ row[labelField] }}</td>
                    <td v-for="col in sampleColumns" :key="col">{{ row[col] }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <!-- 翻页期间常驻（只置灰），否则条本身消失，指针下方会空掉 -->
            <div v-if="totalSamplePages > 1" class="sample-pager">
              <button
                class="ghost-btn"
                :disabled="sampleLoading || samplePage <= 1"
                @click="changeSamplePage(samplePage - 1)"
              >上一页</button>
              <span class="sample-pager__info">{{ samplePage }} / {{ totalSamplePages }}</span>
              <button
                class="ghost-btn"
                :disabled="sampleLoading || samplePage >= totalSamplePages"
                @click="changeSamplePage(samplePage + 1)"
              >下一页</button>
            </div>
          </template>
          <div v-else-if="sampleLoading" class="pane-status">正在读取样本…</div>
        </div>
      </div>
    </section>

    <!-- 执行条：必须放在 .card 外面 —— .card 有 backdrop-filter，
         它会让 position: fixed 改为相对卡片定位，fixed 就失效了。 -->
    <div
      v-if="selectedModelId && sourceTab === 'manual' && manualMode === 'input'"
      class="action-bar"
    >
      <button class="infer-btn" :disabled="inferring" @click="handleInfer">
        <span v-if="inferring" class="btn-spinner"></span>
        {{ inferring ? '推理中…' : '执行风险推理' }}
      </button>
    </div>

    <!-- ============ 3 结果（只属于发起它的那一类，切标签即消失） ============ -->
    <section v-if="resultVisible" ref="resultRef" class="card result-card">
      <!-- 批量结果 -->
      <template v-if="batchResult">
        <div class="section-heading">
          <h3>批量研判结果</h3>
          <button class="ghost-btn" @click="exportBatchCsv">导出 CSV</button>
        </div>
        <div class="batch-summary">
          <span class="batch-summary__item">共 {{ batchResult.total }} 条</span>
          <span class="batch-summary__item is-risk">风险 {{ batchResult.risk_count }}</span>
          <span class="batch-summary__item">正常 {{ batchResult.succeeded - batchResult.risk_count }}</span>
          <span v-if="batchResult.failed" class="batch-summary__item is-failed">失败 {{ batchResult.failed }}</span>
        </div>
        <div class="batch-table__wrap">
          <table class="batch-table">
            <thead>
              <tr>
                <th>序号</th><th>分类结果</th><th>风险概率</th><th>风险等级</th><th>风险事件</th><th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in batchResult.items" :key="item.index" :class="{ 'is-failed': item.error }">
                <td>{{ item.index + 1 }}</td>
                <td>
                  <span v-if="item.error" class="cell-muted">{{ item.error }}</span>
                  <span v-else :class="item.is_risk_event ? 'cell-risk' : 'cell-normal'">
                    {{ item.is_risk_event ? '风险类' : '正常类' }}
                  </span>
                </td>
                <td>{{ riskPercent(item) }}</td>
                <td>{{ levelText(item.risk_level) }}</td>
                <td>{{ item.risk_event_id ? '已生成' : UNKNOWN_TEXT }}</td>
                <td>
                  <button v-if="item.risk_event_id" class="link-btn" @click="goEventDetail(item.risk_event_id)">
                    查看事件
                  </button>
                  <span v-else class="cell-muted">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <!-- 单条结果 -->
      <template v-else-if="inferResult">
        <div class="section-heading">
          <h3>推理结果</h3>
        </div>
        <div class="inference-result__content">
          <div class="result-item">
            <span class="result-item__label">分类结果</span>
            <span
              class="result-item__value result-level-badge"
              :class="`level--${inferResult.risk_level ?? 'LOW'}`"
            >
              {{ inferResult.is_risk_event ? '风险类' : '正常类' }}
            </span>
          </div>
          <div class="result-item">
            <span class="result-item__label">预测标签</span>
            <span class="result-item__value">{{ inferResult.prediction_label }}</span>
          </div>
          <div v-if="inferResult.is_risk_event" class="result-item">
            <span class="result-item__label">风险等级</span>
            <span class="result-item__value">{{ levelText(inferResult.risk_level) }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">风险概率</span>
            <span class="result-item__value result-item__value--num">{{ singleRiskPercent }}</span>
          </div>
          <div v-if="inferResult.explain_data?.confidence" class="result-item">
            <span class="result-item__label">判断置信度</span>
            <span class="result-item__value">{{ inferResult.explain_data.confidence }}</span>
          </div>
          <div v-if="inferResult.explain_data?.top_features?.length" class="result-item result-item--features">
            <span class="result-item__label">主要影响字段</span>
            <span class="result-item__value result-item__value--features">
              <span v-for="feature in inferResult.explain_data.top_features.slice(0, TOP_FEATURE_COUNT)" :key="feature.feature_name">
                {{ feature.display_name || feature.feature_name }}={{ feature.raw_value }}（{{ feature.direction }}）
              </span>
            </span>
          </div>
          <div v-if="inferResult.is_risk_event" class="result-item">
            <span class="result-item__label">风险类型</span>
            <span class="result-item__value">{{ inferResult.risk_event?.risk_type || UNKNOWN_TEXT }}</span>
          </div>
          <div class="result-item">
            <span class="result-item__label">使用模型</span>
            <span class="result-item__value">#{{ inferResult.model_version_id }}</span>
          </div>
        </div>

        <div v-if="inferResult.is_risk_event" class="event-tip">
          <span>已生成风险事件 {{ inferResult.risk_event?.id }}</span>
          <button
            v-if="inferResult.risk_event?.id"
            class="link-btn event-tip__btn"
            @click="goEventDetail(inferResult.risk_event?.id)"
          >查看事件详情</button>
        </div>

        <div class="ai-explanation">
          <div class="ai-explanation__head">
            <h3>场景化分析</h3>
            <div class="ai-explanation__actions">
              <button v-if="explanationLoading" class="ghost-btn" type="button" @click="stopExplanation">停止生成</button>
              <button v-else class="ghost-btn" type="button" @click="inferResult && generateExplanation(inferResult)">
                {{ explanationMarkdown ? '重新生成' : '生成AI评价' }}
              </button>
            </div>
          </div>
          <p v-if="explanationLoading && !explanationMarkdown" class="ai-explanation__status">正在根据模型结果生成说明…</p>
          <p v-else-if="explanationStatus === 'stopped'" class="ai-explanation__status">已停止生成</p>
          <p v-else-if="explanationStatus === 'failed'" class="ai-explanation__status">生成失败，可重新生成</p>
          <p v-if="explanationError" class="ai-explanation__error">{{ explanationError }}</p>
          <div v-if="explanationMarkdown" class="ai-explanation__markdown" v-html="safeExplanationHtml"></div>
          <p v-if="explanationFallback" class="ai-explanation__note">当前显示平台规则模板，模型预测结果未受影响。</p>
        </div>

        <details v-if="isManager && adminExplanationJson" class="admin-explanation">
          <summary>管理员中间数据</summary>
          <pre>{{ adminExplanationJson }}</pre>
        </details>
      </template>
    </section>
  </div>
</template>

<style scoped>
.inference-page {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 20px;
  /* 给固定底栏留位置，避免盖住结果表最后几行 */
  padding-bottom: 84px;
}

.inference-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  color: #c8deff;
}

.inference-page__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

/* ---------- 1 选范围 ---------- */
.scope-bar {
  display: grid;
  gap: 18px;
  grid-template-columns: 1fr 1fr;
  align-items: start;
}

.scope-field--scenario {
  grid-column: 1 / -1;
}

.scope-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
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
  width: 100%;
  box-sizing: border-box;
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

.scenario-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.5);
  border: 1px solid rgba(125, 201, 255, 0.12);
  width: fit-content;
  flex-wrap: wrap;
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

.model-metrics {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.76rem;
  color: rgba(220, 234, 255, 0.55);
}

/* ---------- 2 数据来源 ---------- */
.source-card {
  display: grid;
  gap: 16px;
}

.source-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.5);
  border: 1px solid rgba(125, 201, 255, 0.12);
  width: fit-content;
}

.source-tab {
  border: 0;
  padding: 6px 18px;
  border-radius: 999px;
  color: rgba(220, 234, 255, 0.7);
  background: transparent;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s;
}

.source-tab:hover {
  background: rgba(91, 166, 255, 0.1);
  color: #fff;
}

.source-tab.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}

/* 标签下的内容区（手工录入 / 样本库各自一块） */
.source-body {
  display: grid;
  gap: 12px;
  min-width: 0;
}

/* 二级切换：手工录入内部「输入数据 / 批量上传」 */
.sub-tabs {
  display: flex;
  gap: 4px;
  padding: 3px;
  border-radius: 999px;
  background: rgba(8, 17, 31, 0.4);
  border: 1px solid rgba(125, 201, 255, 0.1);
  width: fit-content;
}

.sub-tab {
  border: 0;
  padding: 5px 14px;
  border-radius: 999px;
  color: rgba(220, 234, 255, 0.6);
  background: transparent;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.sub-tab:hover {
  background: rgba(91, 166, 255, 0.1);
  color: #fff;
}

.sub-tab.is-active {
  background: rgba(91, 166, 255, 0.16);
  color: #fff;
}

.pane {
  display: grid;
  gap: 12px;
  min-width: 0;
  /* 字段区内部滚动：页面不会被 279 个字段拉成 30 屏，执行条也始终留在卡片底部。
     （不用 position: sticky —— 祖先 .app-shell 有 overflow: hidden，
     它会成为 sticky 的参照容器且自身不滚动，粘不住。） */
  max-height: 46vh;
  overflow: auto;
  padding-right: 4px;
}

.pane-status {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.5);
}

.pane-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 4px 0 8px;
  background: rgba(9, 18, 32, 0.97);
}

.pane-toolbar__count {
  margin-right: auto;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
}

/* 样本库工具栏：左「已选 + 反选 / 清空」，右「前 N 项 + 两个批量入口」 */
.sample-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.sample-toolbar__left,
.sample-toolbar__right {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.sample-toolbar__count {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.5);
}

.sample-toolbar__head {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.sample-toolbar__label {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
}

.sample-toolbar__num {
  width: 52px;
  padding: 5px 6px;
  font-size: 0.8rem;
  text-align: center;
  border-radius: 7px;
}

/* 样本表 */
.sample-table__wrap {
  position: relative; /* 翻页遮罩（.pane-loading）的定位上下文 */
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 10px;
}

.sample-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.sample-table th {
  position: sticky;
  top: 0;
  background: rgba(11, 22, 40, 0.98);
  color: rgba(220, 234, 255, 0.6);
  font-weight: 500;
  text-align: left;
  padding: 9px 12px;
  white-space: nowrap;
}

.sample-table td {
  padding: 8px 12px;
  color: rgba(232, 241, 255, 0.88);
  border-top: 1px solid rgba(125, 201, 255, 0.07);
  white-space: nowrap;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sample-table tbody tr {
  cursor: pointer;
}

.sample-table tbody tr:hover {
  background: rgba(91, 166, 255, 0.07);
}

.sample-table tbody tr.is-selected {
  background: rgba(91, 166, 255, 0.14);
}

.sample-table__pick {
  width: 34px;
}

.sample-table__pick input {
  accent-color: #5ba6ff;
}

.sample-table__idx {
  width: 56px;
  color: rgba(220, 234, 255, 0.5);
}

.sample-pager {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sample-pager__info {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.6);
}

/* 字段折叠表单 */
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

/* 批量上传：标签 / 云上传图标 / 文件名 / 按钮各占一列。
   .batch-row 自己不生成盒子（display: contents），子元素直接落进 .batch-grid 的列里。 */
.batch-grid {
  display: grid;
  grid-template-columns: max-content max-content max-content max-content;
  justify-content: start;
  align-items: center;
  gap: 10px;
}

.batch-row {
  display: contents;
}

.batch-row .form-label {
  min-width: 120px;
}

/* 原生 file input 藏起来，由云上传图标按钮代它触发（见 pickCsvFile） */
.batch-row__file-input {
  display: none;
}

.upload-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  border: 1px dashed rgba(91, 166, 255, 0.35);
  background: rgba(91, 166, 255, 0.07);
  color: #9ad6ff;
  cursor: pointer;
  transition: all 0.2s;
}

.upload-icon-btn:hover {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.55);
}

.upload-icon-btn svg {
  width: 17px;
  height: 17px;
}

.batch-file-name {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.65);
}

.batch-file-name.is-empty {
  color: rgba(220, 234, 255, 0.35);
}

/* 执行条：固定在视口底部，字段再多也不用滚到底找按钮。
   不用 position: sticky —— 祖先 .app-shell 有 overflow: hidden，
   它会成为 sticky 的参照容器且自身不滚动，粘不住。 */
.action-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding: 12px 30px;
  background: rgba(9, 18, 32, 0.97);
  border-top: 1px solid rgba(125, 201, 255, 0.16);
}

/* ---------- 3 结果 ---------- */
.result-card {
  display: grid;
  gap: 16px;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.section-heading h3 {
  margin: 0;
  font-size: 1.05rem;
}

.batch-summary {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.75);
}

.batch-summary__item.is-risk {
  color: #ff8c84;
}

.batch-summary__item.is-failed {
  color: #ffd166;
}

.batch-table__wrap {
  max-height: 460px;
  overflow: auto;
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 10px;
}

.batch-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.batch-table th {
  position: sticky;
  top: 0;
  background: rgba(11, 22, 40, 0.98);
  color: rgba(220, 234, 255, 0.6);
  font-weight: 500;
  text-align: left;
  padding: 10px 14px;
  white-space: nowrap;
}

.batch-table td {
  padding: 10px 14px;
  border-top: 1px solid rgba(125, 201, 255, 0.07);
  color: #e8f1ff;
  font-variant-numeric: tabular-nums;
}

.batch-table tbody tr:hover {
  background: rgba(91, 166, 255, 0.06);
}

.cell-risk {
  color: #ff8c84;
}

.cell-normal {
  color: #53e5c8;
}

.cell-muted {
  color: rgba(220, 234, 255, 0.45);
}

.inference-result__content {
  display: grid;
  gap: 14px;
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

.result-item--features {
  align-items: flex-start;
}

.result-item__value--features {
  display: grid;
  gap: 4px;
  max-width: 70%;
  text-align: right;
  overflow-wrap: anywhere;
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

.ai-explanation {
  padding-top: 16px;
  border-top: 1px solid rgba(125, 201, 255, 0.12);
}

.ai-explanation__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
}

.ai-explanation__head h3 {
  margin: 0;
  font-size: 1.05rem;
}

.ai-explanation__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-explanation__status,
.ai-explanation__note,
.ai-explanation__error {
  margin: 8px 0;
  font-size: 0.84rem;
  line-height: 1.6;
}

.ai-explanation__status,
.ai-explanation__note {
  color: rgba(220, 234, 255, 0.58);
}

.ai-explanation__error {
  color: #ffd166;
}

.ai-explanation__markdown {
  max-height: 420px;
  overflow: auto;
  color: rgba(232, 241, 255, 0.9);
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.ai-explanation__markdown :deep(h3) {
  margin: 16px 0 6px;
  color: #e8f1ff;
  font-size: 1rem;
}

.ai-explanation__markdown :deep(p),
.ai-explanation__markdown :deep(ol),
.ai-explanation__markdown :deep(ul) {
  margin: 6px 0;
}

.ai-explanation__markdown :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
}

.admin-explanation {
  border-top: 1px solid rgba(125, 201, 255, 0.1);
  padding-top: 12px;
}

.admin-explanation summary {
  color: rgba(154, 214, 255, 0.8);
  cursor: pointer;
  font-size: 0.84rem;
}

.admin-explanation pre {
  max-height: 360px;
  margin: 10px 0 0;
  padding: 12px;
  overflow: auto;
  border: 1px solid rgba(125, 201, 255, 0.1);
  border-radius: 6px;
  background: rgba(8, 17, 31, 0.65);
  color: rgba(220, 234, 255, 0.72);
  font-size: 0.74rem;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* ---------- 通用按钮 ---------- */
.infer-btn {
  padding: 11px 26px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.infer-btn:hover {
  opacity: 0.9;
}

.infer-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 小一号：样本库工具栏里的两个批量入口，和输入框同高、颜色压轻 */
.infer-btn--sm {
  padding: 5px 12px;
  font-size: 0.78rem;
  font-weight: 500;
  border-radius: 7px;
  background: rgba(91, 166, 255, 0.16);
  border: 1px solid rgba(91, 166, 255, 0.3);
  color: #9ad6ff;
}

.infer-btn--sm:hover:not(:disabled) {
  opacity: 1;
  background: rgba(91, 166, 255, 0.26);
  border-color: rgba(91, 166, 255, 0.45);
}

.ghost-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid rgba(91, 166, 255, 0.35);
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
}

.ghost-btn:hover:not(:disabled) {
  background: rgba(91, 166, 255, 0.2);
  border-color: rgba(91, 166, 255, 0.5);
}

.ghost-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.link-btn {
  border: 0;
  background: none;
  padding: 0;
  color: #9ad6ff;
  font-size: 0.85rem;
  cursor: pointer;
}

.link-btn:hover {
  text-decoration: underline;
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

@media (max-width: 900px) {
  .scope-bar {
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
</style>
