<script setup lang="ts">
import type { AlertRecord } from '../../types/security';
import { useRouter } from 'vue-router';

// 初始化路由实例
const router = useRouter();

defineProps<{
  alerts: AlertRecord[];
}>();

defineEmits<{
  openAlert: [id: string];
}>();

/**
 * 告警列表页AI风险研判跳转
 * 通过Vue Router编程式导航携带本条告警三个归一化流量特征，目标页面自动回填推理
 * @param alertItem 当前点击单条告警对象
 */
const jumpBayesAnalyze = (alertItem: AlertRecord) => {
  router.push({
    path: '/risk',
    query: {
      fl: alertItem.flowLength,
      du: alertItem.duration,
      af: alertItem.accessFreq
    }
  });
};
</script>

<template>
  <section class="card alerts-page">
    <div class="section-heading">
      <div>
        <p class="eyebrow">Alert Center</p>
        <h2>告警详情页</h2>
      </div>
      <span class="section-tag">{{ alerts.length }} 条模拟告警</span>
    </div>

    <div class="alerts-table">
      <div class="alerts-table__head">
        <span>告警标题</span>
        <span>攻击类型</span>
        <span>攻击源 IP</span>
        <span>受攻击主机</span>
        <span>风险等级</span>
        <span>时间</span>
        <!-- 表头新增一列 -->
        <span>AI操作</span>
      </div>
      <!-- 外层div包裹，避免整行按钮冲突原有openAlert事件 -->
      <div v-for="alert in alerts" :key="alert.id" class="alerts-table__row" @click="$emit('openAlert', alert.id)">
        <span>{{ alert.title }}</span>
        <span>{{ alert.attackType }}</span>
        <span>{{ alert.sourceIp }}</span>
        <span>{{ alert.targetHost }}</span>
        <span
          ><i :class="['risk-badge', `risk-${alert.riskLevel.toLowerCase()}`]">{{ alert.riskLevel }}</i></span
        >
        <span>{{ alert.timestamp }}</span>
        <!-- 新增AI研判按钮，阻止冒泡防止点开告警详情 -->
        <button class="ai-btn" @click.stop="jumpBayesAnalyze(alert)">AI风险研判</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ai-btn {
  background: #407acc;
  color: #fff;
  border: none;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
}
</style>
