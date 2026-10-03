<script setup lang="ts">
/**
 * ProfilePower —— 电力系统 · 场景管理员首页（管理端数据画像）。
 * 字段口径见 docs/场景管理员首页审查/实施契约.md §7 / §8.2。
 *
 * 视角：**管理端看资源与流程，不是执行端看任务**。与场景用户的「我的工作台」
 * （WorkspacePower.vue）的分工：
 *   用户侧 ＝ 我手上的活：电参量 gauge、设备告警数排行、问题类型告警构成、最近告警；
 *   管理侧 ＝ 这个场景健康吗：跨数据集的电参量基线是否一致、设备/系统被哪些数据集覆盖、
 *            数据集有没有被建模、处置流程积压多少、这个场景有哪些人。
 *   因此本页**不出现**任何 gauge、告警排行、问题类型构成 —— 那是执行端研判图。
 *   原「电参量均值/范围」「问题类型分布」「设备样本数量分布」「电力系统分布与频率」
 *   「各设备故障样本占比」等 7 张研判卡全部移除（后端字段保留，页面不再渲染）。
 *
 * 数据来源两段，作用域不同：
 *   数据资产 /profile  —— 由父组件 AdminProfilePage 传入（props.data），全量数据集统计；
 *   运行态 /workspace、成员 /users —— 本组件另取，用 Promise.allSettled 并行且各自静默降级，
 *   任一失败只让对应那块的数值变成占位符，不阻塞主画像渲染（参照 ProfileGeological.vue）。
 *
 * 可空口径：`PowerProfile` 的 `telemetry_by_dataset` / `component_matrix` / `modeling`
 * 以及行内的 `params` / `counts` / `violations` 都是**必填**字段（dashboardApi.ts 未标可选，
 * dashboard_service.get_profile 恒返回；modeling 对每个可见数据集都有一行，无模型时计 0），
 * 因此不做「字段可能没下发」的空数组兜底 —— 那种兜底会把「没取到」误渲染成
 * 「0 个模型 → 数据白躺」的假告警。真正需要降级的是**另一个请求**的数据：运行态 runtime
 * 与成员 members，失败时保持 null，由各块显示占位符。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type PowerProfile,
  type PowerWorkspace,
  type TelemetryByDataset,
} from '@/api/dashboardApi';
import { getUserList } from '@/api/userApi';
import type { UserAccount } from '@/types/security';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import type { KpiItem } from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashFunnel from '@/components/dashboard/DashFunnel.vue';
import DashLine from '@/components/dashboard/DashLine.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import DashTable from '@/components/dashboard/DashTable.vue';
import type { DashColumn } from '@/components/dashboard/DashTable.vue';
import { fmtDate, fmtNum, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: PowerProfile }>();

/* ------------------------------------------------------------------ */
/* 口径常量                                                            */
/* ------------------------------------------------------------------ */

/** 运行态接口返回的 scenario_key：确认拿到的是本场景的数据，防止串场景渲染 */
const SCENARIO_KEY = 'power';

/** 可见性枚举 → 管理端中文（后端存英文枚举，管理端要能直接读） */
const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};

/** D1 三个电参量列 → 后端 `telemetry_by_dataset[].params[].key`（与后端 POWER_PARAMS 的 key 一致） */
const PARAM_KEYS = {
  voltage: 'VoltageLevel_kV',
  current: 'CurrentAmp',
  temperature: 'Temperature_C',
} as const;

/** D1 卡片的基线口径文案：与后端 `POWER_BASELINE`（dashboard_service.py:191）逐项一致 */
const BASELINE_SOURCE =
  '电力基线：电压 300–700 kV · 电流 400–1600 A · 温度 30–90 ℃ · 工频 49.8–50.2 Hz · 丢包 ≤1%';

/* ------------------------------------------------------------------ */
/* 展示名去重                                                          */
/* ------------------------------------------------------------------ */

/**
 * 数据集展示名去重。
 *
 * 后端 `dataset_display_name_of` 取的是上传文件名，同一份物理文件被不同账号重复注册时
 * （如 power_grid_company_v1 与 powergrid_knowledgebase 同源）会得到**完全相同的展示名**，
 * 矩阵里就会出现两行一模一样的名字、看不出差别。重名时补上 logical_id 以区分。
 */
