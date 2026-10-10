<script setup lang="ts">
/**
 * ProfileGeological —— 地质风险 · 场景管理员首页（管理端）。
 * 字段口径见 docs/场景管理员首页审查/实施契约.md §7 / §8.4。
 *
 * 视角：**管理端看资源与流程，不是执行端看任务**。与场景用户的「我的工作台」
 * （WorkspaceGeological）的区别：
 *   用户侧 ＝ 我手上的活：待处置告警、因子贡献排行、坡度档位排行、最近告警明细；
 *   管理侧 ＝ 这个场景健康吗：数据集各自扮演什么角色、地形因子覆盖是否完整、
 *             哪些数据在建模、哪些数据白躺着、流程积压与人员配置。
 *   因此这里**不**放因子贡献/坡度档位/灾害类型分布这类研判辅助图，也**不**渲染
 *   `recent_events`（那是执行端的派活清单）。
 *
 * 统一骨架（四场景一致，顺序不可变）：
 *   S1 场景资产总览 KPI ×4 → D1 ★数据集角色分工矩阵 → D2 ★地形因子跨数据集覆盖矩阵
 *   → S2 数据集资产明细 → S3 建模覆盖 → S4 场景运行态水位 → S5 场景成员与权限
 *
 * 数据来源两段，作用域不同：
 *   数据资产 /profile —— 数据集全量统计，不受运行态影响（roles / factor_coverage / modeling）。
 *   运行态 /workspace + 成员 /users —— 场景管理员拿到的是整个场景（self_only=false）；
 *   接口失败静默降级，不影响数据资产部分。
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

/* ------------------------------------------------------------------ */
/* 运行态与成员：并行请求 + 各自静默降级                                 */
/* ------------------------------------------------------------------ */

const runtime = ref<GeologicalWorkspace | null>(null);
/** 场景成员；null = 未取到（与「确实 0 人」区分开，避免误报 0） */
const members = ref<UserAccount[] | null>(null);

/**
 * 两个接口并行、各自静默降级：任一失败只影响它自己那块，不阻塞数据资产部分。
 * 模型数不再单独请求 modelVersionApi —— 后端画像已直接下发 `modeling`
 * （按 dataset 聚合的 published/draft/total），前端不再按 dataset_logical_id 自行归集，
 * 避免两套口径。
 */
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

/* ------------------------------------------------------------------ */
/* 画像字段契约：roles / factor_coverage / modeling 均为必填且恒下发      */
/* ------------------------------------------------------------------ */

/**
 * `GeologicalProfile` 把 `roles` / `factor_coverage` / `modeling` 声明为**必填数组**，后端
 * `get_profile` 也在每条代码路径上无条件下发（无数据集时给 `[]`），因此这里不做
 * `?? []` / `Array.isArray` 兜底 —— 那些分支恒不可达，只会让「未建模数」「数据白躺」
 * 多出一套永远为假的真假口径。
 *
 * 唯一保留的判据是「数据白躺」，S1 的未建模数据集数与 S3 的白躺名单共用它。
 */
const isWhiteLying = (item: { total: number }) => item.total === 0;

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI ×4                                              */
/* ------------------------------------------------------------------ */

/**
 * 第 4 个 KPI 是地质特色：未建模数据集数。
 * 「有数据但没有任何模型版本」＝ 数据白躺，是管理端最该追的资产闲置问题。
 */
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

/* ------------------------------------------------------------------ */
/* 展示名与枚举映射                                                     */
/* ------------------------------------------------------------------ */

/**
 * 数据集展示名去重。
 *
 * `dataset_display_name_of` 取的是上传文件名，同源重复的两条记录（如 dis_landslides 与
 * geo_slope_company_v1 都指向 DIS_Landslides.arff）会得到**完全相同的展示名**，
 * 列表里就会出现两行一模一样的名字、看不出差别。重名时补上 logical_id 以区分。
 * D1/D2/S2/S3 全部复用这一份映射，保证同一数据集在四张表里叫同一个名字。
 * 两遍遍历：先数重名，再据此生成展示名。
 */
