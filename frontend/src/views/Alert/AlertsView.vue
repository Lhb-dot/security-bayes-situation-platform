<script setup lang="ts">
/**
 * AlertsView - 风险事件列表页（使用 RiskEvent 统一结构）
 *
 * P0 功能：展示跨场景风险事件，支持场景/风险等级/状态筛选
 * 数据来源：getRiskEventPage() 跨场景聚合
 *
 * 筛选与分页都在后端执行（每页 20 条）：前端只持有当前页数据，
 * 因此筛选结果跨全量事件生效，翻页也不会把页面拉长。
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { getRiskEventPage, hideRiskEvent, unhideRiskEvent } from '@/api/riskEventApi';
import { shortExplanation } from '@/utils/explanationText';
import { keepScroll } from '@/utils/scrollAnchor';
import { useUserStore } from '@/stores/userStore';

/** 真实风险事件（后端 /api/v1/risk-events 返回结构） */
interface RiskEventItem {
  id: number;
  scenario_id: number;
  risk_type: string;
  risk_level: string;
  risk_score: number;
  original_label: string;
  description: string;
  occurred_at: string;
  status: string; // PENDING / PROCESSING / RESOLVED
  hidden_at: string | null; // 非空 = 已隐藏（软隐藏，不是删除）
}

/** 风险事件列表（当前页） */
const events = ref<RiskEventItem[]>([]);
const loading = ref(true);
const error = ref('');
const total = ref(0);
const page = ref(1);
const pageSize = 20;

const userStore = useUserStore();
const router = useRouter();

/** 筛选条件 */
const selectedScenario = ref<number | 'all'>('all');
const selectedRiskLevel = ref<string>('all');
const selectedStatus = ref<string>('all');
/** 是否把已隐藏的事件一起查出来（默认不查 —— 隐藏是可见性开关，不是删除） */
const showHidden = ref(false);

/** 场景数字 ID → 名称（与后端 scenario 表 id 对齐） */
const SCENARIO_META: Record<number, { code: string; name: string }> = {
  1: { code: 'network_security', name: '网络安全' },
  2: { code: 'power_system', name: '电力系统' },
  3: { code: 'flightdeck_operation', name: '航母甲板' },
  4: { code: 'geological_risk', name: '地质风险' },
};
const scenarioName = (id: number) => SCENARIO_META[id]?.name ?? String(id);

/** 场景选项（系统管理员可按场景过滤） */
const scenarioOptions: Array<{ value: number | 'all'; label: string }> = [
  { value: 'all', label: '所有场景' },
  ...Object.entries(SCENARIO_META).map(([id, meta]) => ({ value: Number(id), label: meta.name })),
];

/** 风险等级选项 */
const riskLevelOptions = [
  { value: 'all', label: '全部等级' },
  { value: 'HIGH', label: '高危' },
  { value: 'MEDIUM', label: '中危' },
  { value: 'LOW', label: '低危' },
];

/** 状态选项（前端中文 ↔ 后端枚举） */
const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: '待处置', label: '待处置' },
  { value: '处理中', label: '处理中' },
  { value: '已处置', label: '已处置' },
];
const STATUS_VALUE: Record<string, string> = {
  '待处置': 'PENDING',
  '处理中': 'PROCESSING',
  '已处置': 'RESOLVED',
};
const STATUS_LABEL: Record<string, string> = {
  PENDING: '待处置',
  PROCESSING: '处理中',
  RESOLVED: '已处置',
};

/** 已隐藏事件选项（隐藏 = 软隐藏，数据与处置记录都保留） */
const hiddenOptions = [
  { value: false, label: '不显示' },
  { value: true, label: '显示' },
];

/** 当前筛选条件 → 后端查询参数（'all' 表示该维度不过滤） */
const queryParams = computed(() => ({
  scenario_id: selectedScenario.value === 'all' ? undefined : selectedScenario.value,
  risk_level:
    selectedRiskLevel.value === 'all'
      ? undefined
      : (selectedRiskLevel.value as 'HIGH' | 'MEDIUM' | 'LOW'),
  status:
    selectedStatus.value === 'all'
      ? undefined
      : (STATUS_VALUE[selectedStatus.value] as 'PENDING' | 'PROCESSING' | 'RESOLVED'),
  include_hidden: showHidden.value || undefined,
}));