const displayNames = computed(() => {
  const counts = new Map<string, number>();
  for (const item of props.data.datasets) {
    const name = item.name || item.logical_id;
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const entries: Array<[string, string]> = props.data.datasets.map((item) => {
    const name = item.name || item.logical_id;
    return [item.logical_id, (counts.get(name) ?? 0) > 1 ? `${name}（${item.logical_id}）` : name];
  });
  return new Map(entries);
});

/** 取展示名：优先用去重后的展示名，其次用接口自带的 name，最后兜底 logical_id */
const nameOf = (logicalId: string, fallback?: string | null) =>
  displayNames.value.get(logicalId) ?? fallback ?? logicalId;

/* ------------------------------------------------------------------ */
/* 建模覆盖映射                                                        */
/* ------------------------------------------------------------------ */

/**
 * logical_id → 建模覆盖统计。后端保证每个可见数据集都有一行（无模型时三项均为 0），
 * 所以缺项补 0 只是类型兜底，不会把「没取到」渲染成「数据白躺」。
 */
const modelingMap = computed(
  () => new Map(props.data.modeling.map((item) => [item.logical_id, item])),
);

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI                                                 */
/* ------------------------------------------------------------------ */

/**
 * 工频合格率：按各数据集 `record_count` 加权的 `frequency_pass_rate` 平均。
 *
 * 为什么加权而不是直接取算术平均：电力场景里两个数据集的样本量可能差一个数量级
 * （如 1673 条 vs 340 条），不加权会让小数据集的合格率与大数据集等权，口径失真。
 * 分母（样本总量）为 0 时返回 null —— 显示「—」，不能写成 0%，那是「全部不合格」的假结论。
 */
const frequencyPassRate = computed<number | null>(() => {
  const rows = props.data.telemetry_by_dataset;
  const totalRecords = rows.reduce((sum, item) => sum + item.record_count, 0);
  if (!totalRecords) return null;
  const weighted = rows.reduce(
    (sum, item) => sum + item.record_count * item.frequency_pass_rate,
    0,
  );
  return weighted / totalRecords;
});

const kpis = computed<KpiItem[]>(() => [
  {
    label: '有效数据集数',
    value: props.data.dataset_count,
    unit: '个',
    tone: 'primary',
    sub: `含 ${props.data.dataset_file_count} 份文件`,
  },
  {
    label: '有效样本总量',
    value: props.data.sample_count,
    unit: '条',
    tone: 'primary',
    sub: '同源去重后的有效样本',
  },
  {
    label: '统一风险占比',
    value: fmtPercent(props.data.risk_rate),
    tone: 'warning',
    sub: '全场景合并口径',
    raw: true,
  },
  {
    label: '工频合格率',
    value: frequencyPassRate.value === null ? null : fmtPercent(frequencyPassRate.value),
    tone: 'success',
    sub: '49.8–50.2 Hz 区间占比',
    raw: true,
  },
]);

/* ------------------------------------------------------------------ */
/* D1 ★ 电参量基线一致性（跨数据集）                                    */
/* ------------------------------------------------------------------ */

const d1Columns: DashColumn[] = [
  { key: 'name', label: '数据集' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'voltage', label: '电压均值' },
  { key: 'current', label: '电流均值' },
  { key: 'temperature', label: '温度均值' },
  { key: 'frequency', label: '工频合格率', numeric: true, align: 'right' },
  { key: 'packet_loss', label: '遥测丢包率', numeric: true, align: 'right' },
  { key: 'verdict', label: '结论' },
];

/**
 * 电参量均值取值：按 key 从该数据集的 params 里找。
 *
 * 为什么返回 null 而不是 0：mean 为 null 的语义是「该数据集没有这个字段 / 无法计算」，
 * 写成 0 会被读成「实测均值为 0」，是完全相反的管理结论。null 交给 DashTable 渲染成「—」。
 */
const meanText = (row: TelemetryByDataset, key: string): string | null => {
  const param = row.params.find((item) => item.key === key);
  if (!param || param.mean === null) return null;
  return param.unit ? `${fmtNum(param.mean)} ${param.unit}` : fmtNum(param.mean);
};

/** 结论：基线全部达标给绿标；否则把越界项逐条列出并标红 —— 管理端要看到具体越界在哪一项 */
const verdictOf = (row: TelemetryByDataset): { text: string; tone: 'ok' | 'up' } =>
  row.baseline_ok
    ? { text: '达标', tone: 'ok' }
    : { text: row.violations.join('、') || '基线越界', tone: 'up' };

const d1Rows = computed<Array<Record<string, unknown>>>(() =>
  props.data.telemetry_by_dataset.map((item) => ({
    logical_id: item.logical_id,
    name: nameOf(item.logical_id, item.name),
    record_count: item.record_count,
    voltage: meanText(item, PARAM_KEYS.voltage),
    current: meanText(item, PARAM_KEYS.current),
    temperature: meanText(item, PARAM_KEYS.temperature),
    frequency: fmtPercent(item.frequency_pass_rate),
    packet_loss:
      item.packet_loss_mean === null ? null : `${fmtNum(item.packet_loss_mean)} %`,
    verdict: verdictOf(item),
  })),
);

/* ------------------------------------------------------------------ */
/* D2 ★ 设备 × 系统 覆盖矩阵                                           */
/* ------------------------------------------------------------------ */

const d2Columns: DashColumn[] = [
  { key: 'value', label: '设备/系统' },
  { key: 'kind', label: '类型' },
  { key: 'coverage', label: '覆盖数据集' },
  { key: 'dataset_count', label: '覆盖数', numeric: true, align: 'right' },
];

const d2Rows = computed<Array<Record<string, unknown>>>(() =>
  props.data.component_matrix.map((item) => ({
    value: item.value,
    kind: item.kind === 'system' ? '系统' : '设备',
    coverage: item.counts
      .map((entry) => `${nameOf(entry.logical_id)}(${entry.count} 条, ${fmtPercent(entry.risk_rate)})`)
      .join('、'),
    dataset_count: item.counts.length,
  })),
);

/* ------------------------------------------------------------------ */
/* S2 数据集资产明细 / S3 建模覆盖                                      */
/* ------------------------------------------------------------------ */

const s2Columns: DashColumn[] = [
  { key: 'name', label: '数据集名' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'label_field', label: '标签字段' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'visibility', label: '可见性' },
  { key: 'model_count', label: '已发布模型数' },
  { key: 'version', label: '版本', numeric: true, align: 'right' },
];

/**
 * 数据集基底行：`props.data.datasets` 只在这一处遍历，S2 明细表与 S3 建模覆盖都从它派生
 * （原先 S2、S3 各自 map 一遍 datasets，并各自去 modelingMap 里查一次模型数）。
 * 字段 = S2 的表格单元格 + S3 需要的模型版本三元组 `models`。
 */
const datasetRows = computed(() =>
  props.data.datasets.map((item) => {
    const stat = modelingMap.value.get(item.logical_id);
    return {
      logical_id: item.logical_id,
      name: nameOf(item.logical_id, item.name),
      record_count: item.record_count,
      label_field: item.label_field,
      risk_rate: fmtPercent(item.risk_rate),
      attribute_count: item.attribute_count,
      visibility: VISIBILITY_TEXT[item.visibility] ?? item.visibility,
      // 未登记风险口径 = 该数据集的标签没有进显式登记表 → 不产生风险事件，必须让管理员看见
      unregistered: item.caliber_registered === false,
      model_count: `已发布 ${stat?.published ?? 0} / 共 ${stat?.total ?? 0}`,
      version: `v${item.version}`,
      // S3 用：该数据集的模型版本三元组（无模型时三项均为 0 = 数据白躺）
      models: {
        published: stat?.published ?? 0,
        draft: stat?.draft ?? 0,
        total: stat?.total ?? 0,
      },
    };
  }),
);

/**
 * 建模覆盖柱状图：每数据集一根柱 = 该数据集的模型版本总数。
 *
 * DashBars 只渲染 `count`（value2 不生效），所以「已发布 / 草稿」只能写进标签文本。
 */
const modelingBars = computed(() =>
  datasetRows.value.map((row) => ({
    value: `${row.name}（已发布 ${row.models.published} / 草稿 ${row.models.draft}）`,
    count: row.models.total,
  })),
);

/** total === 0 的数据集 = 数据白躺（有数据但一个模型版本都没有） */
const idleDatasets = computed(() =>
  datasetRows.value.filter((row) => row.models.total === 0).map((row) => row.name),
);

/* ------------------------------------------------------------------ */
/* S4 场景运行态水位 / S5 场景成员与权限                                */
/* ------------------------------------------------------------------ */

const runtime = ref<PowerWorkspace | null>(null);
/** 场景成员；null = 未取到（与「确实 0 人」区分开） */
const members = ref<UserAccount[] | null>(null);

/**
 * 两个接口并行、各自静默降级：运行态失败不影响成员块，反之亦然，都不阻塞主画像。
 * 场景画像本身由父组件传入（props.data），所以这里只有两个请求。
 * 成员显式传 `scenario_id`（后端仅对 SCENARIO_ADMIN 自动收窄，SUPER_ADMIN 需自行传参）。
 */
const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getUserList({ scenario_id: scenarioId, page_size: 200 }),
  ]);

  runtime.value =
    runtimeResult.status === 'fulfilled' && runtimeResult.value.scenario_key === SCENARIO_KEY
      ? (runtimeResult.value as PowerWorkspace)
      : null;
  members.value =
    memberResult.status === 'fulfilled'
      ? memberResult.value.items.filter((item) => item.scenario_id === scenarioId)
      : null;
};

