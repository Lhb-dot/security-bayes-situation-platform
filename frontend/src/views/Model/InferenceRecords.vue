<script setup lang="ts">
/**
 * InferenceRecords - 推理记录
 *
 * 需求 6.2（P0）：普通用户只能查询本人推理记录；管理员可以查询平台全部推理记录。
 * 需求 6.8.4：管理员查看单个用户数据时，可以按用户ID筛选。
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import {
  getInferenceExplain,
  getInferenceRecordList,
  streamInferenceExplanation,
} from '@/api/inferenceRecordApi';
import { useUserStore } from '@/stores/userStore';

/** 真实推理记录（后端 /api/v1/inference-records 返回结构，含补全展示字段） */
interface InferenceRecordItem {
  id: number;
  user_id: number;
  model_version_id: number;
  scenario_id: number;
  scenario_code: string | null;
  algorithm_id: number;
  algorithm_name: string | null;
  dataset_id: number;
  dataset_logical_id: string | null;
  dataset_name: string | null;
  dataset_version: number;
  risk_type: string | null;
  original_label: string;
  prediction_label: string;
  risk_level: string | null;
  risk_score: number | null;
  is_risk_event: boolean;
  executed_at: string;
  risk_event_id: number | null;
  input_features: Record<string, unknown>;
  model_evaluation?: {
    available: boolean;
    source: 'ai' | 'fallback' | null;
    markdown: string | null;
    generated_at: string | null;
  };
}

const records = ref<InferenceRecordItem[]>([]);
const loading = ref(false);
const router = useRouter();
const userStore = useUserStore();

/** 是否管理员（决定描述文案） */
const isAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN' || userStore.currentUser?.role === 'SCENARIO_ADMIN');

/** 场景数字 ID → 名称 */
const SCENARIO_META: Record<number, { code: string; name: string }> = {
  1: { code: 'network_security', name: '网络安全' },
  2: { code: 'power_system', name: '电力系统' },
  3: { code: 'flightdeck_operation', name: '航母甲板作业' },
  4: { code: 'geological_risk', name: '地质风险' },
};
const scenarioName = (id: number) => SCENARIO_META[id]?.name ?? String(id);

/**
 * 算法显示名统一为「中文名(英文缩写)」（见 alembic 20260822_000006），
 * 例如「双视图示例加权朴素贝叶斯(DIWNB)」。列表列宽有限，只展示括号里的英文缩写，
 * 完整名称通过 title 悬浮查看。格式不含括号时原样返回。
 */
const algorithmShortName = (name: string | null) => {
  const matched = /\(([^()]+)\)\s*$/.exec(name ?? '');
  return matched ? matched[1] : name || '—';
};

const loadRecords = async () => {
  loading.value = true;
  try {
    const items = await getInferenceRecordList({ page_size: 200 });
    records.value = items as unknown as InferenceRecordItem[];
  } finally {
    loading.value = false;
  }
};

// 查看输入特征
const featureTarget = ref<InferenceRecordItem | null>(null);
const featureDialogVisible = ref(false);
const openFeatures = (r: InferenceRecordItem) => {
  featureTarget.value = r;
  featureDialogVisible.value = true;
};

const featureRows = computed(() =>
  featureTarget.value
    ? Object.entries(featureTarget.value.input_features ?? {}).map(([name, value]) => ({
        name,
        value: value == null ? '—' : String(value),
      }))
    : [],
);

const closeFeatures = () => {
  featureDialogVisible.value = false;
  featureTarget.value = null;
};

const explanationTarget = ref<InferenceRecordItem | null>(null);
const explanationDialogVisible = ref(false);
const explanationLoading = ref(false);
const explanationMarkdown = ref('');
const explanationSource = ref<'ai' | 'fallback' | null>(null);
const explanationGeneratedAt = ref<string | null>(null);
const explanationError = ref('');
const modelEvaluationMarkdown = ref('');
const explanationWasAvailable = ref(false);
const explanationGenerating = ref(false);
let explanationController: AbortController | null = null;

