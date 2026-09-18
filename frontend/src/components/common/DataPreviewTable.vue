<script setup lang="ts">
/**
 * DataPreviewTable.vue — 数据集数据内容预览表（Task 011 / 需求 2.4）
 *
 * 只读分页表格：列用正式字段名动态生成，极宽表整表横向滚动（不冻结首列），
 * 标签列（labelField）高亮。数据经 datasetStore.fetchPreview（页面不直连 API）。
 *
 * 滚轮优先级：表格是定高（max-height）内滚容器，浏览器默认会先滚表格、页面不动。
 * 这里用 attachOuterFirstWheel 反转滚动链 —— 先把外层页面滚到顶/底，余量再滚表格。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useDatasetStore } from '@/stores/datasetStore';
import { attachOuterFirstWheel } from '@/utils/scrollChain';

const props = withDefaults(
  defineProps<{
    datasetId: string;
    labelField: string;
    pageSize?: number;
  }>(),
  {
    pageSize: 50,
  }
);

const datasetStore = useDatasetStore();
const currentPage = ref(1);
const loading = ref(true);
const error = ref('');

const preview = computed(() => datasetStore.preview);
const rows = computed(() => preview.value?.rows ?? []);
const total = computed(() => preview.value?.total ?? 0);
/** 动态列：以首行键为正式字段名（跨分页字段结构稳定） */
const columns = computed<string[]>(() => (rows.value.length > 0 ? Object.keys(rows.value[0]) : []));

const loadPage = async (page: number) => {
  loading.value = true;
  error.value = '';
  try {
    await datasetStore.fetchPreview(props.datasetId, { page, page_size: props.pageSize });
  } catch (err) {
    error.value = err instanceof Error ? err.message : '预览数据加载失败';
  } finally {
    loading.value = false;
  }
};

/** 标签列单元格高亮（列属性等于 labelField） */
const cellClass = ({ column }: { column: { property: string } }): string =>
  column.property === props.labelField ? 'preview-label-cell' : '';

/** 标签列表头高亮 */
const headerClass = ({ column }: { column: { property: string } }): string =>
  column.property === props.labelField ? 'preview-label-header' : '';

onMounted(() => {
  loadPage(1);
});

watch(
  () => props.datasetId,
  () => {
    currentPage.value = 1;
    loadPage(1);
  }
);

/**
 * 外层优先的滚轮滚动：包裹层只在「加载完成且无错误」时渲染，
 * 因此用 ref 监听（而不是 onMounted）来挂载/卸载 wheel 监听。
 */
const tableWrapRef = ref<HTMLElement | null>(null);
let detachWheel: (() => void) | null = null;

watch(tableWrapRef, (el) => {
  detachWheel?.();
  detachWheel = null;
  if (el) detachWheel = attachOuterFirstWheel(el);
});

onBeforeUnmount(() => {
  detachWheel?.();
  detachWheel = null;
});
</script>

<template>
  <div class="data-preview">
    <!-- 加载状态 -->
    <div v-if="loading" class="data-preview__state">
      <div class="loader"></div>
      <p>正在加载数据内容...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="data-preview__state data-preview__state--error">
      <p>{{ error }}</p>
      <el-button size="small" plain @click="loadPage(currentPage)">重试</el-button>
    </div>

    <template v-else>
      <p class="data-preview__tip">只读数据预览：每页最多 {{ pageSize }} 条，标签列已高亮。</p>
      <div ref="tableWrapRef" class="data-preview__table-wrap">
        <el-table
          :data="rows"
          stripe
          max-height="520"
          style="width: 100%"
          empty-text="暂无数据"
          :cell-class-name="cellClass"
          :header-cell-class-name="headerClass"
        >
          <!-- 全部列等宽、整表一起横向滚动：不冻结首列。
               冻结列是 position:sticky 叠在滚动内容之上的独立图层，叠上本表的半透明单元格底色后，
               滚过去的列会从首列底下透出来，看起来就是「第一列不动、和第二列文字重叠」。 -->
          <el-table-column
            v-for="col in columns"
            :key="col"
            :prop="col"
            :label="col === labelField ? `${col}（标签）` : col"
            min-width="132"
            show-overflow-tooltip
          />
        </el-table>
      </div>
      <div class="data-preview__pager">
        <el-pagination
          v-model:current-page="currentPage"
          layout="total, prev, pager, next"
          :page-size="pageSize"
          :total="total"
          background
          @current-change="loadPage"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.data-preview {
  display: grid;
  gap: 12px;
}

.data-preview__state {
  display: grid;
  place-items: center;
  gap: 14px;
  padding: 56px 0;
}

.data-preview__state p {
  margin: 0;
  color: rgba(220, 234, 255, 0.65);
}

.data-preview__state--error p {
  color: #ff8c84;
}

.data-preview__tip {
  margin: 0;
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.5);
}

.data-preview__table-wrap {
  border: 1px solid rgba(125, 201, 255, 0.1);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(8, 18, 34, 0.7);
}

.data-preview__pager {
  display: flex;
  justify-content: flex-end;
}
</style>

<style>
/* Element Plus 暗色表格覆盖（data-preview 命名空间） */
.data-preview .el-table,
.data-preview .el-table__inner-wrapper,
.data-preview .el-table__body-wrapper,
.data-preview .el-table__header-wrapper {
  background-color: transparent !important;
}