watch(() => props.data.scenario_id, loadAll);
onMounted(loadAll);

const summary = computed(() => runtime.value?.summary ?? null);

/** 近 10 天活动 = activity_trend 的 total 求和（每天一次推理批次） */
const activityTotal = computed(() =>
  (runtime.value?.activity_trend ?? []).reduce((sum, point) => sum + point.total, 0),
);

const runtimeKpis = computed<KpiItem[]>(() => {
  const item = summary.value;
  return [
    {
      label: '待处置积压',
      value: item ? item.pending : null,
      unit: '条',
      tone: 'danger',
      sub: '全场景待处置风险事件',
    },
    {
      label: '已处置率',
      // total 为 0 时没有分母，显示「—」而不是 0%（0% 会被读成「一件都没处置」）
      value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
      tone: 'success',
      sub: '已处置 / 全场景事件',
      raw: true,
    },
    {
      label: '近 10 天活动',
      value: item ? activityTotal.value : null,
      unit: '次',
      tone: 'primary',
      sub: '按天统计的推理量合计',
    },
  ];
});

/** 处置漏斗：待处置 → 处理中 → 已处置 */
const funnelItems = computed(() =>
  (summary.value?.status_funnel ?? []).map((item) => ({ label: item.label, count: item.count })),
);

/** 近 10 天活动趋势：推理量 / 其中判定为风险的量（不渲染 recent_events，那是执行端派活清单） */
const trendPoints = computed(() =>
  (runtime.value?.activity_trend ?? []).map((item) => ({
    label: fmtDate(item.date),
    value: item.total,
    value2: item.risk,
  })),
);