/** 加载数据（筛选与分页均由后端执行） */
const loadEvents = async (targetPage: number = page.value) => {
  loading.value = true;
  error.value = '';
  try {
    const data = await getRiskEventPage({
      ...queryParams.value,
      page: targetPage,
      page_size: pageSize,
    });
    events.value = data.items as unknown as RiskEventItem[];
    total.value = data.total;
    page.value = data.page;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '风险事件加载失败';
  } finally {
    loading.value = false;
  }
};

/** 筛选条件变化时回到第 1 页重新查询 */
watch([selectedScenario, selectedRiskLevel, selectedStatus, showHidden], () => {
  loadEvents(1);
});

const tableWrapRef = ref<HTMLElement | null>(null);

/** 翻页：包一层滚动锚定，换页后视口停在原处（见 utils/scrollAnchor.ts） */
const changePage = (target: number) => keepScroll(() => loadEvents(target), tableWrapRef.value);

/** 风险等级 → 中文（配色由 .ev-level--* 类承担，这里只管文案） */
const RISK_LEVEL_LABEL: Record<string, string> = {
  HIGH: '高危',
  MEDIUM: '中危',
  LOW: '低危',
};

/** 原始标签中文化（模型输出的原始类标；未收录的原样显示） */
const ORIGINAL_LABEL: Record<string, string> = {
  anomaly: '异常',
  normal: '正常',
  '1': '风险',
  '0': '正常',
};
const originalLabel = (value: string) => ORIGINAL_LABEL[value] ?? value;

/** 行内「查看」→ 风险事件详情页 */
const goEventDetail = (row: RiskEventItem) => {
  router.push({ path: `/events/${row.id}` });
};

/** 正在切换隐藏状态的事件 id（按钮置灰用） */
const togglingId = ref<number | null>(null);

/**
 * 隐藏 / 取消隐藏风险事件。
 *
 * 走软隐藏：需求 5.2 访问控制第 4 条要求历史事件不得被无痕删除，后端 DELETE 接口
 * 因此永远返回 400，所以这里改的是可见性开关 —— 数据与处置记录一行不动。
 * 隐藏后该行默认从列表消失；取消隐藏后如果没勾「显示」，行同样会消失，两种情况都重拉列表。
 */
const toggleHidden = async (row: RiskEventItem) => {
  const willHide = !row.hidden_at;
  try {
    await ElMessageBox.confirm(
      willHide
        ? `确认隐藏事件 #${row.id}？隐藏后不在列表显示，数据不会删除。`
        : `确认取消隐藏事件 #${row.id}？`,
      willHide ? '隐藏风险事件' : '取消隐藏风险事件',
      {
        type: 'warning',
        confirmButtonText: willHide ? '隐藏' : '取消隐藏',
        cancelButtonText: '取消',
      },
    );
  } catch {
    return; // 用户取消
  }
  togglingId.value = row.id;
  try {
    if (willHide) await hideRiskEvent(String(row.id));
    else await unhideRiskEvent(String(row.id));
    ElMessage.success(willHide ? '风险事件已隐藏' : '风险事件已取消隐藏');
    await loadEvents();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '操作失败');
  } finally {
    togglingId.value = null;
  }
};

onMounted(() => {
  loadEvents(1);
});
</script>

