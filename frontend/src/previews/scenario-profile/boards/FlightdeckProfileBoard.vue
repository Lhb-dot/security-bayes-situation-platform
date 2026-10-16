<script setup lang="ts">
/**
 * FlightdeckProfileBoard —— 舰面调度态势 · 场景管理员首页看板（纯展示）。
 * 取数在 sections/ProfileFlightdeck.vue（/profile 由父组件传入，/workspace 与 /users 本页另取）。
 *
 * 视角：**管理端看数据资产与治理，不是执行端看飞行态势**。与场景用户「我的工作台」的分工：
 *   用户侧 ＝ 我手上的活（双机方向角雷达、最小间距分布、最近告警）；
 *   管理侧 ＝ 这批数据能不能用（是否存在内容重复的文件、正类口径一致吗、哪份数据白躺没人建模）。
 * 因此本页不渲染任何研判图（间距曲线、方向角雷达、接近率、碰撞对比、总航程等）。
 *
 * 可空口径：`modeling` / `redundancy` / `caliber_registered` 是契约必填字段，后端无条件下发，
 * 故不做「旧后端未上线」的兜底分支；需要降级的是另一个请求的运行态 runtime 与成员 members。
 */
import { computed } from 'vue';
import type { FlightdeckProfile, WorkspaceBase } from '@/api/dashboardApi';
import type { UserAccount } from '@/types/security';
import { fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';
import CockpitPanel from '../CockpitPanel.vue';
import CockpitKpis from '../CockpitKpis.vue';
import type { CockpitKpi } from '../CockpitKpis.vue';
import CockpitBars from '../CockpitBars.vue';
import CockpitColumns from '../CockpitColumns.vue';
import CockpitMatrix from '../CockpitMatrix.vue';
import type { CockpitColumn } from '../CockpitMatrix.vue';
import CockpitRows from '../CockpitRows.vue';
import type { CockpitRow } from '../CockpitRows.vue';
import CockpitStack from '../CockpitStack.vue';
import CockpitTrend from '../CockpitTrend.vue';
import CockpitDonut from '../CockpitDonut.vue';
import { labelKindText, percentText, visibilityText } from '../profileTokens';

const props = defineProps<{
  data: FlightdeckProfile;
  /** 运行态（/workspace）；本看板只读 summary / activity_trend 这两个四场景同构字段 */
  runtime: WorkspaceBase | null;
  members: UserAccount[] | null;
  memberTotal?: number | null;
}>();

/* ------------------------------------------------------------------ */
/* 口径常量                                                            */
/* ------------------------------------------------------------------ */

const MEMBER_PAGE_SIZE = 200;

/** 编码形态中文映射（numeric / interval / paired / unknown） */
const ENCODING_TEXT: Record<string, string> = {
  numeric: '数值连续',
  interval: '离散区间',
  paired: '配对轨迹',
  unknown: '未知',
};

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI ×4                                              */
/* ------------------------------------------------------------------ */

/**
 * 冗余度直接取画像顶层 `redundancy`（后端按 1 - 有效分组数 / 文件数 算好下发）。
 * 前端不再按 dataset_file_count / dataset_count 现算一遍：那是同一个公式的第二份实现，
 * 只会在两边口径漂移时给出两个数。
 */
const assetKpis = computed<CockpitKpi[]>(() => {
  const stat = props.data.redundancy;
  return [
    {
      label: '有效数据集数',
      value: props.data.dataset_count,
      unit: '个',
      tone: 'primary',
      icon: 'data',
      sub: `含 ${stat.file_count} 份文件`,
    },
    {
      label: '有效样本总量',
      value: props.data.sample_count,
      unit: '条',
      tone: 'success',
      icon: 'layers',
      sub: '内容完全相同的文件已去重',
    },
    {
      label: '统一风险占比',
      value: fmtPercent(props.data.risk_rate),
      tone: 'warning',
      icon: 'alert',
      sub: `风险样本 ${fmtInt(props.data.risk_count)} 条 / 全部样本`,
    },
    {
      label: '重复内容冗余率',
      value: fmtPercent(stat.redundancy_rate),
      tone: 'purple',
      icon: 'matrix',
      sub: `${stat.file_count} 份文件 → ${stat.effective_group_count} 个有效数据集`,
    },
  ];
});

/* ------------------------------------------------------------------ */
/* 01 数据集资产                                                        */
/* ------------------------------------------------------------------ */

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
    { label: '标签类型', value: labelKindText(item.label_kind) },
    {
      label: '风险口径登记',
      value: item.caliber_registered ? '已登记' : '未登记·不产事件',
      tone: item.caliber_registered ? 'success' : 'warning',
    },
    { label: '可见性', value: visibilityText(item.visibility) },
    { label: '上传者角色', value: item.uploader_role ?? '—' },
    { label: '物理文件数', value: props.data.redundancy.file_count },
  ];
});

