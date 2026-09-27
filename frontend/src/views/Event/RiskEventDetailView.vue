<script setup lang="ts">
/**
 * RiskEventDetailView.vue — 风险事件详情页（Task 012 / 需求 5.7）
 *
 * 三组信息：判定说明 / 基本信息 / 输入特征 —— 按「结论 → 属性与出处 → 原始数据」排列。
 * 处置状态流转：待处置 → 处理中 → 已处置（已处置为终态禁用），入口在页头。
 * 解释文本为事件生成时固化存储，前端不拼接、不重算（需求 5.7.3.1/5.7.3.4）。
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useRiskEventStore } from '@/stores/riskEventStore';
import { useUserStore } from '@/stores/userStore';
import { formatExplanation } from '@/utils/explanationText';
import type { RiskEvent, RiskLevelUpper } from '@/types/security';
import RiskLevelTag from '@/components/common/RiskLevelTag.vue';

const route = useRoute();
const router = useRouter();
const riskEventStore = useRiskEventStore();
const userStore = useUserStore();

const eventId = computed(() => String(route.params.eventId ?? ''));
const loading = ref(true);
const error = ref('');
const notFound = ref(false);
const denied = ref(false);
const featuresExpanded = ref(false);

const event = computed<RiskEvent | null>(() => riskEventStore.detail);

/** 场景名映射（展示用，与现有页面一致） */
const SCENARIO_LABEL: Record<string, string> = {
  network_security: '网络安全',
  power_system: '电力系统',
  geological_risk: '地质风险',
  flightdeck_operation: '航母甲板',
};

/** 原始标签中文化（模型输出的原始类标；未收录的原样显示） */
const ORIGINAL_LABEL: Record<string, string> = {
  anomaly: '异常',
  normal: '正常',
  '1': '风险',
  '0': '正常',
};

/** RiskLevelTag 需要小写等级，做显式映射（大写 → 小写） */
const TAG_LEVEL: Record<RiskLevelUpper, 'critical' | 'high' | 'medium' | 'low'> = {
  HIGH: 'high',
  MEDIUM: 'medium',
  LOW: 'low',
};
const tagLevel = computed<'critical' | 'high' | 'medium' | 'low'>(() =>
  event.value ? TAG_LEVEL[event.value.risk_level] : 'low'
);

/** 处置状态 → 徽章色调类名（避免把中文写进 class） */
const STATUS_TONE: Record<string, string> = {
  '待处置': 'pending',
  '处理中': 'processing',
  '已处置': 'resolved',
};

const scoreText = computed(() =>
  event.value ? `${(event.value.risk_score * 100).toFixed(1)}%` : '--'
);

const originalLabelText = computed(() =>
  event.value ? (ORIGINAL_LABEL[event.value.original_label] ?? event.value.original_label) : '--'
);

/** 创建者：优先经 userStore.users 映射用户名，未加载则显示 user_id */
const creatorName = computed(() =>
  event.value
    ? (userStore.users.find((u) => u.user_id === event.value?.created_by_user_id)?.display_name
        ?? event.value.created_by_user_id)
    : '--'
);

const loadData = async () => {
  loading.value = true;
  error.value = '';
  notFound.value = false;
  denied.value = false;
  try {
    await riskEventStore.fetchDetail(eventId.value);
  } catch (err) {
    const msg = err instanceof Error ? err.message : '事件加载失败';
    if (msg === '风险事件不存在') notFound.value = true;
    else if (msg === '无权查看该事件' || msg === '无权访问该场景') denied.value = true;
    else error.value = msg;
  } finally {
    loading.value = false;
  }
};

/** 下一处置状态（已处置为终态 → null） */
const nextStatus = computed<RiskEvent['status'] | null>(() => {
  if (!event.value) return null;
  if (event.value.status === '待处置') return '处理中';
  if (event.value.status === '处理中') return '已处置';
  return null;
});

const handleStatusChange = async () => {
  // 先把目标状态取出来再 await：流转成功后 event.status 立刻变成新值，
  // nextStatus 随之重算为 null，事后再拼进提示语就成了「已更新处置状态为「null」」。
  const target = nextStatus.value;
  if (!event.value || !target) return;
  try {
    await riskEventStore.updateStatus(event.value.event_id, target);
    ElMessage.success(`已更新处置状态为「${target}」`);
  } catch (err) {
    ElMessage.error(err instanceof Error ? err.message : '状态更新失败');
  }
};

