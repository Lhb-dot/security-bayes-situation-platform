<script setup lang="ts">
import AdminOverviewDashboard from './AdminOverviewDashboard.vue';
import type { AdminOverviewData } from './adminOverview';

// 仅供独立预览；正式组件不导入本文件，不会用快照填补接口缺失数据。
const previewOverview: AdminOverviewData = {
  scenarioCount: 4, datasetCount: 9, sampleCount: 50345, algorithmCount: 6,
  trainedModels: 12, publishedModels: 6, inferenceCount: 128, reportCount: 16,
  servedUserCount: 18, eventCount: 18, pendingCount: 6, processingCount: 4, resolvedCount: 8, userCount: 24,
  scenes: [
    { key: 'network', name: '网络安全', path: '/scenarios/network_security/dashboard', samples: 31453, datasets: 2, userCount: 8, adminCount: 1, riskRate: .142 },
    { key: 'power', name: '电力系统', path: '/scenarios/power_system/dashboard', samples: 2000, datasets: 1, userCount: 6, adminCount: 1, riskRate: .797 },
    { key: 'flight_deck', name: '舰面调度', path: '/scenarios/flightdeck_operation/dashboard', samples: 507, datasets: 1, userCount: 3, adminCount: 1, riskRate: .254 },
    { key: 'geological', name: '地质风险', path: '/scenarios/geological_risk/dashboard', samples: 16385, datasets: 5, userCount: 2, adminCount: 1, riskRate: .28 },
  ],
};
</script>

<template>
  <AdminOverviewDashboard :data="previewOverview" preview />
</template>
