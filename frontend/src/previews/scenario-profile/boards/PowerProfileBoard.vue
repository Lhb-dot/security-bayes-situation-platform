<script setup lang="ts">
/**
 * PowerProfileBoard —— 电力系统 · 场景管理员首页看板（纯展示）。
 * 取数在 sections/ProfilePower.vue（/profile 由父组件传入，/workspace 与 /users 本页另取）。
 *
 * 视角：**管理端看资源与流程，不是执行端看任务**。与场景用户「我的工作台」的分工：
 *   用户侧 ＝ 我手上的活（电参量 gauge、设备告警排行、问题类型构成、最近告警）；
 *   管理侧 ＝ 这个场景健康吗（跨数据集的电参量基线是否一致、设备/系统被哪些数据覆盖、
 *             数据集有没有被建模、处置流程积压多少、这个场景有哪些人）。
 * 因此本页不出现任何 gauge、告警排行、问题类型构成 —— 那是执行端研判图。
 *
 * 可空口径：`telemetry_by_dataset` / `component_matrix` / `modeling` 都是必填字段
 * （dashboardApi.ts 未标可选、后端 get_profile 恒返回），故不做「字段没下发」的空数组兜底 ——
 * 那种兜底会把「没取到」误渲染成「0 个模型 → 数据白躺」的假告警。真正需要降级的是
 * **另一个请求**的数据：运行态 runtime 与成员 members，失败时保持 null，各块显示「—」。
 */
import { computed } from 'vue';
import type { PowerProfile, TelemetryByDataset, WorkspaceBase } from '@/api/dashboardApi';
import type { UserAccount } from '@/types/security';
import { fmtInt, fmtNum, fmtPercent } from '@/components/dashboard/dashFormat';
import CockpitPanel from '../CockpitPanel.vue';
import CockpitKpis from '../CockpitKpis.vue';
import type { CockpitKpi } from '../CockpitKpis.vue';
import CockpitBars from '../CockpitBars.vue';
import CockpitMatrix from '../CockpitMatrix.vue';
import type { CockpitColumn } from '../CockpitMatrix.vue';
import CockpitRows from '../CockpitRows.vue';
import type { CockpitRow } from '../CockpitRows.vue';
import CockpitStack from '../CockpitStack.vue';
import CockpitTrend from '../CockpitTrend.vue';
import CockpitDonut from '../CockpitDonut.vue';
import { percentText } from '../profileTokens';

const props = defineProps<{
  data: PowerProfile;
  /** 运行态（/workspace）；本看板只读 summary / activity_trend 这两个四场景同构字段 */
  runtime: WorkspaceBase | null;
  members: UserAccount[] | null;
  memberTotal?: number | null;
}>();

/* ------------------------------------------------------------------ */
/* 口径常量                                                            */
/* ------------------------------------------------------------------ */

const MEMBER_PAGE_SIZE = 200;
const VISIBILITY_TEXT: Record<string, string> = { platform: '平台', company: '公司', personal: '个人' };

/** D1 三个电参量列 → 后端 `telemetry_by_dataset[].params[].key`（与后端 POWER_PARAMS 一致） */
const PARAM_KEYS = {
  voltage: 'VoltageLevel_kV',
  current: 'CurrentAmp',
  temperature: 'Temperature_C',
} as const;

/** D1 卡片脚注的基线口径：与后端 POWER_BASELINE 逐项一致 */
const BASELINE_SOURCE =
  '电力基线：电压 300–700 kV · 电流 400–1600 A · 温度 30–90 ℃ · 工频 49.8–50.2 Hz · 丢包 ≤1%';

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI ×4                                              */
/* ------------------------------------------------------------------ */

/**
 * 工频合格率：按各数据集 `record_count` 加权的 `frequency_pass_rate` 平均。
 * 电力场景里两个数据集的样本量可能差一个数量级，不加权会让小数据集与大数据集等权，口径失真。
 * 分母（样本总量）为 0 时返回 null —— 显示「—」，不能写成 0%（那是「全部不合格」的假结论）。
 */
const frequencyPassRate = computed<number | null>(() => {
  const rows = props.data.telemetry_by_dataset;
  const totalRecords = rows.reduce((sum, item) => sum + item.record_count, 0);
  if (!totalRecords) return null;
  const weighted = rows.reduce((sum, item) => sum + item.record_count * item.frequency_pass_rate, 0);
  return weighted / totalRecords;
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
  { label: '统一风险占比', value: fmtPercent(props.data.risk_rate), tone: 'warning', icon: 'alert', sub: '全场景合并口径' },
  {
    label: '工频合格率',
    value: frequencyPassRate.value === null ? null : fmtPercent(frequencyPassRate.value),
    tone: 'purple',
    icon: 'trend',
    sub: '49.8–50.2 Hz 区间占比 · 按样本量加权',
  },
]);