const safeExplanationHtml = computed(() =>
  explanationMarkdown.value
    ? DOMPurify.sanitize(marked.parse(explanationMarkdown.value, { async: false }) as string)
    : '',
);

const safeModelEvaluationHtml = computed(() =>
  modelEvaluationMarkdown.value
    ? DOMPurify.sanitize(marked.parse(modelEvaluationMarkdown.value, { async: false }) as string)
    : '',
);

const openExplanation = async (record: InferenceRecordItem) => {
  explanationController?.abort();
  explanationTarget.value = record;
  explanationDialogVisible.value = true;
  explanationLoading.value = true;
  explanationMarkdown.value = '';
  explanationSource.value = null;
  explanationGeneratedAt.value = null;
  explanationError.value = '';
  modelEvaluationMarkdown.value = record.model_evaluation?.markdown ?? '';
  explanationWasAvailable.value = false;
  explanationGenerating.value = false;
  try {
    const result = await getInferenceExplain(String(record.id));
    const saved = result.generated_explanation;
    explanationWasAvailable.value = Boolean(saved?.available && saved.markdown);
    if (!saved?.available || !saved.markdown) {
      explanationError.value = '该记录尚未保存解释文本，请点击右上角生成AI评价。';
      return;
    }
    explanationMarkdown.value = saved.markdown;
    explanationSource.value = saved.source ?? null;
    explanationGeneratedAt.value = saved.generated_at ?? null;
  } catch (err) {
    explanationError.value = err instanceof Error ? err.message : '解释文本读取失败';
  } finally {
    explanationLoading.value = false;
  }
};

const generateExplanation = async () => {
  const target = explanationTarget.value;
  if (!target || explanationLoading.value) return;

  explanationController?.abort();
  explanationController = new AbortController();
  explanationLoading.value = true;
  explanationGenerating.value = true;
  explanationError.value = '';
  explanationMarkdown.value = '';
  explanationSource.value = null;
  explanationGeneratedAt.value = null;

  try {
    await streamInferenceExplanation(
      {
        scenario: {},
        sample: {},
        model_result: {},
        algorithm_details: {},
        recommended_actions: [],
        inference_record_id: target.id,
        model_version_id: target.model_version_id,
      },
      {
        onDelta: (content) => { explanationMarkdown.value += content; },
        onError: (message) => { explanationError.value = message; },
      },
      explanationController.signal,
    );

    const refreshed = await getInferenceExplain(String(target.id));
    const saved = refreshed.generated_explanation;
    if (!saved?.available || !saved.markdown) {
      throw new Error('AI评价生成后未能保存，请稍后重试');
    }
    explanationMarkdown.value = saved.markdown;
    explanationSource.value = saved.source ?? null;
    explanationGeneratedAt.value = saved.generated_at ?? null;
    explanationWasAvailable.value = true;
  } catch (err) {
    if ((err as Error)?.name !== 'AbortError') {
      explanationError.value = err instanceof Error ? err.message : 'AI评价生成失败';
    }
  } finally {
    explanationLoading.value = false;
    explanationGenerating.value = false;
    explanationController = null;
  }
};

const closeExplanation = () => {
  explanationController?.abort();
  explanationController = null;
  explanationDialogVisible.value = false;
  explanationTarget.value = null;
  explanationMarkdown.value = '';
  modelEvaluationMarkdown.value = '';
  explanationWasAvailable.value = false;
  explanationGenerating.value = false;
};

/** 风险记录 → 跳转风险事件详情 */
const goEventDetail = (r: InferenceRecordItem) => {
  if (r.risk_event_id == null) {
    ElMessage.info('该记录未生成风险事件');
    return;
  }
  router.push({ path: `/events/${r.risk_event_id}` });
};

onMounted(() => {
  loadRecords();
});
</script>

