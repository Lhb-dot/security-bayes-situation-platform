<script setup lang="ts">
/**
 * Settings — 设置（普通用户）/ 系统设置（管理员）
 *
 * V3.0 调整：
 * - 普通用户"设置"：第一个区块 = 选择感兴趣的场景（可多选，用户自选，非管理员分配），
 *   后面是当前用户可修改的个人设置（修改密码 / 主题 / 自动刷新）。
 *   不含任何管理员专属项（风险阈值等不出现）。
 * - 管理员"系统设置"：风险阈值（需求 5.4.1，按场景隔离、[0,1]、high>medium、变更日志）、
 *   场景启停、自动刷新、主题。
 */
import { computed, onMounted, ref } from 'vue';
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
import type { ScenarioId, ThresholdChangeLog, ThresholdConfig, UserAccount } from '@/types/security';

const userStore = useUserStore();
const settingsStore = useSettingsStore();
const router = useRouter();
const currentUser = ref<UserAccount | null>(null);
const isAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN' || currentUser.value?.role === 'SCENARIO_ADMIN');
const canConfigureThresholds = computed(() =>
  currentUser.value?.role === 'SUPER_ADMIN' || !!currentUser.value?.scenario_code,
);

// ===================== 普通用户：个人设置（场景由管理员分配，用户不可自选） =====================
const pwdForm = ref({ oldPassword: '', newPassword: '', confirm: '' });
const changingPwd = ref(false);
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
    pwdForm.value = { oldPassword: '', newPassword: '', confirm: '' };
    await userStore.logout();
    router.push('/login');
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '修改失败');
  } finally {
    changingPwd.value = false;
  }
};

const savePersonalSettings = () => {
  settingsStore.saveRefreshSettings();
  ElMessage.success('个人设置已保存');
};

// ===================== 管理员：系统设置（风险阈值等 admin-only） =====================
const SCENARIO_LABEL: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板作业',
  geological_risk: '地质风险',
};
/** 阈值可配置场景：系统管理员=全部；其他账号=绑定场景 */
const isScenarioAdmin = computed(() => currentUser.value?.role === 'SCENARIO_ADMIN');
const isSuperAdmin = computed(() => currentUser.value?.role === 'SUPER_ADMIN');
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
const scenarioSwitches = ref([
  { id: 'network_security', label: '网络安全态势感知', enabled: true },
  { id: 'power_system', label: '电力系统风险态势感知', enabled: true },
  { id: 'geological_risk', label: '地质风险态势感知', enabled: true },
]);

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

const saveAdminSettings = () => {
  settingsStore.saveRefreshSettings();
  ElMessage.success('系统设置已保存');
};

onMounted(async () => {
  currentUser.value = userStore.currentUser;
  settingsStore.loadForUser(currentUser.value?.user_id);
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

    <!-- ==================== 普通用户：选场景（第一个区块） ==================== -->
    <!-- ==================== 普通用户：个人设置（场景由管理员分配，不可自选） ==================== -->
    <template v-if="!isAdmin">
      <section class="card settings-section settings-section--span">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Account</p>
            <h3>修改密码</h3>
          </div>
        </div>
        <div class="settings-form settings-form--row3">
          <div class="settings-form__item">
            <label class="settings-form__label">原密码</label>
            <input v-model="pwdForm.oldPassword" type="password" class="settings-form__input" placeholder="请输入原密码" />
          </div>
          <div class="settings-form__item">
            <label class="settings-form__label">新密码</label>
            <input v-model="pwdForm.newPassword" type="password" class="settings-form__input" placeholder="至少 6 位" />
          </div>
          <div class="settings-form__item">
            <label class="settings-form__label">确认新密码</label>
            <input v-model="pwdForm.confirm" type="password" class="settings-form__input" placeholder="再次输入新密码" />
          </div>
        </div>
        <button class="settings-btn settings-btn--primary" :disabled="changingPwd" @click="changePwd">
          {{ changingPwd ? '提交中...' : '修改密码' }}
        </button>
      </section>

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
        <button class="settings-btn" @click="savePersonalSettings">保存个人设置</button>
      </section>
    </template>

    <!-- ==================== 当前账号阈值 ==================== -->
    <section v-if="canConfigureThresholds" class="card settings-section settings-section--span">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Threshold</p>
          <h3>我的风险阈值</h3>
          <p class="settings-section__hint">告警按当前账号在对应场景的阈值判定，修改后立即生效。</p>
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

    <!-- ==================== 管理员：系统设置 ==================== -->
    <template v-if="isAdmin">
      <div class="settings-grid">
        <section v-if="!isScenarioAdmin" class="card settings-section">
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
        </section>

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
        </section>

      </div>

      <div class="settings-actions">
        <button class="settings-btn settings-btn--primary" @click="saveAdminSettings">保存全部系统设置</button>
      </div>
    </template>
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

.settings-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin-bottom: 24px;
}

.settings-section {
  padding: 20px 24px;
}

.settings-section__hint {
  margin: 6px 0 0;
  color: rgba(220, 234, 255, 0.55);
  font-size: 0.82rem;
}

.settings-section--span {
  grid-column: 1 / -1;
}

.perm-tip {
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 209, 102, 0.12);
  color: rgba(255, 209, 102, 0.85);
  font-size: 0.78rem;
}

