<script setup lang="ts">
/**
 * AdminOverviewPage —— 平台运行总览（最外层管理员首页）。
 * 数据来自 /dashboard/admin/overview，字段口径见 docs/首页字段口径说明.md。
 *
 * 口径要点（docs/首页字段口径说明.md 第 6 条）：
 * - 有效数据集 / 有效样本量按「同源衍生只计一次」去重（carrier 三份算 1 个数据集）；
 * - 运行态指标来自 risk_event / inference_record / app_user 真实表，跑推理前为 0。
 */
import { onMounted, ref } from 'vue';
import { getAdminDashboard, type DashboardOverview } from '@/api/dashboardApi';
import DashShell from '@/components/dashboard/DashShell.vue';
import DashKpis from '@/components/dashboard/DashKpis.vue';
import DashCard from '@/components/dashboard/DashCard.vue';
import DashColumns from '@/components/dashboard/DashColumns.vue';
import DashRows from '@/components/dashboard/DashRows.vue';
import { fmtInt, fmtPercent } from '@/components/dashboard/dashFormat';

const loading = ref(true);
const error = ref('');
const data = ref<DashboardOverview | null>(null);

const load = async () => {
  loading.value = true;
  error.value = '';
  try {
    data.value = await getAdminDashboard();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '首页数据加载失败';
  } finally {
    loading.value = false;
  }
};

onMounted(load);
</script>

<template>
  <DashShell
    eyebrow="Admin · Platform"
    title="平台运行总览 · 管理端"
    subtitle="数据规模与运行态指标"
    badge="实时数据"
    :loading="loading"
    :error="error"
    @retry="load"
  >
    <template v-if="data">
      <DashKpis
        :items="[
          { label: '接入场景', value: data.totals.scenario_count, unit: '个', tone: 'primary', sub: '已接入场景' },
          { label: '有效数据集', value: data.totals.effective_dataset_count, unit: '个', tone: 'success', sub: '同源文件已去重' },
          { label: '有效样本量', value: data.totals.effective_sample_count, unit: '条', tone: 'warning', sub: '去重后统计' },
          { label: '可用算法', value: data.totals.algorithm_count, unit: '种', tone: 'purple', sub: '已注册算法' },
        ]"
      />

      <div class="d-grid2">
        <DashCard title="各场景有效样本量" source="同源衍生文件只计一次">
          <DashColumns :items="data.scenarios.map((s) => ({ label: s.name.replace('态势', ''), value: s.effective_sample_count }))" />
        </DashCard>
        <DashCard title="各场景数据集数量" source="按场景统计数据集数量（同源去重）">
          <DashColumns :items="data.scenarios.map((s) => ({ label: s.name.replace('态势', ''), value: s.dataset_count }))" />
        </DashCard>
      </div>

      <div class="d-grid2">
        <DashCard title="各场景风险样本占比（%）" source="按各数据集标签字段全量统计（同源去重）">
          <DashColumns
            :items="data.scenarios.map((s) => ({ label: s.name.replace('态势', ''), value: Number((s.risk_rate * 100).toFixed(1)) }))"
            :percent-value="true"
          />
        </DashCard>
        <DashCard title="场景运行清单" source="场景与数据集聚合">
          <DashRows
            :rows="data.scenarios.map((s) => ({
              label: `${s.name} · ${s.access_status === 'ACTUAL' ? '已接入' : '未接入'}`,
              value: `${fmtInt(s.effective_sample_count)} 条 · ${s.dataset_count} 个数据集 · 风险占比 ${fmtPercent(s.risk_rate)}`,
            }))"
          />
        </DashCard>
      </div>

      <DashCard
        title="运行态指标"
        wide
        :source="[
          '风险事件当前为 ' + fmtInt(data.runtime.risk_event_count) + ' 条，尚无事件时前两项为 0。',
        ]"
      >
        <DashKpis
          :items="[
            { label: '风险事件总数', value: data.runtime.risk_event_count, unit: '条', tone: 'gray', sub: '累计风险事件' },
            { label: '待处置', value: data.runtime.pending_event_count, unit: '条', tone: 'gray', sub: '待处置' },
            { label: '推理记录', value: data.runtime.inference_count, unit: '条', tone: 'gray', sub: '累计推理记录' },
            { label: '账号总数', value: data.runtime.user_count, unit: '个', tone: 'gray', sub: '平台账号' },
          ]"
        />
      </DashCard>
    </template>
  </DashShell>
</template>