const displayNames = computed(() => {
  const counts = new Map<string, number>();
  for (const item of props.data.datasets) {
    const name = item.name || item.logical_id;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const names = new Map<string, string>();
  for (const item of props.data.datasets) {
    const name = item.name || item.logical_id;
    names.set(item.logical_id, (counts.get(name) ?? 0) > 1 ? `${name}（${item.logical_id}）` : name);
  }
  return names;
});

/** logical_id → 展示名；优先去重表，其次后端行内的 name，最后回退 logical_id */
const nameOf = (logicalId: string, fallback?: string) =>
  displayNames.value.get(logicalId) ?? fallback ?? logicalId;

/** 标签类型中文映射：纯描述性，不参与正类判定 */
const LABEL_KIND_TEXT: Record<string, string> = {
  binary: '二分类',
  multiclass: '多分类',
  numeric: '数值',
  unknown: '未知',
};
const labelKindText = (kind: string) => LABEL_KIND_TEXT[kind] ?? '未知';

/** 可见性中文映射 */
const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};
const visibilityText = (value: string | undefined) =>
  value ? (VISIBILITY_TEXT[value] ?? value) : '—';

/* ------------------------------------------------------------------ */
/* D1 ★ 数据集角色分工矩阵                                              */
/* ------------------------------------------------------------------ */

/** 「不该入模」的角色：编目表是全球事件背景库、基线集是负样本采样法的参照物，
 *  两者未建模是设计使然，不计入「数据白躺」告警。 */
const UNTRAINABLE_ROLES = new Set(['全球编目表', '随机基线集']);

/**
 * 管理端的第一问：这些数据集各干什么活？
 * 角色（因子表/风险标签表/致灾因子表/全球编目表/随机基线集）由后端显式登记表映射，
 * 前端不做任何推断。
 *
 * 本表**只讲职责**（角色 / 标签 / 建模与研判状态），不复述样本量、字段数、风险占比 ——
 * 那些是「资产属性」，统一在 S2 资产明细里出现一次。同一粒度的信息全页只展示一次。
 *
 * 「建模与研判状态」把原先分开的两列（参与训练 / 产生风险事件）压成一个结论：
 * 两列各自是二值，并排放时读者要自己做四象限判断，而页面不给判据；更关键的是
 * 「未建模」在编目表、基线集上属于**设计使然**，在因子表 / 标签表上才是**数据白躺** ——
 * 一律标黄会把真正的告警稀释掉。合并后每个数据集只给一个结论，结论里已含「该不该建」。
 *
 * 三类问题必须留在表里被看见，而不是像旧版那样用 is_risk_label 过滤掉整行。
 */
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
      name: nameOf(item.logical_id, item.name),
      role: item.role,
      label_field: item.label_field,
      label_kind: labelKindText(item.label_kind),
      status,
    };
  }),
);

/* ------------------------------------------------------------------ */
/* D2 ★ 地形因子跨数据集覆盖矩阵                                        */
/* ------------------------------------------------------------------ */

/**
 * 管理端的第二问：地形因子到底被哪些数据集覆盖？
 * 覆盖数 = 该因子有字段定义的数据集数量；分箱一致性 = 同一因子在不同数据集里的
 * 取值定义（ARFF 分箱区间）是否一致 —— 不一致意味着跨数据集统计口径不可直接合并。
 */
const factorColumns: DashColumn[] = [
  { key: 'factor', label: '因子', width: 200 },
  { key: 'datasets', label: '覆盖数据集' },
  { key: 'coverage', label: '覆盖数', numeric: true, align: 'right', width: 90 },
  { key: 'binning', label: '分箱一致性', width: 110 },
];

/**
 * 分箱一致性只在**多源**时才有意义：只有一份数据含该因子时，「一致」是恒真命题
 * （后端把单源定义为 `consistent_binning = true`），显示「一致」会让读者以为比对过了。
 * 单源一律显示「单源无从比较」，把「这个因子只有一个来源」直接说出来。
 */
const factorRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.factor_coverage.map((item) => ({
    factor: item.factor,
    datasets: item.datasets.map((logicalId) => nameOf(logicalId)).join('、'),
    coverage: item.datasets.length,
    binning:
      item.datasets.length > 1
        ? item.consistent_binning
          ? { text: '一致', tone: 'ok' }
          : { text: '不一致', tone: 'up' }
        : { text: '单源无从比较', tone: 'muted' },
  })),
);

/* ------------------------------------------------------------------ */
/* S2 数据集资产明细                                                    */
/* ------------------------------------------------------------------ */

/**
 * 管理端的资产视角：每份数据**本身**什么样（体量 / 字段数 / 可见性 / 版本）。
 *
 * 与 D1 的分工：D1 讲「职责」（角色、标签口径、建模状态），S2 讲「资产属性」。
 * 标签字段归 D1、模型数归 S3，这里都不再出现 —— 同一粒度的信息全页只展示一次。
 *
 * 遍历**全部** datasets，不做任何过滤：未登记风险口径的行必须留在表里
 * （旧版用 is_risk_label 把它过滤掉，结果管理端看不到「谁没登记」）。
 * 该状态现在由 D1 的「建模与研判状态」列统一表达，不再在此处重复标注。
 */
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
    name: nameOf(item.logical_id, item.name),
    record_count: fmtInt(item.record_count),
    risk_rate: fmtPercent(item.risk_rate),
    attribute_count: item.attribute_count,
    visibility: visibilityText(item.visibility),
    version: item.version,
  })),
);

/* ------------------------------------------------------------------ */
/* S3 建模覆盖                                                          */
/* ------------------------------------------------------------------ */

/** S3 的单一基底：每数据集一行，柱状图与版本合计都从它派生 */
const modelingRows = computed(() =>
  props.data.modeling.map((item) => ({
    name: nameOf(item.logical_id),
    published: item.published,
    draft: item.draft,
    total: item.total,
  })),
);

/** 每个数据集一根柱 = 模型版本总数；为 0 即「数据白躺」 */
const modelingBars = computed(() =>
  modelingRows.value.map((row) => ({ value: row.name, count: row.total })),
);

/** 已发布 / 草稿合计（逐数据集的模型数由本块柱状图给出，不再在 S2 重复一列） */
const modelTotals = computed(() =>
  modelingRows.value.reduce(
    (acc, row) => ({ published: acc.published + row.published, draft: acc.draft + row.draft }),
    { published: 0, draft: 0 },
  ),
);

/* ------------------------------------------------------------------ */
/* S4 场景运行态水位                                                    */
/* ------------------------------------------------------------------ */

/** 近 10 天活动量 = activity_trend 各天 total 求和；运行态未取到时为 null（KPI 显示「—」） */
const activityTotal = computed(() => {
  const points = runtime.value?.activity_trend;
  return points ? points.reduce((sum, point) => sum + point.total, 0) : null;
});

/** 运行态 KPI：积压 / 处置率 / 近 10 天活动量 */
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

/** 处置漏斗：待处置 → 处理中 → 已处置 */
const funnelItems = computed(() =>
  (summary.value?.status_funnel ?? []).map((item) => ({ label: item.label, count: item.count })),
);

/** 近 10 天活动趋势：推理量 / 其中判定为风险的量（x 轴取 MM-DD，复用 dashFormat.fmtDate） */
const trendPoints = computed(() =>
  (runtime.value?.activity_trend ?? []).map((item) => ({
    label: fmtDate(item.date),
    value: item.total,
    value2: item.risk,
  })),
);

/* ------------------------------------------------------------------ */
/* S5 场景成员与权限                                                    */
/* ------------------------------------------------------------------ */

/** 场景成员：按账号角色分组计数，范围限本场景 */
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

  <!-- D1 ★ 数据集角色分工矩阵 -->
  <DashCard
    title="数据集角色分工矩阵"
    source="按数据集逐行对比 · 角色由显式登记表映射 · 状态列综合「是否入模」「是否登记风险口径」「角色是否可训练」三条判据"
  >
    <DashTable :columns="roleColumns" :rows="roleRows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 ★ 地形因子跨数据集覆盖矩阵 -->
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
