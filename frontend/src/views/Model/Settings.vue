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
import { ElMessage } from 'element-plus';
import {
  changeOwnPassword,
  getCurrentUser,
  getThresholdChangeLogs,
  getThresholds,
  saveThreshold,
} from '@/services/mockApi';
import { useUserStore } from '@/stores/userStore';
import type { ScenarioId, ThresholdChangeLog, ThresholdConfig, UserAccount } from '@/types/security';

const userStore = useUserStore();
const currentUser = ref<UserAccount | null>(null);
const isAdmin = computed(() => currentUser.value?.role === 'ADMIN');

// ===================== 普通用户：选择感兴趣的场景 =====================
const ALL_SCENARIOS: Array<{ id: ScenarioId; label: string; desc: string }> = [
  { id: 'network_security', label: '网络安全', desc: '网络流量二分类风险' },
  { id: 'power_system', label: '电力系统', desc: '电力设备风险事件' },
  { id: 'geological_risk', label: '地质风险', desc: '滑坡易发性风险' },
  { id: 'flightdeck_operation', label: '航母甲板作业', desc: '双机协同碰撞风险' },
];
const myScenarios = ref<ScenarioId[]>([]);
const savingScenarios = ref(false);

const toggleScenario = (id: ScenarioId) => {
  if (myScenarios.value.includes(id)) {
    myScenarios.value = myScenarios.value.filter((s) => s !== id);
  } else {
    myScenarios.value = [...myScenarios.value, id];
  }
};

const saveMyScenarios = async () => {
  // 至少选择一个场景（用户必须关注 ≥1 个场景，否则其它页面无可用场景）
  if (myScenarios.value.length === 0) {
    ElMessage.warning('请至少选择一个感兴趣的场景（不可为 0）');
    return;
  }
  savingScenarios.value = true;
  try {
    await userStore.updateMyScenarios(myScenarios.value);
    currentUser.value = userStore.currentUser;
    ElMessage.success('关注的场景已保存，其它页面将实时更新');
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败');
  } finally {
    savingScenarios.value = false;
  }
};

// ===================== 普通用户：个人设置 =====================
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
    await changeOwnPassword(pwdForm.value.oldPassword, pwdForm.value.newPassword);
    ElMessage.success('密码修改成功');
    pwdForm.value = { oldPassword: '', newPassword: '', confirm: '' };
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '修改失败');
  } finally {
    changingPwd.value = false;
  }
};

const darkTheme = ref(true);
const autoRefresh = ref(true);
const refreshInterval = ref(30);
const savePersonalSettings = () => {
  ElMessage.success('个人设置已保存');
};

// ===================== 管理员：系统设置（风险阈值等 admin-only） =====================
const SCENARIO_LABEL: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  flightdeck_operation: '航母甲板作业',
  geological_risk: '地质风险',
};
const activeScenarios: ScenarioId[] = ['network_security', 'power_system', 'geological_risk'];
const thresholds = ref<ThresholdConfig[]>([]);
const changeLogs = ref<ThresholdChangeLog[]>([]);
const saving = ref(false);
const editing = ref<Record<string, { medium: number; high: number }>>({
  network_security: { medium: 0.45, high: 0.75 },
  power_system: { medium: 0.5, high: 0.8 },
  flightdeck_operation: { medium: 0.5, high: 0.8 },
  geological_risk: { medium: 0.5, high: 0.8 },
});
const scenarioSwitches = ref([
  { id: 'network_security', label: '网络安全态势感知', enabled: true },
  { id: 'power_system', label: '电力系统风险态势感知', enabled: true },
  { id: 'geological_risk', label: '地质风险态势感知', enabled: true },
  { id: 'flightdeck_operation', label: '航母甲板保障作业态势感知', enabled: true },
]);

const loadThresholds = async () => {
  const [ths, logs] = await Promise.all([getThresholds(), getThresholdChangeLogs()]);
  thresholds.value = ths;
  changeLogs.value = logs;
  editing.value = {};
  for (const t of ths) {
    editing.value[t.scenario_id] = { medium: t.medium_threshold, high: t.high_threshold };
  }
};

