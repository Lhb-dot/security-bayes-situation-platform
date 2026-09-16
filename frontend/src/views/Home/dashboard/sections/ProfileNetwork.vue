<script setup lang="ts">
/**
 * ProfileNetwork —— 网络安全 · 数据画像（管理端）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 数据源：NF-UNSW-NB15-v2.arff（协议/端口/包长/重传） + KDDTrain_20Percent.arff（flag/服务）。
 */
import type { NetworkProfile } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import { fmtInt, fmtNum, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: NetworkProfile }>();

const trafficRows = () => {
  const traffic = props.data.traffic;
  return [
    { label: '平均入向字节', value: fmtInt(traffic.avg_in_bytes) },
    { label: '平均重传字节', value: fmtInt(traffic.avg_retrans_in_bytes) },
    { label: '重传字节占比', value: fmtPercent(traffic.retransmission_ratio, 2) },
    { label: '入向字节中位数', value: fmtNum(traffic.in_bytes_stats?.median, 0) },
  ];
};
</script>

<template>
  <DashKpis
    :items="[
      { label: '连接样本总量', value: data.sample_count, unit: '条', tone: 'primary', sub: '两数据集合计' },
      { label: '异常样本数', value: data.risk_count, unit: '条', tone: 'danger', sub: '按标签字段统计' },
      { label: '异常样本占比', value: fmtPercent(data.risk_rate), tone: 'warning', sub: '全量统计', raw: true },
      { label: '目的端口种类', value: data.distinct_port_count, unit: '个', tone: 'success', sub: '按端口去重' },
    ]"
  />

  <div class="d-grid2">
    <DashCard title="协议分布" source="协议号已映射为名称，非主流协议归入「其他」">
      <DashDonut :items="data.protocol_distribution" center-label="合计" :limit="6" />
    </DashCard>
    <DashCard title="目的端口 TOP 8" source="按目的端口统计">
      <DashBars :items="data.top_ports" prefix="端口 " suffix=" 条" />
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="流量包长五段分布" source="按包长区间统计">
      <DashColumns :items="data.flow_segments" />
    </DashCard>
    <DashCard title="连接状态分布" source="按连接状态统计">
      <DashBars :items="data.flags" suffix=" 条" />
    </DashCard>
  </div>

  <div class="d-grid3">
    <DashCard
      title="平均入向字节 / 重传占比"
      :source="'按入向字节与重传字节统计'"
    >
      <DashRows :rows="trafficRows()" />
    </DashCard>
    <DashCard title="应用服务 TOP" source="按应用服务统计">
      <DashBars :items="data.services" suffix=" 条" />
    </DashCard>
    <DashCard title="数据集规模对比" source="按数据集统计样本量">
      <DashColumns :items="data.datasets.map((item) => ({ label: item.name || item.logical_id, value: item.record_count }))" />
    </DashCard>
  </div>
</template>
