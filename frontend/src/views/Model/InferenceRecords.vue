<script setup lang="ts">
/**
 * 推理记录页：场景用户只能查询本人记录，管理员可以查询平台全部记录。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import {
  getInferenceExplain,
  getInferenceRecordPage,
  removeInferenceRecord,
  streamInferenceExplanation,
} from '@/api/inferenceRecordApi';
import { useUserStore } from '@/stores/userStore';
import { formatBeijingDateTime, parseInstant } from '@/utils/datetime';
import { keepScroll } from '@/utils/scrollAnchor';

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

// 列表分页：每页 20 条，服务端分页（单条记录含 explain_data，整表拉取会到十几 MB）
const page = ref(1);
const pageSize = 20;
const total = ref(0);

const isManagement = computed(() => userStore.isManagement);

const canDelete = computed(() => !!userStore.currentUser);

const SCENARIO_META: Record<number, { code: string; name: string }> = {
  1: { code: 'network_security', name: '网络安全' },
  2: { code: 'power_system', name: '电力系统' },
  3: { code: 'flightdeck_operation', name: '舰面调度态势' },
  4: { code: 'geological_risk', name: '地质风险' },
};
const scenarioName = (id: number) => SCENARIO_META[id]?.name ?? String(id);

const loadRecords = async (targetPage: number = page.value) => {
  loading.value = true;
  try {
    const data = await getInferenceRecordPage({ page: targetPage, page_size: pageSize });
    records.value = data.items as unknown as InferenceRecordItem[];
    total.value = data.total;
    page.value = data.page;
  } finally {
    loading.value = false;
  }
};

const tableWrapRef = ref<HTMLElement | null>(null);

// 翻页：包一层滚动锚定，换页后视口停在原处（见 utils/scrollAnchor.ts）
const changePage = (target: number) => keepScroll(() => loadRecords(target), tableWrapRef.value);

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
const explanationReasoning = ref('');
const explanationGeneratedAt = ref<string | null>(null);
const explanationError = ref('');
const modelEvaluationMarkdown = ref('');
const explanationWasAvailable = ref(false);
const explanationGenerating = ref(false);
const modelEvaluationVisible = ref(false);
const modelEvaluationBlock = ref<HTMLElement | null>(null);
const explanationReasoningRef = ref<HTMLElement | null>(null);
let explanationController: AbortController | null = null;
/**
 * 解释文本请求序号：关弹窗 / 换记录 / 重新生成都 +1。
 * 先发出的请求后回来时序号已变，必须整段丢弃，否则 A 记录的响应会盖住
 * 后打开的 B 记录的正文，也会把新流程刚设上的 loading 提前清掉。
 */
let explanationRequestSeq = 0;

const stickExplanationToBottom = () => {
  if (!explanationGenerating.value) return;
  void nextTick(() => {
    const body = document.querySelector<HTMLElement>('.inference-explanation-dialog .el-dialog__body');
    for (const el of [body, explanationReasoningRef.value]) {
      if (el) el.scrollTop = el.scrollHeight;
    }
  });
};

watch([explanationReasoning, explanationMarkdown], stickExplanationToBottom);

const hasModelEvaluation = computed(() => Boolean(modelEvaluationMarkdown.value));

/**
 * 只用于弹窗里的 `generated_explanation.generated_at`，它是后端手写进 JSONB 的 UTC ISO 串
 * （如 2026-09-14T09:09:08.949249+00:00），直接渲染会把带微秒的原文怼到界面上。
 * 表格里的 `executed_at` 是 ORM DateTime 列，row_to_dict 已转成北京时间字符串，不用再过这里。
 */
const formatBeijingTime = (value: string | null | undefined): string => {
  if (!value) return '';
  const ms = parseInstant(value);
  return ms === null ? String(value) : formatBeijingDateTime(ms);
};

const toggleModelEvaluation = async () => {
  modelEvaluationVisible.value = !modelEvaluationVisible.value;
  if (!modelEvaluationVisible.value) return;
  await nextTick();
  modelEvaluationBlock.value?.scrollIntoView({ block: 'start', behavior: 'smooth' });
};

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
  const seq = ++explanationRequestSeq;
  explanationController?.abort();
  explanationTarget.value = record;
  explanationDialogVisible.value = true;
  explanationLoading.value = true;
  explanationMarkdown.value = '';
  explanationReasoning.value = '';
  explanationGeneratedAt.value = null;
  explanationError.value = '';
  modelEvaluationMarkdown.value = record.model_evaluation?.markdown ?? '';
  modelEvaluationVisible.value = false;
  explanationWasAvailable.value = false;
  explanationGenerating.value = false;
  try {
    const result = await getInferenceExplain(String(record.id));
    if (seq !== explanationRequestSeq) return;
    const saved = result.generated_explanation;
    explanationWasAvailable.value = Boolean(saved?.available && saved.markdown);
    if (!saved?.available || !saved.markdown) {
      explanationError.value = '该记录尚未保存解释文本，请点击右上角生成AI评价。';
      return;
    }
    explanationMarkdown.value = saved.markdown;
    explanationGeneratedAt.value = saved.generated_at ?? null;
  } catch (err) {
    if (seq !== explanationRequestSeq) return;
    explanationError.value = err instanceof Error ? err.message : '解释文本读取失败';
  } finally {
    if (seq === explanationRequestSeq) explanationLoading.value = false;
  }
};

