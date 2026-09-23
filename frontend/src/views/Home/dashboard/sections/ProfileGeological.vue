<script setup lang="ts">
/**
 * ProfileGeological —— 地质风险 · 场景管理员首页（管理端）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 口径：数据集无「区域」字段，坡度相关一律按真实字段 Slope 分档；地形因子取 DIS_raw_data 全量实测。
 *
 * 视角：**管理端看资源与流程，不是执行端看任务**。与场景用户的「我的工作台」的区别：
 *   用户侧（WorkspaceGeological）＝ 我手上的活：待处置告警、因子贡献、坡度档位排行；
 *   管理侧（本组件）＝ 这个场景健康吗：处置进度、数据集能不能建模、数据有没有质量问题。
 *   因此这里**不**放「因子贡献排行」「坡度档位排行」这类研判辅助图（那是执行者用的），
 *   事件列表也只保留待处置中风险分最高的几条（＝需要先派活的），不做全量明细。
 *
 * 数据来源两段，作用域不同：
 *   运行态 /workspace —— 范围由后端 _event_scope / _activity_trend 按角色收窄，
 *   场景管理员拿到的是整个场景（self_only=false）；接口失败静默降级，不影响数据资产部分。
 *   数据资产 /profile —— 数据集全量统计，不受运行态影响。
 */
import { computed, onMounted, ref, watch } from 'vue';
import {
  getScenarioWorkspace,
  type DatasetStat,
  type GeologicalProfile,
  type GeologicalWorkspace,
} from '@/api/dashboardApi';
import { getModelVersionList, type BackendModelVersion } from '@/api/modelVersionApi';
import { getUserList } from '@/api/userApi';
import type { UserAccount } from '@/types/security';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashEvents from '@/components/dashboard/DashEvents.vue';
import DashFunnel from '@/components/dashboard/DashFunnel.vue';
import DashLine from '@/components/dashboard/DashLine.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import { fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: GeologicalProfile }>();

/** 标签字段为真实风险标签的数据集（dis_global_catalog 的标签是灾害规模，不是风险标签，单列） */
const riskDatasets = () => props.data.datasets.filter((item) => item.is_risk_label);
const catalogDataset = () => props.data.datasets.find((item) => !item.is_risk_label);

/* ------------------------------------------------------------------ */
/* 运行态：流程与积压                                                   */
/* ------------------------------------------------------------------ */

const runtime = ref<GeologicalWorkspace | null>(null);
/** 场景内模型；null = 未取到（与「确实 0 个」区分开，避免误报 0） */
const models = ref<BackendModelVersion[] | null>(null);
/** 场景成员；null = 未取到 */
const members = ref<UserAccount[] | null>(null);

/**
 * 三个接口并行、各自静默降级：任一失败只影响它自己那块，不阻塞整页。
 * 模型与成员不属于 /workspace、/profile 的返回范围，是前端另行获取的。
 */
const loadAll = async () => {
  const scenarioId = props.data.scenario_id;
  const [runtimeResult, modelResult, memberResult] = await Promise.allSettled([
    getScenarioWorkspace(scenarioId),
    getModelVersionList({ scenario_id: scenarioId, page_size: 100 }),
    getUserList({ page_size: 200 }),
  ]);

  runtime.value =
    runtimeResult.status === 'fulfilled' && runtimeResult.value.scenario_key === 'geological'
      ? (runtimeResult.value as GeologicalWorkspace)
      : null;
  models.value = modelResult.status === 'fulfilled' ? modelResult.value : null;
  members.value =
    memberResult.status === 'fulfilled'
      ? memberResult.value.items.filter((item) => item.scenario_id === scenarioId)
      : null;
};

watch(() => props.data.scenario_id, loadAll);
onMounted(loadAll);

const summary = computed(() => runtime.value?.summary ?? null);

