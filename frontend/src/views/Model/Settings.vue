<script setup lang="ts">
/**
 * Settings — 设置（普通用户）/ 系统设置（管理员）
 *
 * 布局对齐 settings-demo/index.html：
 * - 顶部横向页签：账号与安全 / 基础设置 / 风险阈值 / 场景管理（按角色过滤可见性）
 * - 每个页签内容为左右两栏卡片；需要横向空间的卡片用 .settings-section--span 占满整行
 *
 * 功能口径保持不变：
 * - 普通用户：账号与安全（账号信息 + 改密）、基础设置（自动刷新 + 模型解释服务）
 * - 管理员：额外可见风险阈值（按账号 + 场景，[0,1]、high>medium、变更日志）；系统管理员额外可见场景启停
 */
import { computed, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { syncThreshold } from '@/services/mockApi';
import {
  getRiskThresholdAuditLogs,
  getRiskThresholds,
  updateRiskThreshold,
} from '@/api/riskThresholdApi';
import { useSettingsStore } from '@/stores/settingsStore';
import { useUserStore } from '@/stores/userStore';
import { getAISetting, testAISetting, updateAISetting, type AISetting } from '@/api/aiSettingApi';
import type { ScenarioId, ThresholdChangeLog, ThresholdConfig, UserAccount } from '@/types/security';

const userStore = useUserStore();
const settingsStore = useSettingsStore();
const router = useRouter();
const currentUser = ref<UserAccount | null>(null);
const isScenarioAdmin = computed(() => currentUser.value?.role === 'SCENARIO_ADMIN');
const isSuperAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN');
const isAdmin = computed(() => isSuperAdmin.value || isScenarioAdmin.value);
/** 阈值可配置场景：系统管理员=全部；其他账号=绑定场景（后端按绑定场景放行） */
const canConfigureThresholds = computed(() => isSuperAdmin.value || !!currentUser.value?.scenario_code);

const SCENARIO_LABEL: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板作业',
  geological_risk: '地质风险',
};
const ROLE_LABEL: Record<string, string> = {
  SUPER_ADMIN: '系统管理员',
  SCENARIO_ADMIN: '场景管理员',
  SCENARIO_USER: '场景用户',
};

// ===================== 页签 =====================
type TabKey = 'account' | 'general' | 'threshold' | 'scenario';
const activeTab = ref<TabKey>('account');
const tabs = computed<{ key: TabKey; label: string }[]>(() => {
  const list: { key: TabKey; label: string }[] = [
    { key: 'account', label: '账号与安全' },
    { key: 'general', label: '基础设置' },
  ];
  if (canConfigureThresholds.value) list.push({ key: 'threshold', label: '风险阈值' });
  if (isSuperAdmin.value) list.push({ key: 'scenario', label: '场景管理' });
  return list;
});
// 当前页签被角色隐藏时，自动落到第一个可见页签
watch(tabs, list => {
  if (!list.some(t => t.key === activeTab.value)) activeTab.value = list[0]?.key ?? 'account';
});

// ===================== 账号信息 =====================
const accountRoleLabel = computed(() => ROLE_LABEL[currentUser.value?.role ?? ''] ?? '-');
const accountRoleBadge = computed(() => {
  const role = currentUser.value?.role;
  if (role === 'SUPER_ADMIN') return 'role-badge--super';
  if (role === 'SCENARIO_USER') return 'role-badge--user';
  return 'role-badge--admin';
});
const accountScenarioLabel = computed(() => {
  if (isSuperAdmin.value) return '全部场景（不绑定）';
  const code = currentUser.value?.scenario_code;
  return code ? (SCENARIO_LABEL[code] ?? code) : '未绑定场景';
});
const accountEnabled = computed(() => currentUser.value?.status !== 'disabled');

// ===================== 修改密码（弹窗） =====================
const pwdDialogVisible = ref(false);
const pwdForm = ref({ oldPassword: '', newPassword: '', confirm: '' });
const changingPwd = ref(false);

const openPwdDialog = () => {
  pwdForm.value = { oldPassword: '', newPassword: '', confirm: '' };
  pwdDialogVisible.value = true;
};

