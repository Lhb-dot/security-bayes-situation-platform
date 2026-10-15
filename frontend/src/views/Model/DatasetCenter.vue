<script setup lang="ts">
/**
 * DatasetCenter - 数据集中心页面
 *
 * 全平台数据集统一管理
 * 支持按场景筛选、数据集列表展示、数据集字段预览
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import type { Dataset, DatasetVersion, ScenarioId } from '@/types/security';
import {
  getDatasetList,
  getDatasetVersions,
  uploadDatasetFile,
  appendDatasetRows,
  getDatasetRevisions,
  disableDatasetVersion,
  deleteDatasetVersion,
  getDatasetAiAnalysis,
  streamDatasetAiAnalysis,
} from '@/api/datasetApi';
import type { DatasetRevisionItem } from '@/api/datasetApi';
import ScenarioSelector from '@/components/common/ScenarioSelector.vue';
import { useUserStore } from '@/stores/userStore';

const router = useRouter();

/** 场景名称映射（表格标签与上传弹窗选项共用） */
const SCENARIO_LABEL: Record<ScenarioId, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '舰面调度态势',
};

/** 数据格式标签（键为 Dataset.data_format 全集，取值不会落空） */
const FORMAT_LABEL: Record<Dataset['data_format'], string> = {
  csv: 'CSV',
  arff: 'ARFF',
  json: 'JSON',
};

// ===================== 状态 =====================
/** 全部数据集（缓存，用于前端筛选） */
const allDatasets = ref<Dataset[]>([]);
/** 筛选后的数据集列表（绑定表格） */
const filteredDatasets = ref<Dataset[]>([]);
/** 当前选中的场景筛选值 */
const selectedScenario = ref<ScenarioId | 'all'>('all');
/** 加载状态 */
const loading = ref(true);
/** 错误信息 */
const error = ref('');

/** current user (new uploads are available to all roles; version mutations remain admin-only) */
const userStore = useUserStore();
const isManagement = computed(() => userStore.isManagement);
const isSuperAdmin = computed(() => userStore.isSuperAdmin);
const canUpload = computed(() => Boolean(userStore.currentUser));

const uploadDialogVisible = ref(false);
const uploadForm = ref({
  dataset_id: '',
  name: '',
  scenario_id: '' as ScenarioId | '',
  label_field: '',
});
/** 上传数据集时选择的文件 */
const selectedFile = ref<File | null>(null);
/** 隐藏的原生 file input：由云上传图标按钮触发（复用 RiskInference 批量上传的交互） */
const uploadFileInputRef = ref<HTMLInputElement | null>(null);
const appendFileInputRef = ref<HTMLInputElement | null>(null);

/** 云上传图标按钮：把点击转发给隐藏的原生 file input（清空后重选同一个文件也能触发 change） */
const pickFile = (input: HTMLInputElement | null) => {
  if (!input) return;
  input.value = '';
  input.click();
};

const onFileChange = (e: Event) => {
  const input = e.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
};

const openUploadDialog = () => {
  uploadForm.value = {
    dataset_id: '',
    name: '',
    scenario_id: isSuperAdmin.value ? '' : (userStore.boundScenarioId ?? ''),
    label_field: '',
  };
  selectedFile.value = null;
  uploadDialogVisible.value = true;
};

/** 上传新数据集：选择文件 + 填标签字段，后端自动识别 ARFF/CSV 并解析字段 */
const submitNewDataset = async () => {
  if (!uploadForm.value.dataset_id.trim()) {
    ElMessage.warning('请填写数据集编码');
    return;
  }
  if (!uploadForm.value.name.trim()) {
    ElMessage.warning('请填写数据集名称');
    return;
  }
  if (!selectedFile.value) {
    ElMessage.warning('请选择要上传的 ARFF / CSV 文件');
    return;
  }
  if (!uploadForm.value.label_field.trim()) {
    ElMessage.warning('请填写标签字段名（通常是最后一列）');
    return;
  }
  try {
    await uploadDatasetFile({
      file: selectedFile.value,
      logical_id: uploadForm.value.dataset_id.trim(),
      name: uploadForm.value.name.trim(),
      scenario_id: uploadForm.value.scenario_id,
      label_field: uploadForm.value.label_field.trim(),
    });
    ElMessage.success('数据集上传成功');
    uploadDialogVisible.value = false;
    await loadDatasets();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '上传失败');
  }
};

const submitUpload = async () => {
  if (!uploadForm.value.scenario_id) {
    ElMessage.warning('必须指定所属场景');
    return;
  }
  await submitNewDataset();
};

