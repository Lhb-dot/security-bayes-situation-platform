<template>
  <CockpitKpis :items="overviewKpis" />

  <div class="pf-board">
    <!-- 数据集资产明细 -->
    <CockpitPanel index="01" title="数据集资产明细" hint="全量数据集" align="top" foot="只列资产属性；标签口径见 02 口径矩阵，模型数见 03 建模覆盖">
      <CockpitMatrix :columns="assetColumns" :rows="assetRows" row-key="logical_id" />
    </CockpitPanel>

    <!-- 风险口径可比性矩阵 -->
    <CockpitPanel
      index="02"
      title="数据集风险口径可比性矩阵"
      hint="逐数据集 · 能否直接合并"
      align="top"
      foot="偏离 = 该数据集风险占比 ÷ 场景合并风险占比；「未登记·不产事件」表示风险口径未进显式登记表，不会产生风险事件"
    >
      <CockpitMatrix :columns="caliberColumns" :rows="caliberRows" row-key="logical_id" />
    </CockpitPanel>

    <!-- 建模覆盖 -->
    <CockpitPanel
      index="03"
      title="建模覆盖"
      hint="每数据集模型版本数"
      align="top"
      :foot="whiteLying.length ? `数据白躺 ${whiteLying.length} 份：${whiteLying.join(LIST_SEPARATOR)}` : '全部数据集均已有模型版本'"
    >
      <CockpitKpis size="sm" :columns="3" :items="modelKpis" />
      <CockpitBars :items="modelingBars" :label-width="86" :value-width="56" />
    </CockpitPanel>

    <!-- 场景运行态势 -->
    <CockpitPanel index="04" title="场景运行态势" :hint="runtimeHint" align="top" foot="运行态为全场景口径（含所有用户），与数据资产的全量统计相互独立">
      <CockpitKpis size="sm" :columns="3" :items="runtimeKpis" />
      <template v-if="runtime">
        <CockpitStack :items="statusItems" />
        <CockpitTrend :points="trendPoints" name="推理" name2="判为风险" unit=" 次" />
      </template>
      <p v-else class="pf-empty">运行态数据未取到</p>
    </CockpitPanel>

    <!-- 流量统计维度覆盖矩阵 -->
    <CockpitPanel
      index="05"
      title="流量统计维度覆盖矩阵"
      hint="维度 × 数据集"
      align="top"
      :foot="singleSource.length ? `仅一份数据支撑：${singleSource.map((item) => item.dimension).join(LIST_SEPARATOR)} —— 该维度跨数据集不可互相校验` : '每个统计维度都有多份数据支撑'"
    >
      <CockpitGrid :columns="datasetColumns" :rows="dimensionRows" accent="#62cdb4" />
    </CockpitPanel>

    <!-- 可见性与场景成员 -->
    <CockpitPanel
      index="06"
      title="数据集可见性与场景成员"
      hint="范围限本场景"
      align="top"
      foot="成员按账号角色分组计数；可见性为数据集注册时的共享范围"
    >
      <CockpitDonut :items="visibilityItems" center-label="数据集" :percent="false" suffix=" 个" />
      <p v-if="members === null" class="pf-empty">成员数据未取到</p>
      <CockpitRows v-else :rows="memberRows" :columns="2" />
    </CockpitPanel>
  </div>
</template>
<script setup lang="ts">
/**
 * 网络安全 · 场景管理员首页看板，纯展示。取数在 sections/ProfileNetwork.vue，
 * 本组件只负责渲染，便于用示例数据直接挂载预览。
 */
