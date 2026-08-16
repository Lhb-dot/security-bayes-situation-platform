<script setup lang="ts">
/**
 * DataPreviewTable.vue — 数据集数据内容预览表（Task 011 / 需求 2.4）
 *
 * 只读分页表格：列用正式字段名动态生成，极宽表横向滚动 + 冻结首列，
 * 标签列（labelField）高亮。数据经 datasetStore.fetchPreview（页面不直连 mockApi）。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useDatasetStore } from '@/stores/datasetStore';

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
      <p class="data-preview__tip">只读数据预览（需求 2.4）：每页最多 {{ pageSize }} 条，标签列已高亮。</p>
      <div class="data-preview__table-wrap">
        <el-table
          :data="rows"
          border
          max-height="520"
          style="width: 100%"
          empty-text="暂无数据"
          :cell-class-name="cellClass"
          :header-cell-class-name="headerClass"
        >
          <el-table-column
            v-for="col in columns"
            :key="col"
            :prop="col"
            :label="col === labelField ? `${col}（标签）` : col"
            :fixed="col === columns[0] ? 'left' : false"
            min-width="140"
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
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.data-preview .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
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

.data-preview .el-pagination {
  --el-pagination-bg-color: rgba(8, 17, 31, 0.8);
  --el-pagination-text-color: rgba(220, 234, 255, 0.75);
  --el-pagination-button-color: rgba(220, 234, 255, 0.75);
}
</style>