/** 场景成员：按角色分组计数，管理员需要知道这个场景里有哪些人、权限怎么分 */
const memberRows = computed(() => {
  const list = members.value;
  if (list === null) return [];
  const adminCount = list.filter((item) => item.role === 'SCENARIO_ADMIN').length;
  const userCount = list.filter((item) => item.role === 'SCENARIO_USER').length;
  const disabledCount = list.filter((item) => item.status !== 'active').length;
  const rows = [
    { label: '场景管理员', value: `${adminCount} 人` },
    { label: '场景用户', value: `${userCount} 人` },
    { label: '合计', value: `${list.length} 人` },
  ];
  if (disabledCount) rows.push({ label: '已禁用', value: `${disabledCount} 人` });
  return rows;
});
</script>

<template>
  <!-- S1 场景资产总览 KPI ×4（前 3 个四场景一致，第 4 个为电力特色） -->
  <DashKpis :items="kpis" />

  <!-- D1 ★ 电参量基线一致性（跨数据集） -->
  <DashCard title="电参量基线一致性（跨数据集）" :source="BASELINE_SOURCE">
    <DashTable :columns="d1Columns" :rows="d1Rows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 ★ 设备 × 系统 覆盖矩阵 -->
  <DashCard
    title="设备 × 系统 覆盖矩阵"
    source="按设备/系统 × 数据集统计样本量与风险占比；括号内为样本量与风险占比"
  >
    <DashTable :columns="d2Columns" :rows="d2Rows" row-key="value" dense />
  </DashCard>

  <!-- S2 数据集资产明细 -->
  <DashCard
    title="数据集资产明细"
    source="按数据集逐行列出资产口径；标注「未登记风险口径」的数据集不产生风险事件"
  >
    <DashTable :columns="s2Columns" :rows="datasetRows" row-key="logical_id">
      <template #label_field="{ row }">
        <span>{{ row.label_field }}</span>
        <span v-if="row.unregistered" class="d-tag d-tag--warn" style="margin-left: 6px">
          未登记风险口径
        </span>
      </template>
    </DashTable>
  </DashCard>

  <!-- S3 建模覆盖 -->
  <DashCard title="建模覆盖" source="每根柱 = 该数据集的模型版本总数；标注已发布 / 草稿">
    <DashBars :items="modelingBars" :label-width="320" suffix=" 个版本" />
    <p v-if="idleDatasets.length" style="margin: 10px 0 0; font-size: 11.5px; line-height: 1.7">
      <span class="d-tag d-tag--warn">数据白躺 {{ idleDatasets.length }} 份</span>
      <span style="margin-left: 6px">{{ idleDatasets.join('、') }}</span>
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
  <DashCard title="场景成员与权限" source="按账号角色统计，范围限本场景">
    <DashRows :rows="memberRows" />
  </DashCard>
</template>
