<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import type { AlertRecord, DashboardSnapshot } from '../types/security';
import ThreatMap from './ThreatMap.vue';

const props = defineProps<{
  snapshot: DashboardSnapshot;
  alerts: AlertRecord[];
}>();

const emit = defineEmits<{
  close: [];
  openAlert: [id: string];
}>();

const panelRef = ref<HTMLElement | null>(null);
const feedIndex = ref(0);
let timer: number | undefined;

const rotatingAlerts = computed(() => {
  if (!props.alerts.length) return [];
  return Array.from({ length: Math.min(5, props.alerts.length) }, (_, index) => {
    return props.alerts[(feedIndex.value + index) % props.alerts.length];
  });
});

const enterFullscreen = async () => {
  if (panelRef.value && document.fullscreenElement !== panelRef.value) {
    await panelRef.value.requestFullscreen?.();
  }
};

const exitFullscreen = async () => {
  if (document.fullscreenElement) {
    await document.exitFullscreen();
  }
};

const closeWarRoom = async () => {
  await exitFullscreen();
  emit('close');
};

onMounted(() => {
  void enterFullscreen();
  timer = window.setInterval(() => {
    feedIndex.value = (feedIndex.value + 1) % Math.max(props.alerts.length, 1);
  }, 2600);
});

onBeforeUnmount(() => {
  if (timer) {
    window.clearInterval(timer);
  }
  void exitFullscreen();
});
</script>

<template>
  <div ref="panelRef" class="war-room">
    <div class="war-room__backdrop"></div>
    <header class="war-room__topbar">
      <div>
        <p class="eyebrow">War Room Mode</p>
        <h2>全屏威胁作战视图</h2>
      </div>
      <div class="war-room__actions">
        <button class="ghost-button" @click="enterFullscreen">进入全屏</button>
        <button class="ghost-button" @click="exitFullscreen">退出全屏</button>
        <button class="ghost-button" @click="closeWarRoom">关闭作战模式</button>
      </div>
    </header>

    <section class="war-room__metrics">
      <article v-for="metric in snapshot.metrics" :key="metric.label" class="war-room__metric">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
      </article>
    </section>

    <section class="war-room__main">
      <article class="card war-room__map">
        <div class="section-heading">
          <div>
            <p class="eyebrow">Situation View</p>
            <h3>超大地图联动</h3>
          </div>
          <span class="section-tag">悬浮查看攻击链路</span>
        </div>
        <ThreatMap :maps="snapshot.sourceMap" large />
      </article>

      <aside class="war-room__side">
        <article class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Live Feed</p>
              <h3>实时攻击播报</h3>
            </div>
          </div>
          <div class="war-room__feed">
            <button
              v-for="alert in rotatingAlerts"
              :key="`${alert.id}-${feedIndex}`"
              class="war-room__feed-item"
              @click="$emit('openAlert', alert.id)"
            >
              <strong>{{ alert.title }}</strong>
              <span>{{ alert.sourceIp }} -> {{ alert.targetHost }}</span>
              <em>{{ alert.attackType }}</em>
            </button>
          </div>
        </article>

        <article class="card">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Playbook</p>
              <h3>互动操作建议</h3>
            </div>
          </div>
          <div class="war-room__playbook">
            <button class="war-room__playbook-item">按风险等级筛选高危链路</button>
            <button class="war-room__playbook-item">切换中国 / 世界攻击视角</button>
            <button class="war-room__playbook-item">悬浮折线图查看时段明细</button>
            <button class="war-room__playbook-item">点击告警进入 AI 分析详情</button>
          </div>
        </article>
      </aside>
    </section>
  </div>
</template>
