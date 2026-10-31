<script setup lang="ts">
/**
 * 网络安全 · 场景管理员首页。管理端看资源与口径：
 * 数据集标签是否同一套风险语言、统计维度覆盖几份数据、流程积压与人员配置。
 * 执行端的研判图与 recent_events 不在此页。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type NetworkProfile,
  type WorkspaceBase,
} from '@/api/dashboardApi';
import { getUserList } from '@/api/userApi';
import type { UserAccount } from '@/types/security';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashFunnel from '@/components/dashboard/DashFunnel.vue';
import DashLine from '@/components/dashboard/DashLine.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import DashTable from '@/components/dashboard/DashTable.vue';
import type { DashCell, DashColumn } from '@/components/dashboard/DashTable.vue';
import { fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: NetworkProfile }>();


const LIST_SEPARATOR = '、';
const DEVIATION_DIGITS = 2;
const DEVIATION_BASELINE = 1;
const COVERAGE_SINGLE_SOURCE = 1;
const MEMBER_PAGE_SIZE = 200;
const ROLE_SCENARIO_ADMIN = 'SCENARIO_ADMIN';
const ROLE_SCENARIO_USER = 'SCENARIO_USER';
const ACCOUNT_STATUS_ACTIVE = 'active';


const runtime = ref<WorkspaceBase | null>(null);
const members = ref<UserAccount[] | null>(null);
const memberTotal = ref<number | null>(null);

const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getUserList({ scenario_id: scenarioId, page_size: MEMBER_PAGE_SIZE }),
  ]);

  runtime.value = runtimeResult.status === 'fulfilled' ? runtimeResult.value : null;
  if (memberResult.status === 'fulfilled') {
    members.value = memberResult.value.items.filter((item) => item.scenario_id === scenarioId);
    memberTotal.value = memberResult.value.total;
  } else {
    members.value = null;
    memberTotal.value = null;
  }
};

watch(() => props.data.scenario_id, loadAll);
onMounted(loadAll);

const summary = computed(() => runtime.value?.summary ?? null);


const caliberLanguages = computed(() => {
  const rows = props.data.caliber_matrix;
  if (!rows.length) return null;
  return new Set(rows.map((row) => row.label_field)).size;
});

const caliberSplitSub = computed(() =>
  caliberLanguages.value === null
    ? '后端未下发风险口径矩阵'
    : `${caliberLanguages.value} 套风险语言 · 不可直接合并`,
);

const overviewKpis = computed(() => [
  {
    label: '有效数据集数',
    value: props.data.dataset_count,
    unit: '个',
    tone: 'primary' as const,
    sub: `含 ${props.data.dataset_file_count} 份文件`,
  },
  { label: '有效样本总量', value: props.data.sample_count, unit: '条', tone: 'success' as const },
  {
    label: '统一风险占比',
    value: fmtPercent(props.data.risk_rate),
    tone: 'warning' as const,
    raw: true,
  },
  {
    label: '风险口径分裂度',
    value: caliberLanguages.value,
    unit: '套',
    tone: 'warning' as const,
    sub: caliberSplitSub.value,
  },
]);


const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};
const visibilityText = (value: string | undefined) =>
  value ? (VISIBILITY_TEXT[value] ?? value) : '—';


const caliberColumns: DashColumn[] = [
  { key: 'name', label: '数据集', width: 220 },
  { key: 'label_field', label: '标签字段' },
  { key: 'positive_labels', label: '正类取值' },
  { key: 'deviation', label: '与场景合并口径偏离', numeric: true, align: 'right' },
  { key: 'registered', label: '登记状态' },
];

/**
 * 偏离倍数单元格：>1 高于场景合并口径（红）、<1 低于（蓝）、=1 持平（灰）、无基准（—）。
 * `deviation` 由后端给 number | null（场景风险占比为 0 时 null），故这里只需判 null 与
 * 非有限值（JSON 里不会有 Infinity/NaN，保留该判断是为了不把异常值渲染成「×NaN」）。
 */
