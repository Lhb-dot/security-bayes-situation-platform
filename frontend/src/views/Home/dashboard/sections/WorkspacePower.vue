<script setup lang="ts">
/**
 * WorkspacePower —— 电力系统 · 我的工作台（场景用户首页）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 说明：原「设备健康度排行」实测 77%~82% 无区分度，已替换为「设备 × 问题类型告警构成」。
 */
import type { PowerWorkspace } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashGauge from '@/components/dashboard/DashGauge.vue';
import DashEvents from '@/components/dashboard/DashEvents.vue';

defineProps<{ data: PowerWorkspace }>();

/** 电参量正常区间（按数据集实际量级给出参考带，仅用于刻度条分色） */
const NORMAL_BAND: Record<string, { low: number | null; high: number | null }> = {
  VoltageLevel_kV: { low: 300, high: 700 },
  CurrentAmp: { low: 400, high: 1600 },
  Temperature_C: { low: 30, high: 90 },
  PowerFrequencyHz: { low: 49.8, high: 50.2 },
};
</script>

<template>
  <DashKpis
    :items="[
      { label: '我的待处置告警', value: data.summary.pending, unit: '条', tone: 'danger', sub: '待处置' },
      { label: '今日新增', value: data.summary.today, unit: '条', tone: 'warning', sub: '今日新增' },
      { label: '高置信告警', value: data.summary.high_confidence, unit: '条', tone: 'purple', sub: '风险分 ≥ 0.8' },
      { label: '受影响设备', value: data.device_ranking.length, unit: '类', tone: 'primary', sub: '按设备去重' },
    ]"
  />

  <p v-if="!data.summary.total" class="d-note">
    当前账号还没有风险事件：本页运行态指标会在「风险研判」产生告警后自动有值。
  </p>

  <DashCard
    title="告警样本电参量均值"
    :source="['取告警事件均值，反映被判定异常样本的电参量水平。']"
  >
    <DashGauge
      v-for="item in data.telemetry"
      :key="item.key"
      :name="item.name"
      :unit="item.unit"
      :mean="item.stats?.mean ?? null"
      :min="item.stats?.min ?? null"
      :max="item.stats?.max ?? null"
      :low="NORMAL_BAND[item.key]?.low ?? null"
      :high="NORMAL_BAND[item.key]?.high ?? null"
    />
  </DashCard>

  <div class="d-grid2">
    <DashCard
      title="风险分区间分布"
      :source="['按风险分区间统计告警分布。']"
    >
      <DashDonut :items="data.summary.score_bins" center-label="告警" />
    </DashCard>
    <DashCard title="设备告警数排行" source="按设备统计告警数">
      <DashBars :items="data.device_ranking" suffix=" 条" />
    </DashCard>
  </div>

  <DashCard
    title="设备问题类型告警构成"
    source="按设备与问题类型统计"
  >
    <DashColumns
      :items="data.component_issue_distribution.map((item) => ({ label: `${item.component}·${item.issue}`, value: item.count }))"
      :height="200"
    />
  </DashCard>

  <DashCard title="最近告警" source="最近告警记录，最多 20 条">
    <DashEvents :items="data.recent_events" />
  </DashCard>
</template>
