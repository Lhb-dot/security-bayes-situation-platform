import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './style.css';
import router from './router';
import { useUserStore } from '@/stores/userStore';

// Element Plus 按需引入（配置见 vite.config.ts 的 ElementPlusResolver）：
// 组件与其样式由 unplugin-vue-components 在编译期自动注入，这里不再
// `app.use(ElementPlus)`，也不再引入 element-plus/dist/index.css 全量样式。
//
// 但 ElMessage / ElMessageBox 在 11 个文件里是**显式 import** 的服务式调用，
// 不会被 AutoImport 接管，样式也不会被自动注入 —— 必须在此显式引入，
// 否则消息提示与确认弹窗会变成无样式裸文本。
import 'element-plus/theme-chalk/base.css';
import 'element-plus/theme-chalk/el-message.css';
import 'element-plus/theme-chalk/el-message-box.css';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia).use(router);

const userStore = useUserStore(pinia);
userStore.bootstrap().finally(() => app.mount('#app'));