/* ------------------------------------------------------------------ */
/* 02 ★ 编码形态与分组治理表                                            */
/* ------------------------------------------------------------------ */

/**
 * 内容分组 → 可读组名。后端 `source_group` 是内容指纹（"{size}-{sha1前16位}"），
 * 直接上屏读者看不懂；这里按 groups[] 顺序编号并带上成员数：
 * 「内容分组」列取到相同值的行，就是内容完全相同的重复注册文件 —— 这正是本表要传达的信息。
 * `groups[].group_id` 与 `groups[].fingerprint` 是同一个值，故只需登记一个键。
 */
const groupLabels = computed(() => {
  const map = new Map<string, string>();
  props.data.groups.forEach((group, index) => {
    map.set(group.group_id, `G${index + 1} · ${group.file_count} 份`);
  });
  return map;
});

const familyColumns: CockpitColumn[] = [
  { key: 'name', label: '数据集', ellipsis: true, ellipsisWidth: 130 },
  { key: 'source_group', label: '内容分组' },
  { key: 'encoding', label: '编码形态' },
  { key: 'risk_count', label: '正类数', numeric: true, align: 'right' },
  { key: 'collision_consistent', label: '正类一致性' },
];

/** 正类一致性：与分组代表的正类数相同才算一致，不一致标红（管理告警） */
const familyRows = computed(() =>
  props.data.encoding_family.map((row) => ({
    logical_id: row.logical_id,
    name: row.logical_id,
    source_group: groupLabels.value.get(row.source_group) ?? row.source_group,
    encoding: ENCODING_TEXT[row.encoding] ?? '未知',
    risk_count: row.risk_count,
    collision_consistent: row.collision_consistent
      ? { text: '一致', tone: 'ok' as const }
      : { text: '不一致', tone: 'up' as const },
  })),
);

/* ------------------------------------------------------------------ */
/* 03 建模覆盖                                                          */
/* ------------------------------------------------------------------ */

const modelStats = computed(() => {
  const map = new Map<string, { published: number; total: number }>();
  props.data.modeling.forEach((item) => map.set(item.logical_id, { published: item.published, total: item.total }));
  return map;
});

const modelingBars = computed(() =>
  props.data.datasets.map((item) => ({
    label: item.logical_id,
    value: modelStats.value.get(item.logical_id)?.total ?? 0,
    suffix: ' 个版本',
  })),
);

const modelTotals = computed(() =>
  props.data.modeling.reduce(
    (acc, item) => ({ published: acc.published + item.published, draft: acc.draft + item.draft }),
    { published: 0, draft: 0 },
  ),
);

const idleNames = computed(() =>
  props.data.datasets.filter((item) => (modelStats.value.get(item.logical_id)?.total ?? 0) === 0).map((item) => item.logical_id),
);

const modelKpis = computed<CockpitKpi[]>(() => [
  { label: '已发布合计', value: modelTotals.value.published, unit: '个', tone: 'success' },
  { label: '草稿合计', value: modelTotals.value.draft, unit: '个', tone: 'primary' },
  { label: '数据白躺', value: idleNames.value.length, unit: '份', tone: 'warning' },
]);

/* ------------------------------------------------------------------ */
/* 04 场景运行态势                                                      */
/* ------------------------------------------------------------------ */

