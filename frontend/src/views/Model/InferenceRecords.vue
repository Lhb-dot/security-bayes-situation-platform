<script setup lang="ts">
/**
 * InferenceRecords - 推理记录
 *
 * 需求 6.2（P0）：普通用户只能查询本人推理记录；管理员可以查询平台全部推理记录。
 * 需求 6.8.4：管理员查看单个用户数据时，可以按用户ID筛选。
 */
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { getInferenceRecordList } from '@/api/inferenceRecordApi';
import { useUserStore } from '@/stores/userStore';

/** 真实推理记录（后端 /api/v1/inference-records 返回结构，含补全展示字段） */
interface InferenceRecordItem {
  id: number;
  user_id: number;
  model_version_id: number;
  scenario_id: number;
  scenario_code: string | null;
  algorithm_id: number;
  algorithm_name: string | null;
  dataset_id: number;
  dataset_logical_id: string | null;
  dataset_version: number;
  risk_type: string | null;
  original_label: string;
  prediction_label: string;
  risk_level: string | null;
  risk_score: number | null;
  is_risk_event: boolean;
  executed_at: string;
  risk_event_id: number | null;
  input_features: Record<string, unknown>;
}

const records = ref<InferenceRecordItem[]>([]);
const loading = ref(false);
const router = useRouter();
const userStore = useUserStore();

/** 是否管理员（决定描述文案） */
const isAdmin = computed(() => userStore.currentUser?.role === 'SUPER_ADMIN' || userStore.currentUser?.role === 'SCENARIO_ADMIN');

/** 场景数字 ID → 名称 */
const SCENARIO_META: Record<number, { code: string; name: string }> = {
  1: { code: 'network_security', name: '网络安全' },
  2: { code: 'power_system', name: '电力系统' },
  3: { code: 'flightdeck_operation', name: '航母甲板作业' },
  4: { code: 'geological_risk', name: '地质风险' },
};
const scenarioName = (id: number) => SCENARIO_META[id]?.name ?? String(id);

const loadRecords = async () => {
  loading.value = true;
  try {
    const items = await getInferenceRecordList({ page_size: 200 });
    records.value = items as unknown as InferenceRecordItem[];
  } finally {
    loading.value = false;
  }
};

// 查看输入特征
const featureTarget = ref<InferenceRecordItem | null>(null);
const openFeatures = (r: InferenceRecordItem) => {
  featureTarget.value = r;
};

/** 风险记录 → 跳转风险事件详情 */
const goEventDetail = (r: InferenceRecordItem) => {
  if (r.risk_event_id == null) {
    ElMessage.info('该记录未生成风险事件');
    return;
  }
  router.push({ path: `/events/${r.risk_event_id}` });
};

onMounted(() => {
  loadRecords();
});
</script>

