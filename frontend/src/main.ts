import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './style.css';
// 新增：导入路由
import router from './router';

// ========== 下面两行是新增Element Plus全局注册代码 ==========
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

// 挂载 Pinia + 路由 + ElementPlus
createApp(App).use(createPinia()).use(router).use(ElementPlus).mount('#app');
