<script setup lang="ts">
/**
 * DashScatter —— 二维散点图（对应 demo 的「双机航向映射散点图」）。
 * 坐标来源为 risk_event.fault_position_x/y（后端用航向角映射的占位坐标，非真实甲板位置）。
 * 颜色按风险分：≥0.9 红 / ≥0.7 黄 / 其余 绿。
 */
import { computed } from 'vue';
import { fmtInt, fmtNum } from './dashFormat';
import { SHOW_DASH_HINTS } from './dashHints';

const props = withDefaults(
  defineProps<{
    points: Array<{ event_id: number; x: number | null; y: number | null; risk_score: number | null; status: string }>;
    /** 坐标基准上限（后端 0-1000 底图） */
    domain?: number;
    height?: number;
  }>(),
  { domain: 1000, height: 240 },
);

const VIEW_W = 320;
const PLOT_X = 48;
const PLOT_Y = 18;
const PLOT_W = 256;
const PLOT_H = 174;

const color = (score: number | null): string => {
  const value = Number(score ?? 0);
  if (value >= 0.9) return '#ff7b72';
  if (value >= 0.7) return '#ffd166';
  return '#53e5c8';
};

const dots = computed(() =>
  props.points
    .filter((point) => point.x !== null && point.y !== null)
    .map((point) => ({
      ...point,
      cx: Math.round((PLOT_X + (Number(point.x) / props.domain) * PLOT_W) * 10) / 10,
      cy: Math.round((PLOT_Y + (Number(point.y) / props.domain) * PLOT_H) * 10) / 10,
      fill: color(point.risk_score),
    })),
);
</script>

<template>
  <div>
    <svg :viewBox="`0 0 ${VIEW_W} 224`" width="100%" :height="height" role="img">
      <rect :x="PLOT_X" :y="PLOT_Y" :width="PLOT_W" :height="PLOT_H" fill="rgba(91,166,255,.04)" stroke="rgba(125,201,255,.2)" />
      <g stroke="rgba(125,201,255,.10)">
        <line v-for="index in 5" :key="'vx' + index"
              :x1="PLOT_X + (PLOT_W / 5) * index" :y1="PLOT_Y"
              :x2="PLOT_X + (PLOT_W / 5) * index" :y2="PLOT_Y + PLOT_H" />
        <line v-for="index in 4" :key="'hy' + index"
              :x1="PLOT_X" :y1="PLOT_Y + (PLOT_H / 4) * index"
              :x2="PLOT_X + PLOT_W" :y2="PLOT_Y + (PLOT_H / 4) * index" />
      </g>
      <circle v-for="dot in dots" :key="dot.event_id" :cx="dot.cx" :cy="dot.cy" r="5" :fill="dot.fill" opacity=".82">
        <title>事件 #{{ dot.event_id }} · 风险分 {{ fmtNum(dot.risk_score, 2) }}</title>
      </circle>
      <text :x="PLOT_X" :y="PLOT_Y + PLOT_H + 20" fill="rgba(220,234,255,.5)" font-size="9">坐标基准 0-{{ domain }}</text>
    </svg>
    <p v-if="SHOW_DASH_HINTS" class="d-src">
      共 {{ fmtInt(dots.length) }} 个告警点。
    </p>
  </div>
</template>