/** 输入特征键值对（只读；超宽特征折叠滚动） */
const featureEntries = computed<Array<{ key: string; value: string }>>(() =>
  Object.entries(event.value?.raw_features ?? {}).map(([key, value]) => ({
    key,
    value: typeof value === 'object' ? JSON.stringify(value) : String(value),
  }))
);
const visibleFeatureEntries = computed(() =>
  featuresExpanded.value ? featureEntries.value : featureEntries.value.slice(0, 50)
);

onMounted(loadData);
</script>

<template>
  <div class="event-detail">
    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载风险事件详情...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadData">重试</button>
    </section>

    <!-- 不存在 -->
    <section v-else-if="notFound" class="state-card">
      <p>风险事件不存在</p>
      <button class="ghost-button" @click="router.back()">返回</button>
    </section>

    <!-- 无权访问 -->
    <section v-else-if="denied" class="state-card">
      <p>无权查看该事件</p>
      <button class="ghost-button" @click="router.back()">返回</button>
    </section>

    <template v-else-if="event">
      <!-- 头部：身份 + 等级 + 状态 + 处置入口 -->
      <section class="card event-detail__head">
        <div>
          <p class="eyebrow">Risk Event Detail</p>
          <h2>风险事件详情</h2>
          <p class="event-detail__id">{{ event.event_id }}</p>
        </div>
        <div class="event-detail__head-actions">
          <RiskLevelTag :level="tagLevel" size="large" />
          <span
            class="event-detail__status"
            :class="`event-detail__status--${STATUS_TONE[event.status] ?? 'pending'}`"
          >
            {{ event.status }}
          </span>
          <el-button v-if="nextStatus" type="primary" @click="handleStatusChange">
            流转至「{{ nextStatus }}」
          </el-button>
          <el-button plain @click="router.back()">返回</el-button>
        </div>
      </section>

      <!-- 1 判定说明 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">判定说明</h3>
        <p class="event-detail__explain">{{ formatExplanation(event.description) }}</p>
      </section>

      <!-- 2 基本信息：判定属性在前，数据出处在后 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">基本信息</h3>
        <div class="event-detail__grid">
          <div class="event-detail__item"><span>所属场景</span><strong>{{ SCENARIO_LABEL[event.scenario_id] ?? event.scenario_id }}</strong></div>
          <div class="event-detail__item"><span>风险评分</span><strong class="level-text">{{ scoreText }}</strong></div>
          <div class="event-detail__item"><span>原始标签</span><strong>{{ originalLabelText }}</strong></div>
          <div class="event-detail__item"><span>发生时间</span><strong>{{ event.occurred_at }}</strong></div>
          <div v-if="event.fault_position_x != null" class="event-detail__item"><span>故障位置 X</span><strong>{{ event.fault_position_x }}</strong></div>
          <div v-if="event.fault_position_y != null" class="event-detail__item"><span>故障位置 Y</span><strong>{{ event.fault_position_y }}</strong></div>
          <div class="event-detail__item"><span>数据集</span><strong>{{ event.dataset_id }}</strong></div>
          <div class="event-detail__item"><span>数据集版本</span><strong>{{ event.dataset_version }}</strong></div>
          <div class="event-detail__item"><span>模型版本</span><strong>{{ event.model_version_id }}</strong></div>
          <div class="event-detail__item"><span>算法</span><strong>{{ event.algorithm_id }}</strong></div>
          <div class="event-detail__item"><span>推理记录</span><strong>{{ event.inference_record_id }}</strong></div>
          <div class="event-detail__item"><span>创建者</span><strong>{{ creatorName }}</strong></div>
        </div>
      </section>

      <!-- 4 输入特征 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">
          输入特征
          <span class="event-detail__count">{{ featureEntries.length }} 项</span>
        </h3>
        <div class="event-detail__features" :class="{ 'is-collapsed': !featuresExpanded }">
          <div v-for="entry in visibleFeatureEntries" :key="entry.key" class="event-detail__feature-row">
            <span class="event-detail__feature-key">{{ entry.key }}</span>
            <span class="event-detail__feature-value">{{ entry.value }}</span>
          </div>
        </div>
        <el-button
          v-if="featureEntries.length > 50"
          size="small"
          plain
          class="event-detail__expand"
          @click="featuresExpanded = !featuresExpanded"
        >
          {{ featuresExpanded ? '收起' : `展开全部（${featureEntries.length} 项）` }}
        </el-button>
      </section>
    </template>
  </div>
