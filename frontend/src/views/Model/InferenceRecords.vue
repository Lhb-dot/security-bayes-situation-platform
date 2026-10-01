<script setup lang="ts">
/**
 * InferenceRecords - 推理记录
 *
 * 需求 6.2（P0）：普通用户只能查询本人推理记录；管理员可以查询平台全部推理记录。
 * 需求 6.8.4（管理员按用户ID筛选）**未实现**：后端 list_inference_records 没有 user_id 参数，
 * 本页也没有筛选栏。原先预留的 .records-filters / .filter-item / .filter-select 等 36 行 CSS
 * 从未被模板引用，已于 2026-09-27 删除。要做时前后端一起加。
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
import { keepScroll } from '@/utils/scrollAnchor';

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

/** 列表分页：每页 20 条，服务端分页（单条记录含 explain_data，整表拉取会到十几 MB） */
const page = ref(1);
const pageSize = 20;
const total = ref(0);

/** 是否管理员（决定描述文案） */
const isAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN' || userStore.currentUser?.role === 'SCENARIO_ADMIN');

/**
 * 是否平台超管 —— 只有超管能删推理记录。
 *
 * 用 store 的 `isSuperAdmin`（= role 恰为 SUPER_ADMIN），**不要**复用本文件上面的 `isAdmin`
 * —— 那个是 `SUPER_ADMIN || SCENARIO_ADMIN`（等于 store 的 `isManagement`，名字有歧义，
 * 只用于描述文案）。后端删除接口走 `require_admin`，场景管理员会拿到 403，
 * 所以入口必须窄一级，否则他看到一个必然失败的按钮。
 */
const canDelete = computed(() => userStore.isSuperAdmin);

