import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './style.css';
import router from './router';
import { useUserStore } from '@/stores/userStore';
import { startApplication } from '@/utils/appStartup';

// Element Plus 按需引入（配置见 vite.config.ts 的 ElementPlusResolver）：
import 'element-plus/theme-chalk/base.css';
import 'element-plus/theme-chalk/el-overlay.css';
import 'element-plus/theme-chalk/el-message.css';
import 'element-plus/theme-chalk/el-message-box.css';
import 'element-plus/theme-chalk/el-notification.css';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);

const userStore = useUserStore(pinia);
void startApplication(app, router, userStore);