</template>

<style scoped>
.event-detail {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 18px;
}

.event-detail__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 22px 26px;
}

.event-detail__head h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
  color: #c8deff;
}

.event-detail__id {
  margin: 0;
  font-size: 0.95rem;
  color: rgba(180, 200, 235, 0.55);
  font-variant-numeric: tabular-nums;
}

.event-detail__head-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 14px;
  flex-shrink: 0;
}

/* 尺寸与 RiskLevelTag 的 large 变体、以及同排按钮三者对齐：
   min-width 80 / height 32 / padding 0 16 / 字号 0.85rem。
   两个状态徽章等宽，换行时也不会参差。 */
.event-detail__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
  height: 32px;
  padding: 0 16px;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
}

/* 页头按钮与两个徽章统一为胶囊，尺寸同上 —— 这一行是「状态 + 动作」，
   尺寸和形状不齐会显得散。 */
.event-detail__head-actions :deep(.el-button) {
  height: 32px;
  padding: 0 18px;
  border-radius: 999px;
  font-size: 0.85rem;
}

.event-detail__status--pending {
  background: rgba(255, 177, 107, 0.12);
  color: rgba(230, 180, 110, 0.9);
}

.event-detail__status--processing {
  background: rgba(91, 166, 255, 0.12);
  color: rgba(155, 195, 240, 0.9);
}

.event-detail__status--resolved {
  background: rgba(83, 229, 200, 0.12);
  color: rgba(83, 229, 200, 0.85);
}

.event-detail__card {
  padding: 20px 24px;
}

.event-detail__card-title {
  margin: 0 0 16px;
  font-size: 1rem;
  color: #e8f1ff;
}

.event-detail__count {
  margin-left: 8px;
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.5);
  font-weight: 400;
}

.event-detail__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.event-detail__item {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 11px 14px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.event-detail__item span {
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.55);
}

.event-detail__item strong {
  font-size: 0.9rem;
  color: #dbe9ff;
  word-break: break-all;
}

.event-detail__item .level-text {
  color: #ffd166;
}

/* 输入特征（超宽特征折叠滚动，避免卡顿） */
.event-detail__features {
  display: grid;
  gap: 6px;
}

.event-detail__features.is-collapsed {
  max-height: 320px;
  overflow-y: auto;
}

.event-detail__feature-row {
  display: grid;
  grid-template-columns: minmax(180px, 260px) 1fr;
  gap: 12px;
  padding: 7px 12px;
  border-radius: 8px;
  background: rgba(6, 15, 28, 0.6);
  border: 1px solid rgba(125, 201, 255, 0.06);
}

.event-detail__feature-key {
  font-size: 0.82rem;
  color: #9ad6ff;
  word-break: break-all;
}

.event-detail__feature-value {
  font-size: 0.82rem;
  color: rgba(217, 232, 255, 0.9);
  word-break: break-all;
}

.event-detail__expand {
  margin-top: 12px;
}

.event-detail__explain {
  margin: 0;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(91, 166, 255, 0.07);
  border: 1px solid rgba(91, 166, 255, 0.18);
  color: #dbe9ff;
  font-size: 0.92rem;
  line-height: 1.7;
}

@media (max-width: 768px) {
  .event-detail__head {
    flex-direction: column;
    align-items: flex-start;
  }
  .event-detail__head-actions {
    justify-content: flex-start;
  }
  .event-detail__feature-row {
    grid-template-columns: 1fr;
    gap: 4px;
  }
}
</style>

<style>
/* Element Plus 暗色覆盖（event-detail 命名空间） */
.event-detail .el-button--primary {
  --el-button-bg-color: #5ba6ff;
  --el-button-border-color: #5ba6ff;
  --el-button-text-color: #ffffff;
  --el-button-hover-bg-color: #4a94ee;
  --el-button-hover-border-color: #4a94ee;
  --el-button-hover-text-color: #ffffff;
}

.event-detail .el-button.is-plain {
  --el-button-bg-color: rgba(91, 166, 255, 0.1) !important;
  --el-button-border-color: rgba(91, 166, 255, 0.35) !important;
  --el-button-text-color: #9ad6ff !important;
  --el-button-hover-bg-color: rgba(91, 166, 255, 0.2) !important;
  --el-button-hover-border-color: rgba(91, 166, 255, 0.5) !important;
  --el-button-hover-text-color: #bae3ff !important;
}
</style>
