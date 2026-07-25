# 网络安全态势感知贝叶斯AI研判平台

## 一、项目介绍
本项目为前后端分离架构的网络安全态势可视化与 AI 风险研判系统，前端基于Vue3 + TS + Vite + Element Plus + ECharts 开发，采用 History 干净路由模式，后端基于 Python FastAPI 搭建贝叶斯算法服务，实现攻击态势大屏可视化、告警全生命周期管理、朴素贝叶斯模型训练、单条告警流量自动风险推理完整业务闭环。

可完成多数据集模型训练、评估指标实时计算、历史实验可复现、告警自动 AI 研判等核心功能，适用于网络入侵行为检测与安全态势分析场景。

## 二、整体技术栈

### 2.1 前端技术栈
- 框架：Vue3 `<script setup>` 语法糖 + TypeScript 强类型约束
- 路由：Vue Router 4 HTML5 History 模式
- UI 组件：Element Plus
- 可视化图表：ECharts（攻击趋势饼图、折线图、境内外攻击地图）
- 网络请求：Axios 统一封装接口调用

### 2.2 后端技术栈
- 服务框架：FastAPI 高性能接口服务
- 核心算法：PMWNB矩阵加权贝叶斯（改进朴素贝叶斯）
- 数据集：网络攻击数据集、电力数据集、航母数据集（CSV 格式）
- 数据处理：特征等宽 / 等频离散化、0~1 区间归一化
- 部署支持：虚拟环境隔离、Docker 打包、Windows/Linux一键启动脚本

## 三、项目目录结构

### 3.1 前端 Vue 项目目录
```plaintext
ai-security-visualization-demo-codex-map-and-layout-fixes/
├── public/
│   ├── maps/
│   │   ├── china.svg
│   │   └── world.svg
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── api/
│   │   └── modelApi.js
│   ├── assets/
│   ├── components/
│   │   ├── AlertDetailView.vue
│   │   ├── AlertsView.vue
│   │   ├── DashboardView.vue
│   │   └── 各类图表、弹窗子组件
│   ├── router/
│   │   └── index.ts
│   ├── services/
│   │   └── mockApi.ts
│   ├── types/
│   │   └── security.ts
│   ├── utils/
│   │   └── request.js
│   ├── views/
│   │   └── RiskAnalysis.vue
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
├── tsconfig.json
└── .prettierrc
```

### 3.2 后端 Python 算法项目目录
```plaintext
task2_algo-climber-backend/
├── data/
├── docs/
├── input/
├── models/
├── output/
├── services/
├── test/
├── trained_models/
├── config.py
├── server.py
├── requirements.txt
├── process_kdd_arff.py
├── start.sh
└── README.md
```

### 3.3 项目整体架构
```plaintext
AI安全态势感知贝叶斯研判平台
├── ai-security-visualization-demo-codex-map-and-layout-fixes
└── task2_algo-climber-backend
```

## 四、核心功能模块介绍

### 4.1 首页安全态势大屏 Dashboard
1. 全局威胁指标卡片：威胁总数、高危事件数量、AI 研判准确率、平均处置响应时间；
2. 24 小时攻击趋势折线图、攻击类型占比环形饼图、TOP 攻击源 IP / 目标主机排行榜；
3. 国内 / 全球攻击来源地理热力流向地图，直观展示攻击溯源；
4. 实时滚动告警列表，点击"AI 风险研判"按钮通过路由 Query 携带流量特征，跳转 AI 页面自动回填推理；
5. 后端接口异常自动降级 Mock 模拟数据兜底，页面不白屏崩溃。

### 4.2 告警列表页面 AlertsView
1. 全量模拟告警表格展示，包含攻击标题、类型、源 IP、目标主机、风险等级、发生时间；
2. 每行独立 AI 研判按钮，通过`@click.stop`阻止行点击打开详情，携带本条告警三个流量特征跳转预测页面；
3. 统一采用 Vue Router 标准编程式导航，彻底修复原生 hash 跳转无法传参 Bug。

