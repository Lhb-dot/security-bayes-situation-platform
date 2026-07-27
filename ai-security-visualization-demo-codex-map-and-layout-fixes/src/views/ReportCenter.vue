<script setup lang="ts">
/**
 * ReportCenter - 报告中心页面
 *
 * 报告列表：名称、场景、创建时间、状态
 * 操作：查看、下载、重新生成
 */
import { onMounted, ref } from 'vue';
import type { Report } from '@/types/security';
import { getReportList } from '@/services/mockApi';
import { ElMessage } from 'element-plus';

const reports = ref<Report[]>([]);
const loading = ref(true);
const error = ref('');

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

const handleDownload = (report: Report) => {
  if (report.file_url) {
    ElMessage.success(`正在下载：${report.title}`);
  } else {
    ElMessage.info('该报告暂无下载文件');
  }
};

const handleRegenerate = async (report: Report) => {
  ElMessage.success(`已重新生成报告：${report.title}`);
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

onMounted(() => {
  loadReports();
});
</script>

<template>
  <div class="report-center">
    <div class="report-center__header">
      <div>
        <p class="eyebrow">Report Center</p>
        <h2>报告中心</h2>
        <p class="report-center__desc">态势报告生成与下载管理</p>
      </div>
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
            <el-tag size="small" effect="dark" :type="row.format === 'pdf' ? 'danger' : row.format === 'html' ? 'warning' : 'info'">
              {{ formatLabel[row.format] ?? row.format.toUpperCase() }}
            </el-tag>
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
  border: 1px solid rgba(125, 201, 255, 0.16);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(11, 22, 40, 0.6);
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

.report-table__actions {
  display: flex;
  gap: 4px;
  justify-content: center;
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
  background-color: rgba(91, 166, 255, 0.08) !important;
  color: #9ad6ff !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.12) !important;
}

.report-center .el-table td.el-table__cell {
  background-color: transparent !important;
  color: #d9e8ff !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.06) !important;
}

.report-center .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: rgba(255, 255, 255, 0.02) !important;
}

.report-center .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(91, 166, 255, 0.06) !important;
}

.report-center .el-table__empty-text {
  color: rgba(220, 234, 255, 0.4) !important;
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
