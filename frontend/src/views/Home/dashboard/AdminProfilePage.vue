<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { getScenarioProfile, getScenarioWorkspace, type ScenarioProfile, type ScenarioWorkspace } from '@/api/dashboardApi';
import { getScenarioList, resolveScenarioId, type ApiScenario } from '@/api/scenarioApi';
import { getUserList } from '@/api/userApi';
import { useUserStore } from '@/stores/userStore';
import ScenarioScreenDashboard from './scenarioScreen/ScenarioScreenDashboard.vue';

const props = defineProps<{ scenarioRef: string }>();
const router = useRouter();
const userStore = useUserStore();
const profile = ref<ScenarioProfile | null>(null);
const runtime = ref<ScenarioWorkspace | null>(null);
const scenarios = ref<ApiScenario[]>([]);
const members = ref<{ total: number; enabled: number; disabled: number } | null>(null);
const loading = ref(false);
const error = ref('');
const runtimeError = ref('');
const memberError = ref('');
const sceneError = ref('');
const loggingOut = ref(false);
const updatedAt = ref('');
const statusError = computed(() => error.value || runtimeError.value || memberError.value || sceneError.value);
let mounted = false;
let revision = 0;
let controller: AbortController | null = null;
let timer: number | undefined;
const cancel = () => { revision += 1; controller?.abort(); controller = null; loading.value = false; };
const errorText = (err: unknown, fallback: string) => err instanceof Error ? err.message : fallback;

async function load() {
  if (!mounted || loading.value || loggingOut.value || !userStore.isManagement) return;
  const currentRevision = ++revision;
  const requestController = new AbortController();
  controller = requestController;
  loading.value = true;
  const current = () => mounted && currentRevision === revision && !requestController.signal.aborted;
  const options = { signal: requestController.signal };
  try {
    // 数字 ID 只解析一次，画像和运行接口始终指向同一场景。
    const id = await resolveScenarioId(props.scenarioRef);
    if (!current()) return;
    const tasks: Promise<unknown>[] = [
      getScenarioProfile(id, options).then(result => {
        if (!current()) return;
        profile.value = result;
        error.value = '';
        updatedAt.value = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
      }).catch(err => { if (current()) error.value = errorText(err, '场景画像读取失败'); }),
      getScenarioWorkspace(id, options).then(result => {
        if (!current()) return;
        // 后端明细策略中系统管理员只看本人，旧接口的 self_only 未涵盖该角色。
        runtime.value = userStore.isSuperAdmin
          ? { ...result, scope: { ...result.scope, self_only: true } }
          : result;
        runtimeError.value = '';
      }).catch(err => { if (current()) { runtime.value = null; runtimeError.value = errorText(err, '运行统计读取失败'); } }),
      getScenarioList(options).then(result => { if (current()) { scenarios.value = result; sceneError.value = ''; } })
        .catch(err => { if (current()) sceneError.value = errorText(err, '场景列表读取失败'); }),
    ];
    if (userStore.isScenarioAdmin) {
      // /users 对场景管理员仅返回本场景普通用户；使用 total 而不是当前页长度。
      tasks.push(Promise.all([
        getUserList({ scenario_id: id, role: 'SCENARIO_USER', page_size: 1 }, options),
        getUserList({ scenario_id: id, role: 'SCENARIO_USER', page_size: 1, status: 'ENABLED' }, options),
        getUserList({ scenario_id: id, role: 'SCENARIO_USER', page_size: 1, status: 'DISABLED' }, options),
      ]).then(([all, enabled, disabled]) => {
        if (!current()) return;
        members.value = { total: all.total, enabled: enabled.total, disabled: disabled.total };
        memberError.value = '';
      }).catch(err => { if (current()) { members.value = null; memberError.value = errorText(err, '场景用户统计读取失败'); } }));
    }
    await Promise.allSettled(tasks);
  } catch (err) {
    if (current()) error.value = errorText(err, '场景数据读取失败');
  } finally {
    if (current()) { loading.value = false; controller = null; }
  }
}
const refreshVisible = () => { if (document.visibilityState === 'visible') void load(); };
watch(() => [props.scenarioRef, userStore.currentUser?.user_id, userStore.currentUser?.role], () => {
  cancel();
  profile.value = null; runtime.value = null; members.value = null; scenarios.value = [];
  error.value = ''; runtimeError.value = ''; memberError.value = ''; sceneError.value = ''; updatedAt.value = '';
  void load();
});
onMounted(() => {
  mounted = true;
  void load();
  timer = window.setInterval(refreshVisible, 30_000);
  document.addEventListener('visibilitychange', refreshVisible);
});
onUnmounted(() => {
  mounted = false;
  cancel();
  window.clearInterval(timer);
  document.removeEventListener('visibilitychange', refreshVisible);
});
async function navigate(href: string) {
  try { await router.push(href); } catch { ElMessage.error('页面跳转失败，请稍后重试'); }
}
async function logout() {
  if (loggingOut.value) return;
  loggingOut.value = true;
  cancel();
  try { await userStore.logout(); } catch { ElMessage.warning('退出请求未完成，已清除本地登录状态'); }
  finally {
    try { await router.replace('/login'); } catch { ElMessage.error('登录页加载失败，请刷新页面'); }
    loggingOut.value = false;
  }
}
</script>

<template>
  <ScenarioScreenDashboard
    :data="profile" :runtime="runtime" :scenarios="scenarios" :members="members"
    :role="userStore.currentUser?.role ?? null" :user-name="userStore.currentUser?.display_name || userStore.currentUser?.username || ''"
    :loading="loading" :error="statusError" :runtime-error="runtimeError" :member-error="memberError"
    :logging-out="loggingOut" :updated-at="updatedAt"
    @refresh="load" @navigate="navigate" @logout="logout"
  />
</template>
