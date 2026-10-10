<script setup lang="ts">
/**
 * ProfileNetwork —— 网络安全 · 场景管理员首页（管理端）。
 * 字段口径见 docs/场景管理员首页审查/实施契约.md §7 / §8.1。
 *
 * 视角：**管理端看资源与口径，不是执行端看任务**。与场景用户的「我的工作台」
 * （WorkspaceNetwork）的区别：
 *   用户侧 ＝ 我手上的活：待处置告警、异常端口偏离度、包长五段分布、协议分布、最近告警明细；
 *   管理侧 ＝ 这个场景的数据能不能直接合并着用：多个数据集的标签字段/正类取值是不是同一套
 *             风险语言、流量统计维度被几份数据覆盖、哪些数据白躺着、流程积压与人员配置。
 *   因此这里**不**渲染 port_deviation / flow_segments / top_ports / protocol_distribution /
 *   flags / services / traffic 这类研判辅助图，也**不**渲染 `recent_events`（那是执行端的
 *   派活清单）。后端字段全部保留（向后兼容），只是不再上屏。
 *
 * 统一骨架（四场景一致，顺序不可变）：
 *   S1 场景资产总览 KPI ×4 → D1 ★数据集风险口径可比性矩阵 → D2 ★流量统计维度覆盖矩阵
 *   → S2 数据集资产明细 → S3 建模覆盖 → S4 场景运行态水位 → S5 场景成员与权限
 *
 * 数据来源两段，作用域不同：
 *   数据资产 /profile —— 数据集全量统计，不受运行态影响（caliber_matrix / dimension_coverage / modeling）。
 *   运行态 /workspace + 成员 /users —— 场景管理员拿到的是整个场景（self_only=false）；
 *   接口失败静默降级，不影响数据资产部分。
 *
 * 扩展字段不做「未下发」空数组兜底：三者在前端类型里必填（dashboardApi.ts:153/208/210），
 * 后端 get_profile 也无条件下发（dashboard_service.py:1386/1486/1488），不存在只缺它们的中间态。
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

/* ------------------------------------------------------------------ */
/* 口径常量：阈值 / 枚举字面量 / 分隔符一律在此具名，computed 与模板共用   */
/* ------------------------------------------------------------------ */

/** 列表分隔符：正类取值、覆盖数据集、白躺数据集共用 */
const LIST_SEPARATOR = '、';
/** 偏离倍数：保留位数 / 持平基准（×1 = 与场景合并口径持平） */
const DEVIATION_DIGITS = 2;
const DEVIATION_BASELINE = 1;
/** 覆盖数阈值：=1 表示该维度只有一份数据能算 */
const COVERAGE_SINGLE_SOURCE = 1;
/** 成员列表单页上限（后端分页硬上限，见 backend/app/utils/common.py:65） */
const MEMBER_PAGE_SIZE = 200;
/** 角色与账号状态字面量（frontend/src/types/security.ts:376 / 385） */
const ROLE_SCENARIO_ADMIN = 'SCENARIO_ADMIN';
const ROLE_SCENARIO_USER = 'SCENARIO_USER';
const ACCOUNT_STATUS_ACTIVE = 'active';

/* ------------------------------------------------------------------ */
/* 运行态与成员：并行请求 + 各自静默降级                                 */
/* ------------------------------------------------------------------ */

/**
 * 运行态（/workspace）与成员（/users）不属于 /profile 的返回范围，前端另行获取。
 * 类型收窄到 WorkspaceBase：本页只用 summary / activity_trend 这两个四场景同构的字段，
 * 不校验 scenario_key —— 多一层 key 校验只会在后端换 key 时把整块静默变空。
 */
const runtime = ref<WorkspaceBase | null>(null);
/** 场景成员；null = 未取到（与「确实 0 人」区分开，避免误报 0） */
const members = ref<UserAccount[] | null>(null);
/** /users 命中的账号总数；与单页返回条数不等时说明统计被分页截断 */
const memberTotal = ref<number | null>(null);