/* ------------------------------------------------------------------ */
/* 01 数据集资产                                                        */
/* ------------------------------------------------------------------ */

/** 单数据集场景用键值行把资产口径铺开（表格只有一行时信息密度过低） */
const datasetRows = computed<CockpitRow[]>(() => {
  const list = props.data.datasets;
  if (!list.length) return [];
  const item = list[0];
  return [
    { label: '数据集', value: `${item.logical_id}（v${item.version}）` },
    { label: '样本量', value: fmtInt(item.record_count) },
    { label: '风险样本 / 占比', value: `${fmtInt(item.risk_count)} · ${fmtPercent(item.risk_rate)}` },
    { label: '字段数', value: item.attribute_count },
    { label: '标签字段', value: item.label_field },
    { label: '标签类型', value: item.label_kind },
    {
      label: '风险口径登记',
      value: item.caliber_registered ? '已登记' : '未登记·不产事件',
      tone: item.caliber_registered ? 'success' : 'warning',
    },
    { label: '可见性', value: VISIBILITY_TEXT[item.visibility] ?? item.visibility },
    { label: '上传者角色', value: item.uploader_role ?? '—' },
    { label: '数据集文件数', value: props.data.dataset_file_count },
  ];
});

/* ------------------------------------------------------------------ */
/* 02 ★ 电参量基线一致性（跨数据集）                                    */
/* ------------------------------------------------------------------ */

/**
 * 电参量均值取值：按 key 从该数据集的 params 里找。
 * mean 为 null 的语义是「该数据集没有这个字段 / 无法计算」，写成 0 会被读成
 * 「实测均值为 0」，是完全相反的管理结论 —— 交给单元格渲染「—」。
 */
const meanText = (row: TelemetryByDataset, key: string): string | null => {
  const param = row.params.find((item) => item.key === key);
  if (!param || param.mean === null) return null;
  return param.unit ? `${fmtNum(param.mean)} ${param.unit}` : fmtNum(param.mean);
};

/** 结论：基线全部达标给绿标；否则把越界项逐条列出并标红 —— 管理端要看到具体越界在哪一项 */
const verdictOf = (row: TelemetryByDataset) =>
  row.baseline_ok
    ? { text: '达标', tone: 'ok' as const }
    : { text: row.violations.join('、') || '基线越界', tone: 'up' as const };

const telemetryColumns: CockpitColumn[] = [
  { key: 'name', label: '数据集', ellipsis: true, ellipsisWidth: 118 },
  { key: 'voltage', label: '电压均值' },
  { key: 'current', label: '电流均值' },
  { key: 'temperature', label: '温度均值' },
  { key: 'frequency', label: '工频合格率', numeric: true, align: 'right' },
  { key: 'packet_loss', label: '遥测丢包率', numeric: true, align: 'right' },
  { key: 'verdict', label: '结论' },
];

const telemetryRows = computed(() =>
  props.data.telemetry_by_dataset.map((item) => ({
    logical_id: item.logical_id,
    name: item.logical_id,
    voltage: meanText(item, PARAM_KEYS.voltage),
    current: meanText(item, PARAM_KEYS.current),
    temperature: meanText(item, PARAM_KEYS.temperature),
    frequency: fmtPercent(item.frequency_pass_rate),
    packet_loss: item.packet_loss_mean === null ? null : `${fmtNum(item.packet_loss_mean)} %`,
    verdict: verdictOf(item),
  })),
);

/* ------------------------------------------------------------------ */
/* 03 建模覆盖                                                          */
/* ------------------------------------------------------------------ */

const modelingBars = computed(() =>
  props.data.modeling.map((item) => ({ label: item.logical_id, value: item.total, suffix: ' 个版本' })),
);

const modelTotals = computed(() =>
  props.data.modeling.reduce(
    (acc, item) => ({ published: acc.published + item.published, draft: acc.draft + item.draft }),
    { published: 0, draft: 0 },
  ),
);

const idleDatasets = computed(() => props.data.modeling.filter((item) => item.total === 0).map((item) => item.logical_id));

const modelKpis = computed<CockpitKpi[]>(() => [
  { label: '已发布合计', value: modelTotals.value.published, unit: '个', tone: 'success' },
  { label: '草稿合计', value: modelTotals.value.draft, unit: '个', tone: 'primary' },
  { label: '数据白躺', value: idleDatasets.value.length, unit: '份', tone: 'warning' },
]);

