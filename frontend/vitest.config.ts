import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'node',
      include: ['src/**/*.spec.ts'],
      // Vue 组件测试经按需导入加载 Element Plus 的 CSS，由 Vite 处理该依赖。
      server: { deps: { inline: ['element-plus'] } },
    },
  }),
);
