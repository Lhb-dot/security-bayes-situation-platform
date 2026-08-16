<script setup lang="ts">
/**
 * DatasetDetailView.vue — 数据集详情页（Task 011 / 需求 2.4）
 *
 * 两页签：字段结构 + 数据内容预览（只读分页、标签列高亮）。
 * 数据链路：页面 → datasetStore / scenarioStore（页面不直连 mockApi）。
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useDatasetStore } from '@/stores/datasetStore';
import { useScenarioStore } from '@/stores/scenarioStore';
import DataPreviewTable from '@/components/common/DataPreviewTable.vue';

const route = useRoute();
const router = useRouter();
const datasetStore = useDatasetStore();
const scenarioStore = useScenarioStore();

const datasetId = computed(() => String(route.params.datasetId ?? ''));
const loading = ref(true);
const error = ref('');
const notFound = ref(false);
const activeTab = ref('fields');

const dataset = computed(() =>
  datasetStore.datasets.find((d) => d.dataset_id === datasetId.value) ?? null
);
const scenarioName = computed(() =>
  dataset.value ? (scenarioStore.scenarioById(dataset.value.scenario_id)?.name ?? dataset.value.scenario_id) : ''
);
const fields = computed(() =>
  datasetStore.fields.length > 0 ? datasetStore.fields : (dataset.value?.fields ?? [])
);
const labelField = computed(() =>
  fields.value.find((f) => f.field_role === '分类标签')?.field_name ?? ''
);

onMounted(async () => {
  loading.value = true;
  error.value = '';
  notFound.value = false;
  try {
    await Promise.all([datasetStore.fetchDatasets(), scenarioStore.fetchScenarioList()]);
    if (!dataset.value) {
      notFound.value = true;
      return;
    }
    await datasetStore.fetchFields(datasetId.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '数据集加载失败';
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="dataset-detail">
    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载数据集信息...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="router.back()">返回</button>
    </section>

    <!-- 不存在 / 无权访问 -->
    <section v-else-if="notFound" class="state-card">
      <p>数据集不存在或无权访问</p>
      <button class="ghost-button" @click="router.back()">返回</button>
    </section>

    <template v-else-if="dataset">
      <!-- 顶部头部 -->
      <section class="card dataset-detail__head">
        <div>
          <p class="eyebrow">Dataset Detail</p>
          <h2>{{ dataset.name }}</h2>
          <p class="dataset-detail__meta">
            {{ scenarioName }} · {{ dataset.data_format.toUpperCase() }} · 版本 {{ dataset.dataset_version }}
            · {{ dataset.record_count.toLocaleString() }} 样本 · {{ dataset.field_count }} 字段
          </p>
        </div>
        <div class="dataset-detail__actions">
          <el-tag :type="dataset.enabled ? 'success' : 'info'" effect="dark">
            {{ dataset.enabled ? '已启用' : '已停用' }}
          </el-tag>
          <el-button plain @click="router.back()">返回</el-button>
        </div>
      </section>

      <!-- 两页签 -->
      <el-tabs v-model="activeTab" class="dataset-detail__tabs">
        <el-tab-pane label="字段结构" name="fields">
          <div class="dataset-detail__table-wrap">
            <el-table
              :data="fields"
              stripe
              style="width: 100%"
              empty-text="该数据集暂无字段信息"
            >
              <el-table-column prop="field_name" label="字段名" min-width="160" />
              <el-table-column prop="field_type" label="数据类型" width="110" align="center" />
              <el-table-column prop="field_role" label="字段角色" width="110" align="center">
                <template #default="{ row }: { row: { field_role: string } }">
                  <span class="dataset-detail__role" :class="row.field_role === '分类标签' ? 'is-label' : 'is-input'">
                    {{ row.field_role }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="字段说明" min-width="200" show-overflow-tooltip />
              <el-table-column prop="sample_value" label="样例值" width="130" show-overflow-tooltip />
              <el-table-column label="枚举值域" min-width="180" show-overflow-tooltip>
                <template #default="{ row }: { row: { enum_values?: string[] } }">
                  <span class="dataset-detail__enum">{{ row.enum_values?.join(' / ') ?? '—' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="数据内容预览" name="preview">
          <DataPreviewTable :datasetId="dataset.dataset_id" :labelField="labelField" :pageSize="50" />
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<style scoped>
.dataset-detail {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 18px;
}

.dataset-detail__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
}

.dataset-detail__head h2 {
  margin: 8px 0 6px;
  font-size: 1.45rem;
}

.dataset-detail__meta {
  margin: 0;
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.6);
}

.dataset-detail__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.dataset-detail__table-wrap {
  border: 1px solid rgba(125, 201, 255, 0.1);
  border-radius: 14px;
  overflow: hidden;
  background: rgba(8, 18, 34, 0.7);
}

.dataset-detail__role {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
}

.dataset-detail__role.is-label {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.dataset-detail__role.is-input {
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
}

.dataset-detail__enum {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.65);
}

@media (max-width: 768px) {
  .dataset-detail__head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

<style>
/* Element Plus 暗色覆盖（dataset-detail 命名空间） */
.dataset-detail .el-table,
.dataset-detail .el-table__inner-wrapper,
.dataset-detail .el-table__body-wrapper,
.dataset-detail .el-table__header-wrapper {
  background-color: transparent !important;
}

.dataset-detail .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.dataset-detail .el-table td.el-table__cell {
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.dataset-detail .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
}

.dataset-detail .el-table__empty-text {
  color: rgba(180, 200, 235, 0.3) !important;
}

.dataset-detail .el-tabs__item {
  color: rgba(220, 234, 255, 0.65);
}

.dataset-detail .el-tabs__item.is-active {
  color: #5ba6ff;
}

.dataset-detail .el-tabs__active-bar {
  background-color: #5ba6ff;
}

.dataset-detail .el-tabs__nav-wrap::after {
  background-color: rgba(125, 201, 255, 0.12);
}
</style>