### 4.3 告警详情弹窗 AlertDetailView
1. 展示告警完整信息：原始攻击日志、攻击时间线、AI 初步分析结论、多条处置建议；
2. 内置跳转 AI 研判按钮，自动传递本条告警归一化流量特征，实现一键闭环研判。

### 4.4 AI 贝叶斯模型训练与风险研判页面 RiskAnalysis
1. 风险阈值配置：自定义高 / 中 / 低三级风险判定阈值，前端合法性校验（高 > 中 > 低）后保存至后端；
2. 模型训练模块
   - 下拉选择数据集、选择算法（PMWNB矩阵加权贝叶斯）、离散化方式（等宽 / 等频）；
   - 点击一键训练，后端加载 CSV 数据集完成算法训练，实时计算返回准确率、F1 分数、召回率、训练耗时并前端展示；
3. 风险预测模块
   - 两种数据输入方式：
     ①人工手动填写 0~1 浮点数测试；
     ②告警页面跳转路由自动回填流量长度、连接时长、访问频次；
   - 强前置校验：未完成模型训练禁止执行预测，拦截无效请求；
   - 调用后端推理接口，返回风险等级、风险概率、攻击类型；
4. 历史实验记录管理：自动保存每一次训练参数与指标，支持复现历史实验、删除记录，用于论文多组实验对比。

## 五、数据流完整业务链路
1. 前端三处告警入口（首页滚动告警、列表页表格、详情弹窗）点击 AI 按钮，通过`router.push`携带fl/du/af三个流量特征作为路由 Query 参数；
2. RiskAnalysis 页面路由监听自动解析参数，填充至三个输入框；
3. 若已完成模型训练，自动调用后端`riskInfer`推理接口；
4. 后端调用已训练贝叶斯模型计算风险结果，回传给前端展示研判结论；
5. 模型训练时前端仅传递配置参数，所有训练过程、评估指标由后端算法实时计算。

## 六、Mock 模拟数据说明（services/mockApi.ts）
1. 数据生成规则：`createAlert`函数循环生成 12 条模拟告警，每条告警强制附带 flowLength、duration、accessFreq 三个 0~1 随机两位小数，保证跳转传参不会字段缺失；
2. 数据性质：三组流量特征为前端开发阶段纯模拟随机值，仅用于调试跳转自动回填交互逻辑；正式对接后端后，替换为后端采集真实流量、归一化处理后的真实特征数据；
3. 刷新能力：提供`refreshMockData()`方法，首页右上角刷新按钮可一键重置全部模拟告警与随机特征值。

## 七、本地开发环境配置手册

### 7.1 环境版本硬性要求
| 软件 | 推荐稳定版本 | 用途 |
| ---- | ------------ | ---- |
| Node.js | v16 ~ v18 | 前端项目依赖运行 |
| Python | 3.9 ~ 3.10 | 后端算法与 FastAPI 服务 |

### 7.2 前端启动命令
```bash
npm install
npm run dev
```
访问地址：http://localhost:5173

### 7.3 后端启动命令
#### 方式1：直接安装依赖运行
```bash
pip install -r requirements.txt
pip install scikit-learn joblib
```

#### 方式2：虚拟环境运行
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install scikit-learn joblib
```

Windows CMD 解决中文乱码：
```cmd
set PYTHONUTF8=1
```

启动服务：
```bash
python server.py
```
接口文档地址：http://127.0.0.1:12312/docs

## 八、开发与Git版本管理规范
### 8.1 代码编写规范
1. 全局禁止原生`location.hash`哈希跳转，统一使用 Vue Router `router.push` 编程式导航；
2. 路由跳转分为两类：
   - 无参跳转：顶部导航切换页面、数据集选择、模型训练；
   - 带参Query跳转：告警条目携带流量特征进入AI研判页面；
3. 全部Vue组件使用TypeScript `defineProps/defineEmits` 强类型约束，不使用隐式any；
4. 模拟告警数据统一放在`services/mockApi.ts`，不在组件内硬编码数组。