<template>
  <div class="records-page">
    <div class="records-page__header">
      <div>
        <p class="eyebrow">Inference Records</p>
        <h2>推理记录</h2>
        <p class="records-page__desc">
          {{ isAdmin ? '平台全部推理记录（可筛选用户）' : '仅显示本人发起的推理记录' }}
        </p>
      </div>
    </div>

    <section class="card records-section">
      <div class="records-table-wrap">
        <table class="records-table">
          <!-- 13 列宽度合计 100%（见下方 .col-* 规则）。配合 table-layout: fixed，
               表格宽度恒等于容器宽度，因此不会出现横向滚动条；
               固定内容的列按内容给足，数据集/算法两列吃掉剩余空间，窄窗口优先让它们省略号截断。 -->
          <colgroup>
            <col class="col-id" />
            <col class="col-user" />
            <col class="col-scenario" />
            <col class="col-dataset" />
            <col class="col-dataset-version" />
            <col class="col-algorithm" />
            <col class="col-model-version" />
            <col class="col-original-label" />
            <col class="col-risk-type" />
            <col class="col-risk-level" />
            <col class="col-risk-score" />
            <col class="col-time" />
            <col class="col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>推理记录ID</th>
              <th>发起人</th>
              <th>场景</th>
              <th>数据集</th>
              <th>版本</th>
              <th>算法</th>
              <th>模型版本</th>
              <th>原始标签</th>
              <th>风险类型</th>
              <th>等级</th>
              <th>风险概率</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td>{{ r.id }}</td>
              <td>{{ r.user_id }}</td>
              <td>{{ scenarioName(r.scenario_id) }}</td>
              <td :title="r.dataset_name || r.dataset_logical_id || ''">{{ r.dataset_name || r.dataset_logical_id }}</td>
              <td>{{ r.dataset_version }}</td>
              <td :title="r.algorithm_name || ''">{{ algorithmShortName(r.algorithm_name) }}</td>
              <td>{{ r.model_version_id }}</td>
              <td>{{ r.original_label }}</td>
              <td>
                <span v-if="r.is_risk_event" class="risk-badge">{{ r.risk_type }}</span>
                <span v-else class="normal-badge">正常</span>
              </td>
              <td>
                <span v-if="r.is_risk_event" class="level-badge" :class="`level-badge--${r.risk_level}`">{{ r.risk_level }}</span>
                <span v-else>—</span>
              </td>
              <td>{{ r.is_risk_event ? ((r.risk_score ?? 0) * 100).toFixed(1) + '%' : '—' }}</td>
              <td>{{ r.executed_at }}</td>
              <td>
                <div class="op-group">
                  <button class="op-btn" @click="openFeatures(r)">输入特征</button>
                  <button class="op-btn" @click="openExplanation(r)">查看解释</button>
                  <button v-if="r.is_risk_event" class="op-btn" @click="goEventDetail(r)">查看事件</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="loading" class="records-empty">加载中...</p>
        <p v-else-if="records.length === 0" class="records-empty">暂无推理记录</p>
      </div>
    </section>

    <!-- 输入特征弹窗：与数据集中心的字段预览使用同一套 Element Plus 弹窗/表格样式 -->
    <el-dialog
      v-model="featureDialogVisible"
      class="inference-feature-dialog"
      :title="`输入特征 - 推理记录 ${featureTarget?.id ?? ''}`"
      width="760px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
      @close="closeFeatures"
    >
      <el-table
        :data="featureRows"
        stripe
        max-height="62vh"
        style="width: 100%"
        empty-text="该推理记录暂无输入特征"
      >
        <el-table-column prop="name" label="特征名" min-width="220" />
        <el-table-column prop="value" label="特征值" min-width="260" show-overflow-tooltip />
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="explanationDialogVisible"
      class="inference-explanation-dialog"
      width="820px"
      top="5vh"
      append-to-body
      :close-on-click-modal="false"
      @close="closeExplanation"
    >
      <template #header="{ titleId, titleClass }">
        <div class="inference-explanation-dialog__header">
          <span :id="titleId" :class="titleClass">模型解释 - 推理记录 {{ explanationTarget?.id ?? '' }}</span>
          <button
            class="inference-explanation-dialog__generate"
            type="button"
            :disabled="explanationLoading"
            @click="generateExplanation"
          >
            {{ explanationWasAvailable ? '重新生成' : '生成AI评价' }}
          </button>
        </div>
      </template>
      <p v-if="explanationLoading" class="explanation-state">
        {{ explanationGenerating ? '正在生成AI评价...' : '正在读取已保存解释...' }}
      </p>
      <template v-else>
        <p v-if="explanationError" class="explanation-state explanation-state--error">{{ explanationError }}</p>
        <section v-if="safeModelEvaluationHtml" class="linked-model-evaluation">
          <div class="linked-model-evaluation__title">关联模型评价（已保存）</div>
          <div class="saved-explanation-markdown" v-html="safeModelEvaluationHtml"></div>
        </section>
        <div class="explanation-meta">
          <span>{{ explanationSource === 'ai' ? 'AI 生成' : '规则回退' }}</span>
          <span v-if="explanationGeneratedAt">保存于 {{ explanationGeneratedAt }}</span>
        </div>
        <div class="saved-explanation-markdown" v-html="safeExplanationHtml"></div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.records-page {
  position: relative;
  z-index: 1;
}