<template>
  <div class="records-page">
    <div class="records-page__header">
      <div>
        <p class="eyebrow">Inference Records</p>
        <h2>推理记录</h2>
        <p class="records-page__desc">
          {{ isAdmin ? '平台全部推理记录（可筛选用户）' : '仅显示本人发起的推理记录' }}
        </p>
      </div>
    </div>

    <section class="card records-section">
      <div class="records-table-wrap">
        <table class="records-table">
          <thead>
            <tr>
              <th>推理记录ID</th>
              <th>发起人</th>
              <th>场景</th>
              <th>数据集</th>
              <th>版本</th>
              <th>算法</th>
              <th>模型版本</th>
              <th>原始标签</th>
              <th>风险类型</th>
              <th>等级</th>
              <th>风险概率</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in records" :key="r.id">
              <td>{{ r.id }}</td>
              <td>{{ r.user_id }}</td>
              <td>{{ scenarioName(r.scenario_id) }}</td>
              <td>{{ r.dataset_logical_id }}</td>
              <td>{{ r.dataset_version }}</td>
              <td>{{ r.algorithm_name }}</td>
              <td>{{ r.model_version_id }}</td>
              <td>{{ r.original_label }}</td>
              <td>
                <span v-if="r.is_risk_event" class="risk-badge">{{ r.risk_type }}</span>
                <span v-else class="normal-badge">正常</span>
              </td>
              <td>
                <span v-if="r.is_risk_event" class="level-badge" :class="`level-badge--${r.risk_level}`">{{ r.risk_level }}</span>
                <span v-else>—</span>
              </td>
              <td>{{ r.is_risk_event ? ((r.risk_score ?? 0) * 100).toFixed(1) + '%' : '—' }}</td>
              <td>{{ r.executed_at }}</td>
              <td>
                <div class="op-group">
                  <button class="op-btn" @click="openFeatures(r)">输入特征</button>
                  <button v-if="r.is_risk_event" class="op-btn" @click="goEventDetail(r)">查看事件</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="loading" class="records-empty">加载中...</p>
        <p v-else-if="records.length === 0" class="records-empty">暂无推理记录</p>
      </div>
    </section>

    <!-- 输入特征弹窗 -->
    <div v-if="featureTarget" class="modal-mask" @click.self="featureTarget = null">
      <div class="modal-card">
        <div class="modal-card__head">
          <h3>推理输入特征 — {{ featureTarget.id }}</h3>
          <button class="modal-close" @click="featureTarget = null">✕</button>
        </div>
        <div class="modal-card__body">
          <pre class="feature-json">{{ JSON.stringify(featureTarget.input_features, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.records-page {
  position: relative;
  z-index: 1;
}

.records-page__header {
  margin-bottom: 20px;
}

.records-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.records-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.records-filters {
  display: flex;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-item__label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.filter-select {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.88rem;
  outline: none;
}

.filter-select option {
  background: #0b1628;
  color: #e8f1ff;
}

.records-section {
  padding: 20px 24px;
}

.records-table-wrap {
  overflow-x: auto;
}

.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.records-table th {
  text-align: left;
  padding: 11px 12px;
  color: rgba(154, 214, 255, 0.8);
  font-weight: 600;
  border-bottom: 1px solid rgba(125, 201, 255, 0.15);
  white-space: nowrap;
}

.records-table td {
  padding: 11px 12px;
  color: rgba(217, 232, 255, 0.9);
  border-bottom: 1px solid rgba(125, 201, 255, 0.07);
  white-space: nowrap;
}

.records-table tbody tr:hover {
  background: rgba(20, 44, 72, 0.5);
}

.records-empty {
  padding: 24px;
  text-align: center;
  color: rgba(220, 234, 255, 0.5);
}

.op-btn {
  padding: 5px 12px;
  border: 1px solid rgba(125, 201, 255, 0.28);
  border-radius: 6px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.8rem;
  cursor: pointer;
}

.op-btn:hover {
  background: rgba(91, 166, 255, 0.2);
}

.op-group {
  display: flex;
  gap: 6px;
}

.risk-badge,
.normal-badge,
.level-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 0.76rem;
}

.risk-badge {
  background: rgba(255, 123, 114, 0.14);
  color: #ff7b72;
}

.normal-badge {
  background: rgba(83, 229, 200, 0.12);
  color: #53e5c8;
}

.level-badge--HIGH {
  background: rgba(255, 123, 114, 0.18);
  color: #ff8a83;
}

.level-badge--MEDIUM {
  background: rgba(255, 209, 102, 0.16);
  color: #ffd166;
}

.level-badge--LOW {
  background: rgba(91, 166, 255, 0.14);
  color: #9ad6ff;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(3, 8, 16, 0.7);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-card {
  width: 520px;
  max-width: calc(100vw - 40px);
  border-radius: 14px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  background: linear-gradient(160deg, rgba(13, 26, 46, 0.96), rgba(8, 17, 31, 0.98));
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}

.modal-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(125, 201, 255, 0.1);
}

.modal-card__head h3 {
  margin: 0;
  font-size: 1.02rem;
}

.modal-close {
  border: none;
  background: transparent;
  color: rgba(220, 234, 255, 0.6);
  font-size: 1rem;
  cursor: pointer;
}

.modal-card__body {
  padding: 18px 20px;
  max-height: 60vh;
  overflow: auto;
}

.feature-json {
  margin: 0;
  padding: 14px;
  border-radius: 8px;
  background: rgba(6, 15, 28, 0.85);
  color: #9ad6ff;
  font-size: 0.82rem;
  line-height: 1.6;
  overflow: auto;
}
</style>