/**
 * 两个接口并行、各自静默降级：任一失败只影响它自己那块，不阻塞数据资产部分。
 * 成员显式传 `scenario_id`：后端只对 SCENARIO_ADMIN 自动收窄场景，SUPER_ADMIN
 * 不传参时拿到的是全平台账号、`total` 也是全平台人数，S5 会渲染出「未纳入统计 N 人」
 * 的假行。传参后 `total` 即本场景权威人数。本地再过滤一次作为纵深防御。
 */
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

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI ×4                                              */
/* ------------------------------------------------------------------ */

/**
 * 第 4 个 KPI 是网络安全特色：**风险口径分裂度**。
 * 统计口径：全部数据集用了几种不同的「标签字段名」。
 * 为什么这么算：同一场景内如果两个数据集一个叫 `Label`、一个叫 `class`，
 * 它们的「1 / anomaly」正类取值根本不在同一套风险语言里，合并统计前必须先做显式映射；
 * 分裂度 > 1 就意味着「统一风险占比」这个数是由多套口径拼出来的，不能直接横向比较。
 * 矩阵为空时返回 null（而不是 0）—— 0 会被读成「口径完全统一」，是误报。
 */
const caliberLanguages = computed(() => {
  const rows = props.data.caliber_matrix;
  if (!rows.length) return null;
  return new Set(rows.map((row) => row.label_field)).size;
});

/** 第 4 个 KPI 的口径副标题（SHOW_DASH_HINTS=false 时不上屏，口径仍按契约备好） */
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

/* ------------------------------------------------------------------ */
/* 展示名与枚举映射                                                     */
/* ------------------------------------------------------------------ */

/**
 * 数据集展示名去重。
 *
 * `dataset_display_name_of` 取的是上传文件名，同源重复的两条记录（如 NF-UNSW-NB15-v2 与
 * net_flow_company_v1 都指向同一份 arff）会得到**完全相同的展示名**，
 * 列表里就会出现两行一模一样的名字、看不出差别。重名时补上 logical_id 以区分。
 * D1/D2/S2/S3 全部复用这一份映射，保证同一数据集在四张表里叫同一个名字。
 */
const displayNames = computed(() => {
  const names = props.data.datasets.map((item) => item.name || item.logical_id);
  const counts = new Map<string, number>();
  for (const name of names) counts.set(name, (counts.get(name) ?? 0) + 1);
  return new Map(
    props.data.datasets.map((item, index) => [
      item.logical_id,
      (counts.get(names[index]) ?? 0) > 1 ? `${names[index]}（${item.logical_id}）` : names[index],
    ]),
  );
});

/** logical_id → 展示名；优先去重表，其次后端行内的 name，最后回退 logical_id */
const nameOf = (logicalId: string, fallback?: string) =>
  displayNames.value.get(logicalId) ?? fallback ?? logicalId;

/** 可见性中文映射 */
const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};
const visibilityText = (value: string | undefined) =>
  value ? (VISIBILITY_TEXT[value] ?? value) : '—';

/* ------------------------------------------------------------------ */
/* D1 ★ 数据集风险口径可比性矩阵                                        */
/* ------------------------------------------------------------------ */

/**
 * 管理端的第一问：这些数据集的风险口径能不能直接合并？
 *
 * 逐行摆出「标签字段 + 正类取值」，把「同一个场景里其实有好几套风险语言」这件事
 * 变成可见的事实；`deviation` 再把每份数据的风险占比与场景合并口径的倍数关系标出来，
 * 偏离越大说明该数据集越不能代表场景整体。
 *
 * 本表**只讲口径**（标签字段 / 正类取值 / 偏离 / 登记状态），不复述样本量、风险样本、
 * 风险占比 —— 那些是「资产属性」，统一在 S2 资产明细里出现一次。同一粒度的信息全页只展示一次。
 *
 * 「未登记·不产事件」是**管理告警**，不是隐藏理由：constants.py 禁止按标签字符串 /
 * 数值大小自动推断正类，未进显式登记表的数据集不会产生风险事件，必须留在表里被看见。
 * 登记状态由本表承载后，S2 不再重复挂「未登记风险口径」标签。
 */
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
      name: nameOf(item.logical_id, item.name),
      label_field: item.label_field,
      // 未登记正类 → 不猜、不推断，直接写「未登记」（显式登记表缺项）
      positive_labels: positives.length ? positives.join(LIST_SEPARATOR) : '未登记',
      deviation: deviationCell(item.deviation),
      registered: item.registered
        ? { text: '已登记', tone: 'ok' }
        : { text: '未登记·不产事件', tone: 'warn' },
    };
  }),
);

