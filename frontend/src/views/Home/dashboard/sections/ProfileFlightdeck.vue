<script setup lang="ts">
/**
 * ProfileFlightdeck —— 舰面调度 · 场景管理员首页（管理端）。
 * 字段口径见 docs/场景管理员首页审查/实施契约.md §7 / §8.3。
 *
 * 视角：**管理端看数据资产与治理，不是执行端看飞行态势**。与场景用户的「我的工作台」
 * （WorkspaceFlightdeck）的区别：
 *   用户侧 = 我手上的活：双机方向角雷达、最小间距分布、最近告警；
 *   管理侧 = 这批数据能不能用：同源文件是否重复入模、正类口径一致吗、哪份数据白躺没人建模。
 * 因此本页**不再渲染任何研判图**（间距曲线、方向角雷达、接近率、碰撞对比、总航程等），
 * 后端字段按契约 §5.3 仍然保留（向后兼容），只是本页不使用。
 *
 * 数据来源三段，作用域不同：
 *   /profile   数据资产全量统计（由父组件 AdminProfilePage 以 prop 传入，页面主骨架）；
 *   /workspace 运行态水位，范围由后端按角色收窄（场景管理员 self_only=false）；
 *   /users     场景成员，前端按 scenario_id 过滤；
 *   三者用 Promise.allSettled 并行，任一失败只影响它自己那一块，不阻塞整页。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type FlightdeckProfile,
  type FlightdeckWorkspace,
  type RedundancyStat,
} from '@/api/dashboardApi';
import { getModelVersionList, type BackendModelVersion } from '@/api/modelVersionApi';
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
import { fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: FlightdeckProfile }>();

/* ------------------------------------------------------------------ */
/* 运行态 / 模型 / 成员（额外接口，各自静默降级）                        */
/* ------------------------------------------------------------------ */

const runtime = ref<FlightdeckWorkspace | null>(null);
/** 场景内模型版本；null = 未取到（与「确实 0 个」区分开，避免误报「数据白躺」） */
const models = ref<BackendModelVersion[] | null>(null);
/** 场景成员；null = 未取到 */
const members = ref<UserAccount[] | null>(null);

/**
 * 三个接口并行、各自静默降级：任一失败只影响它自己那块，不阻塞主画像渲染。
 * 模型版本接口是 `modeling` 字段（后端任务 B 新增）未上线时的兜底数据源。
 */
const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, modelResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getModelVersionList({ scenario_id: scenarioId, page_size: 100 }),
    getUserList({ page_size: 200 }),
  ]);

  runtime.value =
    runtimeResult.status === 'fulfilled' && runtimeResult.value.scenario_key === 'flight_deck'
      ? (runtimeResult.value as FlightdeckWorkspace)
      : null;
  models.value = modelResult.status === 'fulfilled' ? modelResult.value : null;
  members.value =
    memberResult.status === 'fulfilled'
      ? memberResult.value.items.filter((item) => item.scenario_id === scenarioId)
      : null;
};

watch(() => props.data.scenario_id, loadAll);
onMounted(loadAll);

/* ------------------------------------------------------------------ */
/* 通用：展示名与中文映射                                               */
/* ------------------------------------------------------------------ */

/**
 * 数据集展示名去重。
 *
 * `dataset_display_name_of` 取的是上传文件名，同源重复的记录（如 carrier_track_company_v1
 * 与 Feature2_Cleaning_lisan 指向同一份内容）会得到**完全相同的展示名**，
 * 列表里就会出现多行一模一样的名字、看不出差别。重名时补上 logical_id 以区分。
 */
const displayNames = computed(() => {
  const list = props.data.datasets ?? [];
  const names = list.map((item) => item.name || item.logical_id);
  const counts = new Map<string, number>();
  names.forEach((name) => counts.set(name, (counts.get(name) ?? 0) + 1));
  const map = new Map<string, string>();
  list.forEach((item, index) => {
    const name = names[index];
    map.set(item.logical_id, (counts.get(name) ?? 0) > 1 ? `${name}（${item.logical_id}）` : name);
  });
  return map;
});

const nameOf = (logicalId: string) => displayNames.value.get(logicalId) ?? logicalId;

