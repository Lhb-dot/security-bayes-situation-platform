# 多场景态势感知与贝叶斯风险分析平台

基于 **Vue 3 + TypeScript + Vite + Element Plus** 构建的前端可视化平台，面向网络安全、电力系统、航母甲板保障作业等多场景的态势感知与贝叶斯风险分析场景。

> 当前版本以**前端展示和交互完整性**为主，数据通过本地 Mock 接口驱动，后端接口已预留接口层，便于后续替换为真实后端。

---

## 功能总览

### 核心业务闭环

```
场景选择 → 数据集查看（字段预览 + 字段角色）
    → 模型训练（PMWNB/贝叶斯算法，输出 Accuracy/Recall/F1/G-mean）
    → 风险推理（动态字段输入，基于所选数据集字段）
    → 风险事件统一展示（12 字段 RiskEvent 结构）
```

### 页面清单

| 路由 | 页面 | 说明 | 优先级 |
|:-----|:-----|:-----|:------:|
| `/overview` | 全局总览 | 跨场景风险指标聚合、趋势图、分布统计、高风险事件列表 | P0 |
| `/dashboard` | 首页大屏 | 态势感知大屏，含攻击趋势、攻击类型分布、Top 攻击源、攻击轨迹动画 | P0 |
| `/scenarios` | 场景中心 | 场景列表卡片，含接入状态标识（已接入/暂未接入）| P0 |
| `/scenarios/:id/dashboard` | 场景大屏 | 单场景专属看板：风险指标、趋势图、分布图、事件排行 | P0 |
| `/datasets` | 数据集中心 | 按场景筛选数据集、字段预览（含字段角色：输入特征/分类标签）| P0 |
| `/inference` | 风险研判 | 选择场景 → 选择数据集 → 动态生成输入字段 → 执行风险推理 | P0 |
| `/alerts` | 风险事件 | 统一 RiskEvent 列表，三级筛选（场景/等级/状态）| P0 |
| `/risk` | 模型训练 | 场景绑定 → 数据集选择 → 贝叶斯模型训练（含 G-mean）+ 风险预测 | P0 |
| `/models` | 模型中心 | 模型版本管理，五维指标展示（Accuracy/Precision/Recall/F1/G-mean）| P1 |
| `/situation` | 态势分析 | 多维度风险趋势分析，跨场景数据聚合 | P1 |
| `/reports` | 报告中心 | 态势报告列表，查看/下载/重新生成 | P1 |
| `/settings` | 系统设置 | 全局阈值配置、场景启停、自动刷新、主题切换 | P2 |

### 场景支持

| 场景 | ID | 接入状态 | 数据集 | 说明 |
|:-----|:---|:---------|:-------|:-----|
| 网络安全态势感知 | `network_security` | ✅ 已接入 | KDDTrain+ 20 Percent（41 字段）、NF-UNSW-NB15-v2（41 字段）| 完整功能支持 |
| 电力系统风险态势感知 | `power_system` | ✅ 已接入 | PowerGrid Knowledgebase（9 字段） | 完整功能支持 |
| 航母甲板保障作业态势感知 | `flightdeck_operation` | ⏸️ 暂未接入 | 无数据集 | 预留场景，仅展示占位提示 |

---

## 技术栈

| 技术 | 用途 |
|:-----|:------|
| **Vue 3** (Composition API + `<script setup>`) | 前端框架 |
| **TypeScript** | 类型安全 |
| **Vite 8.x** | 构建工具 |
| **vue-tsc** | TypeScript 类型检查 |
| **vue-router** (hash 模式) | 路由管理 |
| **Element Plus** | UI 组件库（表格、弹窗、标签、按钮、消息提示） |
| **CSS 自定义** | 暗色科幻主题（渐变背景、毛玻璃效果、科幻色板） |

### 主题色板

| 色值 | 用途 |
|:-----|:------|
| `#5ba6ff` | 主色（按钮、激活态） |
| `#9ad6ff` | 辅助色（标题、强调文字） |
| `#e8f1ff` | 主文字色 |
| `rgba(220, 234, 255, 0.7)` | 次要文字 |
| `rgba(125, 201, 255, 0.16)` | 边框色 |
| `rgba(11, 22, 40, 0.6)` | 卡片/表格底色 |

---

## 数据架构

### 核心类型定义（`src/types/security.ts`）

#### `RiskEvent` — 风险事件（需求 5.2 节 12 字段）

```typescript
interface RiskEvent {
  event_id: string;
  scenario_id: ScenarioId;
  dataset_id: string;
  model_version_id: string;
  original_label: string;
  risk_type: string;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  occurred_at: string;
  status: '待处置' | '处理中' | '已处置';
  raw_features: Record<string, unknown>;
  description: string;
}
```

#### `DatasetField` — 数据集字段

```typescript
interface DatasetField {
  field_name: string;
  field_type: string;
  field_role: '输入特征' | '分类标签';  // 标记字段角色
  nullable: boolean;
  description: string;
  sample_value: string;
}
```

### Mock 数据层（`src/services/mockApi.ts`）

所有接口通过 `simulateLatency`（~180ms）模拟异步延迟，函数签名与真实接口一致，后续替换后端时**页面层无需修改**。

