<script setup lang="ts">
import type { AlertRecord } from '../types/security';
// 补上路由导入
import { useRouter } from 'vue-router';

// 初始化路由实例
const router = useRouter();

const props = defineProps<{
  alert: AlertRecord;
}>();

defineEmits<{
  back: [];
}>();

/**
 * 告警详情页跳转AI风险研判页面
 * 通过query携带本条告警流量特征参数，进入页面自动回填做单样本风险推理
 */
const goAiPredict = () => {
  router.push({
    path: '/risk',
    query: {
      fl: props.alert.flowLength,
      du: props.alert.duration,
      af: props.alert.accessFreq
    }
  });
};
</script>

<template>
  <div class="detail-layout">
    <section class="card detail-hero">
      <button class="ghost-button" @click="$emit('back')">返回告警列表</button>
      <button class="ghost-button" style="margin-left: 12px" @click="goAiPredict">AI风险溯源研判</button>
      <div class="detail-hero__header">
        <div>
          <p class="eyebrow">Incident Detail</p>
          <h2>{{ alert.title }}</h2>
          <p class="detail-hero__sub">{{ alert.sourceIp }} -> {{ alert.targetHost }}</p>
        </div>
        <span :class="['risk-badge', `risk-${alert.riskLevel.toLowerCase()}`]">{{ alert.riskLevel }}</span>
      </div>
    </section>

    <section class="detail-grid">
      <article class="card detail-block">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Overview</p>
            <h3>基本信息</h3>
          </div>
        </div>
        <div class="detail-info">
          <div>
            <span>告警 ID</span><strong>{{ alert.id }}</strong>
          </div>
          <div>
            <span>攻击类型判断</span><strong>{{ alert.attackType }}</strong>
          </div>
          <div>
            <span>攻击时间</span><strong>{{ alert.timestamp }}</strong>
          </div>
          <div>
            <span>当前状态</span><strong>{{ alert.status }}</strong>
          </div>
        </div>
      </article>

      <article class="card detail-block">
        <div class="section-heading">
          <div>
            <p class="eyebrow">AI Result</p>
            <h3>AI 分析结果</h3>
          </div>
        </div>
        <p class="detail-paragraph">{{ alert.aiAnalysis }}</p>
        <p class="detail-chip">模型置信度 {{ alert.confidence }}%</p>
      </article>

      <article class="card detail-block">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Advice</p>
            <h3>处置建议</h3>
          </div>
        </div>
        <ul class="detail-list">
          <li v-for="item in alert.recommendations" :key="item">{{ item }}</li>
        </ul>
      </article>

      <article class="card detail-block detail-block--wide">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Raw Log</p>
            <h3>原始日志</h3>
          </div>
        </div>
        <pre class="log-panel">{{ alert.rawLog }}</pre>
      </article>

      <article class="card detail-block detail-block--wide">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Timeline</p>
            <h3>攻击时间线</h3>
          </div>
        </div>
        <div class="timeline">
          <div v-for="event in alert.timeline" :key="event.time + event.stage" class="timeline__item">
            <div class="timeline__dot"></div>
            <div class="timeline__content">
              <div class="timeline__head">
                <strong>{{ event.stage }}</strong>
                <time>{{ event.time }}</time>
              </div>
              <p>{{ event.description }}</p>
            </div>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>
