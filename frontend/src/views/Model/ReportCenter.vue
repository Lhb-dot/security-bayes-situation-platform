<script setup lang="ts">
/**
 * ReportCenter - 报告中心页面
 *
 * 报告列表：名称、场景、创建时间、状态
 * 操作：查看、下载、重新生成
 */
import { computed, onMounted, ref } from 'vue';
import type { Report, ReportData, ScenarioId, UserAccount } from '@/types/security';
import BarChart from '@/components/charts/BarChart.vue';
import PieChart from '@/components/charts/PieChart.vue';
import { useScenarioStore } from '@/stores/scenarioStore';
import { useUserStore } from '@/stores/userStore';
import { getReportList, getReportDetail, generateReport, updateReportSchedule, removeReport } from '@/api/reportApi';
import { ElMessage, ElMessageBox } from 'element-plus';

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

const handleView = async (report: Report) => {
  viewTarget.value = report;
  viewVisible.value = true;
  try {
    // 拉取详情以获取结构化 report_data（列表接口不返回，避免载荷膨胀）
    viewTarget.value = await getReportDetail(report.report_id);
  } catch {
    // 详情拉取失败时回退到列表数据（仅显示摘要文本）
  }
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

/** 删除报告（生成者本人或管理员） */
const handleDelete = async (report: Report) => {
  try {
    await ElMessageBox.confirm(
      `确认删除报告「${report.title}」？删除后不可恢复。`,
      '删除报告',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    );
  } catch {
    return; // 用户取消
  }
  try {
    await removeReport(report.report_id);
    ElMessage.success('报告已删除');
    await loadReports();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '删除失败');
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

// ===================== 报告结构化详情（report_data 渲染，6.10.3） =====================
const viewReportData = computed<ReportData | undefined>(() => {
  const d = viewTarget.value?.report_data;
  // 旧结构报告（无 report_info）回退纯文本，避免模板访问 undefined 报错
  return d && (d as ReportData).report_info ? (d as ReportData) : undefined;
});

const pctText = (v: number | null | undefined): string => (v == null ? '—' : `${(v * 100).toFixed(0)}%`);

/** 态势核心指标卡 */
const overviewMetrics = computed(() => {
  const o = viewReportData.value?.overview;
  if (!o) return [];
  return [
    { label: '推理总量', value: String(o.total_inferences) },
    { label: '风险', value: `${o.risk_count}（${pctText(o.risk_ratio)}）`, tone: 'high' },
    { label: '正常', value: `${o.normal_count}（${pctText(o.normal_ratio)}）`, tone: 'normal' },
    { label: '高危', value: String(o.high_count), tone: 'high' },
    { label: '中危', value: String(o.medium_count), tone: 'medium' },
    { label: '低危', value: String(o.low_count), tone: 'low' },
    { label: '待处置/已处置', value: `${o.pending_count}/${o.resolved_count}` },
    { label: '平均风险概率', value: o.avg_risk_prob == null ? '—' : o.avg_risk_prob.toFixed(3) },
    { label: '风险变化方向', value: o.risk_trend },
  ];
});

/** 预测标签分布（柱状） */
const labelDistBar = computed(() => {
  const dist = viewReportData.value?.prediction?.label_distribution ?? [];
  return dist.map((d) => ({ name: d.label, score: d.count }));
});

/** 风险概率区间（横向柱状） */
const riskProbBar = computed(() => {
  const buckets = viewReportData.value?.prediction?.risk_prob_buckets ?? [];
  return buckets.map((b) => ({ name: b.range, score: b.count }));
});

/** 类别概率（环形图） */
const classProbItems = computed(() => {
  const dist = viewReportData.value?.prediction?.class_probability ?? [];
  const palette = ['#5ba6ff', '#53e5c8', '#ff7b72', '#ffd166', '#a78bfa'];
  return dist.map((d, i) => ({
    label: d.class,
    value: d.probability ?? 0,
    color: palette[i % palette.length],
  }));
});

/** 有独立视图的模型 */
const multiViewModels = computed(() =>
  (viewReportData.value?.model_analysis ?? []).filter((m) => m.has_views),
);

/** 无独立视图的模型 */
const singleViewModels = computed(() =>
  (viewReportData.value?.model_analysis ?? []).filter((m) => !m.has_views),
);

/** 单个模型的多视图对比图数据 */
const viewChartFor = (model: ReportData['model_analysis'][number]) => {
  const views = model.views ?? [];
  if (views.length < 2) return null;
  const categories = (views[0].distribution ?? []).map((d) => d.class);
  return {
    categories,
    series: views.map((v) => ({
      name: v.name,
      data: categories.map((c) => v.distribution.find((d) => d.class === c)?.probability ?? 0),
    })),
  };
};

/** 关键风险特征 Top-K */
const topFeatures = computed(() => viewReportData.value?.feature_analysis?.top_features ?? []);

/** 风险趋势 */
const trendRows = computed(() => viewReportData.value?.trend ?? []);

/** 重点风险事件 */
const keyEvents = computed(() => viewReportData.value?.key_events ?? []);

const riskLevelLabel = (level: string | null | undefined): string => {
  if (!level) return '';
  return ({ HIGH: '高危', MEDIUM: '中危', LOW: '低危' } as Record<string, string>)[level] ?? level;
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

        <el-table-column label="操作" width="360" align="center" fixed="right">
          <template #default="{ row }: { row: Report }">
            <div class="report-table__actions">
              <el-button size="small" type="primary" plain @click="handleView(row)">查看</el-button>
              <el-button size="small" @click="handleDownload(row)">下载</el-button>
              <el-button v-if="row.generated_by === currentUser?.user_id" size="small" type="success" plain @click="openSchedule(row)">定时</el-button>
              <el-button v-if="row.generated_by === currentUser?.user_id" size="small" type="warning" plain @click="handleRegenerate(row)">重新生成</el-button>
              <el-button v-if="row.generated_by === currentUser?.user_id || isAdmin" size="small" type="danger" plain @click="handleDelete(row)">删除</el-button>
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
      width="820px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <!-- 结构化报告（6.10.2/6.10.3 定义的完整内容） -->
      <div v-if="viewReportData" class="report-detail">
        <!-- 一、报告基本信息 -->
        <section class="report-section">
          <h3 class="report-section__title">报告基本信息</h3>
          <div class="info-grid">
            <span class="info-item"><b>报告期</b>{{ viewReportData.report_info.report_period ?? '—' }}</span>
            <span class="info-item"><b>生成者</b>{{ viewReportData.report_info.generated_by }}</span>
            <span class="info-item"><b>场景</b>{{ viewReportData.report_info.scenario_name ?? '—' }}</span>
            <span class="info-item"><b>数据范围</b>{{ viewReportData.report_info.data_scope }}</span>
            <span class="info-item"><b>涉及算法</b>{{ viewReportData.report_info.algorithms.map((a) => a.name).join('、') || '—' }}</span>
            <span class="info-item"><b>生成时间</b>{{ viewReportData.report_info.generated_at }}</span>
          </div>
        </section>

        <!-- 二、态势概况 -->
        <section class="report-section">
          <h3 class="report-section__title">态势概况</h3>
          <div class="stat-grid">
            <div
              v-for="m in overviewMetrics"
              :key="m.label"
              class="stat-card"
              :class="m.tone ? 'stat-card--' + m.tone : ''"
            >
              <span class="stat-card__num">{{ m.value }}</span>
              <span class="stat-card__label">{{ m.label }}</span>
            </div>
          </div>
        </section>

        <!-- 三、最终预测结果与概率 -->
        <section class="report-section">
          <h3 class="report-section__title">最终预测结果与概率</h3>
          <div class="chart-row">
            <div v-if="labelDistBar.length" class="chart-box">
              <BarChart :data="labelDistBar" title="预测标签分布" height="220px" />
            </div>
            <div v-if="classProbItems.length" class="chart-box">
              <PieChart :items="classProbItems" donut title="类别概率" height="220px" />
            </div>
          </div>
          <div v-if="riskProbBar.length" class="chart-box">
            <BarChart :data="riskProbBar" horizontal title="风险概率区间分布" height="180px" />
          </div>
          <p class="report-section__hint">
            低置信度/接近阈值样本：{{ viewReportData.prediction.low_confidence_count }} 条
          </p>
        </section>

        <!-- 四、不同视图预测结果与概率 -->
        <section v-if="viewReportData.model_analysis.length" class="report-section">
          <h3 class="report-section__title">不同视图预测结果与概率</h3>
          <div v-for="m in multiViewModels" :key="m.model_version_id" class="model-block">
            <p class="report-section__hint">
              <b>{{ m.algorithm_name ?? m.algorithm_code }}</b>（模型 {{ m.model_version_id }}）
              · 推理 {{ m.inference_count }} 条 / 风险 {{ m.risk_count }} 条
              <template v-if="m.view_weights.length">
                · 视图权重：{{ m.view_weights.map((w) => w.toFixed(2)).join(' / ') }}
              </template>
            </p>
            <div v-if="viewChartFor(m)" class="chart-box">
              <BarChart
                :categories="viewChartFor(m)?.categories ?? []"
                :series="viewChartFor(m)?.series ?? []"
                height="220px"
              />
            </div>
            <table class="mini-table">
              <thead><tr><th>视图</th><th>预测标签</th><th>与最终预测</th></tr></thead>
              <tbody>
                <tr v-for="v in m.views" :key="v.name">
                  <td>{{ v.name }}</td>
                  <td>{{ v.predicted_label }}</td>
                  <td>{{ v.consistent_with_final ? '一致' : '分歧' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="singleViewModels.length" class="report-section__hint">
            无独立视图：{{ singleViewModels.map((m) => m.algorithm_name ?? m.algorithm_code).join('、') }}
          </p>
        </section>

        <!-- 五、特征加权条件概率 -->
        <section v-if="topFeatures.length" class="report-section">
          <h3 class="report-section__title">特征加权条件概率（Top {{ topFeatures.length }}）</h3>
          <p v-if="viewReportData.feature_analysis.calculation_method" class="report-section__hint">
            口径：{{ viewReportData.feature_analysis.calculation_method }}
          </p>
          <table class="mini-table">
            <thead><tr><th>#</th><th>特征值</th><th>所属视图</th><th>权重</th><th>支持方向</th></tr></thead>
            <tbody>
              <tr v-for="f in topFeatures" :key="f.rank">
                <td>{{ f.rank }}</td>
                <td>{{ f.attribute }} = {{ f.value }}</td>
                <td>{{ f.view ?? '—' }}</td>
                <td>{{ f.weight?.toFixed(3) ?? '—' }}</td>
                <td>{{ f.support_direction }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <!-- 六、风险趋势与重点事件 -->
        <section v-if="trendRows.length || keyEvents.length" class="report-section">
          <h3 class="report-section__title">风险趋势与重点事件</h3>
          <table v-if="trendRows.length" class="mini-table">
            <thead><tr><th>日期</th><th>推理</th><th>风险</th><th>风险占比</th></tr></thead>
            <tbody>
              <tr v-for="t in trendRows" :key="t.date">
                <td>{{ t.date }}</td>
                <td>{{ t.inference_count }}</td>
                <td>{{ t.risk_count }}</td>
                <td>{{ pctText(t.risk_ratio) }}</td>
              </tr>
            </tbody>
          </table>
          <template v-if="keyEvents.length">
            <p class="report-section__hint report-section__hint--mt">重点风险事件</p>
            <table class="mini-table">
              <thead><tr><th>时间</th><th>等级</th><th>概率</th><th>状态</th></tr></thead>
              <tbody>
                <tr v-for="(e, i) in keyEvents" :key="i">
                  <td>{{ e.time }}</td>
                  <td>{{ e.risk_level }}</td>
                  <td>{{ e.probability }}</td>
                  <td>{{ e.status }}</td>
                </tr>
              </tbody>
            </table>
          </template>
        </section>

        <!-- 七、态势分析 + 风险规避指导 -->
        <section v-if="viewReportData.analysis_nl || viewReportData.guidance_nl" class="report-section">
          <h3 class="report-section__title">态势分析</h3>
          <p class="report-nl">{{ viewReportData.analysis_nl }}</p>
          <h3 class="report-section__title report-section__title--mt">风险规避指导</h3>
          <p class="report-nl report-nl--guidance">{{ viewReportData.guidance_nl }}</p>
        </section>

        <!-- 八、数据说明 -->
        <section v-if="viewReportData.data_notes" class="report-section">
          <h3 class="report-section__title">数据说明</h3>
          <p class="report-nl">{{ viewReportData.data_notes }}</p>
        </section>
      </div>

      <!-- 无结构化数据时回退纯文本 -->
      <pre v-else class="report-content">{{ viewTarget?.content ?? viewTarget?.summary }}</pre>
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

/* ===================== 结构化报告详情 ===================== */
.report-detail {
  max-height: 68vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-right: 4px;
}

.report-section {
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 12px;
  padding: 14px 16px;
  background: rgba(8, 17, 31, 0.45);
}

.report-section__title {
  margin: 0 0 10px;
  font-size: 0.95rem;
  font-weight: 600;
  color: #9ad6ff;
  letter-spacing: 0.02em;
}

.report-section__title--mt {
  margin-top: 14px;
}

.report-section__hint {
  margin: 0 0 12px;
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
}

.verdict-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 10px;
  margin-bottom: 10px;
  border: 1px solid rgba(125, 201, 255, 0.14);
}

.verdict-box--risk {
  background: rgba(255, 123, 114, 0.10);
  border-color: rgba(255, 123, 114, 0.30);
}

.verdict-box--normal {
  background: rgba(83, 229, 200, 0.08);
  border-color: rgba(83, 229, 200, 0.25);
}

.verdict-box__label {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
  flex-shrink: 0;
}

.verdict-box__value {
  font-size: 1.05rem;
  font-weight: 700;
}

.verdict-box--risk .verdict-box__value { color: #ff8c84; }
.verdict-box--normal .verdict-box__value { color: #53e5c8; }

.verdict-box__conf {
  margin-left: auto;
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.65);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 12px 8px;
  border-radius: 10px;
  background: rgba(16, 34, 60, 0.6);
}

.stat-card__num {
  font-size: 1.35rem;
  font-weight: 700;
  color: #e8f1ff;
  line-height: 1.1;
}

.stat-card__label {
  font-size: 0.75rem;
  color: rgba(220, 234, 255, 0.55);
}

.stat-card--high .stat-card__num { color: #ff8c84; }
.stat-card--medium .stat-card__num { color: #ffd166; }
.stat-card--low .stat-card__num { color: #53e5c8; }

.report-chart {
  margin-top: 10px;
  height: 220px;
}

.feature-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(16, 34, 60, 0.5);
  font-size: 0.84rem;
}

.feature-item__rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(91, 166, 255, 0.16);
  color: #9ad6ff;
  font-size: 0.75rem;
  flex-shrink: 0;
}

.feature-item__name {
  color: #e8f1ff;
  font-family: 'Consolas', 'Menlo', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.feature-item__class {
  margin-left: auto;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(255, 177, 107, 0.14);
  color: #ffc37d;
  font-size: 0.75rem;
  flex-shrink: 0;
}

.feature-item__weight {
  color: rgba(220, 234, 255, 0.6);
  font-size: 0.78rem;
  flex-shrink: 0;
}

.report-nl {
  margin: 0;
  color: #d9e8ff;
  font-size: 0.86rem;
  line-height: 1.75;
  white-space: pre-wrap;
}

.report-nl--guidance {
  color: #cfe2ff;
}

/* 6.10.3 报告可视化补充样式 */
.stat-card--normal .stat-card__num { color: #53e5c8; }

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
}

.info-item {
  font-size: 0.84rem;
  color: rgba(220, 234, 255, 0.75);
}

.info-item b {
  color: rgba(155, 195, 240, 0.85);
  font-weight: 600;
  margin-right: 8px;
}

.chart-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.chart-box {
  margin: 6px 0;
}

.model-block {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 10px;
  background: rgba(8, 17, 31, 0.4);
}

.report-section__hint--mt {
  margin-top: 12px;
}

.mini-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
  font-size: 0.8rem;
}

.mini-table th,
.mini-table td {
  padding: 6px 10px;
  text-align: left;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08);
  color: rgba(220, 234, 255, 0.8);
}

.mini-table th {
  color: rgba(155, 195, 240, 0.85);
  font-weight: 600;
  background: rgba(16, 34, 60, 0.5);
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