/* ------------------------------------------------------------------ */
/* D2 ★ 流量统计维度覆盖矩阵                                            */
/* ------------------------------------------------------------------ */

/**
 * 管理端的第二问：流量统计维度到底被几份数据支撑？
 * 覆盖数 = 含该维度字段（协议 / 目的端口 / 包长分布 / 连接状态 / 应用服务）的数据集数量。
 * 与**物理文件总数**比较：全覆盖说明该维度在所有入库文件里都有字段定义；
 * 「仅一份数据支撑」意味着这个统计维度只有一份数据能算，跨数据集无法互相校验。
 */
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
      datasets: ids.length ? ids.map((logicalId) => nameOf(logicalId)).join(LIST_SEPARATOR) : '—',
      coverage: ids.length,
      coverage_status: coverageCell(ids.length),
    };
  }),
);

/* ------------------------------------------------------------------ */
/* S2 数据集资产明细                                                    */
/* ------------------------------------------------------------------ */

/**
 * 列结构：数据集名 / 样本量 / 风险占比 / 字段数 / 可见性 / 版本。
 *
 * 本表**只讲资产属性**。`标签字段` 归 D1 口径矩阵（那是它的主题）、`已发布模型数` 归 S3
 * 建模覆盖（柱状图已按数据集逐根呈现），此处都不再重复。
 *
 * 这里遍历**全部** datasets，不做任何过滤：未登记风险口径的行（`caliber_registered === false`）
 * 必须留在表里 —— 用 is_risk_label 过滤会把「谁没登记」直接从管理端视野里抹掉。
 * 「未登记」这件事由 D1 的「登记状态」列统一表达，此处不再重复挂标签。
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

/** 每个数据集一根柱 = 模型版本总数；为 0 即「数据白躺」 */
const modelingBars = computed(() =>
  props.data.modeling.map((item) => ({ value: nameOf(item.logical_id), count: item.total })),
);

/** 白躺数据集（有数据、无任何模型版本）—— 单独点名，柱状图看不出「0 根柱」 */
const whiteLying = computed(() =>
  props.data.modeling.filter((item) => item.total === 0).map((item) => nameOf(item.logical_id)),
);

/** 已发布 / 草稿合计（DashBars 只渲染 count，逐数据集明细在 S2 的「已发布模型数」列） */
const modelTotals = computed(() =>
  props.data.modeling.reduce(
    (acc, item) => ({ published: acc.published + item.published, draft: acc.draft + item.draft }),
    { published: 0, draft: 0 },
  ),
);

/* ------------------------------------------------------------------ */
/* S4 场景运行态水位                                                    */
/* ------------------------------------------------------------------ */

/** 近 10 天活动量：activity_trend[].total 之和；运行态缺失时为 null（≠ 0，见报告 D-1） */
const activityTotal = computed(() =>
  runtime.value ? runtime.value.activity_trend.reduce((sum, point) => sum + point.total, 0) : null,
);

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

/** 近 10 天活动趋势：推理量 / 其中判定为风险的量 */
const trendPoints = computed(() =>
  (runtime.value?.activity_trend ?? []).map((item) => ({
    label: item.date.slice(5),
    value: item.total,
    value2: item.risk,
  })),
);

/* ------------------------------------------------------------------ */
/* S5 场景成员与权限                                                    */
/* ------------------------------------------------------------------ */

/** 场景成员：按账号角色分组计数，范围限本场景 */
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
  // 单页 200 条是硬上限：被分页截断时明说，避免把「取到的一页」当成「全场景成员」
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

  <!-- D1 ★ 数据集风险口径可比性矩阵 -->
  <DashCard
    title="数据集风险口径可比性矩阵"
    source="按数据集逐行对比 · 统一正类口径 · 偏离 = 该数据集风险占比 ÷ 场景合并风险占比（>1 高于场景口径，<1 低于）；「未登记·不产事件」表示风险口径未进显式登记表，不会产生风险事件"
  >
    <DashTable :columns="caliberColumns" :rows="caliberRows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 ★ 流量统计维度覆盖矩阵 -->
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
