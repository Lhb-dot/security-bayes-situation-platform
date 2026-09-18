<script setup lang="ts">
/**
 * ProfileGeological —— 地质风险 · 数据画像（管理端）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 口径：数据集无「区域」字段，坡度相关一律按真实字段 Slope 分档；地形因子取 DIS_raw_data 全量实测。
 */
import type { GeologicalProfile } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import { fmtPercent } from '@/components/dashboard/dashFormat';

const props = defineProps<{ data: GeologicalProfile }>();

/** 标签字段为真实风险标签的数据集（dis_global_catalog 的标签是灾害规模，不是风险标签，单列） */
const riskDatasets = () => props.data.datasets.filter((item) => item.is_risk_label);
const catalogDataset = () => props.data.datasets.find((item) => !item.is_risk_label);
</script>

<template>
  <DashKpis
    :items="[
      { label: '地质数据集', value: data.dataset_count, unit: '个', tone: 'primary', sub: '已登记数据集' },
      { label: '主集风险样本', value: data.risk_count, unit: '条', tone: 'danger', sub: '按标签字段统计' },
      { label: '主集风险占比', value: fmtPercent(data.risk_rate), tone: 'warning', sub: '全量统计', raw: true },
      { label: '可用地形因子', value: data.factor_count, unit: '个', tone: 'success', sub: '按数据集统计' },
    ]"
  />

  <div class="d-grid2">
    <DashCard title="8 个地形因子均值" source="按地形因子全量统计">
      <DashBars :items="data.factors.map((item) => ({ value: item.value, count: item.mean }))" />
    </DashCard>
    <DashCard title="各数据集风险样本占比（%）" source="按各数据集标签字段统计">
      <DashColumns
        :items="riskDatasets().map((item) => ({ label: item.name || item.logical_id, value: Number((item.risk_rate * 100).toFixed(1)) }))"
        :percent-value="true"
      />
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="各数据集样本量" source="按数据集统计样本量">
      <DashColumns :items="data.datasets.map((item) => ({ label: item.name || item.logical_id, value: item.record_count }))" />
    </DashCard>
    <DashCard
      title="数据集清单"
      :source="
        catalogDataset()
          ? '该数据集的标签为灾害规模，非风险标签，不计入风险占比。'
          : '该数据集标签非风险标签，不计入风险占比。'
      "
    >
      <DashRows
        :rows="data.datasets.map((item) => ({
          label: item.name || item.logical_id,
          value: `${item.record_count} 条 · 风险占比 ${fmtPercent(item.risk_rate)}`,
        }))"
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
