import { createApp, h } from 'vue';
import { createPinia } from 'pinia';
import { createMemoryHistory, createRouter } from 'vue-router';
import AdminOverviewDashboard from '@/views/Home/dashboard/AdminOverviewDashboard.vue';
import '@/style.css';
import '@/components/dashboard/dash.css';

// 仅供独立设计预览使用的历史快照；正式首页仍从后端接口读取实时数据。
const previewOverview = {
  scenarioCount: 4,
  datasetCount: 9,
  sampleCount: 50345,
  algorithmCount: 6,
  trainedModels: null,
  publishedModels: 6,
  inferenceCount: 3,
  reportCount: null,
  servedUserCount: null,
  eventCount: 0,
  pendingCount: 0,
  processingCount: 0,
  resolvedCount: 0,
  userCount: 6,
  scenes: [
    { key: 'network' as const, name: '网络安全', shortName: '网络', path: '/scenarios/network_security/dashboard', userCount: null, adminCount: null, datasets: 2, samples: 31453, trainedModels: null, publishedModels: null, inferences: null, events: null, pending: null, riskRate: 0.142 },
    { key: 'power' as const, name: '电力系统', shortName: '电力', path: '/scenarios/power_system/dashboard', userCount: null, adminCount: null, datasets: 1, samples: 2000, trainedModels: null, publishedModels: null, inferences: null, events: null, pending: null, riskRate: 0.797 },
    { key: 'flight_deck' as const, name: '航保作业', shortName: '航保', path: '/scenarios/flightdeck_operation/dashboard', userCount: null, adminCount: null, datasets: 1, samples: 507, trainedModels: null, publishedModels: null, inferences: null, events: null, pending: null, riskRate: 0.254 },
    { key: 'geological' as const, name: '滑坡灾害', shortName: '滑坡', path: '/scenarios/geological_risk/dashboard', userCount: null, adminCount: null, datasets: 5, samples: 16385, trainedModels: null, publishedModels: null, inferences: null, events: null, pending: null, riskRate: 0.28 },
  ],
};

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/', component: { render: () => null } }],
});

const app = createApp({
  render: () => h('div', [
    h(AdminOverviewDashboard, { data: previewOverview, preview: true }),
    h('div', { class: 'preview-note' }, '设计预览 · 历史快照数据'),
  ]),
});
app.use(createPinia());
app.use(router);
app.mount('#app');
