<template>
  <CockpitKpis :items="overviewKpis" />

  <div class="pf-board">
    <!-- 数据集资产明细 -->
    <CockpitPanel index="01" title="数据集资产明细" hint="全量数据集" align="top" foot="只列资产属性；角色与标签口径见 02 角色分工矩阵，模型数见 03 建模覆盖">
      <CockpitMatrix :columns="assetColumns" :rows="assetRows" row-key="logical_id" />
    </CockpitPanel>

    <!-- 数据集角色分工矩阵 -->
    <CockpitPanel
      index="02"
      title="数据集角色分工矩阵"
      hint="角色由显式登记表映射"
      align="top"
      foot="状态列综合「是否入模」「是否登记风险口径」「角色是否可训练」三条判据；编目表与基线集未建模属设计使然，不计入数据白躺"
    >
      <CockpitMatrix :columns="roleColumns" :rows="roleRows" row-key="logical_id" />
    </CockpitPanel>

    <!-- 建模覆盖 -->
    <CockpitPanel
      index="03"
      title="建模覆盖"
      hint="每数据集模型版本数"
      align="top"
      :foot="idleNames.length ? `未建模 ${idleNames.length} 份：${idleNames.join('、')}` : '全部数据集均已有模型版本'"
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

    <!-- 地形因子跨数据集覆盖矩阵 -->
    <CockpitPanel
      index="05"
      title="地形因子跨数据集覆盖矩阵"
      hint="因子 × 数据集"
      align="top"
      :foot="binningConflicts.length ? `分箱不一致：${binningConflicts.join('、')} —— 跨数据集口径不可直接合并` : '多源因子分箱一致，跨数据集口径可直接合并'"
    >
      <CockpitGrid :columns="factorColumns" :rows="factorRows" :split="2" accent="#7dc9ff" />
    </CockpitPanel>

    <!-- 可见性与场景成员 -->
    <CockpitPanel index="06" title="数据集可见性与场景成员" hint="范围限本场景" align="top" foot="成员按账号角色分组计数；可见性为数据集注册时的共享范围">
      <CockpitDonut :items="visibilityItems" center-label="数据集" :percent="false" suffix=" 个" />
      <p v-if="members === null" class="pf-empty">成员数据未取到</p>
      <CockpitRows v-else :rows="memberRows" :columns="2" />
    </CockpitPanel>
  </div>
</template>
<script setup lang="ts">
/**
 * 地质风险 · 场景管理员首页看板，纯展示。取数在 sections/ProfileGeological.vue。
 */
import { computed } from 'vue';
import type { GeologicalProfile, WorkspaceBase } from '@/api/dashboardApi';
import type { UserAccount } from '@/types/security';
import { fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';
import CockpitPanel from '../CockpitPanel.vue';
import CockpitKpis from '../CockpitKpis.vue';
import type { CockpitKpi } from '../CockpitKpis.vue';
import CockpitBars from '../CockpitBars.vue';
import CockpitGrid from '../CockpitGrid.vue';
import type { CockpitGridRow } from '../CockpitGrid.vue';
import CockpitMatrix from '../CockpitMatrix.vue';
import type { CockpitCell, CockpitColumn } from '../CockpitMatrix.vue';
import CockpitRows from '../CockpitRows.vue';
import type { CockpitRow } from '../CockpitRows.vue';
import CockpitStack from '../CockpitStack.vue';
import CockpitTrend from '../CockpitTrend.vue';
import CockpitDonut from '../CockpitDonut.vue';
import { labelKindText, percentText, visibilityText } from '../profileTokens';

const props = defineProps<{
  data: GeologicalProfile;
  runtime: WorkspaceBase | null;
  members: UserAccount[] | null;
  memberTotal?: number | null;
}>();


const MEMBER_PAGE_SIZE = 200;

const UNTRAINABLE_ROLES = new Set(['全球编目表', '随机基线集']);

// S1 场景资产总览 KPI ×4

// 第 4 个 KPI 是地质特色：未建模数据集数（有数据但没有任何模型版本 = 数据白躺）
const unmodeledCount = computed(() => props.data.modeling.filter((item) => item.total === 0).length);

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
  { label: '统一风险占比', value: fmtPercent(props.data.risk_rate), tone: 'warning', icon: 'alert', sub: '全场景合并口径' },
  {
    label: '未建模数据集数',
    value: unmodeledCount.value,
    unit: '个',
    tone: 'purple',
    icon: 'model',
    sub: `${props.data.dataset_file_count} 份数据中 ${unmodeledCount.value} 份无模型`,
  },
]);

// 数据集资产明细

