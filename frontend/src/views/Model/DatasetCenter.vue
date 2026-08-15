<script setup lang="ts">
/**
 * DatasetCenter - 数据集中心页面
 *
 * 全平台数据集统一管理
 * 支持按场景筛选、数据集列表展示、数据集字段预览
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import type { Dataset, DatasetField, DatasetVersion, ScenarioId, UserAccount } from '@/types/security';
import {
  getDatasetList,
  getDatasetFields,
  getDatasetVersions,
  uploadDataset,
  createDatasetVersion,
  disableDatasetVersion,
  deleteDatasetVersion,
  getCurrentUser,
} from '@/services/mockApi';
import ScenarioSelector from '@/components/common/ScenarioSelector.vue';

const router = useRouter();

/** 场景名称映射 */
const SCENARIO_LABEL: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
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

/** 当前登录用户（需求 2.3.1：仅管理员可上传/修改/停用/删除数据集） */
const currentUser = ref<UserAccount | null>(null);
const isAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN' || currentUser.value?.role === 'SCENARIO_ADMIN');

// ===================== 上传数据集 / 创建新版本（需求 2.3.2 / 2.3.3） =====================
const uploadDialogVisible = ref(false);
/** 弹窗模式：upload=上传新数据集(v1)；newVersion=修改已用数据集→创建新版本（保留旧版本） */
const uploadDialogMode = ref<'upload' | 'newVersion'>('upload');
/** 新版本模式下的目标数据集 */
const newVersionTarget = ref<Dataset | null>(null);
const uploadForm = ref({
  dataset_id: '',
  name: '',
  scenario_id: '' as ScenarioId | '',
  data_format: 'arff' as Dataset['data_format'],
  record_count: 0,
});
const uploadFields = ref<Array<{ field_name: string; field_type: string; field_role: '输入特征' | '分类标签'; description: string }>>([
  { field_name: '', field_type: 'float', field_role: '输入特征', description: '' },
]);

const openUploadDialog = () => {
  uploadDialogMode.value = 'upload';
  newVersionTarget.value = null;
  uploadForm.value = { dataset_id: '', name: '', scenario_id: '', data_format: 'arff', record_count: 0 };
  uploadFields.value = [{ field_name: '', field_type: 'float', field_role: '输入特征', description: '' }];
  uploadDialogVisible.value = true;
};

/** 打开"创建新版本"弹窗：加载当前启用版本的字段结构，允许修改后保存为新版本（需求 2.3.3） */
const openNewVersion = async (dataset: Dataset) => {
  uploadDialogMode.value = 'newVersion';
  newVersionTarget.value = dataset;
  uploadForm.value = {
    dataset_id: dataset.dataset_id,
    name: dataset.name,
    scenario_id: dataset.scenario_id,
    data_format: dataset.data_format,
    record_count: dataset.record_count,
  };
  try {
    const fields = await getDatasetFields(dataset.dataset_id);
    uploadFields.value = fields.map((f) => ({
      field_name: f.field_name,
      field_type: f.field_type,
      field_role: f.field_role,
      description: f.description,
    }));
  } catch {
    uploadFields.value = [];
  }
  uploadDialogVisible.value = true;
};

const addUploadField = () => {
  uploadFields.value.push({ field_name: '', field_type: 'float', field_role: '输入特征', description: '' });
};

const removeUploadField = (index: number) => {
  uploadFields.value.splice(index, 1);
};

const submitUpload = async () => {
  if (!uploadForm.value.scenario_id) {
    ElMessage.warning('必须指定所属场景');
    return;
  }
  if (!uploadForm.value.dataset_id.trim() || !uploadForm.value.name.trim()) {
    ElMessage.warning('请填写数据集编码和名称');
    return;
  }
  const fields = uploadFields.value.filter((f) => f.field_name.trim());
  if (fields.length === 0) {
    ElMessage.warning('至少填写一个字段');
    return;
  }
  if (fields.some((f) => fields.filter((x) => x.field_name === f.field_name).length > 1)) {
    ElMessage.warning('字段名不允许重名');
    return;
  }
  if (!fields.some((f) => f.field_role === '分类标签')) {
    ElMessage.warning('必须指定一个分类标签字段');
    return;
  }
  const fieldDefs = fields.map((f) => ({
    field_name: f.field_name.trim(),
    field_type: f.field_type,
    field_role: f.field_role,
    description: f.description,
    sample_value: '',
    nullable: false,
  }));
  try {
    if (uploadDialogMode.value === 'newVersion' && newVersionTarget.value) {
      // 需求 2.3.3：修改已用数据集 → 创建新版本并保留旧版本
      const v = await createDatasetVersion(newVersionTarget.value.dataset_id, fieldDefs);
      ElMessage.success(`已创建新版本 ${v.dataset_version}，旧版本保留`);
    } else {
      await uploadDataset({
        dataset_id: uploadForm.value.dataset_id.trim(),
        name: uploadForm.value.name.trim(),
        scenario_id: uploadForm.value.scenario_id as ScenarioId,
        data_format: uploadForm.value.data_format,
        record_count: uploadForm.value.record_count,
        fields: fieldDefs,
      });
      ElMessage.success('数据集上传成功（v1）');
    }
    uploadDialogVisible.value = false;
    await loadDatasets();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败');
  }
};

