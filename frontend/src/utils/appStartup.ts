import type { App } from 'vue';
import type { Router } from 'vue-router';
import type { useUserStore } from '@/stores/userStore';
import { setUnauthorizedHandler } from './request';

/** 恢复会话后再安装路由，保留直接打开的业务地址；恢复失败也要挂载可登录的应用。 */
export const startApplication = async (
  app: App,
  router: Router,
  userStore: ReturnType<typeof useUserStore>,
): Promise<void> => {
  await userStore.bootstrap();
  app.use(router);
  setUnauthorizedHandler(() => {
    const current = router.currentRoute.value;
    // 错误登录的 401 交给表单；已登录会话失效时先清 Store，避免守卫重新落到首页。
    if (userStore.currentUser) userStore.expireSession();
    if (current.path === '/login') return;
    void router.replace({ path: '/login', query: { redirect: current.fullPath } });
  });
  app.mount('#app');
};
