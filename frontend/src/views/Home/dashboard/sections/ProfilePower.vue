<script setup lang="ts">
/**
 * ProfilePower —— 电力系统 · 数据画像（管理端）。
 * 字段口径见 docs/首页字段口径说明.md。数据源：powergrid_knowledgebase_dataset.arff。
 * 说明：原「设备健康度排行」因 7 类设备故障占比均在 77%~82%（无区分度）已剔除，改为「设备 × 故障占比」。
 */
import type { PowerProfile } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import { fmtNum, fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: PowerProfile }>();

const paramCard = (key: string) => props.data.params.find((item) => item.key === key);

const paramRows = (key: string) => {
  const param = paramCard(key);
  if (!param || !param.stats) return [];
  const unit = param.unit ? ` ${param.unit}` : '';
  return [
    { label: '均值', value: fmtNum(param.stats.mean) + unit },
    { label: '最小值', value: fmtNum(param.stats.min) + unit },
    { label: '最大值', value: fmtNum(param.stats.max) + unit },
    { label: '中位数', value: fmtNum(param.stats.median) + unit },
  ];
};

const frequencyRows = () => {
  const rows = paramRows('PowerFrequencyHz');
  const loss = paramCard('Sensor_Packet_Loss_%');
  if (loss?.stats) rows.push({ label: '平均遥测丢包率', value: fmtNum(loss.stats.mean) + ' %' });
  return rows;
};
</script>

<template>
  <DashKpis
    :items="[
      { label: '监测样本总量', value: data.sample_count, unit: '条', tone: 'primary', sub: '电力数据集' },
      { label: '故障样本数', value: data.fault_count, unit: '条', tone: 'danger', sub: '故障样本' },
      { label: '故障样本占比', value: fmtPercent(data.fault_rate), tone: 'warning', sub: '全量统计', raw: true },
      { label: '监测设备类型', value: data.components.length, unit: '类', tone: 'success', sub: '按设备去重' },
    ]"
  />

  <div class="d-grid3">
    <DashCard title="电压 均值/范围（kV）" source="按全量样本统计">
      <DashRows :rows="paramRows('VoltageLevel_kV')" />
    </DashCard>
    <DashCard title="电流 均值/范围（A）" source="按全量样本统计">
      <DashRows :rows="paramRows('CurrentAmp')" />
    </DashCard>
    <DashCard title="温度 均值/范围（℃）" source="按全量样本统计">
      <DashRows :rows="paramRows('Temperature_C')" />
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="问题类型分布" source="按问题类型统计">
      <DashDonut :items="data.issues" center-label="合计" />
    </DashCard>
    <DashCard title="设备样本数量分布" source="按设备统计">
      <DashColumns :items="data.components.map((item) => ({ label: item.value, value: item.count }))" />
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="电力系统分布与频率" source="按电力系统统计">
      <DashDonut :items="data.systems" center-label="合计" />
      <DashRows :rows="frequencyRows()" />
    </DashCard>
    <DashCard
      title="各设备故障样本占比"
      :source="['按设备统计故障样本占比。']"
    >
      <DashBars :items="data.device_fault_rates.map((item) => ({ value: item.value, count: item.risk_rate }))" percent />
    </DashCard>
  </div>
</template>