// ===================== 版本管理（需求 2.3.3/2.3.5/2.3.6） =====================
const versionDialogVisible = ref(false);
const versionDialogTitle = ref('');
const versionTarget = ref<Dataset | null>(null);
const versionList = ref<DatasetVersion[]>([]);

const openVersionDialog = async (dataset: Dataset) => {
  versionTarget.value = dataset;
  versionDialogTitle.value = `版本管理 - ${dataset.name}`;
  versionDialogVisible.value = true;
  try {
    versionList.value = await getDatasetVersions(dataset.dataset_id);
  } catch {
    versionList.value = [];
  }
};

const handleDisableVersion = async (v: DatasetVersion) => {
  try {
    await disableDatasetVersion(v.dataset_version_id);
    ElMessage.success(`版本 ${v.dataset_version} 已停用`);
    if (versionTarget.value) {
      versionList.value = await getDatasetVersions(versionTarget.value.dataset_id);
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
      versionList.value = await getDatasetVersions(versionTarget.value.dataset_id);
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

/** 跳转数据集详情页（数据内容预览，需求 2.4） */
const goDatasetDetail = (dataset: Dataset) => {
  router.push({ path: `/datasets/${dataset.dataset_id}` });
};

// ===================== 生命周期 =====================
onMounted(() => {
  currentUser.value = getCurrentUser();
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
      <button v-if="isAdmin" class="upload-btn" @click="openUploadDialog">+ 上传数据集</button>
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

        <el-table-column label="版本" width="70" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span class="version-badge" :class="row.enabled ? 'version-badge--on' : 'version-badge--off'">
              {{ row.dataset_version }}{{ row.enabled ? '' : '（停用）' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="100" align="center">
          <template #default="{ row }: { row: Dataset }">
            <span class="dataset-table__time">{{ row.created_at.slice(0, 10) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="260" align="center" fixed="right">
          <template #default="{ row }: { row: Dataset }">
            <div class="dataset-ops">
              <el-button size="small" plain @click="openFieldPreview(row)">
                字段预览
              </el-button>
              <el-button size="small" plain @click="goDatasetDetail(row)">
                数据预览
              </el-button>
              <el-button v-if="isAdmin" size="small" plain @click="openVersionDialog(row)">
                版本管理
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 字段预览弹窗（append-to-body：逃出页面容器层叠上下文，不被 topbar 遮挡） -->
    <el-dialog
      v-model="fieldDialogVisible"
      :title="fieldDialogTitle"
      width="760px"
      top="6vh"
      append-to-body
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
        max-height="62vh"
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

    <!-- 上传数据集 / 创建新版本弹窗（管理员，需求 2.3.2 / 2.3.3；append-to-body 防 topbar 遮挡） -->
    <el-dialog
      v-model="uploadDialogVisible"
      :title="uploadDialogMode === 'newVersion' ? `创建新版本 - ${newVersionTarget?.name ?? ''}` : '上传数据集'"
      width="680px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="upload-form">
        <div class="upload-form__row">
          <label class="upload-form__label">数据集编码<span class="required">*</span></label>
          <input v-model.trim="uploadForm.dataset_id" class="upload-form__input" placeholder="如 my_dataset_01" :disabled="uploadDialogMode === 'newVersion'" />
        </div>
        <div class="upload-form__row">
          <label class="upload-form__label">数据集名称<span class="required">*</span></label>
          <input v-model.trim="uploadForm.name" class="upload-form__input" placeholder="如 My Dataset" :disabled="uploadDialogMode === 'newVersion'" />
        </div>
        <div class="upload-form__row">
          <label class="upload-form__label">所属场景<span class="required">*</span></label>
          <select v-model="uploadForm.scenario_id" class="upload-form__input" :disabled="uploadDialogMode === 'newVersion'">
            <option value="" disabled>-- 请选择场景 --</option>
            <option value="network_security">网络安全</option>
            <option value="power_system">电力系统</option>
            <option value="flightdeck_operation">航母甲板作业</option>
            <option value="geological_risk">地质风险</option>
          </select>
        </div>
        <div class="upload-form__row upload-form__row--split">
          <div class="upload-form__half">
            <label class="upload-form__label">数据格式</label>
            <select v-model="uploadForm.data_format" class="upload-form__input" :disabled="uploadDialogMode === 'newVersion'">
              <option value="arff">ARFF</option>
              <option value="csv">CSV</option>
              <option value="json">JSON</option>
            </select>
          </div>
          <div class="upload-form__half">
            <label class="upload-form__label">样本数量</label>
            <input v-model.number="uploadForm.record_count" type="number" min="0" class="upload-form__input" placeholder="0" />
          </div>
        </div>
        <p v-if="uploadDialogMode === 'newVersion'" class="version-tip">创建新版本将保留旧版本，已产生的历史模型、推理记录和风险事件继续可追溯。</p>

        <div class="upload-form__row">
          <label class="upload-form__label">固定字段结构<span class="required">*</span>（至少一个字段，且必须包含一个分类标签）</label>
          <div class="upload-fields">
            <div v-for="(f, index) in uploadFields" :key="index" class="upload-field-row">
              <input v-model.trim="f.field_name" class="upload-form__input upload-field-name" placeholder="字段名" />
              <select v-model="f.field_type" class="upload-form__input upload-field-type">
                <option value="float">float</option>
                <option value="int">int</option>
                <option value="string">string</option>
              </select>
              <select v-model="f.field_role" class="upload-form__input upload-field-role">
                <option value="输入特征">输入特征</option>
                <option value="分类标签">分类标签</option>
              </select>
              <button class="upload-field-del" @click="removeUploadField(index)">✕</button>
            </div>
            <button class="upload-add-field" @click="addUploadField">+ 添加字段</button>
          </div>
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
      width="720px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="version-dialog-toolbar">
        <span class="version-dialog-toolbar__tip">修改已用数据集时将创建新版本并保留旧版本（需求 2.3.3）</span>
        <el-button
          v-if="versionTarget"
          size="small"
          type="primary"
          plain
          @click="openNewVersion(versionTarget)"
        >
          修改字段 → 创建新版本
        </el-button>
      </div>
      <el-table
        :data="versionList"
        stripe
        max-height="62vh"
        style="width: 100%"
        empty-text="暂无版本记录"
      >
        <el-table-column prop="dataset_version" label="版本" width="70" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            <span class="version-badge" :class="row.enabled ? 'version-badge--on' : 'version-badge--off'">
              {{ row.dataset_version }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="样本数" width="90" align="right">
          <template #default="{ row }: { row: DatasetVersion }">
            {{ row.record_count.toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column prop="field_count" label="字段数" width="70" align="center" />
        <el-table-column prop="uploaded_by" label="上传人" width="80" align="center" />
        <el-table-column prop="uploaded_at" label="上传时间" min-width="150" />
        <el-table-column prop="referenced" label="引用" width="70" align="center">
          <template #default="{ row }: { row: DatasetVersion }">
            <span :class="row.referenced ? 'text-active' : 'text-muted'">{{ row.referenced ? '是' : '否' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center" fixed="right">
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
      <p class="version-tip">已被模型引用的数据集版本只能停用，不能物理删除；停用后不得用于新的模型训练。</p>
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
}

.version-badge--on {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.version-badge--off {
  background: rgba(220, 234, 255, 0.08);
  color: rgba(220, 234, 255, 0.5);
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

.upload-form__row--split {
  flex-direction: row;
  gap: 14px;
}

.upload-form__half {
  flex: 1;
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

.upload-fields {
  display: grid;
  gap: 8px;
  max-height: 45vh; /* 字段较多时列表内部竖向滚动，标题/X/底部按钮始终可见 */
  overflow-y: auto;
  padding-right: 4px;
}

.upload-field-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.upload-field-name {
  flex: 2;
}

.upload-field-type {
  flex: 1;
}

.upload-field-role {
  flex: 1;
}

.upload-field-del {
  border: none;
  background: transparent;
  color: rgba(255, 123, 114, 0.7);
  font-size: 0.9rem;
  cursor: pointer;
  flex-shrink: 0;
  padding: 6px;
}

.upload-add-field {
  padding: 8px 14px;
  border: 1px dashed rgba(125, 201, 255, 0.3);
  border-radius: 8px;
  background: transparent;
  color: #9ad6ff;
  font-size: 0.85rem;
  cursor: pointer;
}

.upload-add-field:hover {
  background: rgba(91, 166, 255, 0.1);
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
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.version-dialog-toolbar__tip {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
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
