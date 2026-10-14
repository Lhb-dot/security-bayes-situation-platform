import { createApp } from 'vue';
import AdminOverviewPreview from '@/views/Home/dashboard/AdminOverviewPreview.vue';
import '@/style.css';

// 独立设计入口，不接入正式路由，不依赖登录会话，不请求或写入后台数据。
createApp(AdminOverviewPreview).mount('#app');
