<script setup lang="ts">
/**
 * WorkspaceGeological —— 地质风险 · 我的工作台（场景用户首页）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 口径：数据集无「区域」字段 → 坡度相关一律按真实字段 Slope 的坡度档位分组。
 */
import type { GeologicalWorkspace } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashEvents from '@/components/dashboard/DashEvents.vue';

defineProps<{ data: GeologicalWorkspace }>();
</script>

<template>
  <DashKpis
    :items="[
      { label: '我的待处置告警', value: data.summary.pending, unit: '条', tone: 'danger', sub: '待处置' },
      { label: '今日新增', value: data.summary.today, unit: '条', tone: 'warning', sub: '今日新增' },
      { label: '高置信告警', value: data.summary.high_confidence, unit: '条', tone: 'purple', sub: '风险分 ≥ ' + (data.summary.high_threshold ?? 0.8).toFixed(2) },
      { label: '涉及坡度档位', value: data.slope_bucket_count, unit: '档', tone: 'primary', sub: '按坡度分档' },
    ]"
  />

  <div class="d-grid2">
    <DashCard title="关键因子贡献排行" source="事件地形因子均值归一">
      <DashBars v-if="data.summary.total" :items="data.factor_contribution" percent-value />
      <p v-else class="d-empty">暂无告警样本</p>
    </DashCard>
    <DashCard title="触发因素分布" source="按触发因素统计">
      <DashDonut v-if="data.trigger_distribution.length" :items="data.trigger_distribution" center-label="合计" />
      <p v-else class="d-empty">暂无告警样本</p>
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard
      title="坡度档位平均风险分排行"
      :source="['按坡度档位分组统计平均风险分。']"
    >
      <DashBars :items="data.slope_ranking.map((item) => ({ value: item.label, count: item.mean_risk_score }))" percent />
    </DashCard>
    <DashCard title="坡度档位告警数排行" source="按坡度档位统计">
      <DashBars :items="data.slope_ranking.map((item) => ({ value: item.label, count: item.count }))" suffix=" 条" />
    </DashCard>
  </div>

  <div class="d-grid2">
    <DashCard title="风险分区间分布" source="按风险分区间统计">
      <DashDonut :items="data.summary.score_bins" center-label="告警" />
    </DashCard>
    <DashCard
      title="各数据集风险占比"
      :source="['静态标签分布，与当前告警无关，仅作数据画像。']"
    >
      <DashColumns
        :items="data.dataset_prior.map((item) => ({ label: item.name || item.logical_id, value: Number((item.risk_rate * 100).toFixed(1)) }))"
        :percent-value="true"
        :height="190"
      />
    </DashCard>
  </div>

  <DashCard title="最近告警" source="最近告警记录，最多 20 条">
    <DashEvents :items="data.recent_events" />
  </DashCard>
</template>
