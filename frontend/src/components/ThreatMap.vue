<script setup lang="ts">
import { computed, ref } from 'vue';
import type { AttackFlow, ThreatMapData } from '../types/security';

const props = defineProps<{
  maps: {
    china: ThreatMapData;
    world: ThreatMapData;
  };
  large?: boolean;
}>();

const activeScope = ref<'china' | 'world'>('world');
const hoveredFlowId = ref('');

const activeMap = computed(() => props.maps[activeScope.value]);
const activeFlow = computed<AttackFlow | null>(
  () => activeMap.value.flows.find((item) => item.id === hoveredFlowId.value) ?? activeMap.value.flows[0] ?? null
);

const pathForFlow = (flow: AttackFlow) => {
  const cx = (flow.x1 + flow.x2) / 2;
  const cy = Math.min(flow.y1, flow.y2) - (Math.abs(flow.x2 - flow.x1) > 20 ? 18 : 12);
  return `M ${flow.x1} ${flow.y1} Q ${cx} ${cy} ${flow.x2} ${flow.y2}`;
};

const width = 100;
const height = 100;
</script>

<template>
  <div class="threat-map" :class="{ 'threat-map--large': large }">
    <div class="threat-map__toolbar">
      <div>
        <strong>{{ activeMap.title }}</strong>
        <p>{{ activeMap.subtitle }}</p>
      </div>
      <div class="scope-switch">
        <button
          class="scope-switch__item"
          :class="{ 'is-active': activeScope === 'world' }"
          @click="activeScope = 'world'"
        >
          世界地图
        </button>
        <button
          class="scope-switch__item"
          :class="{ 'is-active': activeScope === 'china' }"
          @click="activeScope = 'china'"
        >
          中国地图
        </button>
      </div>
    </div>

    <div class="threat-map__board">
      <div class="threat-map__canvas">
        <img
          class="threat-map__background"
          :src="activeScope === 'world' ? '/maps/world.svg' : '/maps/china.svg'"
          :alt="activeScope === 'world' ? '世界地图' : '中国地图'"
        />
        <svg class="threat-map__svg" :viewBox="`0 0 ${width} ${height}`" preserveAspectRatio="none">
          <defs>
            <linearGradient id="flow-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stop-color="#ff836b" />
              <stop offset="100%" stop-color="#5ba6ff" />
            </linearGradient>
          </defs>

          <g class="threat-map__flows" @mouseleave="hoveredFlowId = ''">
            <path
              v-for="flow in activeMap.flows"
              :key="flow.id"
              :d="pathForFlow(flow)"
              class="threat-map__arc"
              :class="[`is-${flow.severity.toLowerCase()}`, { 'is-active': activeFlow?.id === flow.id }]"
              @mouseenter="hoveredFlowId = flow.id"
            />
            <circle
              v-for="flow in activeMap.flows"
              :key="`${flow.id}-missile`"
              r="1.1"
              class="threat-map__missile"
              :class="`is-${flow.severity.toLowerCase()}`"
            >
              <animateMotion :dur="`${3.2 + flow.count / 100}s`" repeatCount="indefinite" :path="pathForFlow(flow)" />
            </circle>
          </g>

          <g class="threat-map__points">
            <g v-for="point in activeMap.points" :key="point.id" :transform="`translate(${point.x}, ${point.y})`">
              <circle class="threat-map__point-core" r="0.95" />
              <circle class="threat-map__point-wave" r="1.3">
                <animate attributeName="r" values="1.3;3.2" dur="2.8s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.7;0" dur="2.8s" repeatCount="indefinite" />
              </circle>
            </g>

            <g :transform="`translate(${activeMap.focusX}, ${activeMap.focusY})`" class="threat-map__focus">
              <circle r="1.5" />
              <circle class="threat-map__focus-ring" r="3.5" />
            </g>
          </g>
        </svg>

        <div class="threat-map__labels">
          <div
            v-for="point in activeMap.points"
            :key="`${point.id}-label`"
            class="threat-map__label"
            :style="{
              left: `${point.x}%`,
              top: `${point.y}%`,
              transform: `translate(${point.dx ?? 14}px, ${point.dy ?? -8}px)`,
            }"
          >
            <strong>{{ point.label }}</strong>
            <small>{{ point.value }}</small>
          </div>
          <div class="threat-map__focus-label" :style="{ left: `${activeMap.focusX}%`, top: `${activeMap.focusY}%` }">
            <strong>{{ activeMap.focusLabel }}</strong>
            <small>核心防护节点</small>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeFlow" class="threat-map__detail">
      <div>
        <p class="eyebrow">Attack Vector</p>
        <strong>{{ activeFlow.source }} -> {{ activeFlow.target }}</strong>
      </div>
      <div class="threat-map__detail-meta">
        <span :class="['risk-badge', `risk-${activeFlow.severity.toLowerCase()}`]">{{ activeFlow.severity }}</span>
        <span>{{ activeFlow.attackType }}</span>
        <span>{{ activeFlow.sourceIp }}</span>
        <span>{{ activeFlow.count }} 次</span>
      </div>
    </div>
  </div>
</template>
