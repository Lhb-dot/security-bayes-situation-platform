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
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type CaliberRow,
  type DimensionCoverage,
  type ModelingStat,
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
 * 成员按契约用 `page_size: 200` 拉一页后在本地按 scenario_id 过滤（不依赖后端过滤参数）。
 */
const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getUserList({ page_size: 200 }),
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
/* 新增字段兜底：后端 B 任务未上线时不得白屏                              */
/* ------------------------------------------------------------------ */

/**
 * `caliber_matrix` / `dimension_coverage` / `modeling` 是本次画像扩展新增的字段。
 * 旧后端不会下发它们，直接 `.map()` 会整页白屏；一律兜底为空数组，
 * 让页面退化为「暂无数据」而不是崩掉。
 */
const rowsOrEmpty = <T,>(value: T[] | undefined): T[] => value ?? [];

const caliber = computed(() => rowsOrEmpty<CaliberRow>(props.data.caliber_matrix));
const dimensionCoverage = computed(() =>
  rowsOrEmpty<DimensionCoverage>(props.data.dimension_coverage),
);
const modeling = computed(() => rowsOrEmpty<ModelingStat>(props.data.modeling));
/**
 * `modeling` 是否真的由后端下发。
 * 未下发时「已发布 0 / 共 0」会算成 0，属于**误报**，因此这类结论一律显示「—」。
 */
const modelingReady = computed(() => Array.isArray(props.data.modeling));

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI ×4                                              */
/* ------------------------------------------------------------------ */

/**
 * 第 4 个 KPI 是网络安全特色：**风险口径分裂度**。
 * 统计口径：全部数据集用了几种不同的「标签字段名」。
 * 为什么这么算：同一场景内如果两个数据集一个叫 `Label`、一个叫 `class`，
 * 它们的「1 / anomaly」正类取值根本不在同一套风险语言里，合并统计前必须先做显式映射；
 * 分裂度 > 1 就意味着「统一风险占比」这个数是由多套口径拼出来的，不能直接横向比较。
 * 后端未下发矩阵时返回 null（显示「—」）而不是 0 —— 0 会被读成「口径完全统一」，是误报。
 */
const caliberLanguages = computed(() => {
  const rows = caliber.value;
  if (!rows.length) return null;
  return new Set(rows.map((row) => row.label_field)).size;
});

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
    sub:
      caliberLanguages.value === null
        ? '后端未下发风险口径矩阵'
        : `${caliberLanguages.value} 套风险语言 · 不可直接合并`,
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
  names.forEach((name) => counts.set(name, (counts.get(name) ?? 0) + 1));
  const map = new Map<string, string>();
  props.data.datasets.forEach((item, index) => {
    const name = names[index];
    map.set(item.logical_id, (counts.get(name) ?? 0) > 1 ? `${name}（${item.logical_id}）` : name);
  });
  return map;
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

/** 每数据集的模型版本统计（后端已按 dataset 聚合，这里只做 logical_id 索引） */
const modelingByDataset = computed(
  () => new Map(modeling.value.map((item) => [item.logical_id, item])),
);

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
 * 「未登记·不产事件」是**管理告警**，不是隐藏理由：constants.py 禁止按标签字符串 /
 * 数值大小自动推断正类，未进显式登记表的数据集不会产生风险事件，必须留在表里被看见。
 */
const caliberColumns: DashColumn[] = [
  { key: 'name', label: '数据集', width: 220 },
  { key: 'label_field', label: '标签字段' },
  { key: 'positive_labels', label: '正类取值' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'risk_count', label: '风险样本', numeric: true, align: 'right' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'deviation', label: '与场景合并口径偏离', numeric: true, align: 'right' },
  { key: 'registered', label: '登记状态' },
];

/**
 * 偏离倍数单元格：>1 高于场景合并口径（红）、<1 低于（蓝）、=1 持平（灰）、无基准（—）。
 * 保留 2 位小数：偏离是「倍数」不是百分比，位数再多在表里也读不出来。
 */
const deviationCell = (value: number | null | undefined): DashCell => {
  if (value === null || value === undefined) return '—';
  const num = Number(value);
  if (!Number.isFinite(num)) return '—';
  const text = `×${num.toFixed(2)}`;
  if (num > 1) return { text, tone: 'up' };
  if (num < 1) return { text, tone: 'down' };
  return { text, tone: 'muted' };
};

