<script setup lang="ts">
/**
 * WorkspaceNetwork —— 网络安全 · 我的工作台（场景用户首页）。
 * 字段口径见 docs/首页字段口径说明.md。
 * 口径：范围严格限定「当前登录用户本人」（后端按 created_by_user_id 强制过滤）。
 */
import type { NetworkWorkspace } from '@/api/dashboardApi';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashBars from '@/components/dashboard/DashBars.vue';
import DashDonut from '@/components/dashboard/DashDonut.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashFunnel from '@/components/dashboard/DashFunnel.vue';
import DashLine from '@/components/dashboard/DashLine.vue';
import DashEvents from '@/components/dashboard/DashEvents.vue';
import { fmtDate } from '@/components/dashboard/dashFormat';

defineProps<{ data: NetworkWorkspace }>();
</script>

<template>
  <DashKpis
    :items="[
      { label: '我的待处置告警', value: data.summary.pending, unit: '条', tone: 'danger', sub: '待处置' },
      { label: '今日新增', value: data.summary.today, unit: '条', tone: 'warning', sub: '今日新增' },
      { label: '高置信告警', value: data.summary.high_confidence, unit: '条', tone: 'purple', sub: '风险分 ≥ ' + (data.summary.high_threshold ?? 0.8).toFixed(2) },
      { label: '异常端口', value: data.abnormal_ports.length, unit: '个', tone: 'primary', sub: '偏离基线 ≥ 2 倍' },
    ]"
  />

  <DashCard title="近 7 天推理活动趋势（条）" source="近 7 天推理活动趋势。实线=推理总数，虚线=判为风险数。">
    <DashLine
      :points="data.activity_trend.map((item) => ({ label: fmtDate(item.date), value: item.total, value2: item.risk }))"
      name="推理总数"
      name2="判为风险"
      area
      suffix=" 条"
    />
  </DashCard>

  <div class="d-grid2">
    <DashCard
      title="风险分区间分布"
      :source="['按风险分区间统计告警分布。']"
    >
      <DashDonut :items="data.summary.score_bins" center-label="告警" />
    </DashCard>
    <DashCard title="处置漏斗" source="按处置状态统计">
      <DashFunnel :items="data.summary.status_funnel" />
    </DashCard>
  </div>

  <div class="d-grid3">
    <DashCard title="告警端口 TOP" source="按目的端口统计">
      <DashBars :items="data.top_ports" prefix="端口 " suffix=" 条" />
    </DashCard>
    <DashCard
      title="端口偏离度评分"
      :source="[`异常端口 ${data.abnormal_ports.length} 个`]"
    >
      <DashBars
        :items="data.port_deviation.map((item) => ({ value: item.value, count: item.deviation }))"
        prefix="端口 "
        suffix=" ×"
        :max="4"
      />
    </DashCard>
    <DashCard title="包长五段分布" source="按包长区间统计">
      <DashColumns :items="data.flow_segments" :height="180" />
    </DashCard>
  </div>

  <DashCard title="最近告警" source="最近告警记录，最多 20 条">
    <DashEvents :items="data.recent_events" />
  </DashCard>
</template>
