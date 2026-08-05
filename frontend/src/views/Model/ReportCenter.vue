<script setup lang="ts">
/**
 * ReportCenter - 报告中心页面
 *
 * 报告列表：名称、场景、创建时间、状态
 * 操作：查看、下载、重新生成
 */
import { computed, onMounted, ref } from 'vue';
import type { Report, ScenarioId, UserAccount } from '@/types/security';
import { getReportList, generateReport, getCurrentUser, getUserList } from '@/services/mockApi';
import { ElMessage } from 'element-plus';

const reports = ref<Report[]>([]);
const loading = ref(true);
const error = ref('');
const currentUser = ref<UserAccount | null>(null);
const users = ref<UserAccount[]>([]);

const isAdmin = computed(() => currentUser.value?.role === 'ADMIN');

const loadReports = async () => {
  loading.value = true;
  error.value = '';
  try {
    reports.value = await getReportList();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '报告数据加载失败';
  } finally {
    loading.value = false;
  }
};

const handleView = (report: Report) => {
  ElMessage.info(`查看报告：${report.title}`);
};

/** 导出报告：生成 Markdown 文本下载（需求 6.2 P1 支持导出） */
const handleDownload = (report: Report) => {
  const content = [
    `# ${report.title}`,
    '',
    `- 场景：${scenarioLabel[report.scenario_id] ?? report.scenario_id}`,
    `- 生成时间：${report.created_at}`,
    `- 格式：${formatLabel[report.format] ?? report.format}`,
    '',
    '## 摘要',
    '',
    report.summary,
    '',
    '---',
    '由多场景贝叶斯分类态势感知系统自动生成',
  ].join('\n');
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${report.report_id}.md`;
  a.click();
  URL.revokeObjectURL(url);
  ElMessage.success(`已导出报告：${report.title}`);
};

/** 重新生成报告（基于当前用户数据范围） */
const handleRegenerate = async (report: Report) => {
  try {
    await generateReport({
      scenario_id: report.scenario_id,
      title: report.title,
      scope: isAdmin.value ? 'all' : 'self',
    });
    ElMessage.success(`已重新生成报告：${report.title}`);
    await loadReports();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '重新生成失败');
  }
};

// ===================== 生成报告（需求 6.2 P1） =====================
const genVisible = ref(false);
const genForm = ref({
  title: '',
  scenario_id: '' as ScenarioId | '',
  scope: 'self' as 'self' | 'all' | 'user',
  target_user_id: '',
});

const openGenerate = () => {
  genForm.value = { title: '', scenario_id: '', scope: isAdmin.value ? 'all' : 'self', target_user_id: '' };
  genVisible.value = true;
};

const submitGenerate = async () => {
  if (!genForm.value.title.trim()) {
    ElMessage.warning('请填写报告标题');
    return;
  }
  if (!genForm.value.scenario_id) {
    ElMessage.warning('请选择报告场景');
    return;
  }
  if (genForm.value.scope === 'user' && !genForm.value.target_user_id) {
    ElMessage.warning('请选择目标用户');
    return;
  }
  try {
    const created = await generateReport({
      scenario_id: genForm.value.scenario_id as ScenarioId,
      title: genForm.value.title.trim(),
      scope: genForm.value.scope,
      target_user_id: genForm.value.target_user_id || undefined,
    });
    ElMessage.success(`报告生成成功：${created.report_id}`);
    genVisible.value = false;
    await loadReports();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '生成失败');
  }
};

const statusLabel: Record<string, string> = {
  completed: '已完成',
  generating: '生成中',
  failed: '生成失败',
};

const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板',
};

const formatLabel: Record<string, string> = {
  markdown: 'Markdown',
  html: 'HTML',
  pdf: 'PDF',
};

onMounted(async () => {
  currentUser.value = getCurrentUser();
  if (isAdmin.value) {
    users.value = await getUserList();
  }
  await loadReports();
});
</script>

<template>
  <div class="report-center">
    <div class="report-center__header">
      <div>
        <p class="eyebrow">Report Center</p>
        <h2>报告中心</h2>
        <p class="report-center__desc">
          {{ isAdmin ? '可基于全平台或指定用户数据生成报告并导出' : '仅可基于本人数据生成报告并导出' }}
        </p>
      </div>
      <button class="gen-btn" @click="openGenerate">+ 生成报告</button>
    </div>

    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载报告数据...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadReports">重试</button>
    </section>

    <!-- 报告列表 -->
    <div v-else class="report-center__table-wrap">
      <el-table
        :data="reports"
        stripe
        style="width: 100%"
        empty-text="暂无报告"
        row-class-name="report-table-row"
      >
        <el-table-column prop="title" label="报告名称" min-width="220" show-overflow-tooltip>
          <template #default="{ row }: { row: Report }">
            <div class="report-table__title-cell">
              <span class="report-table__title">{{ row.title }}</span>
              <span class="report-table__summary">{{ row.summary }}</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="所属场景" width="120" align="center">
          <template #default="{ row }: { row: Report }">
            <span class="report-table__scenario-tag">{{ scenarioLabel[row.scenario_id] ?? row.scenario_id }}</span>
          </template>
        </el-table-column>

        <el-table-column label="格式" width="100" align="center">
          <template #default="{ row }: { row: Report }">
            <span
              class="report-table__format-badge"
              :class="`format-badge--${row.format}`"
            >
              {{ formatLabel[row.format] ?? row.format.toUpperCase() }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="160" align="center" />

        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }: { row: Report }">
            <span
              class="report-table__status"
              :class="`report-status--${row.status}`"
            >
              {{ statusLabel[row.status] ?? row.status }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }: { row: Report }">
            <div class="report-table__actions">
              <el-button size="small" type="primary" plain @click="handleView(row)">查看</el-button>
              <el-button size="small" @click="handleDownload(row)">下载</el-button>
              <el-button size="small" type="warning" plain @click="handleRegenerate(row)">重新生成</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 生成报告弹窗 -->
    <div v-if="genVisible" class="modal-mask" @click.self="genVisible = false">
      <div class="modal-card">
        <div class="modal-card__head">
          <h3>生成态势报告</h3>
          <button class="modal-close" @click="genVisible = false">✕</button>
        </div>
        <div class="modal-card__body">
          <div class="gen-field">
            <label class="gen-field__label">报告标题<span class="required">*</span></label>
            <input v-model.trim="genForm.title" class="gen-field__input" placeholder="如：网络安全月度态势报告" />
          </div>
          <div class="gen-field">
            <label class="gen-field__label">报告场景<span class="required">*</span></label>
            <select v-model="genForm.scenario_id" class="gen-field__input">
              <option value="" disabled>-- 请选择场景 --</option>
              <option value="network_security">网络安全</option>
              <option value="power_system">电力系统</option>
            </select>
          </div>
          <div class="gen-field">
            <label class="gen-field__label">数据范围</label>
            <select v-model="genForm.scope" class="gen-field__input" :disabled="!isAdmin">
              <option value="self">本人数据</option>
              <option v-if="isAdmin" value="all">全平台数据</option>
              <option v-if="isAdmin" value="user">指定用户数据</option>
            </select>
          </div>
          <div v-if="isAdmin && genForm.scope === 'user'" class="gen-field">
            <label class="gen-field__label">目标用户<span class="required">*</span></label>
            <select v-model="genForm.target_user_id" class="gen-field__input">
              <option value="" disabled>-- 请选择用户 --</option>
              <option v-for="u in users" :key="u.user_id" :value="u.user_id">{{ u.username }}（{{ u.display_name }}）</option>
            </select>
          </div>
        </div>
        <div class="modal-card__foot">
          <button class="gen-btn gen-btn--ghost" @click="genVisible = false">取消</button>
          <button class="gen-btn" @click="submitGenerate">生成报告</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.report-center {
  position: relative;
  z-index: 1;
}

.report-center__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 20px;
}

.report-center__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.report-center__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.report-center__table-wrap {
  border: 1px solid rgba(125, 201, 255, 0.10);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(8, 18, 34, 0.7);
}

.report-table-row {
  background: transparent !important;
}

.report-table__title-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
}

.report-table__title {
  font-weight: 600;
  color: #e8f1ff;
  font-size: 0.95rem;
}

.report-table__summary {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.55);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-table__scenario-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  background: rgba(91, 166, 255, 0.14);
  color: #9ad6ff;
}

.report-table__status {
  font-size: 0.82rem;
  padding: 2px 10px;
  border-radius: 999px;
}

.report-status--completed {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.report-status--generating {
  background: rgba(255, 177, 107, 0.12);
  color: #ffc37d;
}

.report-status--failed {
  background: rgba(255, 123, 114, 0.12);
  color: #ff8c84;
}

/* 格式徽章 */
.report-table__format-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.format-badge--pdf {
  background: rgba(255, 123, 114, 0.12);
  color: #e88982;
}

.format-badge--html {
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
}

.format-badge--markdown {
  background: rgba(83, 229, 200, 0.10);
  color: #6fe8d0;
}

.report-table__actions {
  display: flex;
  gap: 4px;
  justify-content: center;
}

/* 生成按钮 */
.gen-btn {
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

.gen-btn:hover {
  opacity: 0.9;
}

.gen-btn--ghost {
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  border: 1px solid rgba(125, 201, 255, 0.25);
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(3, 8, 16, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-card {
  width: 460px;
  max-width: calc(100vw - 40px);
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.96), rgba(8, 17, 31, 0.98));
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.1);
}

.modal-card__head h3 {
  margin: 0;
  font-size: 1.05rem;
}

.modal-close {
  border: none;
  background: transparent;
  color: rgba(220, 234, 255, 0.6);
  font-size: 1rem;
  cursor: pointer;
}

.modal-card__body {
  padding: 20px;
  display: grid;
  gap: 14px;
}

.modal-card__foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid rgba(125, 201, 255, 0.1);
}

.gen-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gen-field__label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.gen-field__label .required {
  color: #ff7b72;
  margin-left: 2px;
}

.gen-field__input {
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.7);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
}

.gen-field__input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.gen-field__input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.gen-field__input option {
  background: #0b1628;
  color: #e8f1ff;
}
</style>

<style>
.report-center .el-table,
.report-center .el-table__inner-wrapper,
.report-center .el-table__body-wrapper,
.report-center .el-table__header-wrapper {
  background-color: transparent !important;
}

.report-center .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.report-center .el-table td.el-table__cell {
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.report-center .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: rgba(10, 24, 44, 0.85) !important;
}

.report-center .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
}

.report-center .el-table__empty-text {
  color: rgba(155, 185, 225, 0.3) !important;
}

.report-center .el-button--primary.is-plain {
  --el-button-bg-color: rgba(91, 166, 255, 0.14) !important;
  --el-button-border-color: rgba(91, 166, 255, 0.35) !important;
  --el-button-text-color: #9ad6ff !important;
  --el-button-hover-bg-color: rgba(91, 166, 255, 0.22) !important;
  --el-button-hover-border-color: rgba(91, 166, 255, 0.5) !important;
  --el-button-hover-text-color: #bae3ff !important;
}

.report-center .el-button--warning.is-plain {
  --el-button-bg-color: rgba(255, 177, 107, 0.14) !important;
  --el-button-border-color: rgba(255, 177, 107, 0.35) !important;
  --el-button-text-color: #ffc37d !important;
  --el-button-hover-bg-color: rgba(255, 177, 107, 0.22) !important;
  --el-button-hover-border-color: rgba(255, 177, 107, 0.5) !important;
  --el-button-hover-text-color: #ffd9a3 !important;
}

.report-center .el-button--default {
  --el-button-bg-color: rgba(220, 234, 255, 0.08) !important;
  --el-button-border-color: rgba(220, 234, 255, 0.2) !important;
  --el-button-text-color: #d9e8ff !important;
  --el-button-hover-bg-color: rgba(220, 234, 255, 0.15) !important;
  --el-button-hover-border-color: rgba(220, 234, 255, 0.35) !important;
  --el-button-hover-text-color: #fff !important;
}
</style>