// ===================== 追加数据（迭代：增加数据条数） =====================
// 增量文件必须与当前数据集同结构；是否新开版本由后端迭代策略决定
// （未被模型引用 → 原地更新，版本号不变；已引用 → 自动新建版本）。
const appendDialogVisible = ref(false);
const appendTarget = ref<Dataset | null>(null);
const appendFile = ref<File | null>(null);
const appendSubmitting = ref(false);

const openAppendDialog = (dataset: Dataset) => {
  appendTarget.value = dataset;
  appendFile.value = null;
  appendSubmitting.value = false;
  appendDialogVisible.value = true;
};

const onAppendFileChange = (e: Event) => {
  const input = e.target as HTMLInputElement;
  appendFile.value = input.files?.[0] ?? null;
};

const submitAppend = async () => {
  const target = appendTarget.value;
  if (!target) return;
  if (!appendFile.value) {
    ElMessage.warning('请选择要追加的增量文件（.arff / .csv）');
    return;
  }
  appendSubmitting.value = true;
  try {
    const version = await appendDatasetRows(target.dataset_id, appendFile.value);
    // 版本号变了说明后端按「已被引用」策略新开了版本，没变则是原地并入
    const rows = version.record_count.toLocaleString();
    ElMessage.success(
      version.dataset_version === target.dataset_version
        ? `追加成功：已并入 ${version.dataset_version}，共 ${rows} 条`
        : `追加成功：已新建版本 ${version.dataset_version}，共 ${rows} 条`
    );
    appendDialogVisible.value = false;
    if (versionTarget.value) {
      await loadVersionDialogData(versionTarget.value.dataset_id);
    }
    await loadDatasets();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '追加失败');
  } finally {
    appendSubmitting.value = false;
  }
};

// ===================== 版本管理（需求 2.3.3/2.3.5/2.3.6） =====================
const versionDialogVisible = ref(false);
const versionDialogTitle = ref('');
const versionTarget = ref<Dataset | null>(null);
const versionList = ref<DatasetVersion[]>([]);
const versionLoading = ref(false);
/** 迭代记录：含原地更新（不新增版本的那类迭代），版本列表看不出来，这里补齐审计视角。 */
const revisionList = ref<DatasetRevisionItem[]>([]);
const revisionLoading = ref(false);

/** 版本 + 迭代记录一起刷新（两者是同一数据集的两种视角，必须同步）。 */
const loadVersionDialogData = async (datasetId: string) => {
  try {
    versionList.value = await getDatasetVersions(datasetId);
  } catch {
    versionList.value = [];
  }
  try {
    revisionList.value = await getDatasetRevisions(datasetId);
  } catch {
    revisionList.value = [];
  }
};

const openVersionDialog = async (dataset: Dataset) => {
  versionTarget.value = dataset;
  versionDialogTitle.value = `版本管理 - ${dataset.name}`;
  // 先清空上一次的版本数据：否则打开瞬间会闪出上一个数据集的样本数/字段数，
  // 数字随请求返回再跳变，看着像「眼睛跳动」。
  versionList.value = [];
  revisionList.value = [];
  versionLoading.value = true;
  revisionLoading.value = true;
  versionDialogVisible.value = true;
  try {
    await loadVersionDialogData(dataset.dataset_id);
  } finally {
    versionLoading.value = false;
    revisionLoading.value = false;
  }
};

const handleDisableVersion = async (v: DatasetVersion) => {
  try {
    await disableDatasetVersion(v.dataset_version_id);
    ElMessage.success(`版本 ${v.dataset_version} 已停用`);
    if (versionTarget.value) {
      await loadVersionDialogData(versionTarget.value.dataset_id);
      await loadDatasets();
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '停用失败');
  }
};

const handleDeleteVersion = async (v: DatasetVersion) => {
  try {
    await deleteDatasetVersion(v.dataset_version_id);
    ElMessage.success(`版本 ${v.dataset_version} 已删除`);
    if (versionTarget.value) {
      await loadVersionDialogData(versionTarget.value.dataset_id);
      await loadDatasets();
    }
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败');
  }
};

// ===================== 数据加载 =====================
const loadDatasets = async () => {
  loading.value = true;
  error.value = '';
  try {
    const data = await getDatasetList();
    allDatasets.value = data;
    applyFilter();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据集加载失败';
  } finally {
    loading.value = false;
  }
};

/** 根据场景筛选 */
const applyFilter = () => {
  if (selectedScenario.value === 'all') {
    filteredDatasets.value = allDatasets.value;
  } else {
    filteredDatasets.value = allDatasets.value.filter(
      (d) => d.scenario_id === selectedScenario.value
    );
  }
};

/** 监听筛选变化 */
watch(selectedScenario, () => {
  applyFilter();
});