const generateExplanation = async () => {
  const target = explanationTarget.value;
  if (!target || explanationLoading.value) return;

  const seq = ++explanationRequestSeq;
  explanationController?.abort();
  explanationController = new AbortController();
  explanationLoading.value = true;
  explanationGenerating.value = true;
  explanationError.value = '';
  explanationMarkdown.value = '';
  explanationReasoning.value = '';
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
        onReasoning: (content) => { explanationReasoning.value += content; },
        onDelta: (content) => {
          if (explanationReasoning.value) explanationReasoning.value = '';
          explanationMarkdown.value += content;
        },
        onError: (message) => {
          explanationReasoning.value = '';
          explanationError.value = message;
        },
      },
      explanationController.signal,
    );

    const refreshed = await getInferenceExplain(String(target.id));
    if (seq !== explanationRequestSeq) return;
    const saved = refreshed.generated_explanation;
    if (!saved?.available || !saved.markdown) {
      throw new Error('AI评价生成后未能保存，请稍后重试');
    }
    explanationMarkdown.value = saved.markdown;
    explanationGeneratedAt.value = saved.generated_at ?? null;
    explanationWasAvailable.value = true;
  } catch (err) {
    if (seq === explanationRequestSeq && (err as Error)?.name !== 'AbortError') {
      explanationReasoning.value = '';
      explanationError.value = err instanceof Error ? err.message : 'AI评价生成失败';
    }
  } finally {
    stickExplanationToBottom();
    if (seq === explanationRequestSeq) {
      explanationLoading.value = false;
      explanationGenerating.value = false;
      explanationController = null;
    }
  }
};

const closeExplanation = () => {
  explanationRequestSeq += 1;
  explanationController?.abort();
  explanationController = null;
  explanationDialogVisible.value = false;
  explanationTarget.value = null;
  explanationMarkdown.value = '';
  explanationReasoning.value = '';
  modelEvaluationMarkdown.value = '';
  modelEvaluationVisible.value = false;
  explanationWasAvailable.value = false;
  explanationGenerating.value = false;
};

const goEventDetail = (r: InferenceRecordItem) => {
  if (r.risk_event_id == null) {
    ElMessage.info('该记录未生成风险事件');
    return;
  }
  router.push({ path: `/events/${r.risk_event_id}` });
};

const deletingId = ref<number | null>(null);

const handleDelete = async (r: InferenceRecordItem) => {
  try {
    await ElMessageBox.confirm(
      `确认删除推理记录 #${r.id}？删除后不可恢复。`,
      '删除推理记录',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    );
  } catch {
    return; // 用户取消
  }
  deletingId.value = r.id;
  try {
    await removeInferenceRecord(String(r.id));
    ElMessage.success('推理记录已删除');
    if (records.value.length === 1 && page.value > 1) page.value -= 1;
    await loadRecords();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败');
  } finally {
    deletingId.value = null;
  }
};

onMounted(() => {
  loadRecords();
});

onBeforeUnmount(() => {
  explanationRequestSeq += 1;
  explanationController?.abort();
  explanationController = null;
});
</script>