const changePwd = async () => {
  if (!pwdForm.value.oldPassword || !pwdForm.value.newPassword) {
    ElMessage.warning('请填写原密码与新密码');
    return;
  }
  if (pwdForm.value.newPassword !== pwdForm.value.confirm) {
    ElMessage.warning('两次输入的新密码不一致');
    return;
  }
  changingPwd.value = true;
  try {
    await userStore.changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword);
    ElMessage.success('密码修改成功，请重新登录');
    pwdDialogVisible.value = false;
    pwdForm.value = { oldPassword: '', newPassword: '', confirm: '' };
    await userStore.logout();
    router.push('/login');
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '修改失败');
  } finally {
    changingPwd.value = false;
  }
};

// ===================== 自动刷新（个人设置） =====================
const savePersonalSettings = () => {
  settingsStore.saveRefreshSettings();
  ElMessage.success('个人设置已保存');
};

// ===================== 模型解释服务 =====================
const aiSetting = ref<AISetting | null>(null);
const savingAI = ref(false);
const testingAI = ref(false);
const togglingAI = ref(false);
const aiDialogVisible = ref(false);
/** 编辑弹窗临时表单：取消不影响已保存配置；api_key 留空表示保留服务端已保存的 key。 */
const aiEditForm = ref({
  provider: 'openai-compatible',
  base_url: '',
  model: '',
  api_key: '',
});

/** 只读展示行：未配置的字段统一显示「未填入」，key 只显示服务端下发的掩码。 */
const aiReadonlyRows = computed(() => [
  { label: '接口地址', value: aiSetting.value?.base_url?.trim() ?? '' },
  { label: '模型名称', value: aiSetting.value?.model?.trim() ?? '' },
  { label: 'API key', value: aiSetting.value?.api_key_masked?.trim() ?? '' },
]);

const loadAISetting = async () => {
  try {
    aiSetting.value = await getAISetting();
  } catch {
    aiSetting.value = null;
  }
};

const openAIEdit = () => {
  aiEditForm.value = {
    provider: aiSetting.value?.provider ?? 'openai-compatible',
    base_url: aiSetting.value?.base_url ?? '',
    model: aiSetting.value?.model ?? '',
    api_key: '',
  };
  aiDialogVisible.value = true;
};

/** 卡片上的「启用 AI 解释」开关：直接落库，失败保持原状态。 */
const toggleAI = async () => {
  const s = aiSetting.value;
  if (!s?.configured || togglingAI.value) return;
  togglingAI.value = true;
  try {
    const next = await updateAISetting({
      provider: s.provider ?? 'openai-compatible',
      base_url: s.base_url ?? '',
      model: s.model ?? '',
      enabled: !s.enabled,
    });
    aiSetting.value = next;
    ElMessage.success(next.enabled ? '已开启 AI 解释' : '已关闭 AI 解释');
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : 'AI 解释开关保存失败');
  } finally {
    togglingAI.value = false;
  }
};

const saveAI = async () => {
  const { base_url, model, api_key } = aiEditForm.value;
  if (!base_url.trim() || !model.trim()) {
    ElMessage.warning('请填写 AI 服务地址和模型名称');
    return;
  }
  if (!api_key.trim() && !aiSetting.value?.configured) {
    ElMessage.warning('首次配置需填写 API key');
    return;
  }
  savingAI.value = true;
  try {
    const payload: {
      provider: string;
      base_url: string;
      model: string;
      enabled: boolean;
      api_key?: string;
    } = {
      provider: aiEditForm.value.provider,
      base_url: base_url.trim(),
      model: model.trim(),
      enabled: aiSetting.value?.enabled ?? true,
    };
    // key 留空 = 不修改服务端已保存的 key
    if (api_key.trim()) payload.api_key = api_key.trim();
    aiSetting.value = await updateAISetting(payload);
    aiDialogVisible.value = false;
    ElMessage.success(
      api_key.trim()
        ? 'AI 设置已保存，API key 仅在服务端保存'
        : 'AI 设置已保存，API key 保持不变',
    );
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : 'AI 设置保存失败');
  } finally {
    savingAI.value = false;
  }
};

const testAI = async () => {
  testingAI.value = true;
  try {
    const result = await testAISetting();
    if (result.connected) ElMessage.success(result.message);
    else ElMessage.warning(result.message);
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : 'AI 连通性测试失败');
  } finally {
    testingAI.value = false;
  }
};

