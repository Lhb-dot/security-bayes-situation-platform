<script setup lang="ts">
/**
 * ProfileFlightdeck —— 舰面调度 · 数据画像（管理端）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 口径：carrier 三份为同源衍生，本页只按其中一份统计（507 条），避免 3 倍重复计数。
 */
import type { FlightdeckProfile } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import DashLine from '@/components/dashboard/DashLine.vue';
import DashRadar from '@/components/dashboard/DashRadar.vue';
import { fmtNum, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: FlightdeckProfile }>();

const distanceRows = () => {
  const rows = [
    { label: '平均最小间距', value: fmtNum(props.data.distance.min?.mean) + ' m' },
    { label: '平均间距', value: fmtNum(props.data.distance.mean?.mean) + ' m' },
    { label: '中位间距', value: fmtNum(props.data.distance.median?.mean) + ' m' },
  ];
  return rows;
};

const approachRows = () => [
  { label: '接近率均值', value: fmtNum(props.data.approach.abs_change_ratio_mean, 3) },
  { label: '距离变化率均值', value: fmtNum(props.data.approach.change_ratio_mean, 3) },
];

const rangeRows = () => [
  { label: '1 号机总航程均值', value: fmtNum(props.data.total_distance.plane1_mean, 1) + ' m' },
  { label: '2 号机总航程均值', value: fmtNum(props.data.total_distance.plane2_mean, 1) + ' m' },
  { label: '航程差均值', value: fmtNum(props.data.total_distance.diff_mean, 1) + ' m' },
];

const relativeRows = () => [
  { label: '相对角均值', value: fmtNum(props.data.relative_angle.mean) + ' °' },
  { label: '相对角最大值', value: fmtNum(props.data.relative_angle.max) + ' °' },
];

const fluctuationRows = () => [
  { label: '间距标准差', value: fmtNum(props.data.distance.std?.mean) + ' m' },
  { label: '间距极差', value: fmtNum(props.data.distance.range?.mean) + ' m' },
];

const angleBars = () => [
  { value: '1 号机均值', count: props.data.direction.plane1.mean },
  { value: '1 号机标准差', count: props.data.direction.plane1.std },
  { value: '2 号机均值', count: props.data.direction.plane2.mean },
  { value: '2 号机标准差', count: props.data.direction.plane2.std },
];

const collisionBars = () => [
  { value: '碰撞样本', count: props.data.collision_comparison.collision.mean_min_distance },
  { value: '正常样本', count: props.data.collision_comparison.normal.mean_min_distance },
];

const radarSeries = () => [
  {
    name: '1 号机',
    color: '#5ba6ff',
    values: [
      props.data.direction.plane1.stats?.mean ?? null,
      props.data.direction.plane1.stats?.max ?? null,
      props.data.direction.plane1.stats?.min ?? null,
      props.data.direction.plane1.stats?.std ?? null,
    ],
  },
  {
    name: '2 号机',
    color: '#a78bfa',
    values: [
      props.data.direction.plane2.stats?.mean ?? null,
      props.data.direction.plane2.stats?.max ?? null,
      props.data.direction.plane2.stats?.min ?? null,
      props.data.direction.plane2.stats?.std ?? null,
    ],
  },
];
</script>

<template>
  <DashKpis
    :items="[
      { label: '轨迹样本总量', value: data.sample_count, unit: '条', tone: 'primary', sub: '同源文件已去重' },
      { label: '碰撞风险样本', value: data.collision_count, unit: '条', tone: 'danger', sub: '碰撞样本' },
      { label: '碰撞样本占比', value: fmtPercent(data.collision_rate), tone: 'warning', sub: '碰撞 / 总样本', raw: true },
      { label: '最小机间距离', value: fmtNum(data.distance.min?.min, 1), unit: 'm', tone: 'success', sub: '全样本最小值' },
    ]"
  />

  <div class="d-grid3">
    <DashCard title="平均最小间距 / 平均间距（m）" source="按全样本统计">
      <DashRows :rows="distanceRows()" />
    </DashCard>
    <DashCard title="接近率均值" source="按全样本统计">
      <DashRows :rows="approachRows()" />
    </DashCard>
    <DashCard title="双机总航程均值（m）" source="按双机分别统计">
      <DashRows :rows="rangeRows()" />
    </DashCard>
  </div>

  <DashCard title="机间距变化曲线" source="按时间步统计全样本均值">
    <DashLine
      :points="data.distance_curve.map((item) => ({ label: 'T' + item.step, value: item.mean }))"
      name="平均间距"
      color="#5ba6ff"
      area
      suffix=" m"
    />
  </DashCard>

  <div class="d-grid2">
    <DashCard
      title="碰撞 vs 正常 最小间距对比（m）"
      :source="['碰撞样本的最小间距显著更低，具有区分度。']"
    >
      <DashBars :items="collisionBars()" color="#ff7b72" />
    </DashCard>
    <DashCard title="1/2 号机方向角统计（°）" source="按双机分别统计">
      <DashBars :items="angleBars()" />
    </DashCard>
  </div>

  <div class="d-grid3">
    <DashCard title="双机方向角对比雷达（°）" source="事件 1/2 号机方向角统计量">
      <DashRadar :axes="['均值', '最大', '最小', '标准差']" :series="radarSeries()" unit="°" />
    </DashCard>
    <DashCard title="相对角统计" source="按全样本统计">
      <DashRows :rows="relativeRows()" />
    </DashCard>
    <DashCard title="间距波动" source="按全样本统计">
      <DashRows :rows="fluctuationRows()" />
    </DashCard>
  </div>
</template>
