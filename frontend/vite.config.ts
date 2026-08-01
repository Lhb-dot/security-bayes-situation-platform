import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      // 配置 @ 等价于 src 文件夹
      '@': resolve(__dirname, 'src'),
    },
  },
});