// ===================== 风险阈值 =====================
const activeScenarios = computed<ScenarioId[]>(() =>
  currentUser.value?.role === 'SUPER_ADMIN'
    ? ['network_security', 'power_system', 'flightdeck_operation', 'geological_risk']
    : currentUser.value?.scenario_code
      ? [currentUser.value.scenario_code]
      : []
);
const thresholds = ref<ThresholdConfig[]>([]);
const changeLogs = ref<ThresholdChangeLog[]>([]);
const showChangeLogs = ref(false);
const saving = ref(false);
/** 阈值长条框当前选中场景：系统管理员可切换，其余账号固定为绑定场景 */
const thresholdScenario = ref<ScenarioId>('network_security');
const editing = ref<Record<string, { medium: number | null; high: number | null }>>({
  network_security: { medium: null, high: null },
  power_system: { medium: null, high: null },
  flightdeck_operation: { medium: null, high: null },
  geological_risk: { medium: null, high: null },
});

const loadThresholds = async () => {
  const ths = await getRiskThresholds();
  thresholds.value = ths.map(t => ({
    ...t,
    medium_threshold: Number(t.medium_threshold ?? 0),
    high_threshold: Number(t.high_threshold ?? 0),
  }));
  const nextEditing: Record<string, { medium: number | null; high: number | null }> = {};
  for (const scenarioId of activeScenarios.value) {
    nextEditing[scenarioId] = { medium: null, high: null };
  }
  for (const t of thresholds.value) {
    nextEditing[t.scenario_id] = {
      medium: Number(t.medium_threshold),
      high: Number(t.high_threshold),
    };
  }
  editing.value = nextEditing;
  const firstScenario = activeScenarios.value[0];
  if (firstScenario) thresholdScenario.value = firstScenario; else thresholdScenario.value = 'network_security';
};

const loadChangeLogs = async () => {
  try {
    changeLogs.value = await getRiskThresholdAuditLogs();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '阈值修改记录加载失败');
  }
};

const toFixed2 = (v: number | string | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '-';
  return Number(v).toFixed(2);
};

const saveScenarioThreshold = async (scenarioId: ScenarioId) => {
  const e = editing.value[scenarioId];
  if (!e || e.medium === null || e.high === null || e.medium < 0 || e.medium > 1 || e.high < 0 || e.high > 1) {
    ElMessage.warning('阈值必须位于 [0,1] 范围内');
    return;
  }
  if (e.high <= e.medium) {
    ElMessage.warning('高风险阈值必须大于中风险阈值');
    return;
  }
  if (Math.round(e.medium * 100) / 100 !== e.medium || Math.round(e.high * 100) / 100 !== e.high) {
    ElMessage.warning('阈值最多只能有两位小数');
    return;
  }
  saving.value = true;
  try {
    const medium = Math.round(e.medium * 100) / 100;
    const high = Math.round(e.high * 100) / 100;
    const saved = await updateRiskThreshold(scenarioId, { medium_threshold: medium, high_threshold: high });
    editing.value[scenarioId] = {
      medium: Number(Number(saved.medium_threshold).toFixed(2)),
      high: Number(Number(saved.high_threshold).toFixed(2)),
    };
    syncThreshold(saved);
    ElMessage.success(`「${SCENARIO_LABEL[scenarioId]}」阈值已保存并实时生效`);
    await loadThresholds();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败');
  } finally {
    saving.value = false;
  }
};

// ===================== 场景启停（系统管理员） =====================
const scenarioSwitches = ref([
  { id: 'network_security', label: '网络安全态势感知', enabled: true },
  { id: 'power_system', label: '电力系统风险态势感知', enabled: true },
  { id: 'geological_risk', label: '地质风险态势感知', enabled: true },
]);

const saveAdminSettings = () => {
  settingsStore.saveRefreshSettings();
  ElMessage.success('系统设置已保存');
};

onMounted(async () => {
  currentUser.value = userStore.currentUser;
  settingsStore.loadForUser(currentUser.value?.user_id);
  await loadAISetting();
  if (canConfigureThresholds.value) await loadThresholds();
});
</script>

