<script setup lang="ts">
/**
 * AlertsView - 风险事件列表页（使用 RiskEvent 统一结构）
 *
 * P0 功能：展示跨场景风险事件，支持场景/风险等级/状态筛选
 * 数据来源：getRiskEvents() 跨场景聚合
 */
import { computed, onMounted, ref } from 'vue';
import { getRiskEventList } from '@/api/riskEventApi';
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
}

/** 风险事件列表 */
const events = ref<RiskEventItem[]>([]);
const loading = ref(true);
const error = ref('');

const userStore = useUserStore();

/** 是否系统管理员（管理员/用户固定自己场景） */
const isSuperAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN');

/** 筛选条件 */
const selectedScenario = ref<number | 'all'>('all');
const selectedRiskLevel = ref<string>('all');
const selectedStatus = ref<string>('all');

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

/** 筛选后的风险事件 */
const filteredEvents = computed(() => {
  let result = events.value;
  if (selectedScenario.value !== 'all') {
    result = result.filter((e) => e.scenario_id === selectedScenario.value);
  }
  if (selectedRiskLevel.value !== 'all') {
    result = result.filter((e) => e.risk_level === selectedRiskLevel.value);
  }
  if (selectedStatus.value !== 'all') {
    result = result.filter((e) => e.status === STATUS_VALUE[selectedStatus.value]);
  }
  return result;
});

/** 加载数据 */
const loadEvents = async () => {
  loading.value = true;
  error.value = '';
  try {
    const items = await getRiskEventList({ page_size: 200 });
    events.value = items as unknown as RiskEventItem[];
  } catch (err) {
    error.value = err instanceof Error ? err.message : '风险事件加载失败';
  } finally {
    loading.value = false;
  }
};

/** 风险等级标签映射 */
const riskLevelMap: Record<string, { label: string; type: string }> = {
  HIGH: { label: '高危', type: 'danger' },
  MEDIUM: { label: '中危', type: 'warning' },
  LOW: { label: '低危', type: 'info' },
};

onMounted(() => {
  loadEvents();
});
</script>

<template>
  <div class="risk-events-page">
    <div class="risk-events-page__header">
      <div>
        <p class="eyebrow">Risk Events</p>
        <h2>风险事件列表</h2>
        <p class="risk-events-page__desc">跨场景统一风险事件展示，支持多维度筛选过滤</p>
      </div>
      <span class="section-tag">{{ filteredEvents.length }} 条事件</span>
    </div>

    <!-- 筛选栏：系统管理员可按场景；管理员/用户固定自己场景（隐藏场景下拉） -->
    <div class="risk-events-filters">
      <label v-if="isSuperAdmin" class="filter-item">
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
    </div>

    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载风险事件...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadEvents">重试</button>
    </section>

    <!-- 空数据提示 -->
    <section v-else-if="filteredEvents.length === 0" class="state-card">
      <p>暂无匹配的风险事件</p>
    </section>

    <!-- 事件列表 -->
    <div v-else class="risk-events-table-wrap">
      <el-table
        :data="filteredEvents"
        stripe
        style="width: 100%"
        row-class-name="event-table-row"
      >
        <el-table-column prop="id" label="事件编号" width="200" show-overflow-tooltip />

        <el-table-column label="所属场景" width="110" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__scenario-tag">{{ scenarioName(row.scenario_id) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="风险类型" width="160" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__risk-type">{{ row.risk_type }}</span>
          </template>
        </el-table-column>

        <el-table-column label="风险等级" width="90" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span
              class="ev-level-badge"
              :class="`ev-level--${row.risk_level}`"
            >
              {{ riskLevelMap[row.risk_level]?.label ?? row.risk_level }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="风险概率" width="100" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__score">{{ (row.risk_score * 100).toFixed(1) }}%</span>
          </template>
        </el-table-column>

        <el-table-column label="原始标签" width="100" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span class="event-table__orig-label">{{ row.original_label }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="风险说明" min-width="220" show-overflow-tooltip />

        <el-table-column prop="occurred_at" label="发生时间" width="160" align="center" />

        <el-table-column label="处置状态" width="100" align="center">
          <template #default="{ row }: { row: RiskEventItem }">
            <span
              class="event-table__status"
              :class="`ev-status--${STATUS_LABEL[row.status] ?? row.status}`"
            >
              {{ STATUS_LABEL[row.status] ?? row.status }}
            </span>
          </template>
        </el-table-column>
      </el-table>
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

.risk-events-filters__group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.risk-events-filters__label {
  font-size: 0.82rem;
  color: rgba(220, 234, 255, 0.6);
  white-space: nowrap;
}

.risk-events-filters__select {
  padding: 7px 12px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
  cursor: pointer;
  min-width: 130px;
}

.risk-events-filters__select:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.risk-events-filters__select option {
  background: #0b1628;
  color: #e8f1ff;
}

.risk-events-filters__tab:hover {
  background: rgba(91, 166, 255, 0.1);
  color: #fff;
}

.risk-events-filters__tab.is-active {
  background: rgba(91, 166, 255, 0.18);
  color: #fff;
  font-weight: 500;
}

/* 表格外层 */
.risk-events-table-wrap {
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

.event-table__risk-type {
  font-size: 0.85rem;
  font-weight: 500;
  color: rgba(175, 198, 230, 0.8);
}

.event-table__score {
  font-weight: 600;
  color: rgba(155, 195, 240, 0.85);
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

.ev-status--待处置 {
  background: rgba(255, 177, 107, 0.08);
  color: rgba(230, 180, 110, 0.7);
}

.ev-status--处理中 {
  background: rgba(91, 166, 255, 0.08);
  color: rgba(155, 195, 240, 0.7);
}

.ev-status--已处置 {
  background: rgba(83, 229, 200, 0.08);
  color: rgba(83, 229, 200, 0.65);
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
</style>
