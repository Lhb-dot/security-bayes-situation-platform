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
app.use(pinia);

// 会话恢复期间若 401，request.js 的响应拦截器会把 hash 直接改成 #/login，
// 抹掉用户原本要去的深链。先记下来，装路由前还原 —— 让守卫自己产出 /login?redirect=<原目标>，
// 否则登录后回不到用户本来想打开的页面。
const initialHash = window.location.hash;

// 顺序要紧：vue-router 在 install 时就会发起首次导航，守卫要读 userStore.currentUser。
// 若先 use(router) 再 bootstrap，首次导航跑在会话恢复完成之前，守卫读到 null，
// 于是把用户直接请求的深链（如 #/reports）改写成 /login —— 所以必须等 bootstrap 落地后再装路由。
const userStore = useUserStore(pinia);
userStore.bootstrap().finally(() => {
  if (window.location.hash !== initialHash) window.location.hash = initialHash;
  app.use(router);
  app.mount('#app');
});
