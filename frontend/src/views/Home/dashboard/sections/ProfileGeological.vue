<script setup lang="ts">
/**
 * 地质风险 · 场景管理员首页。看资源与流程：数据集角色、地形因子覆盖、
 * 建模情况、积压与人。执行端的因子贡献与坡度排行不在此页。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type GeologicalProfile,
  type GeologicalWorkspace,
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
import type { DashColumn, DashCell } from '@/components/dashboard/DashTable.vue';
import { fmtDate, fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: GeologicalProfile }>();


const runtime = ref<GeologicalWorkspace | null>(null);
const members = ref<UserAccount[] | null>(null);

const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getUserList({ scenario_id: scenarioId, page_size: 200 }),
  ]);

  runtime.value =
    runtimeResult.status === 'fulfilled' && runtimeResult.value.scenario_key === 'geological'
      ? (runtimeResult.value as GeologicalWorkspace)
      : null;
  members.value =
    memberResult.status === 'fulfilled'
      ? memberResult.value.items.filter((item) => item.scenario_id === scenarioId)
      : null;
};

watch(() => props.data.scenario_id, loadAll);
onMounted(loadAll);

const summary = computed(() => runtime.value?.summary ?? null);


/**
 * `GeologicalProfile` 把 `roles` / `factor_coverage` / `modeling` 声明为必填数组，后端
 * `get_profile` 也在每条代码路径上无条件下发（无数据集时给 `[]`），因此这里不做
 * `?? []` / `Array.isArray` 兜底，那些分支恒不可达，只会让「未建模数」「数据白躺」
 * 多出一套永远为假的真假口径。
 */
const isWhiteLying = (item: { total: number }) => item.total === 0;


const unmodeledCount = computed(() => props.data.modeling.filter(isWhiteLying).length);

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
    label: '未建模数据集数',
    value: unmodeledCount.value,
    unit: '个',
    tone: 'warning' as const,
    sub: `${props.data.dataset_file_count} 份数据中 ${unmodeledCount.value} 份无模型`,
  },
]);


const LABEL_KIND_TEXT: Record<string, string> = {
  binary: '二分类',
  multiclass: '多分类',
  numeric: '数值',
  unknown: '未知',
};
const labelKindText = (kind: string) => LABEL_KIND_TEXT[kind] ?? '未知';

const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};
const visibilityText = (value: string | undefined) =>
  value ? (VISIBILITY_TEXT[value] ?? value) : '—';


const UNTRAINABLE_ROLES = new Set(['全球编目表', '随机基线集']);

const roleColumns: DashColumn[] = [
  { key: 'name', label: '数据集', width: 220 },
  { key: 'role', label: '角色', width: 110 },
  { key: 'label_field', label: '标签字段' },
  { key: 'label_kind', label: '标签类型' },
  { key: 'status', label: '建模与研判状态' },
];

const roleRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.roles.map((item) => {
    let status: DashCell;
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


const factorColumns: DashColumn[] = [
  { key: 'factor', label: '因子', width: 200 },
  { key: 'datasets', label: '覆盖数据集' },
  { key: 'coverage', label: '覆盖数', numeric: true, align: 'right', width: 90 },
  { key: 'binning', label: '分箱一致性', width: 110 },
];

const factorRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.factor_coverage.map((item) => ({
    factor: item.factor,
    datasets: item.datasets.join('、'),
    coverage: item.datasets.length,
    binning:
      item.datasets.length > 1
        ? item.consistent_binning
          ? { text: '一致', tone: 'ok' }
          : { text: '不一致', tone: 'up' }
        : { text: '单源无从比较', tone: 'muted' },
  })),
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


const modelingRows = computed(() =>
  props.data.modeling.map((item) => ({
    name: item.logical_id,
    published: item.published,
    draft: item.draft,
    total: item.total,
  })),
);

const modelingBars = computed(() =>
  modelingRows.value.map((row) => ({ value: row.name, count: row.total })),
);

const modelTotals = computed(() =>
  modelingRows.value.reduce(
    (acc, row) => ({ published: acc.published + row.published, draft: acc.draft + row.draft }),
    { published: 0, draft: 0 },
  ),
);


const activityTotal = computed(() => {
  const points = runtime.value?.activity_trend;
  return points ? points.reduce((sum, point) => sum + point.total, 0) : null;
});

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

// 近 10 天活动趋势：推理量 / 其中判定为风险的量（x 轴取 MM-DD，复用 dashFormat.fmtDate）
const trendPoints = computed(() =>
  (runtime.value?.activity_trend ?? []).map((item) => ({
    label: fmtDate(item.date),
    value: item.total,
    value2: item.risk,
  })),
);


const memberRows = computed(() => {
  if (members.value === null) return [];
  const list = members.value;
  const admins = list.filter((item) => item.role === 'SCENARIO_ADMIN');
  const users = list.filter((item) => item.role === 'SCENARIO_USER');
  const disabled = list.filter((item) => item.status !== 'active');
  const rows = [
    { label: '场景管理员', value: `${admins.length} 人` },
    { label: '场景用户', value: `${users.length} 人` },
    { label: '合计', value: `${list.length} 人` },
  ];
  if (disabled.length) {
    rows.push({ label: '已禁用', value: `${disabled.length} 人` });
  }
  return rows;
});
</script>

<template>
  <!-- S1 场景资产总览 -->
  <DashKpis :items="overviewKpis" />

  <!-- D1 数据集角色分工矩阵 -->
  <DashCard
    title="数据集角色分工矩阵"
    source="按数据集逐行对比 · 角色由显式登记表映射 · 状态列综合「是否入模」「是否登记风险口径」「角色是否可训练」三条判据"
  >
    <DashTable :columns="roleColumns" :rows="roleRows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 地形因子跨数据集覆盖矩阵 -->
  <DashCard
    title="地形因子跨数据集覆盖矩阵"
    source="按因子逐行对比 · 覆盖数为含该因子字段的数据集数量 · 分箱不一致表示跨数据集口径不可直接合并"
  >
    <DashTable :columns="factorColumns" :rows="factorRows" row-key="factor" dense />
  </DashCard>

  <!-- S2 数据集资产明细 -->
  <DashCard
    title="数据集资产明细"
    source="全量数据集，不做过滤 · 只列资产属性；标签口径见角色分工矩阵、模型数见建模覆盖"
  >
    <DashTable :columns="datasetColumns" :rows="datasetRows" row-key="logical_id" dense />
  </DashCard>

  <!-- S3 建模覆盖 -->
  <DashCard
    title="建模覆盖"
    source="每数据集一根柱 = 模型版本总数；哪份数据该建模而未建模，见上方角色分工矩阵的状态列"
  >
    <DashBars :items="modelingBars" :label-width="250" suffix=" 个版本" />
    <p style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7; color: rgba(220, 234, 255, 0.5)">
      已发布合计 {{ modelTotals.published }} / 草稿合计 {{ modelTotals.draft }}
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
