<script setup lang="ts">
/**
 * ScenarioCenter - 场景中心页面
 *
 * 展示三大场景卡片：网络安全 / 电力系统 / 航母甲板
 * 点击卡片跳转至对应场景大屏
 */
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import type { Scenario } from '@/types/security';
import { getScenarioList } from '@/api/index';
import ScenarioCard from '@/components/common/ScenarioCard.vue';

const router = useRouter();

/** 场景列表数据 */
const scenarios = ref<Scenario[]>([]);
/** 加载状态 */
const loading = ref(true);
/** 错误信息 */
const error = ref('');

/** 获取场景列表 */
const loadScenarios = async () => {
  loading.value = true;
  error.value = '';
  try {
    scenarios.value = await getScenarioList();
  } catch (err) {
    error.value = err instanceof Error ? err.message : '场景数据加载失败';
  } finally {
    loading.value = false;
  }
};

/** 点击卡片 -> 跳转场景大屏 */
const goScenarioDashboard = (scenarioId: string) => {
  router.push({ path: `/scenarios/${scenarioId}/dashboard` });
};

onMounted(() => {
  loadScenarios();
});
</script>

<template>
  <div class="scenario-center">
    <!-- 页面头部 -->
    <div class="scenario-center__header">
      <div>
        <p class="eyebrow">Scenario Center</p>
        <h2>场景中心</h2>
        <p class="scenario-center__desc">
          选择业务场景，进入专属态势感知大屏
        </p>
      </div>
    </div>

    <!-- 加载状态 -->
    <section v-if="loading" class="state-card">
      <div class="loader"></div>
      <p>正在加载场景数据...</p>
    </section>

    <!-- 错误状态 -->
    <section v-else-if="error" class="state-card state-card--error">
      <p>{{ error }}</p>
      <button class="ghost-button" @click="loadScenarios">重试</button>
    </section>

    <!-- 场景卡片网格 -->
    <div v-else class="scenario-center__grid">
      <ScenarioCard
        v-for="scenario in scenarios"
        :key="scenario.scenario_id"
        :scenario="scenario"
        @click="goScenarioDashboard"
      />
    </div>
  </div>
</template>

<style scoped>
.scenario-center {
  position: relative;
  z-index: 1;
  padding: 0;
}

.scenario-center__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 28px;
}

.scenario-center__header h2 {
  margin: 0 0 8px;
  font-size: 1.6rem;
}

.scenario-center__desc {
  margin: 0;
  color: rgba(220, 234, 255, 0.7);
  font-size: 0.95rem;
}

/* 场景卡片网格 3 列布局 */
.scenario-center__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 20px;
}

/* 响应式降级 */
@media (max-width: 1200px) {
  .scenario-center__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .scenario-center__grid {
    grid-template-columns: 1fr;
  }
}
</style>
