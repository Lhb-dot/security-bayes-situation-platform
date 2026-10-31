<script setup lang="ts">
/**
 * 舰面调度 · 场景管理员首页。看数据资产与治理：文件是否重复、正类口径是否一致、
 * 哪份数据没有建模。执行端的雷达与间距分布不在此页。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type FlightdeckProfile,
  type FlightdeckWorkspace,
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
import type { DashColumn } from '@/components/dashboard/DashTable.vue';
import { fmtDate, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: FlightdeckProfile }>();


const MEMBER_PAGE_SIZE = 200;
const ROLE_SCENARIO_ADMIN = 'SCENARIO_ADMIN';
const ROLE_SCENARIO_USER = 'SCENARIO_USER';
const ACCOUNT_STATUS_ACTIVE = 'active';


const runtime = ref<FlightdeckWorkspace | null>(null);
const members = ref<UserAccount[] | null>(null);

const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getUserList({ scenario_id: scenarioId, page_size: MEMBER_PAGE_SIZE }),
  ]);

  runtime.value =
    runtimeResult.status === 'fulfilled' && runtimeResult.value.scenario_key === 'flight_deck'
      ? (runtimeResult.value as FlightdeckWorkspace)
      : null;
  members.value =
    memberResult.status === 'fulfilled'
      ? memberResult.value.items.filter((item) => item.scenario_id === scenarioId)
      : null;
};

watch(() => props.data.scenario_id, loadAll);
onMounted(loadAll);


const ENCODING_TEXT: Record<string, string> = {
  numeric: '数值连续',
  interval: '离散区间',
  paired: '配对轨迹',
  unknown: '未知',
};

const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};


const assetKpis = computed(() => {
  const stat = props.data.redundancy;
  return [
    {
      label: '有效数据集数',
      value: props.data.dataset_count,
      unit: '个',
      tone: 'primary' as const,
      sub: `含 ${props.data.dataset_file_count} 份文件`,
    },
    {
      label: '有效样本总量',
      value: props.data.sample_count,
      unit: '条',
      tone: 'success' as const,
      sub: '内容完全相同的文件已去重',
    },
    {
      label: '统一风险占比',
      value: fmtPercent(props.data.risk_rate),
      tone: 'danger' as const,
      raw: true,
      sub: `风险样本 ${props.data.risk_count} 条 / 全部样本`,
    },
    {
      label: '重复内容冗余率',
      value: fmtPercent(stat.redundancy_rate),
      tone: 'warning' as const,
      raw: true,
      sub: `${stat.file_count} 份文件 → ${stat.effective_group_count} 个有效数据集`,
    },
  ];
});


const groupLabels = computed(() => {
  const map = new Map<string, string>();
  props.data.groups.forEach((group, index) => {
    map.set(group.group_id, `G${index + 1} · ${group.file_count} 份`);
  });
  return map;
});

const familyColumns: DashColumn[] = [
  { key: 'name', label: '数据集' },
  { key: 'source_group', label: '内容分组' },
  { key: 'encoding', label: '编码形态' },
  { key: 'risk_count', label: '正类数', numeric: true, align: 'right' },
  { key: 'collision_consistent', label: '正类一致性' },
];

const familyRows = computed<Array<Record<string, unknown>>>(() =>
  props.data.encoding_family.map((row) => ({
    logical_id: row.logical_id,
    name: row.logical_id,
    source_group: groupLabels.value.get(row.source_group) ?? row.source_group,
    encoding: ENCODING_TEXT[row.encoding] ?? '未知',
    risk_count: row.risk_count,
    collision_consistent:
      row.collision_consistent === true
        ? { text: '一致', tone: 'ok' }
        : { text: '不一致', tone: 'up' },
  })),
);


const absorbedCount = computed(() => {
  const stat = props.data.redundancy;
  return Math.max(stat.file_count - stat.effective_group_count, 0);
});

const redundancyKpis = computed(() => {
  const stat = props.data.redundancy;
  return [
    {
      label: '去重前样本',
      value: stat.raw_samples,
      unit: '条',
      tone: 'danger' as const,
      sub: '按文件逐个求和',
    },
    {
      label: '去重后样本',
      value: stat.deduped_samples,
      unit: '条',
      tone: 'success' as const,
      sub: '分组代表求和',
    },
    {
      label: '被吸收数据集数',
      value: absorbedCount.value,
      unit: '个',
      tone: 'primary' as const,
      sub: '文件数 - 有效数据集数',
    },
  ];
});

const groupBars = computed(() =>
  props.data.groups.map((group) => ({
    value: group.datasets.join(' / '),
    count: group.file_count,
  })),
);


/**
 * 每数据集的模型版本数（published / total），直接取画像顶层 `modeling`
 * （契约 §4.1：一次聚合查询按 dataset_id 分组，无模型的数据集也在列并计 0）。
 */
const modelStats = computed(() => {
  const map = new Map<string, { published: number; total: number }>();
  props.data.modeling.forEach((item) =>
    map.set(item.logical_id, { published: item.published, total: item.total }),
  );
  return map;
});

/**
 * 数据集基底行：S2（资产明细）与 S3（建模覆盖）共用的唯一一次 datasets 遍历。
 * 模型覆盖在这里算一次，下游只做投影，避免同一份 datasets 被多个 computed 各扫一遍。
 */