<template>
  <div class="settings-page">
    <div class="settings-page__header">
      <div>
        <p class="eyebrow">{{ isAdmin ? 'System Settings' : 'My Settings' }}</p>
        <h2>{{ isAdmin ? '系统设置' : '设置' }}</h2>
        <p v-if="isAdmin" class="settings-page__desc">风险阈值按当前账号和场景配置，其余为全局基础参数</p>
        <p v-else class="settings-page__desc">选择你感兴趣的场景（可多选），其它页面将实时更新；下方为个人设置</p>
      </div>
    </div>

    <!-- ==================== 横向页签 ==================== -->
    <nav class="settings-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        class="settings-tab"
        :class="{ 'is-active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- ==================== 账号与安全 ==================== -->
    <div class="settings-panel" :class="{ 'is-active': activeTab === 'account' }">
      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Account</p>
            <h3>账号信息</h3>
          </div>
        </div>
        <div class="detail-info">
          <div>
            <span>用户名</span>
            <strong>{{ currentUser?.username ?? '-' }}</strong>
          </div>
          <div>
            <span>角色</span>
            <strong><span class="role-badge" :class="accountRoleBadge">{{ accountRoleLabel }}</span></strong>
          </div>
          <div>
            <span>绑定场景</span>
            <strong>
              <span v-if="isSuperAdmin">{{ accountScenarioLabel }}</span>
              <span v-else class="scenario-tag">{{ accountScenarioLabel }}</span>
            </strong>
          </div>
          <div>
            <span>账号状态</span>
            <strong>
              <span class="status-badge" :class="accountEnabled ? 'status-badge--on' : 'status-badge--off'">
                {{ accountEnabled ? '启用' : '停用' }}
              </span>
            </strong>
          </div>
        </div>
      </section>

      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Security</p>
            <h3>安全设置</h3>
          </div>
        </div>
        <div class="settings-form">
          <div class="settings-form__item settings-form__item--row">
            <span class="settings-form__label">登录密码</span>
            <button class="settings-btn settings-btn--primary" @click="openPwdDialog">修改密码</button>
          </div>
        </div>
      </section>
    </div>

    <!-- ==================== 基础设置 ==================== -->
    <div class="settings-panel" :class="{ 'is-active': activeTab === 'general' }">
      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Refresh</p>
            <h3>自动刷新设置</h3>
          </div>
        </div>
        <div class="settings-form">
          <div class="settings-form__item settings-form__item--row">
            <label class="settings-form__label">启用自动刷新</label>
            <button class="settings-switches__toggle" :class="{ 'is-on': settingsStore.autoRefresh }" @click="settingsStore.autoRefresh = !settingsStore.autoRefresh">
              <span class="settings-switches__knob"></span>
            </button>
          </div>
          <div class="settings-form__item">
            <label class="settings-form__label">刷新间隔（秒）</label>
            <select v-model.number="settingsStore.refreshInterval" class="settings-form__input" :disabled="!settingsStore.autoRefresh">
              <option :value="10">10 秒</option>
              <option :value="30">30 秒</option>
              <option :value="60">60 秒</option>
              <option :value="120">120 秒</option>
              <option :value="300">300 秒</option>
            </select>
          </div>
        </div>
        <div class="settings-actions">
          <button class="settings-btn" @click="savePersonalSettings">保存个人设置</button>
        </div>
      </section>

      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">AI Provider</p>
            <h3>模型解释服务</h3>
          </div>
          <span
            class="ai-badge"
            :class="aiSetting?.configured ? 'ai-badge--on' : 'ai-badge--off'"
          >{{ aiSetting?.configured ? '已配置' : '未配置' }}</span>
        </div>

        <div class="detail-info ai-readonly">
          <div v-for="row in aiReadonlyRows" :key="row.label">
            <span>{{ row.label }}</span>
            <strong :class="{ 'detail-info__empty': !row.value }">{{ row.value || '未填入' }}</strong>
          </div>
        </div>

        <div class="settings-switches">
          <div class="settings-switches__item">
            <span class="settings-switches__label">启用 AI 解释</span>
            <button
              class="settings-switches__toggle"
              :class="{ 'is-on': !!aiSetting?.enabled }"
              :disabled="!aiSetting?.configured || togglingAI"
              @click="toggleAI"
            >
              <span class="settings-switches__knob"></span>
            </button>
          </div>
        </div>

        <div class="settings-actions">
          <button class="settings-btn" :disabled="testingAI || !aiSetting?.configured" @click="testAI">{{ testingAI ? '测试中...' : '测试连通性' }}</button>
          <button class="settings-btn settings-btn--primary" @click="openAIEdit">编辑</button>
        </div>
      </section>
    </div>

    <!-- ==================== 风险阈值 ==================== -->
    <div class="settings-panel" :class="{ 'is-active': activeTab === 'threshold' }">
      <section class="card settings-section settings-section--span">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Threshold</p>
            <h3>我的风险阈值</h3>
          </div>
          <button class="settings-btn" type="button" @click="showChangeLogs = true; loadChangeLogs()">
            查看阈值修改记录
          </button>
        </div>

        <div v-if="isSuperAdmin" class="threshold-scenario-pick">
          <label class="settings-form__label">选择场景</label>
          <select v-model="thresholdScenario" class="settings-form__input threshold-scenario-pick__select">
            <option v-for="sc in activeScenarios" :key="sc" :value="sc">{{ SCENARIO_LABEL[sc] ?? sc }}</option>
          </select>
        </div>

        <!-- 阈值长条框：系统管理员可切换场景，其余账号固定为绑定场景 -->
        <div class="threshold-bar">
          <div class="threshold-bar__head">
            <h4>{{ SCENARIO_LABEL[thresholdScenario] ?? thresholdScenario }}</h4>
            <span class="threshold-bar__scene">{{ thresholdScenario }}</span>
          </div>
          <div class="threshold-bar__form">
            <div class="threshold-field">
              <label>中风险阈值（0~1）</label>
              <input v-model.number="editing[thresholdScenario].medium" type="number" min="0" max="1" step="0.01" class="settings-form__input" />
              <span v-if="thresholds.find(t => t.scenario_id === thresholdScenario)?.medium_threshold !== undefined" class="threshold-bar__current">
                当前值：{{ toFixed2(thresholds.find(t => t.scenario_id === thresholdScenario)?.medium_threshold) }}
              </span>
            </div>
            <div class="threshold-field">
              <label>高风险阈值（0~1）</label>
              <input v-model.number="editing[thresholdScenario].high" type="number" min="0" max="1" step="0.01" class="settings-form__input" />
              <span v-if="thresholds.find(t => t.scenario_id === thresholdScenario)?.high_threshold !== undefined" class="threshold-bar__current">
                当前值：{{ toFixed2(thresholds.find(t => t.scenario_id === thresholdScenario)?.high_threshold) }}
              </span>
            </div>
            <p class="threshold-bar__rule">要求：0 ≤ 中风险 &lt; 高风险 ≤ 1</p>
            <button class="settings-btn" :disabled="saving" @click="saveScenarioThreshold(thresholdScenario)">
              {{ saving ? '保存中...' : '保存并生效' }}
            </button>
          </div>
        </div>
      </section>
    </div>

    <!-- ==================== 场景管理（系统管理员） ==================== -->
    <div class="settings-panel" :class="{ 'is-active': activeTab === 'scenario' }">
      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Scenarios</p>
            <h3>场景启停控制</h3>
          </div>
        </div>
        <div class="settings-switches">
          <div v-for="sc in scenarioSwitches" :key="sc.id" class="settings-switches__item">
            <span class="settings-switches__label">{{ sc.label }}</span>
            <button class="settings-switches__toggle" :class="{ 'is-on': sc.enabled }" @click="sc.enabled = !sc.enabled">
              <span class="settings-switches__knob"></span>
            </button>
          </div>
        </div>
        <div class="settings-actions">
          <button class="settings-btn settings-btn--primary" @click="saveAdminSettings">保存全部系统设置</button>
        </div>
      </section>
    </div>

    <!-- ==================== 修改密码弹窗 ==================== -->
    <el-dialog
      v-model="pwdDialogVisible"
      title="修改密码"
      class="pwd-setting-dialog"
      width="480px"
      top="10vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="ai-dialog-form">
        <div class="ai-dialog-field">
          <label class="ai-dialog-field__label">原密码</label>
          <input v-model="pwdForm.oldPassword" type="password" class="ai-dialog-input" autocomplete="current-password" placeholder="请输入原密码" />
        </div>
        <div class="ai-dialog-field">
          <label class="ai-dialog-field__label">新密码</label>
          <input v-model="pwdForm.newPassword" type="password" class="ai-dialog-input" autocomplete="new-password" placeholder="至少 6 位" />
        </div>
        <div class="ai-dialog-field">
          <label class="ai-dialog-field__label">确认新密码</label>
          <input v-model="pwdForm.confirm" type="password" class="ai-dialog-input" autocomplete="new-password" placeholder="再次输入新密码" />
        </div>
      </div>
      <template #footer>
        <el-button @click="pwdDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="changingPwd" @click="changePwd">
          {{ changingPwd ? '提交中...' : '确认修改' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ==================== 阈值修改记录弹窗 ==================== -->
    <el-dialog
      v-model="showChangeLogs"
      title="本账号阈值修改记录"
      class="threshold-log-dialog"
      width="760px"
      top="6vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <el-table
        :data="changeLogs"
        stripe
        max-height="62vh"
        style="width: 100%"
        empty-text="暂无阈值修改记录"
      >
        <el-table-column label="变更时间" min-width="170">
          <template #default="{ row }: { row: ThresholdChangeLog }">
            {{ row.operated_at ?? row.changed_at ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="场景" width="150">
          <template #default="{ row }: { row: ThresholdChangeLog }">
            {{ SCENARIO_LABEL[row.scenario_id] ?? row.scenario_id }}
          </template>
        </el-table-column>
        <el-table-column label="中风险阈值" width="120" align="center">
          <template #default="{ row }: { row: ThresholdChangeLog }">
            {{ toFixed2(row.old_medium ?? row.old_medium_threshold) }} →
            <el-tag type="success" effect="plain">{{ toFixed2(row.new_medium ?? row.new_medium_threshold) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="高风险阈值" width="120" align="center">
          <template #default="{ row }: { row: ThresholdChangeLog }">
            {{ toFixed2(row.old_high ?? row.old_high_threshold) }} →
            <el-tag type="success" effect="plain">{{ toFixed2(row.new_high ?? row.new_high_threshold) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- ==================== 编辑 AI 设置弹窗 ==================== -->
    <el-dialog
      v-model="aiDialogVisible"
      title="编辑 AI 设置"
      class="ai-setting-dialog"
      width="520px"
      top="10vh"
      append-to-body
      :close-on-click-modal="false"
    >
      <div class="ai-dialog-form">
        <div class="ai-dialog-field">
          <label class="ai-dialog-field__label">接口地址</label>
          <input v-model="aiEditForm.base_url" class="ai-dialog-input" placeholder="https://api.openai.com/v1" />
        </div>
        <div class="ai-dialog-field">
          <label class="ai-dialog-field__label">模型名称</label>
          <input v-model="aiEditForm.model" class="ai-dialog-input" placeholder="gpt-4o-mini" />
        </div>
        <div class="ai-dialog-field">
          <label class="ai-dialog-field__label">API key</label>
          <input
            v-model="aiEditForm.api_key"
            type="password"
            class="ai-dialog-input"
            autocomplete="new-password"
            placeholder="留空则保留已保存的 key"
          />
        </div>
      </div>
      <template #footer>
        <el-button @click="aiDialogVisible = false">取消</el-button>
        <el-button type="primary" :disabled="savingAI" @click="saveAI">
          {{ savingAI ? '保存中...' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-page {
  position: relative;
  z-index: 1;
}

.settings-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.settings-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.settings-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

/* ===================== 横向页签 ===================== */
.settings-tabs {
  display: flex;
  align-items: center;
  gap: 30px;
  padding: 0 4px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.14);
  overflow-x: auto;
  scrollbar-width: none;
  margin-bottom: 22px;
}

.settings-tabs::-webkit-scrollbar {
  display: none;
}

.settings-tab {
  position: relative;
  border: 0;
  background: transparent;
  padding: 2px 2px 14px;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
  white-space: nowrap;
  flex: 0 0 auto;
  cursor: pointer;
  transition: color 0.2s;
}

.settings-tab:hover {
  color: #fff;
}

.settings-tab.is-active {
  color: #fff;
  font-weight: 600;
}

.settings-tab.is-active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
}

/* ===================== 页签内容：左右两栏 ===================== */
.settings-panel {
  display: none;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
  gap: 18px;
}

.settings-panel.is-active {
  display: grid;
}

.settings-panel > * {
  min-width: 0;
}

.settings-section {
  padding: 20px 24px;
}

.settings-section--span {
  grid-column: 1 / -1;
}

/* 账号信息 / AI 只读行：左右对齐 + 细分隔线 */
.detail-info {
  gap: 0;
}

.detail-info > div {
  padding: 12px 0;
  border-bottom: 1px solid rgba(125, 201, 255, 0.06);
}

.detail-info > div:last-child {
  border-bottom: none;
}

.detail-info .detail-info__empty {
  color: rgba(220, 234, 255, 0.36);
  font-weight: 400;
}

.ai-readonly strong {
  min-width: 0;
  word-break: break-all;
}

/* 徽标：与 UserManagement 同一套色板 */
.role-badge,
.status-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.78rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.role-badge--super {
  background: rgba(255, 183, 77, 0.16);
  color: #ffc37d;
  border: 1px solid rgba(255, 183, 77, 0.3);
}

.role-badge--admin {
  background: rgba(167, 139, 250, 0.18);
  color: #c4b5fd;
  border: 1px solid rgba(167, 139, 250, 0.28);
}

.role-badge--user {
  background: rgba(91, 166, 255, 0.16);
  color: #9ad6ff;
  border: 1px solid rgba(91, 166, 255, 0.28);
}

.status-badge--on {
  background: rgba(14, 99, 76, 0.62);
  color: #6ef0c4;
  border: 1px solid rgba(83, 229, 200, 0.36);
}

.status-badge--off {
  background: rgba(112, 32, 30, 0.55);
  color: #ff9a92;
  border: 1px solid rgba(255, 123, 114, 0.34);
}

.scenario-tag {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(91, 166, 255, 0.12);
  color: #9ad6ff;
  font-size: 0.76rem;
  white-space: nowrap;
}

/* AI 配置状态徽标：与 .status-badge 同一套色板，深底亮字保证对比度 */
.ai-badge {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  white-space: nowrap;
  flex-shrink: 0;
}

.ai-badge--on {
  background: rgba(14, 99, 76, 0.62);
  color: #6ef0c4;
  border: 1px solid rgba(83, 229, 200, 0.36);
}

.ai-badge--off {
  background: rgba(112, 32, 30, 0.55);
  color: #ff9a92;
  border: 1px solid rgba(255, 123, 114, 0.34);
}

/* 阈值 */
.threshold-scenario-pick {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.threshold-scenario-pick__select {
  width: 220px;
}

/* 阈值长条框：单个横向长条，内含可调整的阈值输入 */
.threshold-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
  padding: 18px 22px;
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.16);
  background: rgba(8, 17, 31, 0.55);
}

.threshold-bar__head {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 150px;
  padding-right: 18px;
  border-right: 1px solid rgba(125, 201, 255, 0.1);
}

.threshold-bar__head h4 {
  margin: 0;
  font-size: 1.05rem;
  color: #e8f1ff;
}

.threshold-bar__scene {
  font-size: 0.78rem;
  color: rgba(154, 214, 255, 0.55);
}

.threshold-bar__form {
  display: flex;
  align-items: flex-end;
  gap: 18px;
  flex-wrap: wrap;
  flex: 1;
}

.threshold-field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.threshold-field label {
  font-size: 0.8rem;
  color: rgba(220, 234, 255, 0.65);
}

.threshold-field .settings-form__input {
  width: 150px;
}

.threshold-bar__current {
  font-size: 0.74rem;
  color: rgba(154, 214, 255, 0.6);
}

.threshold-bar__rule {
  flex-basis: 100%;
  margin: 0;
  font-size: 0.76rem;
  color: rgba(255, 209, 102, 0.7);
}

/* ===================== 表单 ===================== */
.settings-form {
  display: grid;
  gap: 16px;
}

.settings-form__item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.settings-form__item--row {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.settings-form__label {
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.7);
}

.settings-form__input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
}

.settings-form__input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

select.settings-form__input option {
  background: #0b1628;
  color: #e8f1ff;
}

/* ===================== 开关 ===================== */
.settings-switches {
  display: grid;
  gap: 14px;
}

.settings-switches__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid rgba(125, 201, 255, 0.06);
}

.settings-switches__item:last-child {
  border-bottom: none;
}

.settings-switches__label {
  font-size: 0.9rem;
  color: #d9e8ff;
}

.settings-switches__toggle {
  width: 44px;
  height: 24px;
  border-radius: 12px;
  border: none;
  background: rgba(220, 234, 255, 0.15);
  cursor: pointer;
  position: relative;
  transition: background 0.25s;
  padding: 0;
  flex-shrink: 0;
}

.settings-switches__toggle.is-on {
  background: linear-gradient(135deg, #5ba6ff, #407acc);
}

.settings-switches__toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-switches__knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.25s;
}

.settings-switches__toggle.is-on .settings-switches__knob {
  transform: translateX(20px);
}

/* ===================== 按钮：统一蓝色填充（与主按钮同款） ===================== */
.settings-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: opacity 0.2s;
  width: fit-content;
}

.settings-btn:hover {
  opacity: 0.9;
}

.settings-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-btn--primary {
  padding: 12px 32px;
  font-weight: 600;
}

.settings-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

@media (max-width: 768px) {
  .settings-panel {
    grid-template-columns: 1fr;
  }
  .threshold-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .threshold-bar__head {
    border-right: none;
    padding-right: 0;
  }
  .threshold-field .settings-form__input {
    width: 100%;
  }
  .threshold-scenario-pick__select {
    flex: 1;
  }
}
</style>

<style>
/* 弹窗 append-to-body 后挂到 body，scoped 样式不生效，故在此补齐。 */
.pwd-setting-dialog,
.threshold-log-dialog,
.ai-setting-dialog {
  background: linear-gradient(180deg, rgba(11, 22, 40, 0.98), rgba(5, 12, 22, 0.98)) !important;
  border: 1px solid rgba(125, 201, 255, 0.18) !important;
  border-radius: 20px !important;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5) !important;
}

.pwd-setting-dialog .el-dialog__title,
.threshold-log-dialog .el-dialog__title,
.ai-setting-dialog .el-dialog__title {
  color: #e8f1ff !important;
  font-size: 1.15rem !important;
}

.pwd-setting-dialog .el-dialog__headerbtn .el-dialog__close,
.threshold-log-dialog .el-dialog__headerbtn .el-dialog__close,
.ai-setting-dialog .el-dialog__headerbtn .el-dialog__close {
  color: rgba(220, 234, 255, 0.5) !important;
}

.pwd-setting-dialog .el-dialog__body,
.threshold-log-dialog .el-dialog__body,
.ai-setting-dialog .el-dialog__body {
  padding: 20px 24px !important;
}

.pwd-setting-dialog .el-dialog__footer,
.ai-setting-dialog .el-dialog__footer {
  padding: 12px 24px 18px !important;
}

.threshold-log-dialog .el-table,
.threshold-log-dialog .el-table__inner-wrapper,
.threshold-log-dialog .el-table__body-wrapper,
.threshold-log-dialog .el-table__header-wrapper {
  background-color: transparent !important;
}

.threshold-log-dialog .el-table th.el-table__cell {
  background-color: rgba(16, 34, 60, 0.9) !important;
  color: rgba(155, 195, 240, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.08) !important;
}

.threshold-log-dialog .el-table td.el-table__cell {
  background-color: rgba(6, 15, 28, 0.85) !important;
  color: rgba(175, 198, 230, 0.85) !important;
  border-bottom: 1px solid rgba(125, 201, 255, 0.04) !important;
}

.threshold-log-dialog .el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background-color: rgba(10, 24, 44, 0.85) !important;
}

.threshold-log-dialog .el-table__body tr:hover > td.el-table__cell {
  background-color: rgba(20, 44, 72, 0.9) !important;
}

.threshold-log-dialog .el-table__empty-text {
  color: rgba(180, 200, 235, 0.3) !important;
}

/* style.css 里的 .el-button 暗色覆盖与 Element Plus 自身样式同权重、且 EP 在后，
   实际不生效（实测取消按钮渲染成白底）。此处用 !important 兜住。 */
.pwd-setting-dialog .el-button,
.ai-setting-dialog .el-button {
  background: rgba(91, 166, 255, 0.1) !important;
  border-color: rgba(125, 201, 255, 0.3) !important;
  color: #9ad6ff !important;
}

.pwd-setting-dialog .el-button:hover,
.ai-setting-dialog .el-button:hover {
  background: rgba(91, 166, 255, 0.18) !important;
  border-color: rgba(91, 166, 255, 0.5) !important;
  color: #fff !important;
}

.pwd-setting-dialog .el-button--primary,
.ai-setting-dialog .el-button--primary {
  background: linear-gradient(135deg, #5ba6ff, #407acc) !important;
  border-color: transparent !important;
  color: #fff !important;
}

.pwd-setting-dialog .el-button--primary:hover,
.ai-setting-dialog .el-button--primary:hover {
  background: linear-gradient(135deg, #5ba6ff, #407acc) !important;
  border-color: transparent !important;
  color: #fff !important;
  opacity: 0.9;
}

.ai-dialog-form {
  display: grid;
  gap: 14px;
}

.ai-dialog-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ai-dialog-field__label {
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.7);
}

.ai-dialog-input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.ai-dialog-input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.ai-dialog-input::placeholder {
  color: rgba(220, 234, 255, 0.32);
}
</style>