<template>
  <div class="records-page">
    <div class="records-page__header">
      <div>
        <p class="eyebrow">Inference Records</p>
        <h2>推理记录</h2>
        <p class="records-page__desc">
          {{ isManagement ? '全部用户的模型推理记录' : '本人发起的模型推理记录' }}
        </p>
      </div>
    </div>

    <section class="card records-section">
      <div ref="tableWrapRef" class="records-table-wrap">
        <div v-if="loading" class="pane-loading"><div class="loader"></div></div>
        <table class="records-table">
          <!-- 列宽度合计 100%（见下方 .col-* 规则）。配合 table-layout: fixed -->
          <colgroup>
            <col class="col-id" />
            <col class="col-user" />
            <col class="col-scenario" />
            <col class="col-model-version" />
            <col class="col-original-label" />
            <col class="col-verdict" />
            <col class="col-time" />
            <col class="col-actions" />
          </colgroup>
          <thead>
            <tr>
              <th>推理记录ID</th>
              <th>发起人</th>
              <th>场景</th>
              <th>模型版本</th>
              <th>预测标签</th>
              <th class="cell-verdict">研判结果</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td>{{ r.id }}</td>
              <td>{{ r.user_id }}</td>
              <td>{{ scenarioName(r.scenario_id) }}</td>
              <td>{{ r.model_version_id }}</td>
              <td>{{ r.original_label }}</td>
              <td class="cell-verdict">
                <div class="verdict">
                  <template v-if="r.is_risk_event">
                    <span class="risk-badge">异常</span>
                    <span class="level-badge" :class="`level-badge--${r.risk_level}`">{{ r.risk_level }}</span>
                    <span class="verdict-score">{{ ((r.risk_score ?? 0) * 100).toFixed(1) }}%</span>
                  </template>
                  <span v-else class="normal-badge">正常</span>
                </div>
              </td>
              <td>{{ r.executed_at }}</td>
              <td>
                <div class="op-group">
                  <button class="op-btn" @click="openFeatures(r)">输入特征</button>
                  <button class="op-btn" @click="openExplanation(r)">查看解释</button>
                  <button v-if="r.is_risk_event" class="op-btn" @click="goEventDetail(r)">查看事件</button>
                  <button
                    v-else-if="canDelete"
                    class="op-btn op-btn--danger"
                    :disabled="deletingId === r.id"
                    @click="handleDelete(r)"
                  >{{ deletingId === r.id ? '删除中' : '删除' }}</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="!loading && records.length === 0" class="records-empty">暂无推理记录</p>
      </div>
      <div v-if="total > 0" class="records-pager">
        <span class="records-pager__total">共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="page"
          layout="prev, pager, next"
          :page-size="pageSize"
          :total="total"
          :disabled="loading"
          background
          @current-change="changePage"
        />
      </div>
    </section>

    <!-- 输入特征弹窗 -->
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
          <div class="inference-explanation-dialog__actions">
            <button
              class="inference-explanation-dialog__evaluation"
              :class="{ 'is-active': modelEvaluationVisible }"
              type="button"
              :aria-pressed="modelEvaluationVisible"
              :title="hasModelEvaluation ? '查看该推理所用模型的 AI 评价' : '该推理所用模型尚未生成 AI 评价'"
              @click="toggleModelEvaluation"
            >
              模型评价
            </button>
            <button
              class="inference-explanation-dialog__generate"
              type="button"
              :disabled="explanationLoading"
              @click="generateExplanation"
            >
              {{ explanationWasAvailable ? '重新生成' : '生成AI评价' }}
            </button>
          </div>
        </div>
      </template>
      <p v-if="explanationLoading && !explanationGenerating" class="explanation-state">
        正在读取已保存解释...
      </p>
      <template v-else>
        <p v-if="explanationGenerating" class="explanation-state">正在生成AI评价...</p>
        <p v-if="explanationError" class="explanation-state explanation-state--error">{{ explanationError }}</p>
        <div v-if="explanationReasoning" class="explanation-reasoning">
          <div class="explanation-reasoning__label">模型推理中</div>
          <div ref="explanationReasoningRef" class="explanation-reasoning__text">{{ explanationReasoning }}</div>
        </div>
        <section
          v-if="modelEvaluationVisible"
          ref="modelEvaluationBlock"
          class="linked-model-evaluation"
        >
          <div class="linked-model-evaluation__title">模型评价</div>
          <div v-if="safeModelEvaluationHtml" class="saved-explanation-markdown" v-html="safeModelEvaluationHtml"></div>
          <p v-else class="explanation-state">该推理所用模型尚未生成 AI 评价。</p>
        </section>
        <div v-if="explanationGeneratedAt" class="explanation-meta">
          <span>保存于 {{ formatBeijingTime(explanationGeneratedAt) }}</span>
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
  color: #c8deff;
}

.records-page__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

.records-section {
  padding: 20px 24px;
}

.records-table-wrap {
  position: relative; /* 翻页遮罩（.pane-loading）的定位上下文 */
  overflow-x: auto;
}

.records-table {
  width: 100%;
  /* 固定布局：列宽完全由下方 .col-* 决定，表格宽度恒等于容器宽度。
     默认的 auto 布局下 13 列全部 nowrap，表格最小宽度会被内容撑到超过容器。
     于是出现横向滚动条并把「操作」列挤到只够竖排按钮。 */
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.85rem;
}

/* 列宽：8 列合计 100%，与模板 colgroup 一一对应。
   「研判结果」与「操作」按最宽的那一行定宽，其余各列按表头刚好放下给。
   1100px 以下表头开始截断、操作列可能折行，td 是 overflow: hidden，宁可折行也不裁按钮。 */