const caliberRows = computed<Array<Record<string, unknown>>>(() =>
  caliber.value.map((item) => {
    const positives = item.positive_labels ?? [];
    return {
      logical_id: item.logical_id,
      name: nameOf(item.logical_id, item.name),
      label_field: item.label_field,
      // 未登记正类 → 不猜、不推断，直接写「未登记」（显式登记表缺项）
      positive_labels: positives.length ? positives.join('、') : '未登记',
      record_count: fmtInt(item.record_count),
      risk_count: fmtInt(item.risk_count),
      risk_rate: fmtPercent(item.risk_rate),
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
  if (count === 1) return { text: '仅一份数据支撑', tone: 'warn' };
  return { text: '部分覆盖', tone: 'muted' };
};

const dimensionRows = computed<Array<Record<string, unknown>>>(() =>
  dimensionCoverage.value.map((item) => {
    const ids = item.datasets ?? [];
    return {
      key: item.key,
      dimension: item.dimension,
      datasets: ids.length ? ids.map((logicalId) => nameOf(logicalId)).join('、') : '—',
      coverage: ids.length,
      coverage_status: coverageCell(ids.length),
    };
  }),
);

/* ------------------------------------------------------------------ */
/* S2 数据集资产明细                                                    */
/* ------------------------------------------------------------------ */

/**
 * 列结构与四场景完全一致（契约 §7）：数据集名 / 样本量 / 标签字段 / 风险占比 /
 * 字段数 / 可见性 / 已发布模型数 / 版本。
 *
 * 这里遍历**全部** datasets，不做任何过滤：未登记风险口径的行（`caliber_registered === false`）
 * 必须带着「未登记风险口径」标注留在表里 —— 用 is_risk_label 过滤会把「谁没登记」直接
 * 从管理端视野里抹掉，而这正是要暴露的登记表缺项问题。
 * 标注放在「标签字段」列内（不新增第 9 列，保持四场景 S2 列结构一致）。
 */
const datasetColumns: DashColumn[] = [
  { key: 'name', label: '数据集名', width: 220 },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'label_field', label: '标签字段' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'visibility', label: '可见性' },
  { key: 'models', label: '已发布模型数' },
  { key: 'version', label: '版本', numeric: true, align: 'right' },
];

const datasetRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.datasets.map((item) => {
    const stat = modelingByDataset.value.get(item.logical_id);
    return {
      logical_id: item.logical_id,
      name: nameOf(item.logical_id, item.name),
      // 未登记风险口径 → 模板插槽里补一枚醒目告警标签
      unregistered: item.caliber_registered === false,
      record_count: fmtInt(item.record_count),
      label_field: item.label_field,
      risk_rate: fmtPercent(item.risk_rate),
      attribute_count: item.attribute_count,
      visibility: visibilityText(item.visibility),
      models: modelingReady.value && stat ? `已发布 ${stat.published} / 共 ${stat.total}` : '—',
      version: item.version,
    };
  }),
);

/* ------------------------------------------------------------------ */
/* S3 建模覆盖                                                          */
/* ------------------------------------------------------------------ */

/** 每个数据集一根柱 = 模型版本总数；为 0 即「数据白躺」 */
const modelingBars = computed(() =>
  modeling.value.map((item) => ({ value: nameOf(item.logical_id), count: item.total })),
);

/** 白躺数据集（有数据、无任何模型版本）—— 单独点名，柱状图看不出「0 根柱」 */
const whiteLying = computed(() =>
  modeling.value.filter((item) => item.total === 0).map((item) => nameOf(item.logical_id)),
);

/** 已发布 / 草稿合计（DashBars 只渲染 count，逐数据集明细在 S2 的「已发布模型数」列） */
const modelTotals = computed(() =>
  modeling.value.reduce(
    (acc, item) => ({ published: acc.published + item.published, draft: acc.draft + item.draft }),
    { published: 0, draft: 0 },
  ),
);

/* ------------------------------------------------------------------ */
/* S4 场景运行态水位                                                    */
/* ------------------------------------------------------------------ */

/** 运行态 KPI：积压 / 处置率 / 近 10 天活动量 */
const runtimeKpis = computed(() => {
  const item = summary.value;
  const activity = runtime.value
    ? (runtime.value.activity_trend ?? []).reduce((sum, point) => sum + Number(point.total ?? 0), 0)
    : null;
  return [
    { label: '待处置积压', value: item ? item.pending : null, unit: '条', tone: 'danger' as const },
    {
      label: '已处置率',
      value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
      tone: 'success' as const,
      raw: true,
    },
    { label: '近 10 天活动', value: activity, unit: '次', tone: 'primary' as const },
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
  // 单页 200 条是硬上限：被分页截断时明说，避免把「取到的一页」当成「全场景成员」
  const overflow = (memberTotal.value ?? 0) - list.length;
  if (overflow > 0) {
    rows.push({ label: '未纳入统计', value: `${overflow} 人（超出单页 200 条）` });
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
    source="全量数据集，不做过滤；未登记风险口径的行在标签字段后单独标注"
  >
    <DashTable :columns="datasetColumns" :rows="datasetRows" row-key="logical_id" dense>
      <template #label_field="{ row }">
        <span>{{ row.label_field }}</span>
        <span v-if="row.unregistered === true" class="d-tag d-tag--warn" style="margin-left: 6px">未登记风险口径</span>
      </template>
    </DashTable>
  </DashCard>

  <!-- S3 建模覆盖 -->
  <DashCard title="建模覆盖" source="每数据集一根柱 = 模型版本总数；总数为 0 即「数据白躺」">
    <DashBars :items="modelingBars" :label-width="260" suffix=" 个版本" />
    <p v-if="modelingReady" style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
      <span v-if="whiteLying.length" class="d-tag d-tag--warn">数据白躺 {{ whiteLying.length }} 份</span>
      <span v-if="whiteLying.length" style="margin-left: 6px">{{ whiteLying.join('、') }}</span>
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
