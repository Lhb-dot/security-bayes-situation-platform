<script setup lang="ts">
/**
 * WorkspaceFlightdeck —— 舰面调度 · 我的工作台（场景用户首页）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 口径：散点图为后端用双机平均航向角映射的占位坐标，非真实甲板位置（图内已标注）。
 */
import type { FlightdeckWorkspace } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashScatter from '@/components/dashboard/DashScatter.vue';
import DashRadar from '@/components/dashboard/DashRadar.vue';
import DashLine from '@/components/dashboard/DashLine.vue';
import DashEvents from '@/components/dashboard/DashEvents.vue';
import { fmtDate, fmtNum } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: FlightdeckWorkspace }>();

const radarSeries = () => [
  {
    name: '1 号机',
    color: '#5ba6ff',
    values: [
      props.data.direction_stats[0]?.stats?.mean ?? null,
      props.data.direction_stats[0]?.stats?.max ?? null,
      props.data.direction_stats[0]?.stats?.min ?? null,
      props.data.direction_stats[0]?.stats?.std ?? null,
    ],
  },
  {
    name: '2 号机',
    color: '#a78bfa',
    values: [
      props.data.direction_stats[1]?.stats?.mean ?? null,
      props.data.direction_stats[1]?.stats?.max ?? null,
      props.data.direction_stats[1]?.stats?.min ?? null,
      props.data.direction_stats[1]?.stats?.std ?? null,
    ],
  },
];
</script>

<template>
  <DashKpis
    :items="[
      { label: '我的待处置告警', value: data.summary.pending, unit: '条', tone: 'danger', sub: '待处置' },
      { label: '今日新增', value: data.summary.today, unit: '条', tone: 'warning', sub: '今日新增' },
      { label: '最小间距', value: data.min_inter_distance === null ? '—' : fmtNum(data.min_inter_distance, 1), unit: 'm', tone: 'primary', sub: '低于 100 m 需关注' },
      { label: '最高模型风险分', value: fmtNum(data.summary.max_risk_score, 2), tone: 'purple', sub: '模型输出风险概率' },
    ]"
  />

  <div class="d-grid2">
    <DashCard
      title="双机航向映射散点图"
      :source="['按双机平均航向角映射的风险方位散点。']"
    >
      <DashScatter :points="data.positions" />
    </DashCard>
    <DashCard title="双机方向角对比雷达（°）" source="按告警事件统计双机方向角">
      <DashRadar
        v-if="data.direction_stats.some((item) => item.stats)"
        :axes="['均值', '最大', '最小', '标准差']"
        :series="radarSeries()"
        unit="°"
      />
      <p v-else class="d-empty">暂无数据</p>
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="最小间距分布" source="按最小间距分箱统计">
      <DashColumns :items="data.distance_distribution" :height="190" axis-unit="单位：条" />
    </DashCard>
    <DashCard title="近 7 天推理活动趋势（条）" source="近 7 天按日聚合">
      <DashLine
        :points="data.activity_trend.map((item) => ({ label: fmtDate(item.date), value: item.total, value2: item.risk }))"
        name="推理总数"
        name2="判为风险"
        area
        suffix=" 条"
      />
    </DashCard>
  </div>

  <DashCard title="最近告警" source="最近告警记录，最多 20 条">
    <DashEvents :items="data.recent_events" />
  </DashCard>
</template>