// 只讲资产属性（体量 / 字段数 / 版本）；标签口径与角色归 02，模型数归 03
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

// 数据集角色分工矩阵

const roleColumns: CockpitColumn[] = [
  { key: 'name', label: '数据集', ellipsis: true, ellipsisWidth: 130 },
  { key: 'role', label: '角色' },
  { key: 'label_field', label: '标签字段' },
  { key: 'label_kind', label: '标签类型' },
  { key: 'status', label: '建模与研判状态' },
];

const roleRows = computed(() =>
  props.data.roles.map((item) => {
    let status: CockpitCell;
    if (item.participates_in_training) {
      status = { text: '已入模', tone: 'ok' };
    } else if (UNTRAINABLE_ROLES.has(item.role)) {
      status = { text: '设计内不入模', tone: 'muted' };
    } else if (item.produces_risk_events) {
      status = { text: '待建模 · 有风险口径', tone: 'warn' };
    } else {
      status = { text: '未登记 · 不产事件', tone: 'warn' };
    }
    return {
      logical_id: item.logical_id,
      name: item.logical_id,
      role: item.role,
      label_field: item.label_field,
      label_kind: labelKindText(item.label_kind),
      status,
    };
  }),
);

// 建模覆盖

const modelingRows = computed(() =>
  props.data.modeling.map((item) => ({
    name: item.logical_id,
    published: item.published,
    draft: item.draft,
    total: item.total,
  })),
);

const modelingBars = computed(() => modelingRows.value.map((row) => ({ label: row.name, value: row.total, suffix: ' 个版本' })));

const modelTotals = computed(() =>
  modelingRows.value.reduce(
    (acc, row) => ({ published: acc.published + row.published, draft: acc.draft + row.draft }),
    { published: 0, draft: 0 },
  ),
);

const idleNames = computed(() => modelingRows.value.filter((row) => row.total === 0).map((row) => row.name));

const modelKpis = computed<CockpitKpi[]>(() => [
  { label: '已发布合计', value: modelTotals.value.published, unit: '个', tone: 'success' },
  { label: '草稿合计', value: modelTotals.value.draft, unit: '个', tone: 'primary' },
  { label: '未建模数据集', value: idleNames.value.length, unit: '份', tone: 'warning' },
]);

// 场景运行态势

const summary = computed(() => props.runtime?.summary ?? null);

// 近 10 天活动量 = activity_trend 各天 total 求和；运行态未取到时为 null（KPI 显示「—」）
const activityTotal = computed(() =>
  props.runtime ? props.runtime.activity_trend.reduce((sum, point) => sum + point.total, 0) : null,
);

const runtimeKpis = computed<CockpitKpi[]>(() => {
  const item = summary.value;
  return [
    { label: '累计风险事件', value: item ? item.total : null, unit: '条', tone: 'primary' },
    { label: '已处置率', value: item && item.total ? fmtPercent(item.resolved / item.total) : null, tone: 'success' },
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
  (props.runtime?.activity_trend ?? []).map((item) => ({ label: item.date.slice(5), value: item.total, value2: item.risk })),
);

// 地形因子跨数据集覆盖矩阵

const factorColumns = computed(() => props.data.datasets.map((item) => item.logical_id));

const factorRows = computed<CockpitGridRow[]>(() => {
  const columns = factorColumns.value;
  return props.data.factor_coverage.map((item) => ({
    label: item.factor,
    on: columns.map((id) => (item.datasets ?? []).includes(id)),
    count: (item.datasets ?? []).length,
  }));
});

const binningConflicts = computed(() =>
  props.data.factor_coverage.filter((item) => (item.datasets ?? []).length > 1 && !item.consistent_binning).map((item) => item.factor),
);

// 可见性与场景成员

const visibilityItems = computed(() => {
  const map = new Map<string, number>();
  props.data.datasets.forEach((item) => {
    const label = visibilityText(item.visibility);
    map.set(label, (map.get(label) ?? 0) + 1);
  });
  return [...map.entries()].map(([label, value]) => ({ label, value }));
});

const memberRows = computed<CockpitRow[]>(() => {
  const list = props.members;
  if (list === null) return [];
  const admins = list.filter((item) => item.role === 'SCENARIO_ADMIN').length;
  const users = list.filter((item) => item.role === 'SCENARIO_USER').length;
  const disabled = list.filter((item) => item.status !== 'active').length;
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

const runtimeHint = computed(() =>
  props.runtime
    ? `处置率 ${percentText(summary.value && summary.value.total ? summary.value.resolved / summary.value.total : null)}`
    : '运行态未取到',
);
</script>