.col-id { width: 9.4%; }
.col-user { width: 6.2%; }
.col-scenario { width: 8.2%; }
.col-model-version { width: 8.2%; }
.col-original-label { width: 8.2%; }
.col-verdict { width: 17.4%; }
.col-time { width: 17.4%; }
.col-actions { width: 25%; }

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

.op-btn--danger {
  border-color: rgba(255, 123, 114, 0.32);
  background: rgba(255, 123, 114, 0.1);
  color: #ff8c84;
}

.op-btn--danger:hover:not(:disabled) {
  background: rgba(255, 123, 114, 0.2);
}

.op-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.op-group {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

/* 「研判结果」= 风险类型 / 等级 / 风险概率 三列合一。
   三列各自只有「异常行有值、正常行是 `—`」两种状态，同一个比特说了三遍；
   风险类型按数据集查表得来，与「场景」列 1:1 重复，整列删除。
   异常行 = 红徽章 + 等级徽章 + 概率，正常行 = 单个绿徽章。
   整列居中要另给 `.verdict` 加 `justify-content`，td 的 `text-align` 管不到 flex 子项。 */
.records-table th.cell-verdict,
.records-table td.cell-verdict {
  text-align: center;
}

.verdict {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 0;
}

.verdict-score {
  color: rgba(217, 232, 255, 0.9);
  font-variant-numeric: tabular-nums;
}

/* 徽章不许超出自己的格子，超长枚举在格内截断成省略号。
   全局 style.css 的 `.risk-badge { min-width: 86px }` 会按类名命中这张表的徽章。
   必须显式 `min-width: 0` 解除泄漏。`max-width: 100%` 负责装不下时截断。 */
.risk-badge,
.normal-badge,
.level-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 0.76rem;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.records-pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 16px;
  --el-pagination-bg-color: rgba(8, 17, 31, 0.8);
  --el-pagination-button-bg-color: rgba(12, 26, 46, 0.9);
  --el-pagination-button-disabled-bg-color: rgba(8, 17, 31, 0.45);
  --el-pagination-text-color: rgba(220, 234, 255, 0.75);
  --el-pagination-button-color: rgba(220, 234, 255, 0.75);
  --el-pagination-button-disabled-color: rgba(180, 200, 235, 0.28);
  --el-pagination-hover-color: #5ba6ff;
}

.records-pager__total {
  color: rgba(220, 234, 255, 0.6);
  font-size: 0.85rem;
}

.records-pager :deep(.el-pagination.is-background .el-pager li),
.records-pager :deep(.el-pagination.is-background .btn-prev),
.records-pager :deep(.el-pagination.is-background .btn-next) {
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 6px;
}

.records-pager :deep(.el-pagination.is-background .el-pager li:not(.is-active):hover),
.records-pager :deep(.el-pagination.is-background .btn-prev:hover),
.records-pager :deep(.el-pagination.is-background .btn-next:hover) {
  background-color: rgba(20, 44, 72, 0.95) !important;
  color: #9ad6ff !important;
}

.records-pager :deep(.el-pagination.is-background .el-pager li.is-active) {
  background-color: #3f7fd4 !important;
  color: #ffffff !important;
  border-color: transparent;
}

.records-pager :deep(.el-pagination.is-background .btn-prev),
.records-pager :deep(.el-pagination.is-background .btn-next) {
  background-color: rgba(12, 26, 46, 0.9) !important;
  color: rgba(220, 234, 255, 0.7) !important;
}

.records-pager :deep(.el-pagination.is-background .btn-prev:disabled),
.records-pager :deep(.el-pagination.is-background .btn-next:disabled) {
  background-color: rgba(8, 17, 31, 0.45) !important;
  color: rgba(180, 200, 235, 0.25) !important;
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

.inference-explanation-dialog__actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
}

.inference-explanation-dialog__evaluation {
  flex: 0 0 auto;
  padding: 7px 14px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  border-radius: 6px;
  background: rgba(125, 201, 255, 0.06);
  color: rgba(200, 222, 250, 0.78);
  font-size: 0.82rem;
  cursor: pointer;
}

.inference-explanation-dialog__evaluation:hover {
  background: rgba(125, 201, 255, 0.16);
  color: #cfe4ff;
}

.inference-explanation-dialog__evaluation.is-active {
  border-color: rgba(83, 229, 200, 0.42);
  background: rgba(83, 229, 200, 0.16);
  color: #53e5c8;
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

.explanation-reasoning {
  margin-bottom: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  border-radius: 8px;
  background: rgba(10, 22, 40, 0.5);
}

.explanation-reasoning__label {
  margin-bottom: 6px;
  color: rgba(154, 214, 255, 0.72);
  font-size: 0.78rem;
}

.explanation-reasoning__text {
  max-height: 200px;
  overflow: auto;
  color: rgba(196, 214, 240, 0.66);
  font-size: 0.85rem;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
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
