<script setup lang="ts">
/**
 * ReportCenter - 报告中心页面
 *
 * 报告列表：名称、场景、创建时间、状态
 * 操作：查看、下载、重新生成
 */
import { computed, onMounted, ref } from 'vue';
import type { Report, ScenarioId, UserAccount } from '@/types/security';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useUserStore } from '@/stores/userStore';
import { getReportList, generateReport, updateReportSchedule } from '@/api/reportApi';
import { ElMessage } from 'element-plus';

const reports = ref<Report[]>([]);
const loading = ref(true);
const error = ref('');
const users = ref<UserAccount[]>([]);
const scenarioStore = useScenarioStore();
const userStore = useUserStore();

const currentUser = computed(() => userStore.currentUser);
const isAdmin = computed(() => userStore.isManagement);
const isSuperAdmin = computed(() => userStore.isSuperAdmin);

const loadReports = async () => {
  loading.value = true;
  error.value = '';
  try {
    reports.value = await getReportList({ page: 1, page_size: 200 });
  } catch (err) {
    error.value = err instanceof Error ? err.message : '报告数据加载失败';
  } finally {
    loading.value = false;
  }
};

const handleView = (report: Report) => {
  viewTarget.value = report;
  viewVisible.value = true;
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
    report.content ?? report.summary,
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
      scope: report.target_user_id ? 'user' : isAdmin.value ? 'all' : 'self',
      target_user_id: report.target_user_id,
      format: report.format,
      scheduled: report.scheduled,
      interval_days: report.interval_days,
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
  format: 'markdown' as 'markdown' | 'html' | 'pdf',
  scheduled: false,
  interval_days: 7,
});

const viewVisible = ref(false);
const viewTarget = ref<Report | null>(null);

const openGenerate = () => {
  genForm.value = { title: '', scenario_id: isSuperAdmin.value ? '' : (currentUser.value?.scenario_code ?? ''), scope: isAdmin.value ? 'all' : 'self', target_user_id: '', format: 'markdown', scheduled: false, interval_days: 7 };
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
      format: genForm.value.format,
      scheduled: genForm.value.scheduled,
      interval_days: genForm.value.scheduled ? genForm.value.interval_days : undefined,
    });
    ElMessage.success(`报告生成成功：${created.report_id}`);
    genVisible.value = false;
    await loadReports();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '生成失败');
  }
};

// ===================== 定时设置（修改/取消定时） =====================
const scheduleVisible = ref(false);
const scheduleTarget = ref<Report | null>(null);
const scheduleForm = ref({
  scheduled: false,
  interval_days: 7,
});

const openSchedule = (report: Report) => {
  scheduleTarget.value = report;
  scheduleForm.value = {
    scheduled: report.scheduled ?? false,
    interval_days: report.interval_days ?? 7,
  };
  scheduleVisible.value = true;
};

const submitSchedule = async () => {
  if (!scheduleTarget.value) return;
  if (scheduleForm.value.scheduled && (!scheduleForm.value.interval_days || scheduleForm.value.interval_days < 1)) {
    ElMessage.warning('请填写正确的生成周期（至少 1 天）');
    return;
  }
  try {
    await updateReportSchedule(
      scheduleTarget.value.report_id,
      scheduleForm.value.scheduled,
      scheduleForm.value.scheduled ? scheduleForm.value.interval_days : undefined,
    );
    ElMessage.success(
      scheduleForm.value.scheduled
        ? `已设为每 ${scheduleForm.value.interval_days} 天自动生成`
        : '已取消定时生成',
    );
    scheduleVisible.value = false;
    await loadReports();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '定时设置失败');
  }
};

/** 输入框聚焦时全选，避免在原数字后追加导致拼接（如 7 变 78） */
const selectAll = (e: Event) => {
  (e.target as HTMLInputElement)?.select();
};

const statusLabel: Record<string, string> = {
  completed: '已完成',
  generating: '生成中',
  failed: '生成失败',
};

const scenarioLabel: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '航母甲板',
};

/** 报告生成场景选项：从 scenarioStore.activeScenarios 注入（Task 016） */
const scenarioOptions = computed(() =>
  scenarioStore.activeScenarios.map((s) => ({ value: s.scenario_id, label: s.name }))
);

const formatLabel: Record<string, string> = {
  markdown: 'Markdown',
  html: 'HTML',
  pdf: 'PDF',
};