const summary = computed(() => props.runtime?.summary ?? null);

const activityTotal = computed(() =>
  props.runtime ? props.runtime.activity_trend.reduce((sum, point) => sum + Number(point.total ?? 0), 0) : null,
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
/* 05 ★ 重复内容冗余度与去重收益                                        */
/* ------------------------------------------------------------------ */

const redundancy = computed(() => props.data.redundancy);

/** 被去重吸收掉的数据集数 = 文件数 - 有效数据集数（多出来的都是重复入模风险） */
const absorbedCount = computed(() => Math.max(redundancy.value.file_count - redundancy.value.effective_group_count, 0));

/** 去重前后样本量对比（两柱）；冗余率本身已是 S1 第 4 个 KPI，此处不重复 */
const dedupColumns = computed(() => [
  { label: '去重前样本', value: redundancy.value.raw_samples, tone: 'danger' as const },
  { label: '去重后样本', value: redundancy.value.deduped_samples, tone: 'success' as const },
]);

const dedupRows = computed<CockpitRow[]>(() => [
  { label: '物理文件数', value: redundancy.value.file_count },
  { label: '有效内容分组', value: redundancy.value.effective_group_count },
  { label: '被吸收数据集数', value: absorbedCount.value, tone: absorbedCount.value ? 'warning' : undefined },
  { label: '重复内容冗余率', value: fmtPercent(redundancy.value.redundancy_rate) },
]);

/** 每个内容分组的成员数据集名（进脚注：条形图放不下长标签，但「哪几份文件重复」必须能查到） */
const groupNames = computed(() =>
  props.data.groups.map((group, index) => `G${index + 1}=${group.datasets.join(' / ')}`).join('；'),
);

/* ------------------------------------------------------------------ */
/* 06 可见性与场景成员                                                  */
/* ------------------------------------------------------------------ */

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

<template>
  <CockpitKpis :items="assetKpis" />

  <div class="pf-board">
    <!-- 01 数据集资产 -->
    <CockpitPanel index="01" title="数据集资产" hint="本场景唯一数据源" align="top" foot="单数据集场景：资产口径逐项铺开，标签口径与登记状态在此一次说清">
      <CockpitRows :rows="datasetRows" :columns="2" />
    </CockpitPanel>

    <!-- 02 ★ 编码形态与分组治理表 -->
    <CockpitPanel
      index="02"
      title="编码形态与分组治理表"
      hint="按文件内容指纹分组"
      align="top"
      foot="内容分组相同的行即内容完全相同的重复注册文件；正类不一致说明同组内至少有一份数据的标签口径有问题"
    >
      <CockpitMatrix :columns="familyColumns" :rows="familyRows" row-key="logical_id" />
    </CockpitPanel>

    <!-- 03 建模覆盖 -->
    <CockpitPanel
      index="03"
      title="建模覆盖"
      hint="每数据集模型版本数"
      align="top"
      :foot="idleNames.length ? `数据白躺 ${idleNames.length} 份：${idleNames.join('、')}` : '全部数据集均已有模型版本'"
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

    <!-- 05 ★ 重复内容冗余度与去重收益 -->
    <CockpitPanel
      index="05"
      title="重复内容冗余度与去重收益"
      hint="去重前 / 去重后"
      align="top"
      :foot="groupNames ? `内容分组：${groupNames}` : '暂无内容分组'"
    >
      <CockpitColumns :items="dedupColumns" unit=" 条" />
      <CockpitRows :rows="dedupRows" :columns="2" />
    </CockpitPanel>

    <!-- 06 可见性与场景成员 -->
    <CockpitPanel index="06" title="数据集可见性与场景成员" hint="范围限本场景" align="top" foot="成员按账号角色分组计数；可见性为数据集注册时的共享范围">
      <CockpitDonut :items="visibilityItems" center-label="数据集" :percent="false" suffix=" 个" />
      <p v-if="members === null" class="pf-empty">成员数据未取到</p>
      <CockpitRows v-else :rows="memberRows" :columns="2" />
    </CockpitPanel>
  </div>
</template>
