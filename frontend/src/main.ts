import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import './style.css';
import router from './router';
import { useUserStore } from '@/stores/userStore';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

const app = createApp(App);
const pinia = createPinia();
app.use(pinia).use(router).use(ElementPlus);

const userStore = useUserStore(pinia);
userStore.bootstrap().finally(() => app.mount('#app'));