const deviationCell = (value: number | null | undefined): DashCell => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const text = `×${value.toFixed(DEVIATION_DIGITS)}`;
  if (value > DEVIATION_BASELINE) return { text, tone: 'up' };
  if (value < DEVIATION_BASELINE) return { text, tone: 'down' };
  return { text, tone: 'muted' };
};

const caliberRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.caliber_matrix.map((item) => {
    const positives = item.positive_labels ?? [];
    return {
      logical_id: item.logical_id,
      name: item.logical_id,
      label_field: item.label_field,
      positive_labels: positives.length ? positives.join(LIST_SEPARATOR) : '未登记',
      deviation: deviationCell(item.deviation),
      registered: item.registered
        ? { text: '已登记', tone: 'ok' }
        : { text: '未登记·不产事件', tone: 'warn' },
    };
  }),
);


const dimensionColumns: DashColumn[] = [
  { key: 'dimension', label: '统计维度', width: 200 },
  { key: 'datasets', label: '覆盖数据集' },
  { key: 'coverage', label: '覆盖数', numeric: true, align: 'right', width: 90 },
  { key: 'coverage_status', label: '覆盖状态', width: 150 },
];

const coverageCell = (count: number): DashCell => {
  if (count === props.data.dataset_file_count) return { text: '全覆盖', tone: 'ok' };
  if (count === COVERAGE_SINGLE_SOURCE) return { text: '仅一份数据支撑', tone: 'warn' };
  return { text: '部分覆盖', tone: 'muted' };
};

const dimensionRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.dimension_coverage.map((item) => {
    const ids = item.datasets ?? [];
    return {
      key: item.key,
      dimension: item.dimension,
      datasets: ids.length ? ids.join(LIST_SEPARATOR) : '—',
      coverage: ids.length,
      coverage_status: coverageCell(ids.length),
    };
  }),
);


const datasetColumns: DashColumn[] = [
  { key: 'name', label: '数据集名', width: 220 },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'visibility', label: '可见性' },
  { key: 'version', label: '版本', numeric: true, align: 'right' },
];

const datasetRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.datasets.map((item) => ({
    logical_id: item.logical_id,
    name: item.logical_id,
    record_count: fmtInt(item.record_count),
    risk_rate: fmtPercent(item.risk_rate),
    attribute_count: item.attribute_count,
    visibility: visibilityText(item.visibility),
    version: item.version,
  })),
);


const modelingBars = computed(() =>
  props.data.modeling.map((item) => ({ value: item.logical_id, count: item.total })),
);

const whiteLying = computed(() =>
  props.data.modeling.filter((item) => item.total === 0).map((item) => item.logical_id),
);

// 已发布 / 草稿合计（DashBars 只渲染 count，逐数据集明细在 S2 的「已发布模型数」列）
const modelTotals = computed(() =>
  props.data.modeling.reduce(
    (acc, item) => ({ published: acc.published + item.published, draft: acc.draft + item.draft }),
    { published: 0, draft: 0 },
  ),
);


const activityTotal = computed(() =>
  runtime.value ? runtime.value.activity_trend.reduce((sum, point) => sum + point.total, 0) : null,
);

const runtimeKpis = computed(() => {
  const item = summary.value;
  return [
    { label: '待处置积压', value: item ? item.pending : null, unit: '条', tone: 'danger' as const },
    {
      label: '已处置率',
      value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
      tone: 'success' as const,
      raw: true,
    },
    { label: '近 10 天活动', value: activityTotal.value, unit: '次', tone: 'primary' as const },
  ];
});

const funnelItems = computed(() =>
  (summary.value?.status_funnel ?? []).map((item) => ({ label: item.label, count: item.count })),
);

const trendPoints = computed(() =>
  (runtime.value?.activity_trend ?? []).map((item) => ({
    label: item.date.slice(5),
    value: item.total,
    value2: item.risk,
  })),
);