.records-page__header {
  margin-bottom: 20px;
}

.records-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.records-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.records-filters {
  display: flex;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-item__label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.filter-select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
}

.filter-select option {
  background: #0b1628;
  color: #e8f1ff;
}

.records-section {
  padding: 20px 24px;
}

.records-table-wrap {
  overflow-x: auto;
}

.records-table {
  width: 100%;
  /* 固定布局：列宽完全由下方 .col-* 决定，表格宽度恒等于容器宽度。
     默认的 auto 布局下 13 列全部 nowrap，表格最小宽度会被内容撑到超过容器，
     于是出现横向滚动条并把「操作」列挤到只够竖排按钮。 */
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.85rem;
}

/* 列宽：13 列合计 100%（与模板 colgroup 一一对应）。
   取值按「容器约 1228px 时各列刚好容纳表头与内容」反推 —— 实测（13.6px 字体、24px 左右内边距）
   各列所需：表头 92/65/52/65/52/52/79/79/79/52/79/52/52，内容最宽
   算法 EMAWNB=82、时间=148、数据集 KDDTrain_20Percent=144、操作两按钮同行=184。
   因此在 1366 及以上宽度的窗口里都不会截断；更窄时按比例缩小，由省略号兜底，但不会溢出容器。 */
.col-id { width: 7.5%; }
.col-user { width: 5.3%; }
.col-scenario { width: 6.4%; }
.col-dataset { width: 12.1%; }
.col-dataset-version { width: 4.3%; }
.col-algorithm { width: 6.7%; }
.col-model-version { width: 6.5%; }
.col-original-label { width: 6.5%; }
.col-risk-type { width: 6.5%; }
.col-risk-level { width: 4.3%; }
.col-risk-score { width: 6.5%; }
.col-time { width: 12.1%; }
.col-actions { width: 15.3%; }

.records-table th {
  text-align: left;
  padding: 11px 12px;
  color: rgba(154, 214, 255, 0.8);
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.15);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.records-table td {
  padding: 11px 12px;
  color: rgba(217, 232, 255, 0.9);
  border-bottom: 1px solid rgba(125, 201, 255, 0.07);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.records-table tbody tr:hover {
  background: rgba(20, 44, 72, 0.5);
}

.records-empty {
  padding: 24px;
  text-align: center;
  color: rgba(220, 234, 255, 0.5);
}

.op-btn {
  padding: 5px 12px;
  border: 1px solid rgba(125, 201, 255, 0.28);
  border-radius: 6px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.8rem;
  cursor: pointer;
}

.op-btn:hover {
  background: rgba(91, 166, 255, 0.2);
}

.op-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.risk-badge,
.normal-badge,
.level-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 0.76rem;
}

.risk-badge {
  background: rgba(255, 123, 114, 0.14);
  color: #ff7b72;
}

