<script setup lang="ts">
/**
 * Settings - 系统设置页面
 *
 * 风险阈值配置、场景启停、自动刷新、深色主题
 */
import { ref } from 'vue';
import { ElMessage } from 'element-plus';

/** 风险阈值 */
const thresholdHigh = ref(0.75);
const thresholdMid = ref(0.45);
const thresholdLow = ref(0.2);

/** 场景启停 */
const scenarioSwitches = ref([
  { id: 'network_security', label: '网络安全态势感知', enabled: true },
  { id: 'power_system', label: '电力系统风险态势感知', enabled: true },
  { id: 'flightdeck_operation', label: '航母甲板保障作业态势感知', enabled: true },
]);

/** 自动刷新 */
const autoRefresh = ref(true);
const refreshInterval = ref(30);

/** 深色主题 */
const darkTheme = ref(true);

const saveThreshold = () => {
  if (thresholdHigh.value <= thresholdMid.value || thresholdMid.value <= thresholdLow.value) {
    ElMessage.warning('阈值设置错误：高风险阈值 > 中风险阈值 > 低风险阈值');
    return;
  }
  ElMessage.success('全局风险阈值保存成功');
};

const saveSettings = () => {
  ElMessage.success('系统设置已保存');
};
</script>

<template>
  <div class="settings-page">
    <div class="settings-page__header">
      <div>
        <p class="eyebrow">System Settings</p>
        <h2>系统设置</h2>
        <p class="settings-page__desc">全局基础参数配置</p>
      </div>
    </div>

    <div class="settings-grid">
      <!-- 风险阈值 -->
      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Threshold</p>
            <h3>风险阈值配置</h3>
          </div>
        </div>
        <div class="settings-form">
          <div class="settings-form__item">
            <label class="settings-form__label">高风险阈值（0~1）</label>
            <input
              v-model.number="thresholdHigh"
              type="number"
              min="0"
              max="1"
              step="0.01"
              class="settings-form__input"
            />
          </div>
          <div class="settings-form__item">
            <label class="settings-form__label">中风险阈值（0~1）</label>
            <input
              v-model.number="thresholdMid"
              type="number"
              min="0"
              max="1"
              step="0.01"
              class="settings-form__input"
            />
          </div>
          <div class="settings-form__item">
            <label class="settings-form__label">低风险阈值（0~1）</label>
            <input
              v-model.number="thresholdLow"
              type="number"
              min="0"
              max="1"
              step="0.01"
              class="settings-form__input"
            />
          </div>
          <button class="settings-btn" @click="saveThreshold">保存阈值</button>
        </div>
      </section>

      <!-- 场景启停 -->
      <section class="card settings-section">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Scenarios</p>
            <h3>场景启停控制</h3>
          </div>
        </div>
        <div class="settings-switches">
          <div
            v-for="sc in scenarioSwitches"
            :key="sc.id"
            class="settings-switches__item"
          >
            <span class="settings-switches__label">{{ sc.label }}</span>
            <button
              class="settings-switches__toggle"
              :class="{ 'is-on': sc.enabled }"
              @click="sc.enabled = !sc.enabled"
            >
              <span class="settings-switches__knob"></span>
            </button>
          </div>
        </div>
      </section>

      <!-- 自动刷新 -->
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
            <button
              class="settings-switches__toggle"
              :class="{ 'is-on': autoRefresh }"
              @click="autoRefresh = !autoRefresh"
            >
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

      <!-- 深色主题 -->
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
            <button
              class="settings-switches__toggle"
              :class="{ 'is-on': darkTheme }"
              @click="darkTheme = !darkTheme"
            >
              <span class="settings-switches__knob"></span>
            </button>
          </div>
        </div>
      </section>
    </div>

    <div class="settings-actions">
      <button class="settings-btn settings-btn--primary" @click="saveSettings">保存全部设置</button>
    </div>
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

.settings-form__input:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

select.settings-form__input option {
  background: #0b1628;
  color: #e8f1ff;
}

/* 开关 */
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

/* 按钮 */
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
}
</style>
