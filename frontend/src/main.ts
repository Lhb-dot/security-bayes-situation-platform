import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './style.css';
import router from './router';
import { useUserStore } from '@/stores/userStore';
import { setUnauthorizedHandler } from '@/utils/request';

// Element Plus 按需引入（配置见 vite.config.ts 的 ElementPlusResolver）：
// 组件与其样式由 unplugin-vue-components 在编译期自动注入，这里不再
// `app.use(ElementPlus)`，也不再引入 element-plus/dist/index.css 全量样式。
//
// 但 ElMessage / ElMessageBox / ElNotification 在若干文件里是**显式 import** 的服务式调用，
// 不会被 AutoImport 接管，样式也不会被自动注入 —— 必须在此显式引入，
// 否则消息提示、确认弹窗与后台任务完成通知会变成无样式裸文本。
import 'element-plus/theme-chalk/base.css';
import 'element-plus/theme-chalk/el-message.css';
import 'element-plus/theme-chalk/el-message-box.css';
import 'element-plus/theme-chalk/el-notification.css';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);

// 顺序要紧：vue-router 在 install 时就会发起首次导航，守卫要读 userStore.currentUser。
// 若先 use(router) 再 bootstrap，首次导航跑在会话恢复完成之前，守卫读到 null，
// 于是把用户直接请求的深链（如 /reports）改写成 /login —— 所以必须等 bootstrap 落地后再装路由。
const userStore = useUserStore(pinia);
userStore.bootstrap().finally(() => {
  app.use(router);
  // 会话中途 401（cookie 过期）由这里接管跳转，request.js 只负责清凭据。
  setUnauthorizedHandler(() => {
    const current = router.currentRoute.value;
    if (current.path === '/login') return;
    router.replace({ path: '/login', query: { redirect: current.fullPath } });
  });
  app.mount('#app');
});