// ===================== AI 解析（算法适配，需求：判断数据集适合的算法） =====================
/** 与模型评价 / 推理解释共用同一套 SSE 协议：start → (reasoning | delta)* → done。 */
const aiDialogVisible = ref(false);
const aiDialogTitle = ref('');
const aiDialogLoading = ref(false);
/** 已尝试读取过历史结果（含「确实没有」），避免重复请求。 */
const aiDialogLoaded = ref(false);
const aiDialogStatus = ref('');
const aiDialogError = ref('');
const aiDialogReasoning = ref('');
const aiDialogMarkdown = ref('');
const aiDialogDatasetId = ref<string | number>('');
const aiBodyRef = ref<HTMLElement | null>(null);
const aiReasoningRef = ref<HTMLElement | null>(null);
let aiAbort: AbortController | null = null;

const aiDialogHtml = computed(() =>
  aiDialogMarkdown.value
    ? DOMPurify.sanitize(marked.parse(aiDialogMarkdown.value, { async: false }) as string)
    : ''
);

/** 生成期间把可滚动容器钉在底部，让最新的思考链 / 正文始终可见。 */
const stickAiToBottom = () => {
  if (!aiDialogLoading.value) return;
  void nextTick(() => {
    // 弹窗本体固定，滚动落在 el-dialog__body 上，这里取它的滚动容器。
    const body = aiBodyRef.value?.closest('.el-dialog__body') as HTMLElement | null;
    for (const el of [body, aiReasoningRef.value]) {
      if (el) el.scrollTop = el.scrollHeight;
    }
  });
};

watch([aiDialogReasoning, aiDialogMarkdown], stickAiToBottom);

/** 打开弹窗时读取已保存的解析结果，不触发 AI；没有历史则留给空状态呈现。 */
const loadAiAnalysis = async () => {
  if (!aiDialogDatasetId.value || aiDialogLoaded.value) return;
  aiDialogStatus.value = '';
  aiDialogError.value = '';
  try {
    const response = await getDatasetAiAnalysis(aiDialogDatasetId.value);
    if (response.available && response.markdown) {
      aiDialogMarkdown.value = response.markdown;
      aiDialogReasoning.value = '';
    }
  } catch (err) {
    aiDialogError.value = err instanceof Error ? err.message : '读取解析结果失败';
  } finally {
    aiDialogLoaded.value = true;
  }
};

const runAiAnalysis = async (regenerate = false) => {
  if (!aiDialogDatasetId.value || aiDialogLoading.value) return;
  aiAbort?.abort();
  const controller = new AbortController();
  aiAbort = controller;
  aiDialogLoading.value = true;
  aiDialogError.value = '';
  aiDialogReasoning.value = '';
  if (regenerate) aiDialogMarkdown.value = '';
  aiDialogStatus.value = regenerate ? '正在重新解析数据集...' : '正在解析数据集...';
  try {
    await streamDatasetAiAnalysis(
      aiDialogDatasetId.value,
      {
        onStart: (data) => {
          aiDialogStatus.value = String(data.status ?? '正在解析数据集...');
        },
        // 推理型模型的思维链只用于「正在生成」的反馈，不并入正文。
        onReasoning: (content) => {
          aiDialogReasoning.value += content;
        },
        onDelta: (content) => {
          // 正文一到就清空思考链：它只负责让用户看到「确实在生成」，不留在结果里。
          if (aiDialogReasoning.value) aiDialogReasoning.value = '';
          aiDialogMarkdown.value += content;
        },
        onError: (message) => {
          aiDialogError.value = message;
        },
        onDone: () => {
          // 生成结束即清空状态条，正文自己会呈现结果。
          aiDialogStatus.value = '';
          aiDialogLoaded.value = true;
          stickAiToBottom();
        },
      },
      controller.signal,
    );
  } catch (err) {
    if ((err as { name?: string })?.name === 'AbortError') return;
    aiDialogError.value = err instanceof Error ? err.message : 'AI 解析失败';
    aiDialogStatus.value = '';
    aiDialogReasoning.value = '';
  } finally {
    if (aiAbort === controller) {
      aiDialogLoading.value = false;
      aiAbort = null;
    }
  }
};

const openAiAnalysis = (dataset: Dataset) => {
  aiAbort?.abort();
  aiAbort = null;
  aiDialogTitle.value = `AI 解析 - ${dataset.name}`;
  aiDialogDatasetId.value = dataset.dataset_id;
  aiDialogLoading.value = false;
  aiDialogLoaded.value = false;
  aiDialogStatus.value = '';
  aiDialogError.value = '';
  aiDialogReasoning.value = '';
  aiDialogMarkdown.value = '';
  aiDialogVisible.value = true;
  void loadAiAnalysis();
};

const closeAiAnalysis = () => {
  aiAbort?.abort();
  aiAbort = null;
  aiDialogLoading.value = false;
};