/** 场景数字 ID → 名称 */
const SCENARIO_META: Record<number, { code: string; name: string }> = {
  1: { code: 'network_security', name: '网络安全' },
  2: { code: 'power_system', name: '电力系统' },
  3: { code: 'flightdeck_operation', name: '航母甲板作业' },
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

/** 翻页：包一层滚动锚定，换页后视口停在原处（见 utils/scrollAnchor.ts） */
const changePage = (target: number) => keepScroll(() => loadRecords(target), tableWrapRef.value);

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
/** 推理型模型的思维链：只用于等待期展示「确实在生成」，正文到达即覆盖，且不落库 */
const explanationReasoning = ref('');
const explanationGeneratedAt = ref<string | null>(null);
const explanationError = ref('');
const modelEvaluationMarkdown = ref('');
const explanationWasAvailable = ref(false);
const explanationGenerating = ref(false);
/** 「模型评价」入口开关：默认关闭，只展示本条研判的 AI 评价 */
const modelEvaluationVisible = ref(false);
const modelEvaluationBlock = ref<HTMLElement | null>(null);
const explanationReasoningRef = ref<HTMLElement | null>(null);
let explanationController: AbortController | null = null;
/**
 * 解释文本请求序号：关弹窗 / 换记录 / 重新生成都 +1。
 * 先发出的请求后回来时序号已变，必须整段丢弃 —— 否则 A 记录的响应会盖住
 * 后打开的 B 记录的正文，也会把新流程刚设上的 loading 提前清掉。
 */
let explanationRequestSeq = 0;

/**
 * 流式生成期间把可滚动容器钉在底部，让最新的思维链/正文始终可见。
 * 只在生成中生效：读快照、打开弹窗都会一次性赋正文，无条件跟随会把用户直接拽到底。
 * 弹窗是 append-to-body，正文滚动容器挂在 body 下，只能按类名查。
 */
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

/** 该推理所用模型是否已保存 AI 评价（无评价时入口仍可点，面板内给出提示） */
const hasModelEvaluation = computed(() => Boolean(modelEvaluationMarkdown.value));

/**
 * 后端下发的是 UTC ISO 串（如 2026-09-14T09:09:08.949249+00:00），
 * 直接渲染会把带微秒的 ISO 原文怼到界面上。这里固定按北京时间（UTC+8）格式化，
 * 不依赖浏览器所在时区，避免换机器后显示口径漂移。
 */
const formatBeijingTime = (value: string | null | undefined): string => {
  if (!value) return '';
  const raw = String(value);
  // 无时区标记的裸时间按 UTC 处理（后端统一存 timezone.utc）
  const parsed = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(raw) ? raw : `${raw}Z`);
  if (Number.isNaN(parsed.getTime())) return raw;
  const beijing = new Date(parsed.getTime() + 8 * 60 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${beijing.getUTCFullYear()}-${pad(beijing.getUTCMonth() + 1)}-${pad(beijing.getUTCDate())} ` +
    `${pad(beijing.getUTCHours())}:${pad(beijing.getUTCMinutes())}:${pad(beijing.getUTCSeconds())}`
  );
};

const toggleModelEvaluation = async () => {
  modelEvaluationVisible.value = !modelEvaluationVisible.value;
  if (!modelEvaluationVisible.value) return;
  // 面板在正文顶部，长内容会把按钮顶出视口，展开后主动滚到面板
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
          // 正文一到就覆盖思考链：它只负责让用户看到「确实在生成」，不留在结果里。
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
    // 收尾再钉一次：状态行消失会让正文区高度变化。
    stickExplanationToBottom();
    // 序号已变 = 弹窗被关或换了记录，新流程自己收尾：这里不能覆盖它的
    // loading / generating / controller（controller 被置空后新流就 abort 不掉了）。
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

/** 风险记录 → 跳转风险事件详情 */
const goEventDetail = (r: InferenceRecordItem) => {
  if (r.risk_event_id == null) {
    ElMessage.info('该记录未生成风险事件');
    return;
  }
  router.push({ path: `/events/${r.risk_event_id}` });
};

/** 正在删除的记录 id（按钮转 loading 用） */
const deletingId = ref<number | null>(null);

/**
 * 删除推理记录（仅超管）。
 *
 * 已生成风险事件的记录**不展示入口** —— 后端会直接拒绝（风险事件是审计对象，
 * 记录被删了事件就悬空了）。所以这里不是「点了才知道不行」，而是压根不给点。
 */
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
    // 删掉当前页最后一条时往前退一页，否则会停在一个空页上
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

// 流式解释是一条长连接：离开页面时必须主动断开，否则它会把整段响应读完，
// 并继续往已卸载组件的 ref 上写。序号一并推进，让在途的读快照请求作废。
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
          {{ isAdmin ? '全部用户的模型推理记录' : '本人发起的模型推理记录' }}
        </p>
      </div>
    </div>

    <section class="card records-section">
      <div ref="tableWrapRef" class="records-table-wrap">
        <div v-if="loading" class="pane-loading"><div class="loader"></div></div>
        <table class="records-table">
          <!-- 8 列宽度合计 100%（见下方 .col-* 规则）。配合 table-layout: fixed，
               表格宽度恒等于容器宽度，因此不会出现横向滚动条。

               2026-09-27 两次瘦身，13 列 → 8 列：
               ① 删「数据集 / 版本 / 算法」—— 数据集名和算法名都是 30 字符级别的长串，
                  在这张表里本来就只显示省略号，占着 19.6% 宽度没有信息量。
               ② 「风险类型 / 等级 / 风险概率」三列合成一列「研判结果」—— 见下方 .verdict 注释。 -->
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
              <th>原始标签</th>
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
     默认的 auto 布局下 13 列全部 nowrap，表格最小宽度会被内容撑到超过容器，
     于是出现横向滚动条并把「操作」列挤到只够竖排按钮。 */
  table-layout: fixed;
  border-collapse: collapse;
  font-size: 0.85rem;
}

/* 列宽：8 列合计 100%（与模板 colgroup 一一对应）。

   「研判结果」按**最宽的那一行**定宽，不是按表头：异常行是「异常 + 等级 + 概率」三个元素，
   实测 `异常` 徽章 42.3px、`MEDIUM` 徽章 66.1px（最长的等级）、概率 `96.0%` 约 38px，
   加 2 个 6px 间距 = 158.4px，再算单元格左右 padding 24px → **182.4px**。
   17.4% 在 1440px 下给到 224px、1280px 下 196px、1100px 下 165px，
   三档都装得下（1100px 是余量最小的，还剩 3.5px）。
   不要为了「填满」把这一列拉宽 —— 空白留在中间最显眼，宁可匀给「时间」。

   「操作」25% —— 最宽一行是「输入特征 / 查看解释 / 查看事件」三个按钮，
   每个 = 4 个中文字 × 12.8px（0.8rem）+ 24px padding + 2px border = 77.2px，
   三个 + 2 个 6px 间距 = 243.6px，加单元格 padding 24px = 267.6px。
   25% 在 1440px 下给到 322px、1280px 下 282px，都排在同一行。

   其余各列按「表头刚好放下」给。更窄（<1280px）时表头会开始截断、操作列可能折行 ——
   这是 8 列 + `table-layout: fixed` 的固有代价，`flex-wrap: wrap` 留着兜底，
   宁可折行也不要把按钮裁掉（td 是 overflow: hidden）。 */
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

/* 删除是破坏性动作，单独用红调，别和上面三个查看类按钮长一样 */
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

/* 「研判结果」= 原来「风险类型 / 等级 / 风险概率」三列合一（2026-09-27）。

   为什么能合：这三列各自都只有「异常行有值 / 正常行是 `—`」两种状态 ——
   实测 `inference_record` 里 `is_risk_event=false` 的 1720 条，`risk_score` 与 `risk_level`
   **全为 NULL**（`count(risk_score)` = 0）；`=true` 的 674 条全部有值。所以
   「正常/异常」⇔「等级列是不是 `—`」⇔「概率列是不是 `—`」，同一个比特说了三遍。

   而「风险类型」那列更彻底：它不由记录算出来，是按数据集查表得来
   （`risk_event_service.py:300` 的 `DATASET_RISK_TYPES.get(dataset.logical_id)`，
   取不到映射直接 400），而每个数据集属于唯一场景、同场景内所有数据集映射到同一类型
   → 与「场景」列 **1:1 重复**，整列删除，不再显示 `POWER_SYSTEM_RISK` 这种裸枚举。

   异常行 = 「异常」红徽章 + 等级徽章 + 概率；正常行 = 单个「正常」绿徽章。
   `flex-wrap: nowrap`（默认）—— 概率数字被截断比折行好，整格溢出交给 td 的 overflow 兜底。

   整列居中（表头一起）—— 这一列比内容宽不少，左对齐会在右边留一截空白，
   居中了视觉重心才落在列中间。
   ⚠️ td 上的 `text-align` **管不到 flex 子项**，只对表头那种纯文本生效，
   所以内容居中必须另给 `.verdict` 加 `justify-content`。 */
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

/* 徽章不许超出自己的格子，超长枚举要在格内截断成省略号。

   坑：全局 `style.css` 里有一条 `.risk-badge { min-width: 86px }`（本页推理记录表的徽章在用），
   它按类名命中了这张表里的徽章，把这里的宽度约束**全部顶掉** —— min-width 优先级高于 width。
   结果徽章宽度恒为 86px、跟列宽无关：1440px 下溢出格子 16px、1280px 下 26px、820px 下 55px，
   一路压到右邻列上（就是「两个胶囊挤在一起」的真因）。所以必须显式 `min-width: 0` 解除泄漏。

   `max-width: 100%` 负责「内容装得下就贴合、装不下就截断」—— 它在 table-cell 里是生效的。
   不要写 `width: 100%`：那会把短徽章（`正常` / `HIGH`）也拉满整格，胶囊就不像胶囊了。 */
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

/* ---------------- 分页器（暗色） ----------------
   与数据集中心的只读预览表保持同一套分页外观；变量挂在包裹层上，
   由 CSS 自定义属性继承进 el-pagination 内部。 */
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

/* 「模型评价」入口：默认收起，选中态用模型评价面板的青色描边呼应 */
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

/* 等待期的思维链：正文一到就被清空，所以这里只求「看得出在动」，不求好读 */
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