/* ------------------------------------------------------------------ */
/* 04 场景运行态势                                                      */
/* ------------------------------------------------------------------ */

const summary = computed(() => props.runtime?.summary ?? null);

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

/* ------------------------------------------------------------------ */
/* 05 ★ 设备 × 系统 覆盖矩阵                                            */
/* ------------------------------------------------------------------ */

/**
 * 管理端的第二问：设备与系统到底被哪些数据集覆盖？
 * 覆盖数 = 含该设备/系统的数据集数量；明细列出「数据集（样本数, 风险占比）」，
 * 让管理员直接看到同一台设备在不同数据源里的样本量与风险口径差异。
 */
const componentColumns: CockpitColumn[] = [
  { key: 'value', label: '设备 / 系统', ellipsis: true, ellipsisWidth: 120 },
  { key: 'kind', label: '类型' },
  { key: 'dataset_count', label: '覆盖数', numeric: true, align: 'right' },
  { key: 'coverage', label: '覆盖明细（数据集：样本数 · 风险占比）', ellipsis: true, ellipsisWidth: 300 },
];

const componentRows = computed(() =>
  props.data.component_matrix.map((item) => ({
    value: item.value,
    kind: item.kind === 'system' ? { text: '系统', tone: 'down' as const } : { text: '设备', tone: 'muted' as const },
    dataset_count: item.counts.length,
    coverage: item.counts
      .map((entry) => `${entry.logical_id}：${fmtInt(entry.count)} · ${fmtPercent(entry.risk_rate)}`)
      .join('；'),
  })),
);

/* ------------------------------------------------------------------ */
/* 06 可见性与场景成员                                                  */
/* ------------------------------------------------------------------ */

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

<template>
  <CockpitKpis :items="overviewKpis" />

  <div class="pf-board">
    <!-- 01 数据集资产 -->
    <CockpitPanel index="01" title="数据集资产" hint="本场景唯一数据源" align="top" foot="单数据集场景：资产口径逐项铺开，标签口径与登记状态在此一次说清">
      <CockpitRows :rows="datasetRows" :columns="2" />
    </CockpitPanel>

    <!-- 02 ★ 电参量基线一致性 -->
    <CockpitPanel
      index="02"
      title="电参量基线一致性（跨数据集）"
      hint="逐数据集 · 是否落在电力基线内"
      align="top"
      :foot="BASELINE_SOURCE"
    >
      <CockpitMatrix :columns="telemetryColumns" :rows="telemetryRows" row-key="logical_id" />
    </CockpitPanel>

    <!-- 03 建模覆盖 -->
    <CockpitPanel
      index="03"
      title="建模覆盖"
      hint="每数据集模型版本数"
      align="top"
      :foot="idleDatasets.length ? `数据白躺 ${idleDatasets.length} 份：${idleDatasets.join('、')}` : '全部数据集均已有模型版本'"
    >
      <CockpitKpis size="sm" :columns="3" :items="modelKpis" />
      <CockpitBars :items="modelingBars" :label-width="86" :value-width="56" />
    </CockpitPanel>

    <!-- 04 场景运行态势 -->
    <CockpitPanel index="04" title="场景运行态势" :hint="runtimeHint" align="top" foot="运行态为全场景口径（含所有用户），与数据资产的全量统计相互独立">
      <CockpitKpis size="sm" :columns="3" :items="runtimeKpis" />
      <template v-if="runtime">
        <CockpitStack :items="statusItems" />
        <CockpitTrend :points="trendPoints" name="推理" name2="判为风险" unit=" 次" />
      </template>
      <p v-else class="pf-empty">运行态数据未取到</p>
    </CockpitPanel>

    <!-- 05 ★ 设备 × 系统 覆盖矩阵 -->
    <CockpitPanel
      index="05"
      title="设备 × 系统 覆盖矩阵"
      hint="覆盖数 = 含该设备/系统的数据集数量"
      align="top"
      foot="同一台设备在不同数据源里的样本量与风险占比一并列出，便于判断跨数据集口径是否可直接合并"
    >
      <CockpitMatrix :columns="componentColumns" :rows="componentRows" row-key="value" />
    </CockpitPanel>

    <!-- 06 可见性与场景成员 -->
    <CockpitPanel index="06" title="数据集可见性与场景成员" hint="范围限本场景" align="top" foot="成员按账号角色分组计数；可见性为数据集注册时的共享范围">
      <CockpitDonut :items="visibilityItems" center-label="数据集" :percent="false" suffix=" 个" />
      <p v-if="members === null" class="pf-empty">成员数据未取到</p>
      <CockpitRows v-else :rows="memberRows" :columns="2" />
    </CockpitPanel>
  </div>
</template>