onBeforeUnmount(() => {
  aiAbort?.abort();
  aiAbort = null;
});

/** 跳转数据集详情页，并打开字段结构或数据内容页签。 */
const goDatasetDetail = (dataset: Dataset, tab: 'fields' | 'preview') => {
  router.push({ path: `/datasets/${dataset.dataset_id}`, query: { tab } });
};

// ===================== 生命周期 =====================
onMounted(async () => {
  if (!userStore.initialized) {
    await userStore.bootstrap();
  }
  // 管理员/用户：默认固定自己场景（不显示下拉）
  if (!userStore.isSuperAdmin) {
    const bound = userStore.boundScenarioId ?? userStore.currentUser?.scenario_ids?.[0];
    if (bound) selectedScenario.value = bound;
  }
  void loadDatasets();
});
</script>

<template>
  <div class="dataset-center">
    <!-- 页面头部 -->
    <div class="dataset-center__header">
      <div>
        <p class="eyebrow">Dataset Center</p>
        <h2>数据集中心</h2>
        <p class="dataset-center__desc">管理各场景数据集及其样本数据</p>
      </div>
      <button v-if="canUpload" class="upload-btn" @click="openUploadDialog">+ 上传数据集</button>
    </div>

    <!-- 筛选栏：系统管理员可切换场景；管理员/用户固定自己场景（场景名在顶栏头像上方显示） -->
    <div class="dataset-center__toolbar">
      <ScenarioSelector v-if="isSuperAdmin" v-model="selectedScenario" />
      <span class="dataset-center__count">
        共 <strong>{{ filteredDatasets.length }}</strong> 个数据集
      </span>
    </div>

    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载数据集...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadDatasets">重试</button>
    </section>

        <!-- 数据集表格 -->
    <div v-else class="dataset-center__table-wrap">
      <el-table
        :data="filteredDatasets"
        stripe
        style="width: 100%"
        empty-text="暂无数据集"
        row-class-name="dataset-table-row"
      >
        <el-table-column
          prop="name"
          label="数据集名称"
          min-width="190"
          show-overflow-tooltip
        >
          <template #default="{ row }: { row: Dataset }">
            <span class="dataset-table__name">{{ row.name }}</span>
          </template>
        </el-table-column>

        <el-table-column label="所属场景" width="130" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span class="dataset-table__scenario-tag">{{ SCENARIO_LABEL[row.scenario_id] ?? row.scenario_id }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="data_format" label="格式" width="80" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span
              class="format-badge"
              :class="`format-badge--${row.data_format}`"
            >
              {{ FORMAT_LABEL[row.data_format] ?? row.data_format.toUpperCase() }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="record_count" label="数据量" width="100" align="right" sortable>
          <template #default="{ row }: { row: Dataset }">
            <span class="dataset-table__number">{{ row.record_count.toLocaleString() }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="field_count" label="字段数" width="100" align="center" sortable />

        <el-table-column label="版本" width="110" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span class="version-badge" :class="row.enabled ? 'version-badge--on' : 'version-badge--off'">
              {{ row.dataset_version }}{{ row.enabled ? '' : '（停用）' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="120" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span class="dataset-table__time">{{ row.created_at.slice(0, 10) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="360" align="center" fixed="right">
          <template #default="{ row }: { row: Dataset }">
            <div class="dataset-ops">
              <el-button size="small" plain @click="goDatasetDetail(row, 'fields')">
                字段预览
              </el-button>
              <el-button size="small" plain @click="goDatasetDetail(row, 'preview')">
                数据预览
              </el-button>
              <el-button size="small" plain @click="openAiAnalysis(row)">
                AI解析
              </el-button>
              <el-button v-if="isManagement" size="small" plain @click="openVersionDialog(row)">
                版本管理
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- AI 解析弹窗（算法适配；append-to-body 防 topbar 遮挡） -->
    <el-dialog
      v-model="aiDialogVisible"
      :title="aiDialogTitle"
      width="760px"
      top="6vh"
      append-to-body
      class="ai-analysis-dialog"
      :close-on-click-modal="false"
      @close="closeAiAnalysis"
    >
      <div ref="aiBodyRef" class="ai-analysis">
        <div v-if="aiDialogError" class="ai-analysis__notice ai-analysis__notice--error">
          {{ aiDialogError }}
        </div>
        <div v-if="aiDialogStatus" class="ai-analysis__status">{{ aiDialogStatus }}</div>

        <div v-if="aiDialogReasoning" class="ai-analysis__reasoning">
          <div class="ai-analysis__reasoning-label">模型推理中</div>
          <div ref="aiReasoningRef" class="ai-analysis__reasoning-text">{{ aiDialogReasoning }}</div>
        </div>

        <div v-if="aiDialogHtml" class="ai-analysis__markdown" v-html="aiDialogHtml"></div>
        <div
          v-else-if="!aiDialogLoading && !aiDialogReasoning && !aiDialogStatus"
          class="ai-analysis__empty"
        >
          暂无解析。点击「解析」调用 AI，判断该数据集适合使用的算法。
        </div>
      </div>
      <template #footer>
        <el-button @click="aiDialogVisible = false">关闭</el-button>
        <el-button
          type="primary"
          :disabled="aiDialogLoading"
          @click="runAiAnalysis(Boolean(aiDialogMarkdown))"
        >
          {{ aiDialogMarkdown ? '重新解析' : '解析' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 上传数据集弹窗（管理员，需求 2.3.2；append-to-body 防 topbar 遮挡） -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传数据集"
      width="680px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="upload-form">
        <div class="upload-form__row">
          <label class="upload-form__label">数据集编码<span class="required">*</span></label>
          <input v-model.trim="uploadForm.dataset_id" class="upload-form__input" placeholder="如 my_dataset_01" />
        </div>
        <div class="upload-form__row">
          <label class="upload-form__label">数据集名称<span class="required">*</span></label>
          <input v-model.trim="uploadForm.name" class="upload-form__input" placeholder="如 My Dataset" />
        </div>
        <div class="upload-form__row">
          <label class="upload-form__label">所属场景<span class="required">*</span></label>
          <select v-model="uploadForm.scenario_id" class="upload-form__input" :disabled="!isSuperAdmin">
            <option value="" disabled>-- 请选择场景 --</option>
            <option value="network_security">网络安全</option>
            <option value="power_system">电力系统</option>
            <option value="flightdeck_operation">舰面调度态势</option>
            <option value="geological_risk">地质风险</option>
          </select>
        </div>
        <!-- 文件选择 + 标签字段（后端自动识别 ARFF/CSV 并解析字段） -->
        <div class="upload-form__row">
          <label class="upload-form__label">数据文件<span class="required">*</span>（.arff / .csv）</label>
          <div class="upload-picker">
            <!-- 原生 file input 藏起来，由云上传图标按钮代它触发（与 RiskInference 批量上传同一交互） -->
            <input
              ref="uploadFileInputRef"
              type="file"
              accept=".arff,.csv"
              class="upload-picker__input"
              @change="onFileChange"
            />
            <button class="upload-icon-btn" type="button" aria-label="选择数据文件" @click="pickFile(uploadFileInputRef)">
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
            <span class="upload-picker__name" :class="{ 'is-empty': !selectedFile }">
              {{ selectedFile ? `${selectedFile.name}（${(selectedFile.size / 1024).toFixed(1)} KB）` : '未选择文件' }}
            </span>
          </div>
        </div>
        <div class="upload-form__row">
          <label class="upload-form__label">标签字段名<span class="required">*</span></label>
          <input v-model.trim="uploadForm.label_field" class="upload-form__input" placeholder="通常是最后一列，如 label / class / Collision" />
        </div>
      </div>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUpload">确认上传</el-button>
      </template>
    </el-dialog>

    <!-- 版本管理弹窗（管理员，需求 2.3.3 / 2.3.5 / 2.3.6；append-to-body 防 topbar 遮挡） -->
    <el-dialog
      v-model="versionDialogVisible"
      :title="versionDialogTitle"
      class="version-dialog"
      width="1100px"
      align-center
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="version-dialog-toolbar">
        <el-button
          v-if="versionTarget"
          size="small"
          plain
          @click="openAppendDialog(versionTarget)"
        >
          追加数据
        </el-button>
      </div>
      <el-table
        :data="versionList"
        class="version-dialog__table"
        max-height="var(--version-pane-max-h)"
        stripe
        style="width: 100%"
        :empty-text="versionLoading ? '加载中…' : '暂无版本记录'"
      >
        <el-table-column prop="dataset_version" label="版本" min-width="80" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            <span class="version-badge" :class="row.enabled ? 'version-badge--on' : 'version-badge--off'">
              {{ row.dataset_version }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="变更类型" min-width="150" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            <span v-if="row.change_type_label" class="iteration-tag">
              {{ row.change_type_label }}
              <span
                v-if="row.is_breaking"
                class="iteration-tag__flag iteration-tag__flag--breaking"
                title="破坏结构兼容：旧模型不可直接复用"
              >不兼容</span>
              <span
                v-else
                class="iteration-tag__flag iteration-tag__flag--compatible"
                title="兼容变更：旧模型仍可使用"
              >兼容</span>
            </span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="样本数" min-width="100" align="right">
          <template #default="{ row }: { row: DatasetVersion }">
            {{ row.record_count.toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column prop="field_count" label="字段数" min-width="90" align="center" />
        <el-table-column prop="uploader_name" label="上传人" min-width="110" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            {{ row.uploader_name || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="uploaded_at" label="上传时间" min-width="180" />
        <el-table-column prop="referenced" label="引用" min-width="90" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            <span :class="row.referenced ? 'text-active' : 'text-muted'">{{ row.referenced ? '是' : '否' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="150" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            <div class="dataset-ops">
              <el-button
                v-if="row.enabled"
                size="small"
                plain
                @click="handleDisableVersion(row)"
              >
                停用
              </el-button>
              <el-button
                v-if="!row.referenced"
                size="small"
                type="danger"
                plain
                @click="handleDeleteVersion(row)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 迭代记录：含「原地更新」（不新增版本）的迭代，补齐版本列表看不到的审计视角 -->
      <div class="revision-history__title">迭代记录</div>
      <div class="revision-history">
        <p v-if="revisionLoading" class="version-tip">加载中…</p>
        <p v-else-if="revisionList.length === 0" class="version-tip">暂无迭代记录</p>
        <ul v-else class="revision-history__list">
          <li v-for="item in revisionList" :key="item.id" class="revision-history__item">
            <span class="revision-history__time">
              {{ item.created_at ? item.created_at.replace('T', ' ').slice(0, 19) : '—' }}
            </span>
            <span class="iteration-tag">
              {{ item.change_type_label }}
              <span
                v-if="item.is_breaking"
                class="iteration-tag__flag iteration-tag__flag--breaking"
              >不兼容</span>
              <span v-else class="iteration-tag__flag iteration-tag__flag--compatible">兼容</span>
            </span>
            <span class="revision-history__mode">
              {{ item.mode === 'new_version' ? '新建版本' : '原地更新' }}
            </span>
            <span class="revision-history__summary">{{ item.summary || item.reason || '—' }}</span>
          </li>
        </ul>
      </div>
    </el-dialog>

    <!-- 追加数据弹窗（迭代：增加数据条数；同结构增量文件，是否新开版本由后端策略决定） -->
    <el-dialog
      v-model="appendDialogVisible"
      :title="`追加数据 - ${appendTarget?.name ?? ''}`"
      width="560px"
      align-center
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="upload-form">
        <p class="version-tip">
          增量文件必须与当前数据集<strong>同结构</strong>（字段名同名同序，格式一致）。
          未被模型引用时直接并入当前版本（版本号不变）；已被引用时自动新建版本，旧版本保留。
        </p>
        <div class="upload-form__row">
          <label class="upload-form__label">增量文件<span class="required">*</span>（.arff / .csv）</label>
          <div class="upload-picker">
            <!-- 原生 file input 藏起来，由云上传图标按钮代它触发（与 RiskInference 批量上传同一交互） -->
            <input
              ref="appendFileInputRef"
              type="file"
              accept=".arff,.csv"
              class="upload-picker__input"
              @change="onAppendFileChange"
            />
            <button class="upload-icon-btn" type="button" aria-label="选择增量文件" @click="pickFile(appendFileInputRef)">
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
            <span class="upload-picker__name" :class="{ 'is-empty': !appendFile }">
              {{ appendFile ? `${appendFile.name}（${(appendFile.size / 1024).toFixed(1)} KB）` : '未选择文件' }}
            </span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="appendDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="appendSubmitting" @click="submitAppend">确认追加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.dataset-center {
  position: relative;
  z-index: 1;
}

.dataset-center__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.dataset-center__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  color: #c8deff;
}

.dataset-center__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

/* 工具栏 */
.dataset-center__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.dataset-center__count {
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.6);
  white-space: nowrap;
}

.dataset-center__count strong {
  color: #9ad6ff;
}

/* 表格外层容器 */
.dataset-center__table-wrap {
  border: 1px solid rgba(125, 201, 255, 0.10);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(8, 18, 34, 0.7);
}

/* 表格行样式覆盖 Element Plus 暗色主题 */
.dataset-table-row {
  background: transparent !important;
}

/* 名称列（原始文件名，超长由列的 show-overflow-tooltip 截断并给悬浮提示） */
.dataset-table__name {
  font-weight: 600;
  color: #c8deff;
  font-size: 0.95rem;
}

/* 场景标签 */
.dataset-table__scenario-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  background: rgba(91, 166, 255, 0.10);
  color: rgba(155, 195, 240, 0.8);
}

/* 数字列 */
.dataset-table__number {
  font-variant-numeric: tabular-nums;
  font-weight: 600;
  color: #b8ceef;
}

/* 时间列 */
.dataset-table__time {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.65);
}

/* AI 解析弹窗（与模型评价正文同款排版） */
.ai-analysis__status,
.ai-analysis__notice,
.ai-analysis__empty {
  margin-bottom: 14px;
  padding: 10px 12px;
  border-radius: 7px;
  background: rgba(91, 166, 255, 0.08);
  color: rgba(220, 234, 255, 0.72);
  font-size: 0.84rem;
}

.ai-analysis__notice--error {
  background: rgba(255, 123, 114, 0.1);
  color: #ffaaa3;
}

.ai-analysis__reasoning {
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  border-radius: 8px;
  background: rgba(10, 22, 40, 0.5);
}

.ai-analysis__reasoning-label {
  margin-bottom: 6px;
  color: rgba(154, 214, 255, 0.72);
  font-size: 0.78rem;
}

.ai-analysis__reasoning-text {
  max-height: 200px;
  overflow: auto;
  color: rgba(196, 214, 240, 0.66);
  font-size: 0.85rem;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.ai-analysis__markdown {
  padding-top: 4px;
  color: rgba(232, 241, 255, 0.88);
  font-size: 0.9rem;
  line-height: 1.7;
}

.ai-analysis__markdown :deep(h1),
.ai-analysis__markdown :deep(h2),
.ai-analysis__markdown :deep(h3) {
  margin: 16px 0 8px;
  color: #d9e8ff;
  font-size: 1rem;
}

.ai-analysis__markdown :deep(p),
.ai-analysis__markdown :deep(ul),
.ai-analysis__markdown :deep(ol) {
  margin: 7px 0;
}

.ai-analysis__markdown :deep(code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: rgba(8, 17, 31, 0.65);
  color: #9ad6ff;
}

.ai-analysis__markdown :deep(strong) {
  color: #eaf3ff;
}

/* 格式徽章 */
.format-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.format-badge--arff {
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
}

.format-badge--csv {
  background: rgba(83, 229, 200, 0.10);
  color: #6fe8d0;
}

.format-badge--json {
  background: rgba(154, 128, 255, 0.12);
  color: #b8a8ff;
}

/* 文本颜色 */
.text-muted {
  color: rgba(220, 234, 255, 0.45);
}

.text-active {
  color: #53e5c8;
}

/* 上传按钮 */
.upload-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.upload-btn:hover {
  opacity: 0.9;
}

.dataset-ops {
  display: flex;
  gap: 6px;
  justify-content: center;
  align-items: center;
}

/* 三个操作按钮：暗色背景 + 圆角 */
.dataset-ops .el-button {
  border-radius: 999px;
  border: 1px solid rgba(91, 166, 255, 0.35);
  background: rgba(91, 166, 255, 0.14);
  color: #9ad6ff;
  font-size: 0.78rem;
}
/* 去掉 Element Plus 默认的相邻按钮左边距（12px），让间距只由上面的 flex gap 控制 */
.dataset-ops .el-button + .el-button {
  margin-left: 0;
}
.dataset-ops .el-button:hover {
  background: rgba(91, 166, 255, 0.26);
  border-color: rgba(91, 166, 255, 0.55);
  color: #fff;
}

/* 版本徽章 */
.version-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  white-space: nowrap;
}

.version-badge--on {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.version-badge--off {
  background: rgba(220, 234, 255, 0.08);
  color: rgba(220, 234, 255, 0.5);
}

/* 迭代类型标签：类型名 + 兼容性徽标（区分「改字段」与「加数据」等迭代） */
.iteration-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.82);
  white-space: nowrap;
}

.iteration-tag__flag {
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 0.7rem;
}

.iteration-tag__flag--compatible {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.iteration-tag__flag--breaking {
  background: rgba(255, 176, 122, 0.14);
  color: #ffb07a;
}

/* 迭代记录：版本表下方的紧凑审计列表（原地更新不进版本表，只能在这里看到）。
   标题在框外当小标题，框内只有记录；框的高度上限由弹窗统一给定（见 .version-dialog）。 */
.revision-history__title {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.72);
  margin-bottom: 6px;
}

.revision-history {
  display: flex;
  flex-direction: column;
  border: 1px solid rgba(220, 234, 255, 0.1);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  padding: 10px 12px;
}

.revision-history .version-tip {
  margin: 0;
}

.revision-history__list {
  list-style: none;
  margin: 0;
  padding: 0 4px 0 0;
  /* 记录很多时框内自身上下滚动，不把弹窗撑出屏幕 */
  overflow-y: auto;
  min-height: 0;
}

.revision-history__item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.72);
  border-bottom: 1px dashed rgba(220, 234, 255, 0.06);
}

.revision-history__time {
  flex: 0 0 auto;
  color: rgba(220, 234, 255, 0.5);
}

.revision-history__mode {
  flex: 0 0 auto;
  color: rgba(220, 234, 255, 0.6);
}

.revision-history__summary {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 上传表单 */
.upload-form {
  display: grid;
  gap: 14px;
}

.upload-form__row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.upload-form__label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.upload-form__label .required {
  color: #ff7b72;
  margin-left: 2px;
}

.upload-form__input {
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.7);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
}

.upload-form__input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.upload-form__input option {
  background: #0b1628;
  color: #e8f1ff;
}

/* 增量文件选择：隐藏原生 file input（原生控件悬停会冒出「未选择文件」提示），
   改由云上传图标按钮触发 —— 与 RiskInference 批量上传复用同一套按钮样式。 */
.upload-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  border-radius: 8px;
  background: rgba(8, 17, 31, 0.7);
}

.upload-picker__input {
  display: none;
}

.upload-picker__name {
  min-width: 0;
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-picker__name.is-empty {
  color: rgba(220, 234, 255, 0.4);
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
  flex-shrink: 0;
}

.upload-icon-btn:hover {
  background: rgba(91, 166, 255, 0.18);
  border-color: rgba(91, 166, 255, 0.55);
}

.version-tip {
  margin: 12px 0 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.5);
  line-height: 1.6;
}

.version-dialog-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
}
</style>

<!-- 全局覆盖：Element Plus 暗色表格样式 -->
<style>
.dataset-center .el-table,
.dataset-center .el-table__inner-wrapper,
.dataset-center .el-table__body-wrapper,
.dataset-center .el-table__header-wrapper {
  background-color: transparent !important;
}

.dataset-center .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.dataset-center .el-table td.el-table__cell {
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.dataset-center .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: rgba(10, 24, 44, 0.85) !important;
}

.dataset-center .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
}

.dataset-center .el-table__empty-text {
  color: rgba(180, 200, 235, 0.3) !important;
}

/* Element Plus 弹窗暗色样式 */
.dataset-center .el-dialog {
  background: linear-gradient(180deg, rgba(11, 22, 40, 0.98), rgba(5, 12, 22, 0.98)) !important;
  border: 1px solid rgba(125, 201, 255, 0.18) !important;
  border-radius: 20px !important;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5) !important;
}

.dataset-center .el-dialog__title {
  color: #e8f1ff !important;
  font-size: 1.15rem !important;
}

.dataset-center .el-dialog__headerbtn .el-dialog__close {
  color: rgba(220, 234, 255, 0.5) !important;
}

.dataset-center .el-dialog__headerbtn:hover .el-dialog__close {
  color: #e8f1ff !important;
}

.dataset-center .el-dialog__body {
  padding: 20px 24px !important;
}

/* AI 解析弹窗（append-to-body，不在 .dataset-center 内）：弹窗本体固定不滚动，只有正文区域滚动 */
.ai-analysis-dialog {
  display: flex;
  flex-direction: column;
  max-height: 86vh;
  margin-bottom: 0 !important;
  overflow: hidden;
}

.ai-analysis-dialog .el-dialog__header,
.ai-analysis-dialog .el-dialog__footer {
  flex: 0 0 auto;
}

.ai-analysis-dialog .el-dialog__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

/* Element Plus 按钮暗色 */
.dataset-center .el-button--primary.is-plain {
  --el-button-bg-color: rgba(91, 166, 255, 0.14) !important;
  --el-button-border-color: rgba(91, 166, 255, 0.35) !important;
  --el-button-text-color: #9ad6ff !important;
  --el-button-hover-bg-color: rgba(91, 166, 255, 0.22) !important;
  --el-button-hover-border-color: rgba(91, 166, 255, 0.5) !important;
  --el-button-hover-text-color: #bae3ff !important;
}

/* 版本管理弹窗（append-to-body，不在 .dataset-center 内）：
   加宽避免表格横向滚动；整体高度受限于视口并垂直居中。
   上下两块（版本表 / 迭代记录）各自最多占「弹窗最大高度」的一半，多出来的部分
   在各自区域内滚动，因此弹窗永远不会超出屏幕。 */
.version-dialog {
  /* 88vh 扣掉标题、工具栏、小标题与间距等固定开销后对半分。
     版本表的 max-height 通过属性绑定同一个变量：只有走 Element Plus 的 max-height
     属性，表格内部才会正确感知纵向滚动条并补上表头占位列。 */
  --version-pane-max-h: calc((88vh - 220px) / 2);
  display: flex;
  flex-direction: column;
  max-width: 96vw;
  max-height: 88vh;
  overflow: hidden;
}

.version-dialog .el-dialog__header {
  flex: 0 0 auto;
}

/* 正文撑满剩余高度：版本表占满可用空间并在表内滚动，迭代记录框固定在底部。 */
.version-dialog .el-dialog__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
}

.version-dialog .revision-history {
  max-height: var(--version-pane-max-h);
}

</style>