import { computed } from 'vue';
import type { NetworkProfile, WorkspaceBase } from '@/api/dashboardApi';
import type { UserAccount } from '@/types/security';
import { fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';
import CockpitPanel from '../CockpitPanel.vue';
import CockpitKpis from '../CockpitKpis.vue';
import type { CockpitKpi } from '../CockpitKpis.vue';
import CockpitBars from '../CockpitBars.vue';
import CockpitDonut from '../CockpitDonut.vue';
import CockpitGrid from '../CockpitGrid.vue';
import type { CockpitGridRow } from '../CockpitGrid.vue';
import CockpitMatrix from '../CockpitMatrix.vue';
import type { CockpitCell, CockpitColumn } from '../CockpitMatrix.vue';
import CockpitRows from '../CockpitRows.vue';
import type { CockpitRow } from '../CockpitRows.vue';
import CockpitStack from '../CockpitStack.vue';
import CockpitTrend from '../CockpitTrend.vue';
import { percentText } from '../profileTokens';

const props = defineProps<{
  data: NetworkProfile;
  runtime: WorkspaceBase | null;
  members: UserAccount[] | null;
  memberTotal?: number | null;
}>();


const LIST_SEPARATOR = '、';
const DEVIATION_DIGITS = 2;
const DEVIATION_BASELINE = 1;
const MEMBER_PAGE_SIZE = 200;
const ROLE_SCENARIO_ADMIN = 'SCENARIO_ADMIN';
const ROLE_SCENARIO_USER = 'SCENARIO_USER';
const ACCOUNT_STATUS_ACTIVE = 'active';

const VISIBILITY_TEXT: Record<string, string> = { platform: '平台', company: '公司', personal: '个人' };


const caliberLanguages = computed(() => {
  const rows = props.data.caliber_matrix;
  if (!rows.length) return null;
  return new Set(rows.map((row) => row.label_field)).size;
});

const overviewKpis = computed<CockpitKpi[]>(() => [
  {
    label: '有效数据集数',
    value: props.data.dataset_count,
    unit: '个',
    tone: 'primary',
    icon: 'data',
    sub: `含 ${props.data.dataset_file_count} 份文件`,
  },
  {
    label: '有效样本总量',
    value: props.data.sample_count,
    unit: '条',
    tone: 'success',
    icon: 'layers',
    sub: `风险样本 ${fmtInt(props.data.risk_count)} 条`,
  },
  {
    label: '统一风险占比',
    value: fmtPercent(props.data.risk_rate),
    tone: 'warning',
    icon: 'alert',
    sub: '全场景合并口径',
  },
  {
    label: '风险口径分裂度',
    value: caliberLanguages.value,
    unit: '套',
    tone: 'purple',
    icon: 'label',
    sub: caliberLanguages.value === null ? '后端未下发风险口径矩阵' : `${caliberLanguages.value} 套风险语言 · 不可直接合并`,
  },
]);


const assetColumns: CockpitColumn[] = [
  { key: 'name', label: '数据集（版本）', ellipsis: true, ellipsisWidth: 130 },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
];

const assetRows = computed(() =>
  props.data.datasets.map((item) => ({
    logical_id: item.logical_id,
    name: `${item.logical_id}（v${item.version}）`,
    record_count: fmtInt(item.record_count),
    risk_rate: fmtPercent(item.risk_rate),
    attribute_count: item.attribute_count,
  })),
);


/**
 * 管理端的第一问：这些数据集的风险口径能不能直接合并？
 * 逐行摆出「标签字段 + 正类取值」，把「同一个场景里其实有好几套风险语言」变成可见事实；
 * `deviation` 再把每份数据的风险占比与场景合并口径的倍数关系标出来。
 * 「未登记·不产事件」是管理告警：未进显式登记表的数据集不会产生风险事件，必须被看见。
 */
const caliberColumns: CockpitColumn[] = [
  { key: 'name', label: '数据集', ellipsis: true, ellipsisWidth: 110 },
  { key: 'label_field', label: '标签字段' },
  { key: 'positive_labels', label: '正类取值', ellipsis: true, ellipsisWidth: 120 },
  { key: 'deviation', label: '偏离', numeric: true, align: 'right' },
  { key: 'registered', label: '登记状态' },
];

const deviationCell = (value: number | null | undefined): CockpitCell => {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  const text = `×${value.toFixed(DEVIATION_DIGITS)}`;
  if (value > DEVIATION_BASELINE) return { text, tone: 'up' };
  if (value < DEVIATION_BASELINE) return { text, tone: 'down' };
  return { text, tone: 'muted' };
};

const caliberRows = computed(() =>
  props.data.caliber_matrix.map((item) => {
    const positives = item.positive_labels ?? [];
    return {
      logical_id: item.logical_id,
      name: item.logical_id,
      label_field: item.label_field,
      positive_labels: positives.length ? positives.join(LIST_SEPARATOR) : '未登记',
      deviation: deviationCell(item.deviation),
      registered: item.registered ? { text: '已登记', tone: 'ok' } : { text: '未登记·不产事件', tone: 'warn' },
    };
  }),
);


const modelingBars = computed(() =>
  props.data.modeling.map((item) => ({ label: item.logical_id, value: item.total, suffix: ' 个版本' })),
);

const modelTotals = computed(() =>
  props.data.modeling.reduce(
    (acc, item) => ({ published: acc.published + item.published, draft: acc.draft + item.draft }),
    { published: 0, draft: 0 },
  ),
);

const whiteLying = computed(() => props.data.modeling.filter((item) => item.total === 0).map((item) => item.logical_id));

const modelKpis = computed<CockpitKpi[]>(() => [
  { label: '已发布合计', value: modelTotals.value.published, unit: '个', tone: 'success' },
  { label: '草稿合计', value: modelTotals.value.draft, unit: '个', tone: 'primary' },
  { label: '数据白躺', value: whiteLying.value.length, unit: '份', tone: 'warning' },
]);


const summary = computed(() => props.runtime?.summary ?? null);

const activityTotal = computed(() =>
  props.runtime ? props.runtime.activity_trend.reduce((sum, point) => sum + point.total, 0) : null,
);

const runtimeKpis = computed<CockpitKpi[]>(() => {
  const item = summary.value;
  return [
    { label: '累计风险事件', value: item ? item.total : null, unit: '条', tone: 'primary' },
    {
      label: '已处置率',
      value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
      tone: 'success',
    },
    { label: '近 10 天活动', value: activityTotal.value, unit: '次', tone: 'warning' },
  ];
});

const statusItems = computed(() => {
  const item = summary.value;
  return [
    { label: '待处置', value: item?.pending ?? 0, tone: 'danger' as const },
    { label: '处理中', value: item?.processing ?? 0, tone: 'warning' as const },
    { label: '已处置', value: item?.resolved ?? 0, tone: 'success' as const },
  ];
});

const trendPoints = computed(() =>
  (props.runtime?.activity_trend ?? []).map((item) => ({
    label: item.date.slice(5),
    value: item.total,
    value2: item.risk,
  })),
);


const datasetColumns = computed(() => props.data.datasets.map((item) => item.logical_id));

const dimensionRows = computed<CockpitGridRow[]>(() => {
  const columns = datasetColumns.value;
  return props.data.dimension_coverage.map((item) => ({
    label: item.dimension,
    on: columns.map((id) => (item.datasets ?? []).includes(id)),
    count: (item.datasets ?? []).length,
  }));
});

const singleSource = computed(() => props.data.dimension_coverage.filter((item) => (item.datasets ?? []).length <= 1));


const visibilityItems = computed(() => {
  const map = new Map<string, number>();
  props.data.datasets.forEach((item) => {
    const label = VISIBILITY_TEXT[item.visibility] ?? item.visibility;
    map.set(label, (map.get(label) ?? 0) + 1);
  });
  return [...map.entries()].map(([label, value]) => ({ label, value }));
});

const memberRows = computed<CockpitRow[]>(() => {
  const list = props.members;
  if (list === null) return [];
  const admins = list.filter((item) => item.role === ROLE_SCENARIO_ADMIN).length;
  const users = list.filter((item) => item.role === ROLE_SCENARIO_USER).length;
  const disabled = list.filter((item) => item.status !== ACCOUNT_STATUS_ACTIVE).length;
  const rows: CockpitRow[] = [
    { label: '场景管理员', value: `${admins} 人` },
    { label: '场景用户', value: `${users} 人` },
    { label: '合计', value: `${list.length} 人` },
  ];
  if (disabled) rows.push({ label: '已禁用', value: `${disabled} 人`, tone: 'warning' });
  const overflow = (props.memberTotal ?? 0) - list.length;
  if (overflow > 0) rows.push({ label: '未纳入统计', value: `${overflow} 人（超出单页 ${MEMBER_PAGE_SIZE} 条）`, tone: 'warning' });
  return rows;
});

const runtimeHint = computed(() => (props.runtime ? `处置率 ${percentText(summary.value && summary.value.total ? summary.value.resolved / summary.value.total : null)}` : '运行态未取到'));
</script>