.normal-badge {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.level-badge--HIGH {
  background: rgba(255, 123, 114, 0.18);
  color: #ff8a83;
}

.level-badge--MEDIUM {
  background: rgba(255, 209, 102, 0.16);
  color: #ffd166;
}

.level-badge--LOW {
  background: rgba(91, 166, 255, 0.14);
  color: #9ad6ff;
}

</style>

<style>
/* 该弹窗与 DatasetCenter 的字段预览弹窗保持一致；append-to-body 后需使用独立全局选择器。 */
.inference-feature-dialog {
  background: linear-gradient(180deg, rgba(11, 22, 40, 0.98), rgba(5, 12, 22, 0.98)) !important;
  border: 1px solid rgba(125, 201, 255, 0.18) !important;
  border-radius: 20px !important;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5) !important;
}

.inference-feature-dialog .el-dialog__title {
  color: #e8f1ff !important;
  font-size: 1.15rem !important;
}

.inference-feature-dialog .el-dialog__headerbtn .el-dialog__close {
  color: rgba(220, 234, 255, 0.5) !important;
}

.inference-feature-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #e8f1ff !important;
}

.inference-feature-dialog .el-dialog__body {
  padding: 20px 24px !important;
}

.inference-feature-dialog .el-table,
.inference-feature-dialog .el-table__inner-wrapper,
.inference-feature-dialog .el-table__body-wrapper,
.inference-feature-dialog .el-table__header-wrapper {
  background-color: transparent !important;
}

.inference-feature-dialog .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.inference-feature-dialog .el-table td.el-table__cell {
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.inference-feature-dialog .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: rgba(10, 24, 44, 0.85) !important;
}

.inference-feature-dialog .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
}

.inference-feature-dialog .el-table__empty-text {
  color: rgba(180, 200, 235, 0.3) !important;
}

.inference-explanation-dialog {
  background: linear-gradient(180deg, rgba(11, 22, 40, 0.98), rgba(5, 12, 22, 0.98)) !important;
  border: 1px solid rgba(125, 201, 255, 0.18) !important;
  border-radius: 20px !important;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5) !important;
}

.inference-explanation-dialog .el-dialog__title {
  color: #e8f1ff !important;
  font-size: 1.15rem !important;
}

.inference-explanation-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-right: 44px;
}

.inference-explanation-dialog__generate {
  flex: 0 0 auto;
  padding: 7px 14px;
  border: 1px solid rgba(125, 201, 255, 0.32);
  border-radius: 6px;
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
  font-size: 0.82rem;
  cursor: pointer;
}

.inference-explanation-dialog__generate:hover:not(:disabled) {
  background: rgba(91, 166, 255, 0.24);
}

.inference-explanation-dialog__generate:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.inference-explanation-dialog .el-dialog__body {
  padding: 20px 24px !important;
  max-height: 70vh;
  overflow: auto;
}

.explanation-meta,
.explanation-state {
  color: rgba(220, 234, 255, 0.68);
  font-size: 0.86rem;
}

.explanation-meta {
  display: flex;
  gap: 14px;
  margin-bottom: 14px;
}

.linked-model-evaluation {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(83, 229, 200, 0.18);
  border-radius: 8px;
  background: rgba(83, 229, 200, 0.04);
}

.linked-model-evaluation__title {
  margin-bottom: 8px;
  color: #53e5c8;
  font-size: 0.84rem;
  font-weight: 600;
}

.explanation-state--error {
  color: #ff9a91;
}

.saved-explanation-markdown {
  color: rgba(225, 237, 255, 0.9);
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.saved-explanation-markdown :is(h1, h2, h3) {
  color: #9ad6ff;
  margin: 18px 0 8px;
}

.saved-explanation-markdown :is(p, ol, ul) {
  margin: 8px 0;
}

.saved-explanation-markdown code {
  color: #ffd166;
  background: rgba(125, 201, 255, 0.1);
  padding: 1px 4px;
  border-radius: 4px;
}
</style>
