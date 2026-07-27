<script setup lang="ts">
/**
 * RiskInference - 风险研判页面
 *
 * 左侧：输入特征（duration/protocol/service/src_bytes/dst_bytes）
 * 右侧：推理结果展示
 */
import { ref } from 'vue';
import { getInferenceResult } from '@/services/mockApi';
import type { InferenceResult } from '@/services/mockApi';

const inputData = ref({
  duration: 0.0,
  protocol: 'tcp',
  service: 'http',
  src_bytes: 0,
  dst_bytes: 0,
});

const inferResult = ref<InferenceResult | null>(null);
const inferring = ref(false);
const hasInferred = ref(false);

const handleInfer = async () => {
  inferring.value = true;
  inferResult.value = null;
  hasInferred.value = false;
  try {
    const result = await getInferenceResult(inputData.value);
    inferResult.value = result;
    hasInferred.value = true;
  } catch {
    // ignore
  } finally {
    inferring.value = false;
  }
};
</script>

<template>
  <div class="inference-page">
    <div class="inference-page__header">
      <div>
        <p class="eyebrow">Risk Inference</p>
        <h2>风险研判</h2>
        <p class="inference-page__desc">输入样本特征，执行实时风险推理</p>
      </div>
    </div>

    <div class="inference-layout">
      <!-- 左侧：输入区域 -->
      <section class="card inference-input">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Input</p>
            <h3>输入特征</h3>
          </div>
        </div>

        <div class="inference-form">
          <div class="form-group">
            <label class="form-label">Duration（连接持续时间）</label>
            <input
              v-model.number="inputData.duration"
              type="number"
              step="0.01"
              min="0"
              class="form-input"
              placeholder="0.0"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Protocol（协议类型）</label>
            <select v-model="inputData.protocol" class="form-input">
              <option value="tcp">TCP</option>
              <option value="udp">UDP</option>
              <option value="icmp">ICMP</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Service（目标服务）</label>
            <select v-model="inputData.service" class="form-input">
              <option value="http">HTTP</option>
              <option value="ftp">FTP</option>
              <option value="smtp">SMTP</option>
              <option value="ssh">SSH</option>
              <option value="dns">DNS</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Src Bytes（源到目标字节数）</label>
            <input
              v-model.number="inputData.src_bytes"
              type="number"
              min="0"
              class="form-input"
              placeholder="0"
            />
          </div>

          <div class="form-group">
            <label class="form-label">Dst Bytes（目标到源字节数）</label>
            <input
              v-model.number="inputData.dst_bytes"
              type="number"
              min="0"
              class="form-input"
              placeholder="0"
            />
          </div>

          <button
            class="infer-btn"
            :disabled="inferring"
            @click="handleInfer"
          >
            <span v-if="inferring" class="btn-spinner"></span>
            {{ inferring ? '推理中...' : '执行风险推理' }}
          </button>
        </div>
      </section>

      <!-- 右侧：推理结果 -->
      <section class="card inference-result">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Result</p>
            <h3>推理结果</h3>
          </div>
        </div>

        <div v-if="!hasInferred" class="inference-placeholder">
          <div class="inference-placeholder__icon">🔍</div>
          <p>输入特征后点击「执行风险推理」</p>
        </div>

        <div v-else-if="inferResult" class="inference-result__content">
          <div class="result-item result-item--level">
            <span class="result-item__label">风险等级</span>
            <span
              class="result-item__value result-level-badge"
              :class="`level--${inferResult.risk_level}`"
            >
              {{ inferResult.risk_level }}
            </span>
          </div>

          <div class="result-item">
            <span class="result-item__label">风险概率</span>
            <span class="result-item__value result-item__value--num">
              {{ (inferResult.risk_probability * 100).toFixed(1) }}%
            </span>
          </div>

          <div class="result-item">
            <span class="result-item__label">推荐措施</span>
            <span class="result-item__value">{{ inferResult.recommendation }}</span>
          </div>

          <div class="result-item">
            <span class="result-item__label">使用模型</span>
            <span class="result-item__value">{{ inferResult.model_used }}</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.inference-page {
  position: relative;
  z-index: 1;
}

.inference-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 24px;
}

.inference-page__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.inference-page__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

.inference-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

.inference-form {
  display: grid;
  gap: 18px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 0.85rem;
  color: rgba(220, 234, 255, 0.7);
}

.form-input {
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid rgba(125, 201, 255, 0.2);
  background: rgba(8, 17, 31, 0.6);
  color: #e8f1ff;
  font-size: 0.9rem;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: rgba(91, 166, 255, 0.5);
}

.form-input::placeholder {
  color: rgba(220, 234, 255, 0.3);
}

select.form-input option {
  background: #0b1628;
  color: #e8f1ff;
}

.infer-btn {
  padding: 12px 24px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #5ba6ff, #407acc);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.infer-btn:hover {
  opacity: 0.9;
}

.infer-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 右侧结果 */
.inference-result__content {
  display: grid;
  gap: 20px;
}

.result-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.08);
}

.result-item__label {
  font-size: 0.88rem;
  color: rgba(220, 234, 255, 0.65);
}

.result-item__value {
  font-size: 1rem;
  font-weight: 600;
  color: #e8f1ff;
}

.result-item__value--num {
  font-size: 1.4rem;
  color: #9ad6ff;
  font-variant-numeric: tabular-nums;
}

.result-level-badge {
  padding: 4px 14px;
  border-radius: 999px;
  font-size: 0.95rem;
}

.level--严重 {
  background: rgba(255, 123, 114, 0.18);
  color: #ff8c84;
}

.level--高危 {
  background: rgba(255, 177, 107, 0.18);
  color: #ffc37d;
}

.level--中危 {
  background: rgba(91, 166, 255, 0.18);
  color: #9ad6ff;
}

.level--低危 {
  background: rgba(83, 229, 200, 0.18);
  color: #53e5c8;
}

.inference-placeholder {
  display: grid;
  place-items: center;
  gap: 16px;
  padding: 60px 0;
  color: rgba(220, 234, 255, 0.4);
}

.inference-placeholder__icon {
  font-size: 3rem;
}

@media (max-width: 768px) {
  .inference-layout {
    grid-template-columns: 1fr;
  }
}
</style>