onMounted(async () => {
  if (!userStore.initialized) await userStore.bootstrap();
  await scenarioStore.fetchScenarioList();
  if (isAdmin.value) {
    await userStore.fetchUsers({ page: 1, page_size: 200 });
    users.value = userStore.users;
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

        <el-table-column label="定时" width="120" align="center">
          <template #default="{ row }: { row: Report }">
            <span v-if="row.scheduled" class="report-table__schedule">每 {{ row.interval_days ?? '-' }} 天</span>
            <span v-else class="report-table__schedule report-table__schedule--off">—</span>
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

        <el-table-column label="操作" width="300" align="center" fixed="right">
          <template #default="{ row }: { row: Report }">
            <div class="report-table__actions">
              <el-button size="small" type="primary" plain @click="handleView(row)">查看</el-button>
              <el-button size="small" @click="handleDownload(row)">下载</el-button>
              <el-button v-if="row.generated_by === currentUser?.user_id" size="small" type="success" plain @click="openSchedule(row)">定时</el-button>
              <el-button v-if="row.generated_by === currentUser?.user_id" size="small" type="warning" plain @click="handleRegenerate(row)">重新生成</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 生成报告弹窗（与数据集中心字段预览同款 el-dialog；场景下拉仅系统管理员可见） -->
    <el-dialog
      v-model="genVisible"
      class="report-dialog"
      title="生成态势报告"
      width="760px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="gen-form">
        <div class="gen-field">
          <label class="gen-field__label">报告标题<span class="required">*</span></label>
          <input v-model.trim="genForm.title" class="gen-field__input" placeholder="如：网络安全月度态势报告" />
        </div>
        <div v-if="isSuperAdmin" class="gen-field">
          <label class="gen-field__label">报告场景<span class="required">*</span></label>
          <select v-model="genForm.scenario_id" class="gen-field__input">
            <option value="" disabled>-- 请选择场景 --</option>
            <option v-for="sc in scenarioOptions" :key="sc.value" :value="sc.value">{{ sc.label }}</option>
          </select>
        </div>
        <div v-else class="gen-field">
          <label class="gen-field__label">报告场景</label>
          <div class="gen-field__static">{{ scenarioLabel[genForm.scenario_id] ?? genForm.scenario_id }}</div>
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
        <div class="gen-field">
          <label class="gen-field__label">报告格式</label>
          <select v-model="genForm.format" class="gen-field__input">
            <option value="markdown">Markdown</option>
            <option value="html">HTML</option>
            <option value="pdf">PDF</option>
          </select>
        </div>
        <div class="gen-field">
          <label class="gen-field__label">定时生成</label>
          <div class="gen-schedule">
            <el-switch v-model="genForm.scheduled" />
            <span class="gen-schedule__hint">{{ genForm.scheduled ? '已开启定时生成' : '关闭（手动生成）' }}</span>
          </div>
        </div>
        <div v-if="genForm.scheduled" class="gen-field">
          <label class="gen-field__label">生成周期（天）</label>
          <input v-model.number="genForm.interval_days" type="number" min="1" class="gen-field__input" placeholder="如：7 表示每 7 天生成一份" @focus="selectAll" />
        </div>
      </div>
      <template #footer>
        <button class="gen-btn gen-btn--ghost" @click="genVisible = false">取消</button>
        <button class="gen-btn" @click="submitGenerate">生成报告</button>
      </template>
    </el-dialog>

    <!-- 报告详情弹窗 -->
    <el-dialog
      v-model="viewVisible"
      class="report-dialog"
      :title="viewTarget?.title ?? '报告详情'"
      width="760px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <pre class="report-content">{{ viewTarget?.content ?? viewTarget?.summary }}</pre>
    </el-dialog>

    <!-- 定时设置弹窗：只保存配置，不执行调度 -->
    <el-dialog
      v-model="scheduleVisible"
      class="report-dialog"
      title="定时设置"
      width="460px"
      top="12vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="gen-form">
        <div class="gen-field">
          <label class="gen-field__label">报告</label>
          <div class="gen-field__static">{{ scheduleTarget?.title }}</div>
        </div>
        <div class="gen-field">
          <label class="gen-field__label">定时生成</label>
          <div class="gen-schedule">
            <el-switch v-model="scheduleForm.scheduled" />
            <span class="gen-schedule__hint">{{ scheduleForm.scheduled ? '已开启定时配置' : '关闭（手动生成）' }}</span>
          </div>
        </div>
        <div v-if="scheduleForm.scheduled" class="gen-field">
          <label class="gen-field__label">生成周期（天）</label>
          <input v-model.number="scheduleForm.interval_days" type="number" min="1" class="gen-field__input" placeholder="如：7 表示每 7 天生成一份" @focus="selectAll" />
        </div>
      </div>
      <template #footer>
        <button class="gen-btn gen-btn--ghost" @click="scheduleVisible = false">取消</button>
        <button class="gen-btn" @click="submitSchedule">保存</button>
      </template>
    </el-dialog>
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

.report-table__schedule {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  background: rgba(255, 177, 107, 0.12);
  color: #ffc37d;
}

.report-table__schedule--off {
  color: rgba(220, 234, 255, 0.35);
  background: transparent;
}

.report-table__actions {
  display: flex;
  gap: 4px;
  justify-content: center;
}

/* 生成按钮 */
.gen-btn {
  padding: 10px 22px;
  border: none;
  border-radius: 999px;
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

.gen-form {
  display: grid;
  gap: 14px;
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

.gen-schedule {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 32px;
}

.gen-schedule__hint {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.55);
}

.gen-field__static {
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.12);
  background: rgba(8, 17, 31, 0.4);
  color: #cfe2ff;
  font-size: 0.88rem;
}

.report-content {
  margin: 0;
  min-height: 220px;
  max-height: 62vh;
  overflow: auto;
  white-space: pre-wrap;
  color: #d9e8ff;
  font: inherit;
  line-height: 1.7;
}
</style>

<style>

/* 与数据集中心字段预览弹窗一致的暗色 el-dialog 样式（append-to-body 后挂到 body，用 .report-dialog class 保证生效） */
.report-dialog {
  background: linear-gradient(180deg, rgba(11, 22, 40, 0.98), rgba(5, 12, 22, 0.98)) !important;
  border: 1px solid rgba(125, 201, 255, 0.18) !important;
  border-radius: 20px !important;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5) !important;
}

.report-dialog .el-dialog__title {
  color: #e8f1ff !important;
  font-size: 1.15rem !important;
}

.report-dialog .el-dialog__headerbtn .el-dialog__close {
  color: rgba(220, 234, 255, 0.5) !important;
}

.report-dialog .el-dialog__headerbtn:hover .el-dialog__close {
  color: #e8f1ff !important;
}

.report-dialog .el-dialog__body {
  padding: 20px 24px !important;
}

.report-dialog .el-dialog__footer {
  padding: 12px 24px 18px !important;
}

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

.report-center .el-button {
  border-radius: 999px;
}
</style>
