<script setup lang="ts">
/**
 * EventTimeline.vue — 风险事件时间线（需求 7.2/7.3：时间轴 + 事件卡片，标注关键特征）
 *
 * 纯展示组件：左侧时间轴 + 右侧事件卡片；点击卡片跳风险事件详情。
 */
import { useRouter } from 'vue-router';
import type { RiskEvent } from '@/types/security';

const props = defineProps<{
  events: RiskEvent[];
  /** 从 raw_features 提取展示的字段键（如 IssueType/Component/landslide_trigger） */
  metaKeys?: string[];
}>();

const router = useRouter();

const riskLabel = (level: RiskEvent['risk_level']): string => {
  if (level === 'HIGH') return '高危';
  if (level === 'MEDIUM') return '中危';
  return '低危';
};

const featureValue = (ev: RiskEvent, key: string): string => {
  const v = ev.raw_features[key];
  if (v === undefined || v === null || v === '') return '—';
  return String(v);
};

const goEventDetail = (eventId: string) => {
  router.push({ path: `/events/${eventId}` });
};
</script>

<template>
  <div class="scenario-timeline">
    <div
      v-for="ev in props.events"
      :key="ev.event_id"
      class="scenario-timeline__item"
      @click="goEventDetail(ev.event_id)"
    >
      <div class="scenario-timeline__axis">
        <span class="scenario-timeline__dot" :class="`scenario-timeline__dot--${ev.risk_level.toLowerCase()}`"></span>
      </div>
      <div class="scenario-timeline__card">
        <div class="scenario-timeline__head">
          <span class="scenario-event__badge" :class="`scenario-event__badge--${ev.risk_level.toLowerCase()}`">
            {{ riskLabel(ev.risk_level) }}
          </span>
          <span class="scenario-timeline__time">{{ ev.occurred_at }}</span>
        </div>
        <p class="scenario-timeline__desc">{{ ev.description }}</p>
        <div v-if="props.metaKeys?.length" class="scenario-timeline__meta">
          <span v-for="k in props.metaKeys" :key="k" class="scenario-timeline__meta-item">
            {{ k }}：{{ featureValue(ev, k) }}
          </span>
        </div>
        <span class="scenario-timeline__id">{{ ev.event_id }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scenario-timeline {
  display: grid;
  gap: 12px;
}

.scenario-timeline__item {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 12px;
  cursor: pointer;
}

.scenario-timeline__axis {
  position: relative;
  display: flex;
  justify-content: center;
}

.scenario-timeline__axis::before {
  content: '';
  position: absolute;
  top: 16px;
  bottom: -12px;
  width: 2px;
  background: rgba(125, 201, 255, 0.12);
}

.scenario-timeline__item:last-child .scenario-timeline__axis::before {
  display: none;
}

.scenario-timeline__dot {
  position: relative;
  z-index: 1;
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 50%;
  border: 2px solid rgba(5, 11, 22, 0.9);
}

.scenario-timeline__dot--high { background: #ff7b72; box-shadow: 0 0 8px rgba(255, 123, 114, 0.7); }
.scenario-timeline__dot--medium { background: #ffd166; box-shadow: 0 0 8px rgba(255, 209, 102, 0.6); }
.scenario-timeline__dot--low { background: #53e5c8; box-shadow: 0 0 8px rgba(83, 229, 200, 0.6); }

.scenario-timeline__card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(125, 201, 255, 0.1);
  transition: background 0.2s ease, border-color 0.2s ease;
}

.scenario-timeline__card:hover {
  background: rgba(91, 166, 255, 0.06);
  border-color: rgba(125, 201, 255, 0.22);
}

.scenario-timeline__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.scenario-timeline__time {
  font-size: 0.76rem;
  color: rgba(220, 234, 255, 0.5);
}

.scenario-timeline__desc {
  margin: 0;
  font-size: 0.86rem;
  color: #dbe9ff;
  line-height: 1.5;
}

.scenario-timeline__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.scenario-timeline__meta-item {
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(91, 166, 255, 0.1);
  color: #9ad6ff;
  font-size: 0.76rem;
}

.scenario-timeline__id {
  font-size: 0.72rem;
  color: rgba(220, 234, 255, 0.4);
}
</style>