/* 普通用户：选场景卡片 */
.scenario-pick-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.scenario-pick {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.16);
  background: rgba(255, 255, 255, 0.02);
  color: #d9e8ff;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, transform 0.15s;
}

.scenario-pick:hover {
  border-color: rgba(91, 166, 255, 0.4);
  transform: translateY(-1px);
}

.scenario-pick.is-picked {
  border-color: rgba(83, 229, 200, 0.55);
  background: rgba(83, 229, 200, 0.08);
}

.scenario-pick__name {
  font-size: 1rem;
  font-weight: 600;
}

.scenario-pick__desc {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
}

.scenario-pick__actions {
  display: flex;
  justify-content: flex-end;
}

/* 普通用户：改密三列 */
.settings-form--row3 {
  grid-template-columns: repeat(3, 1fr);
  margin-bottom: 16px;
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

.change-logs {
  padding-top: 16px;
  border-top: 1px solid rgba(125, 201, 255, 0.1);
}

.change-logs__title {
  margin: 0 0 12px;
  font-size: 0.95rem;
  color: #d9e8ff;
}

.change-logs__wrap {
  overflow-x: auto;
}

.change-logs__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

.change-logs__table th {
  text-align: left;
  padding: 10px 12px;
  color: rgba(154, 214, 255, 0.8);
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.15);
  white-space: nowrap;
}

.change-logs__table td {
  padding: 10px 12px;
  color: rgba(217, 232, 255, 0.9);
  border-bottom: 1px solid rgba(125, 201, 255, 0.06);
  white-space: nowrap;
}

.change-logs__new {
  color: #53e5c8;
  font-weight: 600;
}

.change-logs__empty {
  text-align: center;
  color: rgba(220, 234, 255, 0.45);
}

.threshold-log-modal {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.threshold-log-modal__backdrop {
  position: absolute;
  inset: 0;
  background: rgba(2, 8, 18, 0.72);
}

.threshold-log-modal__panel {
  position: relative;
  z-index: 1;
  width: min(960px, 100%);
  max-height: min(680px, 90vh);
  overflow: auto;
  padding: 22px 24px;
}

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
}

.settings-switches__toggle.is-on {
  background: linear-gradient(135deg, #5ba6ff, #407acc);
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

.settings-btn {
  padding: 10px 20px;
  border: 1px solid rgba(125, 201, 255, 0.25);
  border-radius: 10px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.9rem;
  cursor: pointer;
  transition: background 0.2s;
  width: fit-content;
}

.settings-btn:hover {
  background: rgba(91, 166, 255, 0.2);
}

.settings-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.settings-btn--primary {
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  border: none;
  padding: 12px 32px;
  font-weight: 600;
}

.settings-btn--primary:hover {
  opacity: 0.9;
}

.settings-actions {
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .settings-grid {
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
  .scenario-pick-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .settings-form--row3 {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
/* Keep the audit dialog consistent with DatasetCenter's field preview dialog. */
.threshold-log-dialog {
  background: linear-gradient(180deg, rgba(11, 22, 40, 0.98), rgba(5, 12, 22, 0.98)) !important;
  border: 1px solid rgba(125, 201, 255, 0.18) !important;
  border-radius: 20px !important;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5) !important;
}

.threshold-log-dialog .el-dialog__title {
  color: #e8f1ff !important;
  font-size: 1.15rem !important;
}

.threshold-log-dialog .el-dialog__headerbtn .el-dialog__close {
  color: rgba(220, 234, 255, 0.5) !important;
}

.threshold-log-dialog .el-dialog__body {
  padding: 20px 24px !important;
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
</style>
