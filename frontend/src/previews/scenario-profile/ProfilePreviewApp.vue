<script setup lang="ts">
/**
 * ProfilePreviewApp，四场景画像驾驶舱的开发预览入口（不接入路由，不请求后端）。
 * 只用于版式验收（1440×900 / 1920×1080 截图、检查重叠与溢出）：
 * 数据全部来自 previewSample.ts 的示例值，页面右下角固定标注「示例数据」。
 * 正式页面 AdminProfilePage 走真实接口，本文件不被其导入。
 */
import { computed, ref } from 'vue';
import ProfileCockpitShell from './ProfileCockpitShell.vue';
import NetworkProfileBoard from './boards/NetworkProfileBoard.vue';
import PowerProfileBoard from './boards/PowerProfileBoard.vue';
import FlightdeckProfileBoard from './boards/FlightdeckProfileBoard.vue';
import GeologicalProfileBoard from './boards/GeologicalProfileBoard.vue';
import {
  flightdeckMembers,
  flightdeckRuntime,
  flightdeckSample,
  geologicalMembers,
  geologicalRuntime,
  geologicalSample,
  networkMembers,
  networkRuntime,
  networkSample,
  powerMembers,
  powerRuntime,
  powerSample,
} from './previewSample';

type PreviewScene = 'network' | 'power' | 'flightdeck' | 'geological';

const SCENES: Array<{ key: PreviewScene; label: string }> = [
  { key: 'network', label: '网络安全' },
  { key: 'power', label: '电力系统' },
  { key: 'flightdeck', label: '舰面调度' },
  { key: 'geological', label: '地质风险' },
];

const scene = ref<PreviewScene>('network');
const sceneFromUrl = new URLSearchParams(window.location.search).get('scene');
if (sceneFromUrl && SCENES.some((item) => item.key === sceneFromUrl)) scene.value = sceneFromUrl as PreviewScene;

const title = computed(() => {
  if (scene.value === 'network') return '网络安全 · 数据画像';
  if (scene.value === 'power') return '电力系统 · 数据画像';
  if (scene.value === 'flightdeck') return '舰面调度态势 · 数据画像';
  return '地质风险 · 数据画像';
});

const select = (key: PreviewScene) => {
  scene.value = key;
};
</script>

<template>
  <div class="pv-shell">
    <!-- 假顶栏：高度与正式页面的应用顶栏一致，保证可用高度可比 -->
    <div class="pv-topbar">
      <span class="pv-brand">AI SECURITY OPERATIONS CENTER</span>
      <span class="pv-scene">场景数据画像 · 版式预览</span>
    </div>

    <div class="pv-wrap">
      <ProfileCockpitShell
        eyebrow="Admin · Scenario Data Profile"
        :title="title"
        status-text="开发预览：示例数据，非真实统计"
      >
        <NetworkProfileBoard
          v-if="scene === 'network'"
          :data="networkSample"
          :runtime="networkRuntime"
          :members="networkMembers"
          :member-total="networkMembers.length"
        />
        <PowerProfileBoard
          v-else-if="scene === 'power'"
          :data="powerSample"
          :runtime="powerRuntime"
          :members="powerMembers"
          :member-total="powerMembers.length"
        />
        <FlightdeckProfileBoard
          v-else-if="scene === 'flightdeck'"
          :data="flightdeckSample"
          :runtime="flightdeckRuntime"
          :members="flightdeckMembers"
          :member-total="flightdeckMembers.length"
        />
        <GeologicalProfileBoard
          v-else
          :data="geologicalSample"
          :runtime="geologicalRuntime"
          :members="geologicalMembers"
          :member-total="geologicalMembers.length"
        />
      </ProfileCockpitShell>
    </div>

    <div class="pv-tools">
      <span class="pv-flag">示例数据 · 非真实统计</span>
      <button
        v-for="item in SCENES"
        :key="item.key"
        type="button"
        :class="{ 'is-active': scene === item.key }"
        @click="select(item.key)"
      >
        {{ item.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.pv-shell {
  min-height: 100vh;
  padding: 28px;
  box-sizing: border-box;
}

.pv-topbar {
  height: 97px;
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
}

.pv-brand {
  color: #7dc9ff;
  font-size: 0.72rem;
  letter-spacing: 0.24em;
  text-transform: uppercase;
}

.pv-scene {
  color: #eaf3ff;
  font-size: 1.8rem;
  font-weight: 600;
}

.pv-wrap {
  padding: 0 16px 20px;
  box-sizing: border-box;
}

.pv-tools {
  position: fixed;
  right: 18px;
  bottom: 14px;
  z-index: 50;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(125, 201, 255, 0.24);
  border-radius: 8px;
  background: rgba(8, 17, 31, 0.92);
}

.pv-flag {
  color: #ffd166;
  font-size: 11px;
}

.pv-tools button {
  padding: 4px 10px;
  border: 1px solid rgba(125, 201, 255, 0.22);
  border-radius: 999px;
  background: transparent;
  color: #9ad6ff;
  font-size: 11px;
}

.pv-tools button.is-active {
  border-color: #5ba6ff;
  background: rgba(91, 166, 255, 0.18);
  color: #eaf3ff;
}
</style>