const datasetRows = computed(() =>
  props.data.datasets.map((item) => ({
    item,
    name: item.logical_id,
    model: modelStats.value.get(item.logical_id),
  })),
);

const assetColumns: DashColumn[] = [
  { key: 'name', label: '数据集名' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'label_field', label: '标签字段' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'visibility', label: '可见性' },
  { key: 'version', label: '版本', align: 'right' },
];

const assetRows = computed<Array<Record<string, unknown>>>(() =>
  datasetRows.value.map(({ item, name }) => ({
    logical_id: item.logical_id,
    name,
    record_count: item.record_count,
    label_field: item.label_field,
    caliber_registered: item.caliber_registered,
    risk_rate: fmtPercent(item.risk_rate),
    attribute_count: item.attribute_count,
    visibility: VISIBILITY_TEXT[item.visibility] ?? item.visibility,
    version: `v${item.version}`,
  })),
);

const modelingBars = computed(() =>
  datasetRows.value.map(({ name, model }) => ({ value: name, count: model?.total ?? 0 })),
);

const idleNames = computed(() =>
  datasetRows.value.filter(({ model }) => (model?.total ?? 0) === 0).map(({ name }) => name),
);


const summary = computed(() => runtime.value?.summary ?? null);

const trendTotal = computed(() =>
  (runtime.value?.activity_trend ?? []).reduce((sum, point) => sum + Number(point.total ?? 0), 0),
);

const runtimeKpis = computed(() => {
  const item = summary.value;
  return [
    {
      label: '待处置积压',
      value: item ? item.pending : null,
      unit: '条',
      tone: 'danger' as const,
      sub: '全场景待处置风险事件',
    },
    {
      label: '已处置率',
      // 分母为 0 时不下结论，交给 DashKpis 渲染「—」
      value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
      tone: 'success' as const,
      raw: true,
      sub: '已处置 / 事件总数',
    },
    {
      label: '近 10 天活动',
      value: runtime.value ? trendTotal.value : null,
      unit: '次',
      tone: 'primary' as const,
      sub: '近 10 天风险推理调用合计',
    },
  ];
});

const funnelItems = computed(() =>
  (summary.value?.status_funnel ?? []).map((item) => ({ label: item.label, count: item.count })),
);

// 近 10 天活动趋势：推理量 / 其中判定为风险的量（日期统一走 dashFormat 的 MM-DD 口径）
const trendPoints = computed(() =>
  (runtime.value?.activity_trend ?? []).map((item) => ({
    label: fmtDate(item.date),
    value: item.total,
    value2: item.risk,
  })),
);


const memberRows = computed(() => {
  const list = members.value;
  if (list === null) return [];
  const admins = list.filter((item) => item.role === ROLE_SCENARIO_ADMIN);
  const users = list.filter((item) => item.role === ROLE_SCENARIO_USER);
  const disabled = list.filter((item) => item.status !== ACCOUNT_STATUS_ACTIVE);
  const rows: Array<{ label: string; value: string }> = [
    { label: '场景管理员', value: `${admins.length} 人` },
    { label: '场景用户', value: `${users.length} 人` },
    { label: '合计', value: `${list.length} 人` },
  ];
  if (disabled.length) {
    rows.push({ label: '已禁用账号', value: `${disabled.length} 人` });
  }
  return rows;
});
</script>

<template>
  <!-- S1 场景资产总览（前 3 项四场景一致，第 4 项为舰面调度特色：重复内容冗余率） -->
  <DashKpis :items="assetKpis" />

  <!-- D1 舰面调度特色块 1：编码形态与分组治理表 -->
  <DashCard
    title="编码形态与分组治理表"
    source="按文件内容指纹分组 · 内容完全相同的重复注册会被合并"
  >
    <DashTable :columns="familyColumns" :rows="familyRows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 舰面调度特色块 2：重复内容冗余度与去重收益 -->
  <DashCard
    title="重复内容冗余度与去重收益"
    source="冗余率 = 1 - 有效分组数 / 文件数；去重前按文件逐个求和，去重后按分组代表求和"
  >
    <DashKpis :items="redundancyKpis" />
    <div style="margin-top: 14px">
      <DashBars :items="groupBars" :label-width="320" suffix=" 份" />
    </div>
  </DashCard>

  <!-- S2 数据集资产明细 -->
  <DashCard
    title="数据集资产明细"
    source="可见性：平台 / 公司 / 个人；未登记风险口径的数据集不产风险事件，仍全量展示并标注"
  >
    <DashTable :columns="assetColumns" :rows="assetRows" row-key="logical_id" dense>
      <template #label_field="{ row }">
        <span>{{ row.label_field }}</span>
        <span
          v-if="row.caliber_registered === false"
          class="d-tag d-tag--warn"
          style="margin-left: 6px"
        >未登记风险口径</span>
      </template>
    </DashTable>
  </DashCard>

  <!-- S3 建模覆盖 -->
  <DashCard
    title="建模覆盖"
    source="每数据集一根柱 = 模型版本总数（含草稿）；为 0 表示该数据集尚无任何模型版本"
  >
    <DashBars :items="modelingBars" :label-width="250" suffix=" 个" />
    <p v-if="idleNames.length" style="margin: 10px 0 0; font-size: 11.5px; line-height: 1.7">
      <span class="d-tag d-tag--warn">数据白躺 {{ idleNames.length }} 份</span>
      <span style="margin-left: 6px">{{ idleNames.join('、') }}</span>
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