<template>
  <div class="risk-events-page">
    <div class="risk-events-page__header">
      <div>
        <p class="eyebrow">Risk Events</p>
        <h2>风险事件列表</h2>
        <p class="risk-events-page__desc">各场景风险事件汇总与筛选</p>
      </div>
      <span class="section-tag">{{ total }} 条事件</span>
    </div>

    <!-- 筛选栏：系统管理员可按场景；管理员/用户固定自己场景（隐藏场景下拉）。
         这里用 store 的 isSuperAdmin（role 恰为 SUPER_ADMIN），不是 isManagement
         —— 场景管理员也该被固定在自己的场景上。 -->
    <div class="risk-events-filters">
      <label v-if="userStore.isSuperAdmin" class="filter-item">
        <span class="filter-item__label">场景</span>
        <select v-model="selectedScenario" class="filter-select">
          <option v-for="opt in scenarioOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span class="filter-item__label">风险等级</span>
        <select v-model="selectedRiskLevel" class="filter-select">
          <option v-for="opt in riskLevelOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span class="filter-item__label">处置状态</span>
        <select v-model="selectedStatus" class="filter-select">
          <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </label>

      <label class="filter-item">
        <span class="filter-item__label">已隐藏</span>
        <select v-model="showHidden" class="filter-select">
          <option v-for="opt in hiddenOptions" :key="String(opt.value)" :value="opt.value">{{ opt.label }}</option>
        </select>
      </label>
    </div>

    <!-- 加载状态：只有首屏（列表还是空的）才用整块状态卡。
         翻页时保留列表、只盖遮罩 —— 内容高度不变，滚动位置才不会跳。 -->
    <section v-if="loading && !events.length" class="state-card">
      <div class="loader"></div>
      <p>正在加载风险事件...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadEvents(1)">重试</button>
    </section>

    <!-- 空数据提示 -->
    <section v-else-if="total === 0" class="state-card">
      <p>暂无匹配的风险事件</p>
    </section>

    <!-- 事件列表 -->
    <div v-else ref="tableWrapRef" class="risk-events-table-wrap">
      <div v-if="loading" class="pane-loading"><div class="loader"></div></div>
      <el-table
        :data="events"
        stripe
        style="width: 100%"
        row-class-name="event-table-row"
        empty-text="暂无匹配的风险事件"
      >
        <el-table-column prop="id" label="事件编号" width="88" align="center" show-overflow-tooltip />

        <el-table-column label="所属场景" width="96" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__scenario-tag">{{ scenarioName(row.scenario_id) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="风险等级" width="118" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__level">
              <span class="ev-level-badge" :class="`ev-level--${row.risk_level}`">
                {{ RISK_LEVEL_LABEL[row.risk_level] ?? row.risk_level }}
              </span>
              <span class="ev-level-score">{{ (row.risk_score * 100).toFixed(1) }}%</span>
            </span>
          </template>
        </el-table-column>

        <el-table-column label="原始标签" width="92" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__orig-label">{{ originalLabel(row.original_label) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="风险说明" min-width="200" class-name="ev-desc-cell">
          <template #default="{ row }: { row: RiskEventItem }">
            {{ shortExplanation(row.description) }}
          </template>
        </el-table-column>

        <el-table-column prop="occurred_at" label="发生时间" width="158" align="center" />

        <el-table-column label="处置状态" width="94" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <!-- 类名直接用后端枚举（PENDING/PROCESSING/RESOLVED）：
                 此前是拿中文文案拼类名（ev-status--待处置），非 ASCII 类名既难搜也易错 -->
            <span class="event-table__status" :class="`ev-status--${row.status}`">
              {{ STATUS_LABEL[row.status] ?? row.status }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="172" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="ev-ops">
              <el-button size="small" type="primary" plain @click="goEventDetail(row)">查看</el-button>
              <el-button
                size="small"
                :type="row.hidden_at ? 'info' : 'warning'"
                plain
                :disabled="togglingId === row.id"
                @click="toggleHidden(row)"
              >{{ row.hidden_at ? '不隐藏' : '隐藏' }}</el-button>
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 页码条：翻页期间常驻（只置灰），否则条本身消失，指针下方会空掉 -->
    <div v-if="!error && total > 0" class="risk-events-pager">
      <span class="risk-events-pager__total">共 {{ total }} 条</span>
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
  </div>
</template>

<style scoped>
.risk-events-page {
  position: relative;
  z-index: 1;
}

.risk-events-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 16px;
}

.risk-events-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  color: #c8deff;
}

.risk-events-page__desc {
  margin: 0;
  color: rgba(180, 200, 235, 0.55);
  font-size: 0.95rem;
}

/* 筛选栏 */
.risk-events-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 16px 0;
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08);
}

/* 筛选控件外观由全局 .filter-item / .filter-select 提供（style.css） */

/* 表格外层 */
.risk-events-table-wrap {
  position: relative; /* 翻页遮罩（.pane-loading）的定位上下文 */
  border: 1px solid rgba(125, 201, 255, 0.10);
  border-radius: 18px;
  overflow: hidden;
  background: rgba(8, 18, 34, 0.7);
}

.event-table-row {
  background: transparent !important;
}

.event-table__scenario-tag {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.8rem;
  background: rgba(91, 166, 255, 0.10);
  color: rgba(155, 195, 240, 0.8);
}

/* 风险等级：等级徽章 + 概率并排 */
.event-table__level {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ev-level-score {
  font-size: 0.78rem;
  color: rgba(155, 195, 240, 0.7);
  font-variant-numeric: tabular-nums;
}

.event-table__orig-label {
  font-size: 0.82rem;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  color: rgba(175, 198, 230, 0.6);
}

/* 风险等级徽章 */
.ev-level-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 500;
}

.ev-level--HIGH {
  background: rgba(255, 123, 114, 0.12);
  color: #e88982;
}

