<template>
  <section class="not-found">
    <p class="not-found__code">404</p>
    <p class="not-found__title">页面不存在</p>
    <button class="ghost-button" @click="router.replace('/')">返回首页</button>
  </section>
</template>
<script setup lang="ts">
import { useRouter } from 'vue-router';

// 回 '/' 由路由的 redirect 和守卫决定落到哪个角色首页，这里不做判断。
const router = useRouter();
</script>
<style scoped>
.not-found {
  max-width: 380px;
  margin: 64px auto 0;
  padding: 32px 28px;
  text-align: center;
  border-radius: 20px;
  border: 1px solid rgba(125, 201, 255, 0.18);
  background: rgba(8, 17, 31, 0.72);
  backdrop-filter: blur(18px);
}

.not-found__code {
  margin: 0;
  font-size: 2.4rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: rgba(125, 201, 255, 0.5);
}

.not-found__title {
  margin: 6px 0 22px;
  font-size: 1.05rem;
  color: #eaf3ff;
}
</style>
