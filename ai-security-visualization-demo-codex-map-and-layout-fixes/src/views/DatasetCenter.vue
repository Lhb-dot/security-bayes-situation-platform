<script setup lang="ts">
/**
 * DatasetCenter - 数据集中心页面
 *
 * 全平台数据集统一管理
 * 支持按场景筛选、数据集列表展示、数据集字段预览
 */
import { computed, onMounted, ref, watch } from 'vue';
import type { Dataset, DatasetField, ScenarioId } from '@/types/security';
import { getDatasetList, getDatasetFields } from '@/services/mockApi';
import ScenarioSelector from '@/components/common/ScenarioSelector.vue';

/** 场景名称映射 */
const SCENARIO_LABEL: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板',
};

/** 数据格式标签 */
const FORMAT_LABEL: Record<string, string> = {
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

/** 弹窗：字段预览 */
const fieldDialogVisible = ref(false);
const fieldDialogTitle = ref('');
const fieldDialogFields = ref<DatasetField[]>([]);
const fieldDialogLoading = ref(false);

/** 是否选中航母甲板（辅助模板判断，绕过类型收窄） */
const isFlightdeckSelected = computed(() => selectedScenario.value === ('flightdeck_operation' as ScenarioId | 'all'));

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

// ===================== 字段预览弹窗 =====================
const openFieldPreview = async (dataset: Dataset) => {
  fieldDialogTitle.value = `字段预览 - ${dataset.name}`;
  fieldDialogVisible.value = true;
  fieldDialogLoading.value = true;
  try {
    const fields = await getDatasetFields(dataset.dataset_id);
    fieldDialogFields.value = fields;
  } catch (err) {
    fieldDialogFields.value = [];
  } finally {
    fieldDialogLoading.value = false;
  }
};

const closeFieldPreview = () => {
  fieldDialogVisible.value = false;
  fieldDialogFields.value = [];
};

// ===================== 生命周期 =====================
onMounted(() => {
  loadDatasets();
});
</script>

<template>
  <div class="dataset-center">
    <!-- 页面头部 -->
    <div class="dataset-center__header">
      <div>
        <p class="eyebrow">Dataset Center</p>
        <h2>数据集中心</h2>
        <p class="dataset-center__desc">全平台数据集统一管理，支持按业务场景筛选</p>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="dataset-center__toolbar">
      <ScenarioSelector v-model="selectedScenario" />
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

    <!-- 航母甲板场景提示 -->
    <section v-if="isFlightdeckSelected" class="state-card">
      <div class="flightdeck-placeholder">
        <span class="flightdeck-placeholder__icon">🚢</span>
        <h3>暂未接入数据集</h3>
        <p>航母甲板保障作业场景在第一阶段仅预留接口，尚未配置实际数据集。</p>
        <p class="flightdeck-placeholder__hint">待正式数据集接入后，将在此展示数据集列表。</p>
      </div>
    </section>

    <!-- 数据集表格 -->
    <div v-else class="dataset-center__table-wrap">
      <el-table
        :data="filteredDatasets"
        stripe
        style="width: 100%"
        :empty-text="selectedScenario === 'flightdeck_operation' ? '' : '暂无数据集'"
        row-class-name="dataset-table-row"
      >
        <el-table-column
          prop="name"
          label="数据集名称"
          min-width="180"
          show-overflow-tooltip
        >
          <template #default="{ row }: { row: Dataset }">
            <div class="dataset-table__name-cell">
              <span class="dataset-table__name">{{ row.name }}</span>
              <span class="dataset-table__desc">{{ row.description }}</span>
            </div>
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

        <el-table-column prop="field_count" label="字段数" width="80" align="center" />

        <el-table-column prop="created_at" label="创建时间" width="100" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span class="dataset-table__time">{{ row.created_at.slice(0, 10) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }: { row: Dataset }">
            <el-button
              size="small"
              type="primary"
              plain
              @click="openFieldPreview(row)"
            >
              字段预览
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 字段预览弹窗 -->
    <el-dialog
      v-model="fieldDialogVisible"
      :title="fieldDialogTitle"
      width="760px"
      top="6vh"
      :close-on-click-modal="false"
      @close="closeFieldPreview"
    >
      <div v-if="fieldDialogLoading" class="dialog-loading">
        <div class="loader"></div>
        <p>加载字段信息...</p>
      </div>

      <el-table
        v-else
        :data="fieldDialogFields"
        stripe
        style="width: 100%"
        empty-text="该数据集暂无字段信息"
      >
        <el-table-column prop="field_name" label="字段名" min-width="140" />
        <el-table-column prop="field_type" label="数据类型" width="90" align="center">
          <template #default="{ row }: { row: DatasetField }">
            <span
              class="type-badge"
              :class="row.field_type === '数值型' || row.field_type === 'float' || row.field_type === 'int' ? 'type-badge--numeric' : 'type-badge--string'"
            >
              {{ row.field_type }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="field_role" label="字段角色" width="100" align="center">
          <template #default="{ row }: { row: DatasetField }">
            <span
              class="field-role-badge"
              :class="row.field_role === '分类标签' ? 'field-role-label' : 'field-role-input'"
            >
              {{ row.field_role }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="nullable" label="允许为空" width="80" align="center">
          <template #default="{ row }: { row: DatasetField }">
            <span :class="row.nullable ? 'text-muted' : 'text-active'">
              {{ row.nullable ? '是' : '否' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="字段说明" min-width="160" show-overflow-tooltip />
        <el-table-column prop="sample_value" label="样例数据" width="120" show-overflow-tooltip />
      </el-table>
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

/* 名称列 */
.dataset-table__name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
}

.dataset-table__name {
  font-weight: 600;
  color: #c8deff;
  font-size: 0.95rem;
}

.dataset-table__desc {
  font-size: 0.8rem;
  color: rgba(180, 200, 235, 0.5);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

/* 弹窗加载 */
.dialog-loading {
  display: grid;
  place-items: center;
  gap: 16px;
  padding: 48px 0;
}

.dialog-loading p {
  margin: 0;
  color: rgba(220, 234, 255, 0.65);
}

/* 航母甲板暂未接入提示 */
.flightdeck-placeholder {
  display: grid;
  place-items: center;
  gap: 8px;
  padding: 48px 24px;
  text-align: center;
}

.flightdeck-placeholder__icon {
  font-size: 3.5rem;
  margin-bottom: 8px;
}

.flightdeck-placeholder h3 {
  margin: 0;
  font-size: 1.3rem;
  color: #e8f1ff;
}

.flightdeck-placeholder p {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
  max-width: 420px;
}

.flightdeck-placeholder__hint {
  font-size: 0.85rem !important;
  color: rgba(220, 234, 255, 0.45) !important;
  font-style: italic;
}

/* 字段角色标签 */
.field-role-input {
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
}

.field-role-label {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
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

/* 类型徽章（弹窗） */
.type-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 0.76rem;
  font-weight: 500;
}

.type-badge--numeric {
  background: rgba(91, 166, 255, 0.10);
  color: #7dbfff;
}

.type-badge--string {
  background: rgba(220, 234, 255, 0.06);
  color: rgba(220, 234, 255, 0.7);
}

/* 文本颜色 */
.text-muted {
  color: rgba(220, 234, 255, 0.45);
}

.text-active {
  color: #53e5c8;
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

/* Element Plus 按钮暗色 */
.dataset-center .el-button--primary.is-plain {
  --el-button-bg-color: rgba(91, 166, 255, 0.14) !important;
  --el-button-border-color: rgba(91, 166, 255, 0.35) !important;
  --el-button-text-color: #9ad6ff !important;
  --el-button-hover-bg-color: rgba(91, 166, 255, 0.22) !important;
  --el-button-hover-border-color: rgba(91, 166, 255, 0.5) !important;
  --el-button-hover-text-color: #bae3ff !important;
}

</style>
