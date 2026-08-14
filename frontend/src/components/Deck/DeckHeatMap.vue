<script setup lang="ts">
/**
 * DeckHeatMap.vue — 航母甲板热点图（需求 7.4.1）
 *
 * 占位底图（纯色 + 网格，美工替换后仅换背景）+ 按 fault_position_x/y 渲染红色故障点；
 * 坐标基准 1000px，实际渲染坐标 = 原始坐标 ×（当前渲染宽度 / 1000），ResizeObserver 自适应；
 * 悬停 tooltip（风险评分/碰撞概率/发生时间），点击跳风险事件详情。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import type { RiskEvent } from '@/types/security';

const props = withDefaults(
  defineProps<{
    events: RiskEvent[];
    /** 底图基准宽度（需求 7.4.1：1000px） */
    baseWidth?: number;
    /** 占位底图基准高度（按 16:9 推导；美工底图确定后调整） */
    baseHeight?: number;
  }>(),
  {
    baseWidth: 1000,
    baseHeight: 563,
  }
);

const router = useRouter();
const container = ref<HTMLDivElement | null>(null);
const renderWidth = ref(0);
const activePoint = ref<{ event: RiskEvent; left: string; top: string } | null>(null);
let observer: ResizeObserver | null = null;

/** 仅渲染 fault_position_x/y 均非空的事件（需求 7.4.1 规则 3） */
const points = computed(() =>
  props.events.filter((e) => e.fault_position_x != null && e.fault_position_y != null)
);

/** 缩放比例 = 当前渲染宽度 / 1000（高度按同比例，底图保持宽高比） */
const scale = computed(() => (renderWidth.value > 0 ? renderWidth.value / props.baseWidth : 0));

const scaledPoints = computed(() =>
  points.value.map((event) => ({
    event,
    left: `${(Number(event.fault_position_x) * scale.value).toFixed(1)}px`,
    top: `${(Number(event.fault_position_y) * scale.value).toFixed(1)}px`,
  }))
);

const goEventDetail = (eventId: string) => {
  router.push({ path: `/events/${eventId}` });
};

onMounted(() => {
  if (!container.value) return;
  renderWidth.value = container.value.clientWidth;
  observer = new ResizeObserver(() => {
    if (container.value) renderWidth.value = container.value.clientWidth;
  });
  observer.observe(container.value);
});

onBeforeUnmount(() => {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
});
</script>

