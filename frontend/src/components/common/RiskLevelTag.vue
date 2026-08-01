<script setup lang="ts">
/**
 * RiskLevelTag - 统一风险等级标签组件
 *
 * 根据 risk_level 显示不同颜色和文本的标签
 * 适配网络安全/电力系统/航母甲板三大场景
 */

defineProps<{
  /** 风险等级：critical / high / medium / low */
  level: 'critical' | 'high' | 'medium' | 'low';
  /** 标签尺寸 */
  size?: 'small' | 'default' | 'large';
}>();

const levelLabel: Record<string, string> = {
  critical: '严重',
  high: '高危',
  medium: '中危',
  low: '低危',
};
</script>

<template>
  <span
    class="risk-level-tag"
    :class="[`risk-level-${level}`, size ? `risk-level-${size}` : '']"
  >
    {{ levelLabel[level] ?? level }}
  </span>
</template>

<style scoped>
.risk-level-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  padding: 4px 10px;
  border-radius: 999px;
  font-style: normal;
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

/* 尺寸变体 */
.risk-level-small {
  min-width: 44px;
  padding: 2px 8px;
  font-size: 0.7rem;
}

.risk-level-large {
  min-width: 80px;
  padding: 8px 16px;
  font-size: 0.9rem;
}

/* 风险等级颜色（与全局 style.css 中的 .risk-badge 保持一致） */
.risk-level-critical {
  background: rgba(255, 123, 114, 0.18);
  color: #ff8c84;
  border: 1px solid rgba(255, 123, 114, 0.25);
}

.risk-level-high {
  background: rgba(255, 177, 107, 0.18);
  color: #ffc37d;
  border: 1px solid rgba(255, 177, 107, 0.25);
}

.risk-level-medium {
  background: rgba(91, 166, 255, 0.18);
  color: #9ad6ff;
  border: 1px solid rgba(91, 166, 255, 0.25);
}

.risk-level-low {
  background: rgba(83, 229, 200, 0.18);
  color: #53e5c8;
  border: 1px solid rgba(83, 229, 200, 0.25);
}
</style>
