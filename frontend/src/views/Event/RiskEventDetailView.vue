<script setup lang="ts">
/**
 * RiskEventDetailView.vue — 风险事件详情页（Task 012 / 需求 5.7）
 *
 * 五组信息：基本信息 / 模型溯源 / 推理详情 / 输入特征 / 可解释性文本。
 * 处置状态流转：待处置 → 处理中 → 已处置（已处置为终态禁用）。
 * 解释文本为事件生成时固化存储，前端不拼接、不重算（需求 5.7.3.1/5.7.3.4）。
 */
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { useRiskEventStore } from '@/stores/riskEventStore';
import { useUserStore } from '@/stores/userStore';
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

const riskLevelLabel: Record<RiskEvent['risk_level'], string> = {
  HIGH: '高危',
  MEDIUM: '中危',
  LOW: '低危',
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
  if (!event.value || !nextStatus.value) return;
  try {
    await riskEventStore.updateStatus(event.value.event_id, nextStatus.value);
    ElMessage.success(`已更新处置状态为「${nextStatus.value}」`);
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
      <!-- 头部 -->
      <section class="card event-detail__head">
        <div>
          <p class="eyebrow">Risk Event Detail</p>
          <h2>风险事件详情</h2>
          <p class="event-detail__id">{{ event.event_id }}</p>
        </div>
        <div class="event-detail__head-actions">
          <RiskLevelTag :level="tagLevel" size="large" />
          <el-button plain @click="router.back()">返回</el-button>
        </div>
      </section>

      <!-- 1 基本信息 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">基本信息</h3>
        <div class="event-detail__grid">
          <div class="event-detail__item"><span>事件 ID</span><strong>{{ event.event_id }}</strong></div>
          <div class="event-detail__item"><span>所属场景</span><strong>{{ SCENARIO_LABEL[event.scenario_id] ?? event.scenario_id }}</strong></div>
          <div class="event-detail__item"><span>数据集</span><strong>{{ event.dataset_id }}</strong></div>
          <div class="event-detail__item"><span>风险类型</span><strong>{{ event.risk_type || '—' }}</strong></div>
          <div class="event-detail__item"><span>风险等级</span><strong class="level-text">{{ riskLevelLabel[event.risk_level] }}</strong></div>
          <div class="event-detail__item"><span>风险评分</span><strong>{{ Math.round(event.risk_score * 100) }}%</strong></div>
          <div class="event-detail__item"><span>原始标签</span><strong>{{ event.original_label }}</strong></div>
          <div class="event-detail__item"><span>发生时间</span><strong>{{ event.occurred_at }}</strong></div>
          <div class="event-detail__item"><span>处置状态</span><strong :class="event.status === '已处置' ? 'status-done' : ''">{{ event.status }}</strong></div>
          <div v-if="event.fault_position_x != null" class="event-detail__item"><span>故障位置 X</span><strong>{{ event.fault_position_x }}</strong></div>
          <div v-if="event.fault_position_y != null" class="event-detail__item"><span>故障位置 Y</span><strong>{{ event.fault_position_y }}</strong></div>
        </div>
      </section>

      <!-- 2 模型溯源 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">模型溯源</h3>
        <div class="event-detail__grid">
          <div class="event-detail__item"><span>模型版本</span><strong>{{ event.model_version_id }}</strong></div>
          <div class="event-detail__item"><span>算法</span><strong>{{ event.algorithm_id }}</strong></div>
          <div class="event-detail__item"><span>数据集版本</span><strong>{{ event.dataset_version }}</strong></div>
          <div class="event-detail__item"><span>创建者</span><strong>{{ creatorName }}</strong></div>
        </div>
      </section>

      <!-- 3 推理详情 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">推理详情</h3>
        <div class="event-detail__grid">
          <div class="event-detail__item"><span>推理记录</span><strong>{{ event.inference_record_id }}</strong></div>
          <div class="event-detail__item"><span>风险概率</span><strong>{{ Math.round(event.risk_score * 100) }}%</strong></div>
          <div class="event-detail__item"><span>原始标签</span><strong>{{ event.original_label }}</strong></div>
          <div class="event-detail__item">
            <span>标签 vs 风险对照</span>
            <strong>{{ event.original_label }} ↔ {{ riskLevelLabel[event.risk_level] }}（{{ Math.round(event.risk_score * 100) }}%）</strong>
          </div>
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

      <!-- 5 可解释性文本 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">可解释性文本</h3>
        <p class="event-detail__explain">{{ event.description }}</p>
        <p class="event-detail__hint">解释文本在事件生成时固化存储（需求 5.7.3.1），不随阈值修改重算（需求 5.7.3.4）。</p>
      </section>

      <!-- 处置操作 -->
      <section class="card event-detail__card">
        <h3 class="event-detail__card-title">处置操作</h3>
        <div class="event-detail__ops">
          <span class="event-detail__ops-status">当前状态：{{ event.status }}</span>
          <el-button v-if="nextStatus" type="primary" @click="handleStatusChange">
            流转至「{{ nextStatus }}」
          </el-button>
          <el-tag v-else type="success" effect="dark">已处置（终态）</el-tag>
        </div>
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
  margin: 8px 0 4px;
  font-size: 1.45rem;
}

.event-detail__id {
  margin: 0;
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.55);
  font-variant-numeric: tabular-nums;
}

.event-detail__head-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-shrink: 0;
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

.event-detail__item .status-done {
  color: #53e5c8;
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

.event-detail__hint {
  margin: 10px 0 0;
  font-size: 0.78rem;
  color: rgba(220, 234, 255, 0.45);
}

.event-detail__ops {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.event-detail__ops-status {
  font-size: 0.9rem;
  color: rgba(220, 234, 255, 0.75);
}

@media (max-width: 768px) {
  .event-detail__head {
    flex-direction: column;
    align-items: flex-start;
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