const memberRows = computed(() => {
  const list = members.value;
  if (list === null) return [];
  const adminCount = list.filter((item) => item.role === ROLE_SCENARIO_ADMIN).length;
  const userCount = list.filter((item) => item.role === ROLE_SCENARIO_USER).length;
  const disabledCount = list.filter((item) => item.status !== ACCOUNT_STATUS_ACTIVE).length;
  const rows = [
    { label: '场景管理员', value: `${adminCount} 人` },
    { label: '场景用户', value: `${userCount} 人` },
    { label: '合计', value: `${list.length} 人` },
  ];
  if (disabledCount) {
    rows.push({ label: '已禁用', value: `${disabledCount} 人` });
  }
  const overflow = (memberTotal.value ?? 0) - list.length;
  if (overflow > 0) {
    rows.push({ label: '未纳入统计', value: `${overflow} 人（超出单页 ${MEMBER_PAGE_SIZE} 条）` });
  }
  return rows;
});
</script>

<template>
  <!-- S1 场景资产总览 KPI ×4 -->
  <DashKpis :items="overviewKpis" />

  <!-- D1 数据集风险口径可比性矩阵 -->
  <DashCard
    title="数据集风险口径可比性矩阵"
    source="按数据集逐行对比 · 统一正类口径 · 偏离 = 该数据集风险占比 ÷ 场景合并风险占比（>1 高于场景口径，<1 低于）；「未登记·不产事件」表示风险口径未进显式登记表，不会产生风险事件"
  >
    <DashTable :columns="caliberColumns" :rows="caliberRows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 流量统计维度覆盖矩阵 -->
  <DashCard
    title="流量统计维度覆盖矩阵"
    source="按统计维度逐行对比 · 覆盖数 = 含该维度字段的数据集数量 · 「仅一份数据支撑」表示该维度只有一份数据能算，跨数据集不可互相校验"
  >
    <DashTable :columns="dimensionColumns" :rows="dimensionRows" row-key="key" dense />
  </DashCard>

  <!-- S2 数据集资产明细 -->
  <DashCard
    title="数据集资产明细"
    source="全量数据集，不做过滤；「未登记」由 D1 的登记状态列统一表达"
  >
    <DashTable :columns="datasetColumns" :rows="datasetRows" row-key="logical_id" dense />
  </DashCard>

  <!-- S3 建模覆盖 -->
  <DashCard title="建模覆盖" source="每数据集一根柱 = 模型版本总数；总数为 0 即「数据白躺」">
    <DashBars :items="modelingBars" :label-width="260" suffix=" 个版本" />
    <p style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
      <span v-if="whiteLying.length" class="d-tag d-tag--warn">数据白躺 {{ whiteLying.length }} 份</span>
      <span v-if="whiteLying.length" style="margin-left: 6px">{{ whiteLying.join(LIST_SEPARATOR) }}</span>
      <span style="margin-left: 8px; color: rgba(220, 234, 255, 0.5)">
        已发布合计 {{ modelTotals.published }} / 草稿合计 {{ modelTotals.draft }}
      </span>
    </p>
  </DashCard>

  <!-- S4 场景运行态水位 -->
  <DashKpis :items="runtimeKpis" :columns="3" />
  <div class="d-grid2">
    <DashCard title="风险事件处置进度" source="按处置状态统计全场景风险事件">
      <DashFunnel :items="funnelItems" />
    </DashCard>
    <DashCard title="近 10 天活动趋势" source="按天统计风险推理量，以及其中判定为风险的量">
      <DashLine :points="trendPoints" name="推理" name2="风险" area suffix=" 次" />
    </DashCard>
  </div>

  <!-- S5 场景成员与权限 -->
  <DashCard title="场景成员与权限" source="按账号角色分组计数，范围限本场景">
    <p v-if="members === null" class="d-empty">成员数据未取到</p>
    <DashRows v-else :rows="memberRows" />
  </DashCard>
</template>