const saveScenarioThreshold = async (scenarioId: ScenarioId) => {
  const e = editing.value[scenarioId];
  if (e.medium < 0 || e.medium > 1 || e.high < 0 || e.high > 1) {
    ElMessage.warning('阈值必须位于 [0,1] 范围内');
    return;
  }
  if (e.high <= e.medium) {
    ElMessage.warning('高风险阈值必须大于中风险阈值');
    return;
  }
  saving.value = true;
  try {
    await saveThreshold(scenarioId, e.medium, e.high);
    ElMessage.success(`「${SCENARIO_LABEL[scenarioId]}」阈值已保存并实时生效`);
    await loadThresholds();
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '保存失败');
  } finally {
    saving.value = false;
  }
};

const saveAdminSettings = () => {
  ElMessage.success('系统设置已保存');
};

onMounted(async () => {
  currentUser.value = getCurrentUser();
  myScenarios.value = [...(currentUser.value?.scenario_ids ?? [])];
  if (isAdmin.value) await loadThresholds();
});
</script>

<template>
  <div class="settings-page">
    <div class="settings-page__header">
      <div>
        <p class="eyebrow">{{ isAdmin ? 'System Settings' : 'My Settings' }}</p>
        <h2>{{ isAdmin ? '系统设置' : '设置' }}</h2>
        <p v-if="isAdmin" class="settings-page__desc">风险阈值按场景配置（需求 5.4.1），其余为全局基础参数</p>
        <p v-else class="settings-page__desc">选择你感兴趣的场景（可多选），其它页面将实时更新；下方为个人设置</p>
      </div>
    </div>

    <!-- ==================== 普通用户：选场景（第一个区块） ==================== -->
    <section v-if="!isAdmin" class="card settings-section settings-section--span">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Scenarios</p>
          <h3>选择感兴趣的场景</h3>
        </div>
        <span class="perm-tip">可多选，至少选 1 个；保存后其它页面实时更新</span>
      </div>
      <div class="scenario-pick-grid">
        <button
          v-for="sc in ALL_SCENARIOS"
          :key="sc.id"
          class="scenario-pick"
          :class="{ 'is-picked': myScenarios.includes(sc.id) }"
          @click="toggleScenario(sc.id)"
        >
          <span class="scenario-pick__name">{{ sc.label }}</span>
          <span class="scenario-pick__desc">{{ sc.desc }}</span>
        </button>
      </div>
      <div class="scenario-pick__actions">
        <button class="settings-btn settings-btn--primary" :disabled="savingScenarios" @click="saveMyScenarios">
          {{ savingScenarios ? '保存中...' : '保存我关注的场景' }}
        </button>
      </div>
    </section>

    <!-- ==================== 普通用户：个人设置 ==================== -->
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
            <p class="eyebrow">Theme</p>
            <h3>主题设置</h3>
          </div>
        </div>
        <div class="settings-form">
          <div class="settings-form__item settings-form__item--row">
            <label class="settings-form__label">深色主题</label>
            <button class="settings-switches__toggle" :class="{ 'is-on': darkTheme }" @click="darkTheme = !darkTheme">
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
            <button class="settings-switches__toggle" :class="{ 'is-on': autoRefresh }" @click="autoRefresh = !autoRefresh">
              <span class="settings-switches__knob"></span>
            </button>
          </div>
          <div class="settings-form__item">
            <label class="settings-form__label">刷新间隔（秒）</label>
            <select v-model.number="refreshInterval" class="settings-form__input" :disabled="!autoRefresh">
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

    <!-- ==================== 管理员：系统设置 ==================== -->
    <template v-if="isAdmin">
      <div class="settings-grid">
        <section class="card settings-section settings-section--span">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Threshold</p>
              <h3>场景风险阈值配置</h3>
            </div>
            <span class="perm-tip">仅管理员可修改</span>
          </div>

          <div class="threshold-grid">
            <div v-for="sc in activeScenarios" :key="sc" class="threshold-card">
              <div class="threshold-card__head">
                <h4>{{ SCENARIO_LABEL[sc] }}</h4>
                <span class="threshold-card__scene">{{ sc }}</span>
              </div>
              <div class="threshold-card__form">
                <div class="threshold-field">
                  <label>中风险阈值（0~1）</label>
                  <input v-model.number="editing[sc].medium" type="number" min="0" max="1" step="0.01" class="settings-form__input" />
                </div>
                <div class="threshold-field">
                  <label>高风险阈值（0~1）</label>
                  <input v-model.number="editing[sc].high" type="number" min="0" max="1" step="0.01" class="settings-form__input" />
                </div>
                <p class="threshold-card__rule">要求：0 ≤ 中风险 &lt; 高风险 ≤ 1</p>
                <button class="settings-btn" :disabled="saving" @click="saveScenarioThreshold(sc)">
                  {{ saving ? '保存中...' : '保存并生效' }}
                </button>
              </div>
            </div>

            <div class="threshold-card threshold-card--reserved">
              <div class="threshold-card__head">
                <h4>{{ SCENARIO_LABEL.flightdeck_operation }}</h4>
                <span class="threshold-card__scene">flightdeck_operation</span>
              </div>
              <div class="threshold-card__form">
                <p class="threshold-card__reserved-tip">第一阶段仅预留配置能力，不启用实际阈值计算。</p>
              </div>
            </div>
          </div>

          <div class="change-logs">
            <h4 class="change-logs__title">阈值变更记录（需求 5.4.1.5）</h4>
            <div class="change-logs__wrap">
              <table class="change-logs__table">
                <thead>
                  <tr>
                    <th>变更时间</th>
                    <th>场景</th>
                    <th>操作人ID</th>
                    <th>原中风险</th>
                    <th>原高风险</th>
                    <th>新中风险</th>
                    <th>新高风险</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="log in changeLogs" :key="log.log_id">
                    <td>{{ log.changed_at }}</td>
                    <td>{{ SCENARIO_LABEL[log.scenario_id] ?? log.scenario_id }}</td>
                    <td>{{ log.operator_id }}</td>
                    <td>{{ log.old_medium_threshold }}</td>
                    <td>{{ log.old_high_threshold }}</td>
                    <td class="change-logs__new">{{ log.new_medium_threshold }}</td>
                    <td class="change-logs__new">{{ log.new_high_threshold }}</td>
                  </tr>
                  <tr v-if="changeLogs.length === 0">
                    <td colspan="7" class="change-logs__empty">暂无变更记录</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

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
              <button class="settings-switches__toggle" :class="{ 'is-on': autoRefresh }" @click="autoRefresh = !autoRefresh">
                <span class="settings-switches__knob"></span>
              </button>
            </div>
            <div class="settings-form__item">
              <label class="settings-form__label">刷新间隔（秒）</label>
              <select v-model.number="refreshInterval" class="settings-form__input" :disabled="!autoRefresh">
                <option :value="10">10 秒</option>
                <option :value="30">30 秒</option>
                <option :value="60">60 秒</option>
                <option :value="120">120 秒</option>
                <option :value="300">300 秒</option>
              </select>
            </div>
          </div>
        </section>

        <section class="card settings-section">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Theme</p>
              <h3>主题设置</h3>
            </div>
          </div>
          <div class="settings-form">
            <div class="settings-form__item settings-form__item--row">
              <label class="settings-form__label">深色主题</label>
              <button class="settings-switches__toggle" :class="{ 'is-on': darkTheme }" @click="darkTheme = !darkTheme">
                <span class="settings-switches__knob"></span>
              </button>
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
.threshold-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 20px;
}

.threshold-card {
  padding: 16px 18px;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.14);
  background: rgba(255, 255, 255, 0.02);
}

.threshold-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.threshold-card__head h4 {
  margin: 0;
  font-size: 1rem;
  color: #d9e8ff;
}

.threshold-card__scene {
  font-size: 0.72rem;
  color: rgba(154, 214, 255, 0.5);
}

.threshold-card__form {
  display: grid;
  gap: 10px;
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

.threshold-card__rule {
  margin: 0;
  font-size: 0.74rem;
  color: rgba(255, 209, 102, 0.7);
}

.threshold-card__reserved-tip {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.45);
  line-height: 1.6;
  font-style: italic;
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
  .threshold-grid {
    grid-template-columns: 1fr;
  }
  .scenario-pick-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .settings-form--row3 {
    grid-template-columns: 1fr;
  }
}
</style>
