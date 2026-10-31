<template>
  <!-- S1 场景资产总览 KPI ×4（前 3 个四场景一致，第 4 个为电力特色） -->
  <DashKpis :items="kpis" />

  <!-- D1 电参量基线一致性（跨数据集） -->
  <DashCard title="电参量基线一致性（跨数据集）" :source="BASELINE_SOURCE">
    <DashTable :columns="d1Columns" :rows="d1Rows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 设备 × 系统 覆盖矩阵 -->
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
<script setup lang="ts">
/**
 * 电力系统 · 场景管理员首页。看资源与流程：跨数据集的电参量基线、
 * 设备与系统的覆盖、建模情况、积压与人。执行端的 gauge 与告警排行不在此页。
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


const SCENARIO_KEY = 'power';

const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};

const PARAM_KEYS = {
  voltage: 'VoltageLevel_kV',
  current: 'CurrentAmp',
  temperature: 'Temperature_C',
} as const;

const BASELINE_SOURCE =
  '电力基线：电压 300–700 kV · 电流 400–1600 A · 温度 30–90 ℃ · 工频 49.8–50.2 Hz · 丢包 ≤1%';


const modelingMap = computed(
  () => new Map(props.data.modeling.map((item) => [item.logical_id, item])),
);


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
    sub: '内容重复文件去重后的有效样本',
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


/**
 * 本表只讲电参量基线（各参数均值 / 工频合格率 / 丢包率 / 结论），
 * 不复述样本量，那是「资产属性」，在 S2 资产明细里出现一次。同一粒度的信息全页只展示一次。
 */
const d1Columns: DashColumn[] = [
  { key: 'name', label: '数据集' },
  { key: 'voltage', label: '电压均值' },
  { key: 'current', label: '电流均值' },
  { key: 'temperature', label: '温度均值' },
  { key: 'frequency', label: '工频合格率', numeric: true, align: 'right' },
  { key: 'packet_loss', label: '遥测丢包率', numeric: true, align: 'right' },
  { key: 'verdict', label: '结论' },
];

const meanText = (row: TelemetryByDataset, key: string): string | null => {
  const param = row.params.find((item) => item.key === key);
  if (!param || param.mean === null) return null;
  return param.unit ? `${fmtNum(param.mean)} ${param.unit}` : fmtNum(param.mean);
};

const verdictOf = (row: TelemetryByDataset): { text: string; tone: 'ok' | 'up' } =>
  row.baseline_ok
    ? { text: '达标', tone: 'ok' }
    : { text: row.violations.join('、') || '基线越界', tone: 'up' };

const d1Rows = computed<Array<Record<string, unknown>>>(() =>
  props.data.telemetry_by_dataset.map((item) => ({
    logical_id: item.logical_id,
    name: item.logical_id,
    voltage: meanText(item, PARAM_KEYS.voltage),
    current: meanText(item, PARAM_KEYS.current),
    temperature: meanText(item, PARAM_KEYS.temperature),
    frequency: fmtPercent(item.frequency_pass_rate),
    packet_loss:
      item.packet_loss_mean === null ? null : `${fmtNum(item.packet_loss_mean)} %`,
    verdict: verdictOf(item),
  })),
);


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
      .map((entry) => `${entry.logical_id}(${entry.count} 条, ${fmtPercent(entry.risk_rate)})`)
      .join('、'),
    dataset_count: item.counts.length,
  })),
);


const s2Columns: DashColumn[] = [
  { key: 'name', label: '数据集名' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'label_field', label: '标签字段' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'visibility', label: '可见性' },
  { key: 'version', label: '版本', numeric: true, align: 'right' },
];

const datasetRows = computed(() =>
  props.data.datasets.map((item) => {
    const stat = modelingMap.value.get(item.logical_id);
    return {
      logical_id: item.logical_id,
      name: item.logical_id,
      record_count: item.record_count,
      label_field: item.label_field,
      risk_rate: fmtPercent(item.risk_rate),
      attribute_count: item.attribute_count,
      visibility: VISIBILITY_TEXT[item.visibility] ?? item.visibility,
      unregistered: item.caliber_registered === false,
      version: `v${item.version}`,
      models: {
        published: stat?.published ?? 0,
        draft: stat?.draft ?? 0,
        total: stat?.total ?? 0,
      },
    };
  }),
);

const modelingBars = computed(() =>
  datasetRows.value.map((row) => ({
    value: `${row.name}（已发布 ${row.models.published} / 草稿 ${row.models.draft}）`,
    count: row.models.total,
  })),
);

const idleDatasets = computed(() =>
  datasetRows.value.filter((row) => row.models.total === 0).map((row) => row.name),
);


const runtime = ref<PowerWorkspace | null>(null);
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

const funnelItems = computed(() =>
  (summary.value?.status_funnel ?? []).map((item) => ({ label: item.label, count: item.count })),
);

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
