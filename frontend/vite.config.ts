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
    // Element Plus 按需引入：只打包实际用到的组件与其样式，
    // 替代原先 main.ts 里的全量 `app.use(ElementPlus)` + `element-plus/dist/index.css`
    // （全量引入时入口 JS 968KB、入口 CSS 381KB，dev 预构建的 element-plus 达 1.9MB）。
    //
    // ElMessage / ElMessageBox 在 11 个文件里是显式 import，不会被 AutoImport 接管，
    // 其样式由 main.ts 显式引入（见 main.ts 注释）。
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
    // 固定预构建范围：避免开发过程中 Vite 中途发现新依赖触发重新预构建
    // 并整页 reload（体感上就是「突然卡住然后白一下」）。
    //
    // 这里仍把 element-plus 整体预构建：按需引入后每个组件样式都是独立子路径，
    // 若交给 Vite 边跑边发现，开发中会触发一次重新预构建 + 整页 reload。
    // 预构建只影响 dev 体验，生产构建依然按需 tree-shake。
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
