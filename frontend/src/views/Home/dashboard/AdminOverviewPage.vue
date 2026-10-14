<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { getAdminDashboard } from '@/api/dashboardApi';
import { useUserStore } from '@/stores/userStore';
import AdminOverviewDashboard from './AdminOverviewDashboard.vue';
import { mapAdminOverview, type AdminOverviewData } from './adminOverview';

const router = useRouter();
const userStore = useUserStore();
const overview = ref<AdminOverviewData | null>(null);
const loading = ref(false);
const error = ref('');
const loggingOut = ref(false);
const lastUpdated = ref<Date | null>(null);
const lastUpdatedFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
});
const statusTitle = computed(() => {
  const updated = lastUpdated.value ? `上次成功更新：${lastUpdatedFormatter.format(lastUpdated.value)}（北京时间）。` : '';
  return error.value
    ? `${error.value}。${overview.value ? '当前展示上次成功读取的数据。' : ''}${updated}点击重试。`
    : `${updated}点击刷新平台实时数据。`;
});
let mounted = false;
let revision = 0;
let controller: AbortController | null = null;
let refreshTimer: number | undefined;
const cancelPending = () => {
  revision += 1;
  controller?.abort();
  controller = null;
  loading.value = false;
};
const loadOverview = async () => {
  if (!mounted || !userStore.isSuperAdmin || loading.value || loggingOut.value) return;
  const requestRevision = ++revision;
  const requestController = new AbortController();
  controller = requestController;
  loading.value = true;
  const isCurrent = () => mounted && requestRevision === revision && !requestController.signal.aborted && userStore.isSuperAdmin;
  try {
    const payload = await getAdminDashboard({ signal: requestController.signal });
    if (!isCurrent()) return;
    overview.value = mapAdminOverview(payload);
    lastUpdated.value = new Date();
    error.value = '';
  } catch (err) {
    if (!isCurrent()) return;
    // 刷新失败保留上次成功的数据，并由顶部状态明确标记，避免看板闪空。
    error.value = err instanceof Error ? err.message : '平台数据读取失败，请稍后重试';
  } finally {
    if (requestRevision === revision) {
      loading.value = false;
      controller = null;
    }
  }
};
const refreshWhenVisible = () => {
  if (document.visibilityState === 'visible') void loadOverview();
};
watch(() => [userStore.currentUser?.user_id, userStore.currentUser?.role] as const, () => {
  cancelPending();
  overview.value = null;
  lastUpdated.value = null;
  error.value = '';
  if (mounted) void loadOverview();
});
onMounted(() => {
  mounted = true;
  void loadOverview();
  refreshTimer = window.setInterval(refreshWhenVisible, 15_000);
  document.addEventListener('visibilitychange', refreshWhenVisible);
});
onUnmounted(() => {
  mounted = false;
  cancelPending();
  if (refreshTimer !== undefined) window.clearInterval(refreshTimer);
  document.removeEventListener('visibilitychange', refreshWhenVisible);
});
const navigate = async (href: string) => {
  try {
    await router.push(href);
  } catch {
    ElMessage.error('页面跳转失败，请稍后重试');
  }
};
const logout = async () => {
  if (loggingOut.value) return;
  loggingOut.value = true;
  cancelPending();
  try {
    await userStore.logout();
  } catch {
    // store 已清除本地身份；服务端断线时也必须结束当前管理员视图。
    ElMessage.warning('退出请求未完成，已返回登录页');
  } finally {
    try {
      await router.replace('/login');
    } catch {
      ElMessage.error('登录页加载失败，请刷新页面重试');
    } finally {
      loggingOut.value = false;
    }
  }
};
</script>

<template>
  <AdminOverviewDashboard
    :data="overview"
    :loading="loading"
    :error="error"
    :status-title="statusTitle"
    :role="userStore.currentUser?.role ?? null"
    :user-name="userStore.currentUser?.display_name || userStore.currentUser?.username || '系统管理员'"
    :logging-out="loggingOut"
    @refresh="loadOverview"
    @navigate="navigate"
    @logout="logout"
  />
</template>