| 函数 | 返回 | 说明 |
|:-----|:-----|:------|
| `getScenarioList()` | `ScenarioCard[]` | 场景卡片列表 |
| `getScenarioDetail(id)` | `ScenarioDetail` | 场景详情（指标/趋势/分布/事件）|
| `getDatasetList(scenario?)` | `Dataset[]` | 数据集列表，可筛选场景 |
| `getDatasetFields(datasetId)` | `DatasetField[]` | 数据集的字段定义 |
| `trainModel(params)` | `TrainResult` | 模型训练结果（含 G-mean）|
| `getInferenceResult(input)` | `InferenceResult` | 单条风险推理 |
| `getRiskEvents()` | `RiskEvent[]` | 聚合全平台风险事件 |
| `getGlobalOverview()` | `GlobalOverview` | 全局总览指标 |
| `getSituationData()` | `SituationData` | 态势分析数据 |
| `getModelVersions()` | `ModelVersionRecord[]` | 模型版本列表 |
| `getReportList()` | `Report[]` | 报告列表 |

### 数据集 ARFF 字段精确匹配

严格遵循 `requirements-analysis.md` 第 3 节定义：

| 数据集 | 字段数 | 输入特征 | 标签字段 | 依据 |
|:-------|:------:|:--------:|:--------:|:-----|
| KDDTrain+ 20 Percent | 41 | 40 | `class`（二分类） | 需求表 3.1 |
| NF-UNSW-NB15-v2 | 41 | 40 | `Label`（二分类） | 需求表 3.2 |
| PowerGrid Knowledgebase | 9 | 8 | `Target_Event`（二分类） | 需求表 3.3/3.4 |

---

## 项目结构

```
ai-security-visualization-demo-codex-map-and-layout-fixes/
├── src/
│   ├── api/                      # 真实后端 API 调用（readl modelApi）
│   ├── components/
│   │   ├── common/                # 通用组件
│   │   │   ├── RiskLevelTag.vue   # 风险等级标签
│   │   │   └── ScenarioSelector.vue  # 场景选择器
│   │   ├── DonutChart.vue         # 环形图
│   │   ├── LineTrendChart.vue     # 折线趋势图
│   │   └── RankingList.vue        # 排行列表
│   ├── router/
│   │   └── index.ts               # 路由配置（hash 模式，12 条路由）
│   ├── services/
│   │   ├── mockApi.ts             # Mock 数据层（~761 行，含完整数据集定义）
│   │   └── modelApi.js            # 后端模型 API 封装
│   ├── types/
│   │   └── security.ts            # 核心类型定义
│   ├── views/
│   │   ├── AlertsView.vue         # 风险事件列表
│   │   ├── DatasetCenter.vue      # 数据集中心
│   │   ├── ModelCenter.vue        # 模型中心
│   │   ├── OverviewView.vue       # 全局总览
│   │   ├── ReportCenter.vue       # 报告中心
│   │   ├── RiskAnalysis.vue       # 模型训练与预测
│   │   ├── RiskInference.vue      # 风险研判
│   │   ├── ScenarioCard.vue       # 场景卡片
│   │   ├── ScenarioDashboard.vue  # 场景大屏
│   │   ├── Settings.vue           # 系统设置
│   │   └── SituationAnalysis.vue  # 态势分析
│   ├── App.vue                    # 应用入口（导航栏 + 路由视图）
│   ├── main.ts                    # 挂载入口
│   └── style.css                  # 全局样式
└── public/
    └── maps/                      # SVG 地图底图
```

---

## 项目启动

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发环境

```bash
npm run dev
```

### 3. 构建生产版本

```bash
npm run build
```

### 4. 类型检查（单独运行）

```bash
npm run type-check
```

---

## 如何接入后端

### 替换策略

当前 Mock 数据层位于 `src/services/mockApi.ts`，函数签名与真实接口一致。后续替换只需：

1. **创建新的 API 服务文件**（如 `src/services/realApi.ts`），使用 axios/fetch 调用真实后端
2. **保持函数签名不变**（输入参数、返回类型、异步 Promise 接口）
3. **在页面中替换 import 路径**（`mockApi` → `realApi`）

**页面层无需任何修改。**

### 示例

```typescript
// 当前（Mock）
import { getRiskEvents } from '@/services/mockApi';
const events = await getRiskEvents();

// 替换后（真实后端）
import { getRiskEvents } from '@/services/realApi';
const events = await getRiskEvents();
```

---

## 设计风格说明

### 暗色科幻主题

- **背景**：深色渐变 (`#050c16` → `#0b1628`) + 动态网格/粒子 canvas 背景
- **卡片**：玻璃拟态（`rgba` 半透明背景 + 发光边框）
- **梯度**：贯穿全站的 `#5ba6ff` → `#9ad6ff` 蓝色渐变
- **动画**：加载微动效、悬停高亮、平滑过渡、加载骨架

### Element Plus 组件覆盖

全站的 Element Plus 组件（el-table、el-dialog、el-tag、el-button）均通过全局 `<style>` 覆盖为暗色主题，保持视觉一致性。覆盖包括：
- 表格：透明背景、自定义表头、斑马纹、悬停高亮
- 弹窗：渐变背景、圆角、暗色关闭按钮
- 标签/按钮：透明背景 + 主题色

---

## 构建验证

```bash
$ npm run build
# ✓ built in 2.10s
# ✓ 0 TypeScript errors
```

当前版本通过 `vue-tsc -b && vite build` 全量类型检查 + 构建，**零类型错误**。

---

## 继续扩展方向

- [ ] 接入真实后端 API（Spring Boot / FastAPI）
- [ ] 接入真实数据库（MySQL / PostgreSQL / InfluxDB）
- [ ] 用户认证与权限控制（登录页 + JWT）
- [ ] 实时数据推送（WebSocket / SSE）
- [ ] 资产拓扑图与攻击路径回放
- [ ] 自定义可视化大屏布局（拖拽组件）
- [ ] 多语言支持（i18n）
- [ ] 航母甲板场景数据集接入
- [ ] 模型在线部署与实时推理管线
- [ ] AI 研判可解释性展示（SHAP / LIME）

---

## 许可

本项目为课程项目，仅供学习和演示用途。