.data-preview .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.data-preview .el-table td.el-table__cell {
  /* 使用不透明底色，避免横向滚动时内容从冻结列下方透出 */
  background: #06101c !important;
  background-color: #06101c !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

/* 斑马纹（与数据集中心等表格同一套口径） */
.data-preview .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: #0a182c !important;
}

.data-preview .el-table__body tr:hover > td.el-table__cell {
  background-color: #142c48 !important;
}

/* 固定列必须盖住滚动内容，避免横向滚动时发生视觉穿透 */
.data-preview .el-table {
  position: relative;
}

.data-preview .el-table__fixed,
.data-preview .el-table__fixed-right {
  z-index: 20 !important;
  background: #06101c !important;
}

.data-preview .el-table__fixed::before,
.data-preview .el-table__fixed-right::before {
  background-color: #06101c !important;
}

.data-preview .el-table__fixed td.el-table__cell,
.data-preview .el-table__fixed th.el-table__cell,
.data-preview .el-table__fixed-right td.el-table__cell,
.data-preview .el-table__fixed-right th.el-table__cell {
  background: #06101c !important;
  background-color: #06101c !important;
}

/* 固定列内部不依赖 .el-table--striped 祖先，确保 Element Plus 克隆表格也能匹配 */
.data-preview .el-table__fixed tr.el-table__row--striped td.el-table__cell,
.data-preview .el-table__fixed-right tr.el-table__row--striped td.el-table__cell {
  background-color: #0a182c !important;
}

.data-preview .el-table__fixed .el-table__body tr:hover > td.el-table__cell,
.data-preview .el-table__fixed-right .el-table__body tr:hover > td.el-table__cell {
  background-color: #142c48 !important;
}

/* 单元格收紧：预览表列多，靠「截断 + 悬停」而不是换行撑高行高 */
.data-preview .el-table .cell {
  padding: 0 10px;
  line-height: 1.5;
}

.data-preview .el-table th.el-table__cell > .cell {
  font-size: 0.8rem;
}

.data-preview .el-table td.el-table__cell > .cell {
  font-size: 0.82rem;
  font-variant-numeric: tabular-nums;
}

/* 冻结首列加一道阴影，避免和后续列糊在一起 */
.data-preview .el-table__fixed,
.data-preview .el-table__fixed-right {
  box-shadow: 6px 0 12px rgba(0, 0, 0, 0.35);
}

.data-preview .el-table__empty-text {
  color: rgba(180, 200, 235, 0.3) !important;
}

/* 标签列高亮（#ffd166 主题色强调） */
.data-preview .preview-label-header {
  color: #ffd166 !important;
  background-color: rgba(255, 209, 102, 0.1) !important;
}

.data-preview .preview-label-cell {
  background-color: rgba(255, 209, 102, 0.14) !important;
  color: #ffd166 !important;
  font-weight: 600;
}

/* 冻结列是覆盖在滚动内容之上的独立图层，标签单元格也必须使用不透明底色 */
.data-preview .el-table__fixed .preview-label-cell,
.data-preview .el-table__fixed-right .preview-label-cell {
  background-color: #3a321b !important;
  color: #ffd166 !important;
}

/* ---------------- 分页器（暗色） ----------------
   background 模式下页码按钮的底色来自 --el-pagination-button-bg-color（EP 默认 #f0f2f5）、
   禁用态来自 --el-pagination-button-disabled-bg-color（EP 默认 #fff），而页码文字用的是
   我们覆盖过的浅色 —— 浅底浅字所以「看不清」；Total 文案走的是 --el-text-color-regular(#606266)，
   深灰同样看不清。下面补齐这两组变量，并对文案/按钮做定点覆盖。 */
.data-preview .el-pagination {
  --el-pagination-bg-color: rgba(8, 17, 31, 0.8);
  --el-pagination-button-bg-color: rgba(12, 26, 46, 0.9);
  --el-pagination-button-disabled-bg-color: rgba(8, 17, 31, 0.45);
  --el-pagination-text-color: rgba(220, 234, 255, 0.75);
  --el-pagination-button-color: rgba(220, 234, 255, 0.75);
  --el-pagination-button-disabled-color: rgba(180, 200, 235, 0.28);
  --el-pagination-hover-color: #5ba6ff;
}

.data-preview .el-pagination__total,
.data-preview .el-pagination__jump {
  color: rgba(220, 234, 255, 0.6) !important;
}

.data-preview .el-pagination.is-background .el-pager li,
.data-preview .el-pagination.is-background .btn-prev,
.data-preview .el-pagination.is-background .btn-next {
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 6px;
}

.data-preview .el-pagination.is-background .el-pager li:not(.is-active):hover,
.data-preview .el-pagination.is-background .btn-prev:hover,
.data-preview .el-pagination.is-background .btn-next:hover {
  background-color: rgba(20, 44, 72, 0.95) !important;
  color: #9ad6ff !important;
}

.data-preview .el-pagination.is-background .el-pager li.is-active {
  background-color: #3f7fd4 !important;
  color: #ffffff !important;
  border-color: transparent;
}

.data-preview .el-pagination.is-background .btn-prev,
.data-preview .el-pagination.is-background .btn-next {
  background-color: rgba(12, 26, 46, 0.9) !important;
  color: rgba(220, 234, 255, 0.7) !important;
}

.data-preview .el-pagination.is-background .btn-prev:disabled,
.data-preview .el-pagination.is-background .btn-next:disabled {
  background-color: rgba(8, 17, 31, 0.45) !important;
  color: rgba(180, 200, 235, 0.25) !important;
}
</style>