.ev-level--MEDIUM {
  background: rgba(91, 166, 255, 0.12);
  color: rgba(155, 195, 240, 0.9);
}

.ev-level--LOW {
  background: rgba(83, 229, 200, 0.10);
  color: rgba(83, 229, 200, 0.75);
}

/* 处置状态 */
.event-table__status {
  font-size: 0.82rem;
  padding: 2px 10px;
  border-radius: 999px;
}

.ev-status--PENDING {
  background: rgba(255, 177, 107, 0.08);
  color: rgba(230, 180, 110, 0.7);
}

.ev-status--PROCESSING {
  background: rgba(91, 166, 255, 0.08);
  color: rgba(155, 195, 240, 0.7);
}

.ev-status--RESOLVED {
  background: rgba(83, 229, 200, 0.08);
  color: rgba(83, 229, 200, 0.65);
}

/* ---------------- 分页器（暗色） ----------------
   与数据集中心的只读预览表保持同一套分页外观；变量挂在包裹层上，
   由 CSS 自定义属性继承进 el-pagination 内部。 */
.risk-events-pager {
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

.risk-events-pager__total {
  color: rgba(220, 234, 255, 0.6);
  font-size: 0.85rem;
}

.risk-events-pager :deep(.el-pagination.is-background .el-pager li),
.risk-events-pager :deep(.el-pagination.is-background .btn-prev),
.risk-events-pager :deep(.el-pagination.is-background .btn-next) {
  border: 1px solid rgba(125, 201, 255, 0.12);
  border-radius: 6px;
}

.risk-events-pager :deep(.el-pagination.is-background .el-pager li:not(.is-active):hover),
.risk-events-pager :deep(.el-pagination.is-background .btn-prev:hover),
.risk-events-pager :deep(.el-pagination.is-background .btn-next:hover) {
  background-color: rgba(20, 44, 72, 0.95) !important;
  color: #9ad6ff !important;
}

.risk-events-pager :deep(.el-pagination.is-background .el-pager li.is-active) {
  background-color: #3f7fd4 !important;
  color: #ffffff !important;
  border-color: transparent;
}

.risk-events-pager :deep(.el-pagination.is-background .btn-prev),
.risk-events-pager :deep(.el-pagination.is-background .btn-next) {
  background-color: rgba(12, 26, 46, 0.9) !important;
  color: rgba(220, 234, 255, 0.7) !important;
}

.risk-events-pager :deep(.el-pagination.is-background .btn-prev:disabled),
.risk-events-pager :deep(.el-pagination.is-background .btn-next:disabled) {
  background-color: rgba(8, 17, 31, 0.45) !important;
  color: rgba(180, 200, 235, 0.25) !important;
}
</style>

<style>
.risk-events-page .el-table,
.risk-events-page .el-table__inner-wrapper,
.risk-events-page .el-table__body-wrapper,
.risk-events-page .el-table__header-wrapper {
  background-color: transparent !important;
}

.risk-events-page .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.risk-events-page .el-table td.el-table__cell {
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.risk-events-page .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: rgba(10, 24, 44, 0.85) !important;
}

.risk-events-page .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
}

.risk-events-page .el-table__empty-text {
  color: rgba(155, 185, 225, 0.3) !important;
}

/* 风险说明：单元格内单行截断，完整说明进详情页看。
   这里不挂 show-overflow-tooltip —— 悬停浮层会盖住上下相邻行。
   EP 的 .cell 默认 white-space: normal 会折行，必须显式钉成单行 + 省略号。
   列表里展示的是 shortExplanation() 的短文本（去掉与「所属场景」「风险等级」
   两列重复的开头、以及每种类型固定的「建议…」模板尾巴），详情页仍是完整正文。 */
.risk-events-page .ev-desc-cell .cell {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 操作列两个按钮排一行，间距自己控（EP 默认给相邻 el-button 加 margin-left，先清掉） */
.risk-events-page .ev-ops {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* 两个按钮等宽：文案在「查看」/「隐藏」/「不隐藏」之间切，按最宽的「不隐藏」定 64px。
   实测（字体 12px、左右 padding 各 11px、边框 1px）：查看/隐藏 48px、不隐藏 60px、
   取消隐藏 72px。64px 放下「不隐藏」还余 4px；两个都写 width，宽度不随状态变。 */
.risk-events-page .ev-ops .el-button {
  width: 64px;
  margin-left: 0;
}
</style>