<template>
  <div
    ref="container"
    class="deck-heatmap"
    :style="{ aspectRatio: `${baseWidth} / ${baseHeight}` }"
  >
    <!-- 占位甲板底图（美工替换后仅换背景图，坐标基准保持一致） -->
    <div class="deck-heatmap__deck">
      <svg
        class="deck-heatmap__svg"
        viewBox="0 0 1000 563"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="deck-sea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#101f3c" />
            <stop offset="100%" stop-color="#0a1628" />
          </linearGradient>
          <linearGradient id="deck-runway" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stop-color="#274068" />
            <stop offset="100%" stop-color="#35507c" />
          </linearGradient>
        </defs>

        <!-- 海面 / 甲板底色 -->
        <rect x="0" y="0" width="1000" height="563" fill="url(#deck-sea)" />

        <!-- 网格参考线 -->
        <g stroke="rgba(125, 201, 255, 0.07)" stroke-width="1">
          <line x1="0" y1="140" x2="1000" y2="140" />
          <line x1="0" y1="281" x2="1000" y2="281" />
          <line x1="0" y1="422" x2="1000" y2="422" />
          <line x1="200" y1="0" x2="200" y2="563" />
          <line x1="400" y1="0" x2="400" y2="563" />
          <line x1="600" y1="0" x2="600" y2="563" />
          <line x1="800" y1="0" x2="800" y2="563" />
        </g>

        <!-- 甲板外轮廓 -->
        <rect
          x="28"
          y="28"
          width="944"
          height="507"
          rx="18"
          fill="rgba(20, 38, 68, 0.6)"
          stroke="rgba(125, 201, 255, 0.22)"
          stroke-width="2"
        />

        <!-- 斜角降落跑道 -->
        <polygon
          points="120,486 470,96 720,96 820,170 820,224 520,486"
          fill="url(#deck-runway)"
          opacity="0.85"
          stroke="rgba(154, 214, 255, 0.35)"
          stroke-width="2"
        />

        <!-- 跑道中线（虚线） -->
        <line
          x1="168"
          y1="446"
          x2="772"
          y2="160"
          stroke="#ffd166"
          stroke-width="3"
          stroke-dasharray="18 14"
          opacity="0.55"
        />

        <!-- 跑道入口标线 -->
        <g stroke="rgba(234, 243, 255, 0.6)" stroke-width="3">
          <line x1="130" y1="470" x2="158" y2="442" />
          <line x1="140" y1="480" x2="168" y2="452" />
          <line x1="150" y1="490" x2="178" y2="462" />
        </g>

        <!-- 弹射器 1 / 2 -->
        <g stroke="#9ad6ff" stroke-width="2" opacity="0.4">
          <line x1="70" y1="300" x2="300" y2="300" />
          <line x1="70" y1="330" x2="300" y2="330" />
        </g>

        <!-- 舰岛 -->
        <rect
          x="790"
          y="52"
          width="150"
          height="230"
          rx="8"
          fill="#1d3960"
          stroke="rgba(125, 201, 255, 0.3)"
          stroke-width="2"
        />
        <rect x="806" y="68" width="70" height="34" rx="4" fill="rgba(91, 166, 255, 0.18)" />
        <rect x="806" y="112" width="118" height="26" rx="4" fill="rgba(83, 229, 200, 0.1)" />
        <rect x="806" y="150" width="118" height="26" rx="4" fill="rgba(83, 229, 200, 0.1)" />
        <rect x="806" y="188" width="118" height="26" rx="4" fill="rgba(83, 229, 200, 0.1)" />

        <!-- 停机区标注 -->
        <g fill="rgba(154, 214, 255, 0.28)">
          <circle cx="420" cy="360" r="12" />
          <circle cx="470" cy="360" r="12" />
          <circle cx="520" cy="360" r="12" />
          <circle cx="420" cy="410" r="12" />
          <circle cx="470" cy="410" r="12" />
          <circle cx="520" cy="410" r="12" />
        </g>

        <!-- 舰艏方向 -->
        <path
          d="M 940 60 L 960 60 L 950 44 Z"
          fill="rgba(255, 209, 102, 0.7)"
        />
      </svg>
      <span class="deck-heatmap__label">占位甲板底图（美工替换）· 基准 1000×{{ baseHeight }}</span>
    </div>

    <!-- 红色故障点（需求 7.4.1：position absolute + 缩放换算） -->
    <button
      v-for="p in scaledPoints"
      :key="p.event.event_id"
      class="deck-heatmap__dot"
      :style="{ left: p.left, top: p.top }"
      @mouseenter="activePoint = p"
      @mouseleave="activePoint = null"
      @click="goEventDetail(p.event.event_id)"
      :title="`${p.event.event_id}（点击查看详情）`"
    ></button>

    <!-- 悬停 tooltip -->
    <div
      v-if="activePoint"
      class="deck-heatmap__tooltip"
      :style="{ left: `calc(${activePoint.left} + 16px)`, top: `calc(${activePoint.top} - 34px)` }"
    >
      <p>风险评分：{{ Math.round(activePoint.event.risk_score * 100) }}%</p>
      <p>碰撞概率：{{ Math.round(activePoint.event.risk_score * 100) }}%</p>
      <p>发生时间：{{ activePoint.event.occurred_at }}</p>
      <p class="deck-heatmap__tooltip-hint">点击查看事件详情</p>
    </div>

    <!-- 空态 -->
    <p v-if="!scaledPoints.length" class="deck-heatmap__empty">暂无热点数据</p>
  </div>
</template>

<style scoped>
.deck-heatmap {
  position: relative;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  border-radius: 12px;
  border: 1px solid rgba(125, 201, 255, 0.16);
  background: rgba(6, 15, 28, 0.7);
}

/* 占位底图：SVG 甲板示意（美工底图交付后仅替换 .deck-heatmap__svg 内容） */
.deck-heatmap__deck {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #0d1c33, #0a1628 60%, #0f2138);
}

.deck-heatmap__svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.deck-heatmap__label {
  position: absolute;
  top: 10px;
  left: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(5, 11, 22, 0.65);
  border: 1px solid rgba(125, 201, 255, 0.2);
  color: rgba(220, 234, 255, 0.55);
  font-size: 0.72rem;
  z-index: 3;
}

.deck-heatmap__dot {
  position: absolute;
  width: 10px;
  height: 10px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  border: none;
  background: radial-gradient(circle, #ff8a83, #ff4d4d);
  box-shadow: 0 0 10px rgba(255, 77, 77, 0.9), 0 0 4px rgba(255, 77, 77, 0.7);
  cursor: pointer;
  animation: deck-dot-pulse 1.8s ease-in-out infinite;
  z-index: 2;
}

@keyframes deck-dot-pulse {
  0%, 100% { box-shadow: 0 0 6px rgba(255, 77, 77, 0.7); }
  50% { box-shadow: 0 0 16px rgba(255, 77, 77, 1); }
}

.deck-heatmap__tooltip {
  position: absolute;
  z-index: 5;
  min-width: 170px;
  padding: 9px 12px;
  border-radius: 10px;
  background: rgba(10, 20, 38, 0.96);
  border: 1px solid rgba(125, 201, 255, 0.25);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  pointer-events: none;
}

.deck-heatmap__tooltip p {
  margin: 0;
  font-size: 0.78rem;
  color: #dbe9ff;
  line-height: 1.6;
}

.deck-heatmap__tooltip-hint {
  color: rgba(255, 209, 102, 0.8) !important;
}

.deck-heatmap__empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  margin: 0;
  color: rgba(220, 234, 255, 0.45);
  font-size: 0.88rem;
  z-index: 1;
}
</style>