/** 编码形态中文映射（契约 §8.3：numeric/interval/paired/unknown） */
const ENCODING_TEXT: Record<string, string> = {
  numeric: '数值连续',
  interval: '离散区间',
  paired: '配对轨迹',
  unknown: '未知',
};

/** 数据集可见性中文映射（契约 §7） */
const VISIBILITY_TEXT: Record<string, string> = {
  platform: '平台',
  company: '公司',
  personal: '个人',
};

/* ------------------------------------------------------------------ */
/* S1 场景资产总览 KPI ×4                                              */
/* ------------------------------------------------------------------ */

/**
 * 同源冗余度兜底。
 *
 * `redundancy` 是后端任务 B 新增的顶层字段，若后端尚未上线，运行时它是 undefined，
 * 直接读 `data.redundancy.redundancy_rate` 会在渲染期抛错导致整页白屏。
 * 兜底口径不引入新算法，只是把契约 §5.3 的同一个公式用画像里已有的字段现算一遍：
 *   file_count           = dataset_file_count（物理文件数）
 *   effective_group_count= dataset_count（同源去重后的有效数据集数）
 *   redundancy_rate      = 1 - 有效数据集数 / 文件数
 */
const redundancy = computed<RedundancyStat>(() => {
  const raw = props.data.redundancy;
  if (raw) return raw;
  const fileCount = Number(props.data.dataset_file_count ?? 0);
  const groupCount = Number(props.data.dataset_count ?? 0);
  return {
    file_count: fileCount,
    effective_group_count: groupCount,
    redundancy_rate: fileCount > 0 ? 1 - groupCount / fileCount : 0,
    raw_samples: Number(props.data.sample_count ?? 0),
    deduped_samples: Number(props.data.sample_count ?? 0),
  };
});

/** S1：前 3 个四场景一致，第 4 个是舰面调度特色（同源冗余率） */
const assetKpis = computed(() => {
  const stat = redundancy.value;
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
      sub: '同源文件已按同源组去重',
    },
    {
      label: '统一风险占比',
      value: fmtPercent(props.data.risk_rate),
      tone: 'danger' as const,
      raw: true,
      sub: `风险样本 ${props.data.risk_count} 条 / 全部样本`,
    },
    {
      label: '同源冗余率',
      value: fmtPercent(stat.redundancy_rate),
      tone: 'warning' as const,
      raw: true,
      sub: `${stat.file_count} 份文件 → ${stat.effective_group_count} 个有效数据集`,
    },
  ];
});

/* ------------------------------------------------------------------ */
/* D1 ★ 同源编码族治理表                                               */
/* ------------------------------------------------------------------ */

/**
 * 同源组 → 可读组名。
 *
 * 后端 `source_group` 是内容指纹（"{size}-{sha1前16位}"）或显式同源族 ID，
 * 直接上屏读者看不懂。这里按 `groups[]` 顺序编号并带上成员数：
 * 「同源组」一列取到相同值的行，就是同一批样本的不同编码 —— 这正是本表要传达的信息。
 * `groups` 缺失时退回原始 key（至少保证同组同值，不丢信息）。
 */
const groupLabels = computed(() => {
  const map = new Map<string, string>();
  (props.data.groups ?? []).forEach((group, index) => {
    const size = Number(group.file_count ?? (group.datasets ?? []).length);
    const label = `G${index + 1} · ${size} 份`;
    if (group.group_id) map.set(group.group_id, label);
    if (group.fingerprint) map.set(group.fingerprint, label);
  });
  return map;
});

const familyColumns: DashColumn[] = [
  { key: 'name', label: '数据集' },
  { key: 'source_group', label: '同源组' },
  { key: 'encoding', label: '编码形态' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'risk_count', label: '正类数', numeric: true, align: 'right' },
  { key: 'collision_consistent', label: '正类一致性' },
  { key: 'published_model_count', label: '已发布模型数', numeric: true, align: 'right' },
];

/**
 * 同源编码族逐行对比。
 *
 * 管理端要回答的问题：同一批样本被注册成了几种编码？各自的正类数一致吗
 * （不一致说明同源组内至少有一份数据的标签口径有问题）？谁已经拿去建过模了
 * （同源组里只有代表份应该入模，多份入模等于把同一批样本重复喂给模型）。
 */
