<script setup lang="ts">
/**
 * DashGauge —— 刻度条（低/正常/高三段 + 均值游标），对应 demo 的 .gaugebar。
 * 用于电力工作台的「告警样本电参量均值」。
 */
import { computed } from 'vue';
import { fmtNum } from './dashFormat';

const props = withDefaults(
  defineProps<{
    name: string;
    unit?: string;
    mean: number | null;
    min: number | null;
    max: number | null;
    /** 正常区间（用于把轨道切成低/正常/高三段） */
    low?: number | null;
    high?: number | null;
  }>(),
  { unit: '', low: null, high: null },
);

const scale = computed(() => (Number(props.min) || 0) === (Number(props.max) || 0) ? 1 : Number(props.max) - Number(props.min));

const ratio = (value: number | null | undefined): number => {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 0;
  return Math.min(100, Math.max(0, ((Number(value) - Number(props.min || 0)) / scale.value) * 100));
};

/** 三段：低（绿）/ 正常（蓝）/ 高（红）；无数据时不显示分色，仅保留灰底轨道 */
const segments = computed(() => {
  if (props.mean === null || props.mean === undefined) {
    return [{ width: 100, color: 'rgba(255,255,255,.06)' }];
  }
  const lowEnd = props.low === null || props.low === undefined ? 25 : ratio(props.low);
  const highStart = props.high === null || props.high === undefined ? 75 : ratio(props.high);
  const start = Math.min(lowEnd, highStart);
  const end = Math.max(lowEnd, highStart);
  return [
    { width: start, color: 'rgba(83,229,200,.55)' },
    { width: Math.max(end - start, 0), color: 'rgba(91,166,255,.55)' },
    { width: Math.max(100 - end, 0), color: 'rgba(255,123,114,.55)' },
  ];
});

const hasData = computed(() => props.mean !== null && props.mean !== undefined);
</script>

<template>
  <div class="d-gauge">
    <div class="d-gauge-top">
      <span>{{ name }}</span>
      <b>{{ mean === null || mean === undefined ? '—' : fmtNum(mean) }}<em v-if="unit">{{ unit }}</em></b>
    </div>
    <div class="d-gauge-track">
      <span v-for="(segment, index) in segments" :key="index" :style="{ width: segment.width + '%', background: segment.color }"></span>
      <span class="d-gauge-pin" v-if="hasData" :style="{ left: ratio(mean) + '%' }"></span>
    </div>
    <div class="d-gauge-scale">
      <span>{{ min === null || min === undefined ? '—' : fmtNum(min) }}</span>
      <span>{{ max === null || max === undefined ? '—' : fmtNum(max) }}</span>
    </div>
  </div>
</template>