/** 管理指标：积压、处置率、风险水位、资源量 */
const kpis = computed(() => {
  const item = summary.value;
  return [
    { label: '待处置积压', value: item ? item.pending : null, unit: '条', tone: 'danger' as const },
    {
      label: '已处置率',
      value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
      tone: 'success' as const,
      raw: true,
    },
    {
      label: '已发布模型',
      value: models.value
        ? models.value.filter((model) => model.status === 'PUBLISHED').length
        : null,
      unit: '个',
      tone: 'success' as const,
    },
    { label: '数据集', value: props.data.dataset_count, unit: '个', tone: 'primary' as const },
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

/** 待处置中风险分最高的几条 —— 管理端关心「先派哪个活」，不做全量明细 */
const pendingEvents = computed(() =>
  (runtime.value?.recent_events ?? [])
    .filter((item) => item.status === 'PENDING')
    .sort((a, b) => Number(b.risk_score ?? 0) - Number(a.risk_score ?? 0))
    .slice(0, 6),
);

/* ------------------------------------------------------------------ */
/* 数据资产与质量                                                       */
/* ------------------------------------------------------------------ */

/**
 * 数据集展示名去重。
 *
 * `dataset_display_name_of` 取的是上传文件名，同源重复的两条记录（如 dis_landslides 与
 * geo_slope_company_v1 都指向 DIS_Landslides.arff）会得到**完全相同的展示名**，
 * 列表里就会出现两行一模一样的名字、看不出差别。重名时补上 logical_id 以区分。
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

/** 各数据集的模型数（按 dataset_logical_id 归集） */
const modelCountByDataset = computed(() => {
  const map = new Map<string, { total: number; published: number }>();
  (models.value ?? []).forEach((model) => {
    const key = model.dataset_logical_id ?? String(model.dataset_id);
    const entry = map.get(key) ?? { total: 0, published: 0 };
    entry.total += 1;
    if (model.status === 'PUBLISHED') entry.published += 1;
    map.set(key, entry);
  });
  return map;
});

/**
 * 数据集资产：样本量 · 标签字段 · 风险占比 · 模型数。
 *
 * 模型列把「数据 ↔ 模型」的对应关系摆在一起：哪份数据训出了模型、哪份一份没有，
 * 一眼可见。这是管理端最该关心的问题之一（数据白躺着没人用）。
 * models 为 null 表示接口未取到，此时显示占位符而不是「未训练」，避免误报。
 *
 * 这里**不**输出「是否参与建模」——`is_risk_label` 的语义是「logical_id 是否登记在
 * DATASET_RISK_TYPES 常量里」，对后上传、未登记的数据集（如 geo_slope_company_v1）
 * 会判为 false，据此写「编目参考」会与事实相反（它实际是 LS 二分类数据）。
 * 直接展示真实标签字段名，由读者判断，不做推断。
 */
const datasetRows = computed(() =>
  props.data.datasets.map((item) => {
    const stat = modelCountByDataset.value.get(item.logical_id);
    const modelText =
      models.value === null
        ? '模型 —'
        : !stat
          ? '未训练'
          : stat.published === stat.total
            ? `模型 ${stat.total} 个`
            : `模型 ${stat.total} 个（已发布 ${stat.published}）`;
    return {
      label: displayNames.value.get(item.logical_id) ?? item.logical_id,
      value: `${item.record_count} 条 · 标签 ${item.label_field} · 风险 ${fmtPercent(item.risk_rate)} · ${modelText}`,
    };
  }),
);

/** 场景成员：按角色汇总，管理员需要知道这个场景里有哪些人 */
const memberRows = computed(() => {
  if (members.value === null) return [];
  const admins = members.value.filter((item) => item.role === 'SCENARIO_ADMIN');
  const users = members.value.filter((item) => item.role === 'SCENARIO_USER');
  const disabled = members.value.filter((item) => item.status !== 'active');
  const rows = [
    { label: '场景管理员', value: `${admins.length} 人` },
    { label: '场景用户', value: `${users.length} 人` },
    { label: '合计', value: `${members.value.length} 人` },
  ];
  if (disabled.length) {
    rows.push({ label: '已禁用', value: `${disabled.length} 人` });
  }
  return rows;
});

/**
 * 数据质量提示 —— 管理端独有的信息，执行端不需要。
 * 只用 risk_rate 判断，不依赖 is_risk_label（后者是常量映射，对新数据集会误判）。
 */
const qualityRows = computed(() => {
  const rows: Array<{ label: string; value: string }> = [];
  const list = props.data.datasets;

  // ① 有正样本但占比过低 —— 直接影响模型偏向
  list
    .filter((item) => item.record_count > 0 && item.risk_count > 0 && item.risk_rate < 0.05)
    .forEach((item) =>
      rows.push({
        label: item.name || item.logical_id,
        value: `正样本 ${item.risk_count} / ${item.record_count} 条（${fmtPercent(item.risk_rate)}），类别极不平衡`,
      }),
    );

  // ② 标签字段与样本量完全一致 —— 疑似同源重复，会重复计入样本总量
  const bySignature = new Map<string, DatasetStat[]>();
  list.forEach((item) => {
    const key = `${item.label_field}|${item.record_count}|${item.risk_count}`;
    bySignature.set(key, [...(bySignature.get(key) ?? []), item]);
  });
  bySignature.forEach((group) => {
    if (group.length < 2) return;
    rows.push({
      label: group
        .map((item) => displayNames.value.get(item.logical_id) ?? item.logical_id)
        .join(' / '),
      value: `标签、样本量、正样本数完全一致（${group[0].label_field} · ${group[0].record_count} 条），疑似同源重复`,
    });
  });

  return rows;
});
</script>

<template>
  <DashKpis :items="kpis" />

  <div v-if="summary && summary.total" class="d-grid2">
    <DashCard title="风险事件处置进度" source="按处置状态统计全场景风险事件">
      <DashFunnel :items="funnelItems" />
    </DashCard>
    <DashCard title="近 10 天活动趋势" source="按天统计风险推理量，以及其中判定为风险的量">
      <DashLine :points="trendPoints" name="推理" name2="风险" area suffix=" 次" />
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="各数据集样本量" source="按数据集统计样本量">
      <DashBars
        :items="data.datasets.map((item) => ({ value: displayNames.get(item.logical_id) ?? item.logical_id, count: item.record_count }))"
        :label-width="250"
        suffix=" 条"
      />
    </DashCard>
    <DashCard
      title="数据集资产"
      :source="
        catalogDataset()
          ? '该数据集的标签为灾害规模，非风险标签，不计入风险占比。'
          : '该数据集标签非风险标签，不计入风险占比。'
      "
    >
      <DashRows :rows="datasetRows" />
    </DashCard>
  </div>

  <div v-if="memberRows.length || qualityRows.length" class="d-grid2">
    <DashCard v-if="memberRows.length" title="场景成员" source="按账号角色统计，范围限本场景">
      <DashRows :rows="memberRows" />
    </DashCard>
    <DashCard
      v-if="qualityRows.length"
      title="数据质量提示"
      source="按样本标签分布自动检出，影响建模与统计口径"
    >
      <DashRows :rows="qualityRows" />
    </DashCard>
  </div>

  <DashCard
    v-if="pendingEvents.length"
    title="近期待处置事件 · 按风险分排序"
    source="取自最近 20 条风险事件中状态为待处置的记录，按风险分降序取前 6 条；不是全部积压量，完整清单见风险事件页"
  >
    <DashEvents :items="pendingEvents" />
  </DashCard>

  <div class="d-grid2">
    <DashCard title="8 个地形因子均值" source="按地形因子全量统计">
      <DashBars :items="data.factors.map((item) => ({ value: item.value, count: item.mean }))" />
    </DashCard>
    <DashCard title="各数据集风险样本占比（%）" source="按各数据集标签字段统计">
      <DashBars
        :items="riskDatasets().map((item) => ({ value: displayNames.get(item.logical_id) ?? item.logical_id, count: Number((item.risk_rate * 100).toFixed(1)) }))"
        :label-width="250"
        percent-value
      />
    </DashCard>
  </div>

  <div class="d-grid3">
    <DashCard title="地质灾害触发因素分布" source="按触发因素统计">
      <DashDonut
        v-if="data.catalog_distribution.trigger.length"
        :items="data.catalog_distribution.trigger"
        center-label="合计"
        :limit="6"
      />
      <p v-else class="d-empty">暂无数据</p>
    </DashCard>
    <DashCard title="灾害类型分布" source="按灾害类型统计">
      <DashBars v-if="data.catalog_distribution.category.length" :items="data.catalog_distribution.category" />
      <p v-else class="d-empty">暂无数据</p>
    </DashCard>
    <DashCard title="规模分布与国家 TOP" source="按规模与国家统计">
      <DashColumns
        v-if="data.catalog_distribution.size.length"
        :items="data.catalog_distribution.size.map((item) => ({ label: item.value, value: item.count }))"
        :height="170"
      />
      <DashBars v-if="data.catalog_distribution.country.length" :items="data.catalog_distribution.country" suffix=" 起" />
      <p v-if="!data.catalog_distribution.size.length && !data.catalog_distribution.country.length" class="d-empty">暂无可算字段</p>
    </DashCard>
  </div>
</template>