const familyRows = computed<Array<Record<string, unknown>>>(() =>
  (props.data.encoding_family ?? []).map((row) => ({
    logical_id: row.logical_id,
    name: nameOf(row.logical_id),
    source_group: groupLabels.value.get(row.source_group) ?? row.source_group ?? '—',
    encoding: ENCODING_TEXT[row.encoding] ?? '未知',
    attribute_count: row.attribute_count,
    record_count: row.record_count,
    risk_count: row.risk_count,
    // 正类一致性：与同源组代表的 risk_count 相同才算一致，不一致标红（管理告警）
    collision_consistent:
      row.collision_consistent === true
        ? { text: '一致', tone: 'ok' }
        : { text: '不一致', tone: 'up' },
    published_model_count: row.published_model_count,
  })),
);

/* ------------------------------------------------------------------ */
/* D2 ★ 同源冗余度与去重收益                                            */
/* ------------------------------------------------------------------ */

/** 被同源吸收掉的数据集数 = 文件数 - 有效数据集数（多出来的都是重复入模风险） */
const absorbedCount = computed(() =>
  Math.max(
    Number(redundancy.value.file_count ?? 0) - Number(redundancy.value.effective_group_count ?? 0),
    0,
  ),
);

const redundancyKpis = computed(() => {
  const stat = redundancy.value;
  return [
    {
      label: '同源冗余率',
      value: fmtPercent(stat.redundancy_rate),
      tone: 'warning' as const,
      raw: true,
      sub: '1 - 有效数据集数 / 文件数',
    },
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
      sub: '同源组代表求和',
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

/** 每个同源组一根柱 = 组内物理文件数；标签用组内展示名连接，便于核对是哪几份文件同源 */
const groupBars = computed(() =>
  (props.data.groups ?? []).map((group) => ({
    value: (group.datasets ?? []).map((id) => nameOf(id)).join(' / '),
    count: Number(group.file_count ?? (group.datasets ?? []).length),
  })),
);

/* ------------------------------------------------------------------ */
/* S2 数据集资产明细                                                    */
/* ------------------------------------------------------------------ */

/**
 * 每数据集的模型版本数（published / total）。
 *
 * 优先用画像的 `modeling`（契约 §4.1，一次查询按 dataset_id 分组，无模型的数据集也在列）；
 * 该字段是后端任务 B 新增的，未上线时退回模型版本接口在前端归集，保证「已发布模型数」列
 * 不会因为后端未合并而整列空白。两者都取不到时显示「—」，而不是假装 0（会误报未建模）。
 */
const modelingKnown = computed(() => Array.isArray(props.data.modeling) || models.value !== null);

const modelStats = computed(() => {
  const map = new Map<string, { published: number; total: number }>();
  if (Array.isArray(props.data.modeling)) {
    props.data.modeling.forEach((item) =>
      map.set(item.logical_id, { published: item.published, total: item.total }),
    );
    return map;
  }
  (models.value ?? []).forEach((model) => {
    const key = model.dataset_logical_id ?? String(model.dataset_id);
    const entry = map.get(key) ?? { published: 0, total: 0 };
    entry.total += 1;
    if (model.status === 'PUBLISHED') entry.published += 1;
    map.set(key, entry);
  });
  return map;
});

/** 已发布模型数单元格：`已发布 P / 共 T` */
const modelTextOf = (logicalId: string): string => {
  const stat = modelStats.value.get(logicalId);
  if (!stat) return '—';
  return `已发布 ${stat.published} / 共 ${stat.total}`;
};

const assetColumns: DashColumn[] = [
  { key: 'name', label: '数据集名' },
  { key: 'record_count', label: '样本量', numeric: true, align: 'right' },
  { key: 'label_field', label: '标签字段' },
  { key: 'risk_rate', label: '风险占比', numeric: true, align: 'right' },
  { key: 'attribute_count', label: '字段数', numeric: true, align: 'right' },
  { key: 'visibility', label: '可见性' },
  { key: 'model', label: '已发布模型数' },
  { key: 'version', label: '版本', align: 'right' },
];

/**
 * 数据集资产明细（四场景列结构完全一致）。
 *
 * 未登记风险口径的数据集**不隐藏**（契约 §0.1：不得用 is_risk_label 过滤掉未登记数据集），
 * 而是在「标签字段」列挂黄色告警标签 —— 未登记意味着它不会产生风险事件，
 * 这是管理端必须看见的信息，不是可以省略的行。
 * `caliber_registered` 是新增字段，未上线时用同值的 `is_risk_label` 兜底。
 */
const assetRows = computed<Array<Record<string, unknown>>>(() =>
  (props.data.datasets ?? []).map((item) => ({
    logical_id: item.logical_id,
    name: nameOf(item.logical_id),
    record_count: item.record_count,
    label_field: item.label_field,
    caliber_registered: item.caliber_registered ?? item.is_risk_label,
    risk_rate: fmtPercent(item.risk_rate),
    attribute_count: item.attribute_count,
    visibility: VISIBILITY_TEXT[item.visibility] ?? item.visibility ?? '—',
    model: modelingKnown.value ? modelTextOf(item.logical_id) : '—',
    version: `v${item.version}`,
  })),
);

/* ------------------------------------------------------------------ */
/* S3 建模覆盖                                                         */
/* ------------------------------------------------------------------ */

/** 每数据集的模型版本总数（含草稿），按画像 datasets 顺序，与 S2/D1 行序一致 */
const modelingRows = computed(() =>
  (props.data.datasets ?? []).map((item) => {
    const stat = modelStats.value.get(item.logical_id);
    return {
      logical_id: item.logical_id,
      name: nameOf(item.logical_id),
      total: stat?.total ?? 0,
    };
  }),
);

const modelingBars = computed(() =>
  modelingKnown.value
    ? modelingRows.value.map((row) => ({ value: row.name, count: row.total }))
    : [],
);

/** 「数据白躺」= 该数据集一个模型版本都没有；模型数据取不到时不下这个结论 */
const idleNames = computed(() =>
  modelingKnown.value
    ? modelingRows.value.filter((row) => row.total === 0).map((row) => row.name)
    : [],
);

/* ------------------------------------------------------------------ */
/* S4 场景运行态水位                                                    */
/* ------------------------------------------------------------------ */

const summary = computed(() => runtime.value?.summary ?? null);

/** 近 10 天推理活动合计（activity_trend 求和，口径与曲线一致） */
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

/** 场景成员：按角色分组计数（范围限本场景，不是全平台账号） */
const memberRows = computed(() => {
  if (members.value === null) return [];
  const admins = members.value.filter((item) => item.role === 'SCENARIO_ADMIN');
  const users = members.value.filter((item) => item.role === 'SCENARIO_USER');
  const disabled = members.value.filter((item) => item.status !== 'active');
  const rows: Array<{ label: string; value: string }> = [
    { label: '场景管理员', value: `${admins.length} 人` },
    { label: '场景用户', value: `${users.length} 人` },
    { label: '合计', value: `${members.value.length} 人` },
  ];
  if (disabled.length) {
    rows.push({ label: '已禁用账号', value: `${disabled.length} 人` });
  }
  return rows;
});
</script>

<template>
  <!-- S1 场景资产总览（前 3 项四场景一致，第 4 项为舰面调度特色：同源冗余率） -->
  <DashKpis :items="assetKpis" />

  <!-- D1 ★ 舰面调度特色块 1：同源编码族治理表 -->
  <DashCard
    title="同源编码族治理表"
    source="同源组内为同一批样本的不同编码 · 只应保留一份入模"
  >
    <DashTable :columns="familyColumns" :rows="familyRows" row-key="logical_id" dense />
  </DashCard>

  <!-- D2 ★ 舰面调度特色块 2：同源冗余度与去重收益 -->
  <DashCard
    title="同源冗余度与去重收益"
    source="冗余率 = 1 - 有效数据集数 / 文件数；去重前按文件逐个求和，去重后按同源组代表求和"
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
    <p v-else-if="!modelingKnown" class="d-src">模型版本数据未取到，暂不能判定「数据白躺」</p>
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
