import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';
import AutoImport from 'unplugin-auto-import/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Element Plus 按需引入，只打包用到的组件与样式。
    // ElMessage / ElMessageBox 需显式 import，样式在 main.ts 引入。
    AutoImport({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: false,
    }),
  ],
  resolve: {
    alias: {
      // 配置 @ 等价于 src 文件夹
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:12312',
        changeOrigin: true,
      },
    },
  },
  optimizeDeps: {
    // 固定预构建范围，避免开发中途重新预构建导致整页刷新。
    // element-plus 整体预构建；生产构建仍按需 tree-shake。
    include: [
      'vue',
      'vue-router',
      'pinia',
      'axios',
      'dompurify',
      'marked',
      'element-plus',
      'echarts/core',
      'echarts/charts',
      'echarts/components',
      'echarts/renderers',
    ],
  },
});
