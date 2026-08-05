# 多场景贝叶斯分类态势感知系统 — 前端

基于 **Vue 3 + TypeScript + Vite + Element Plus** 构建的多场景贝叶斯分类态势感知平台前端，面向**网络安全、电力系统、航母甲板保障作业**三个业务场景，严格对齐需求文档《用户分级v2.md》（v2.0）的 P0/P1 功能。

> 当前版本数据由本地 Mock 层驱动（`src/services/mockApi.ts`），函数签名与真实后端接口一致，后续替换为真实后端时页面层无需修改。用户登录、角色鉴权、数据范围隔离等 P0 逻辑均已在 Mock 层完整模拟。

---

## 一、功能总览

### P0 业务闭环

系统按需求 6.3 实现「管理员训练闭环」与「普通用户使用闭环」两条验收基线：

```
┌─ 管理员闭环 ─────────────────────────────────────────────┐
│  登录 → 管理普通用户 → 选择场景 → 上传/选择数据集版本     │
│  → 选择已注册算法 → 配置公开训练参数 → 启动训练           │
│  → 查看 Accuracy/Recall/F1/G-mean → 生成 DRAFT 模型版本   │
│  → 审核发布 → 设置默认推荐模型 → 查看全平台数据            │
└──────────────────────────────────────────────────────────┘

┌─ 普通用户闭环 ───────────────────────────────────────────┐
│  登录 → 选择场景 → 选择数据集 → 查看该范围已发布模型      │
│  → 自动选中默认推荐模型（可改选）→ 按模型绑定字段输入样本  │
│  → 单条推理 → 查看结果/风险等级 → 风险类生成 RiskEvent     │
│  → 查看本人推理记录 / 本人风险事件 / 本人态势              │
└──────────────────────────────────────────────────────────┘
```

### 已实现功能明细（对照需求）

| 模块 | 功能 | 需求条款 | 说明 |
|:-----|:-----|:---------|:-----|
| 用户与权限 | 用户登录 | 6.2 | 未登录访问业务页面一律跳转登录页（全局路由守卫 + 请求拦截器携带身份） |
| 用户与权限 | 角色鉴权 | 6.2 | `ADMIN` / `USER` 两种角色，数据层强制校验，前端隐藏按钮不替代权限控制 |
| 用户与权限 | 普通用户账号管理 | 6.2 | 管理员创建/重置密码/启用禁用账号；普通用户可修改本人密码 |
| 用户与权限 | 数据范围隔离 | 6.8 | 普通用户只能查本人推理记录/风险事件/态势；管理员查看全平台或按用户筛选 |
| 场景管理 | 场景列表 / 切换 | 1.1 | 三场景卡片标明接入状态；按当前场景筛选数据集/模型/记录/事件 |
| 数据集管理 | 列表与字段预览 | 6.2 | 展示字段名/类型/角色/样例值；枚举字段按数据集值域校验（3.1.5） |
| 数据集管理 | 上传与版本管理 | 2.3 | 管理员上传（指定场景 + 字段校验）；修改已用数据集创建新版本；被引用只能停用不能物理删除 |
| 算法管理 | 算法代码注册 | 6.6 | A2WNB / MAWNB / EMAWNB / DIWNB / PMWNB 五种，含参数定义，管理员不可增删改算法实现 |
| 模型训练 | 选择场景/数据集/算法 | 6.3.1 | 禁止跨场景/跨数据集合并训练；已停用数据集版本不可训练 |
| 模型训练 | 配置训练参数 | 6.6.3 | 按算法注册参数定义动态生成表单，提供默认值/范围/校验 |
| 模型训练 | 训练生成草稿 | 6.7.2 | 训练成功生成 `DRAFT` 模型版本（TRAINING → DRAFT → PUBLISHED → OFFLINE 状态机） |
| 模型管理 | 保存模型版本 | 6.7.1 | 保存场景/数据集版本/算法/训练参数/评估指标/训练人/状态 |
| 模型管理 | 发布与下线 | 6.7 | 管理员审核发布、下线、重新发布；普通用户仅见已发布模型 |
| 模型管理 | 默认推荐模型 | 6.7.4 | 每个「场景＋数据集」最多一个默认推荐；默认模型下线时自动取消默认 |
| 模型使用 | 已发布模型列表 | 6.7.5 | 推理页展示该范围全部已发布模型（含指标），默认选中推荐模型，可改选 |
| 风险研判 | 单条样本推理 | 6.2 | 按模型绑定数据集字段生成输入表单；风险类结果生成 16 字段 RiskEvent |
| 推理记录 | 本人推理记录 | 6.2 | 普通用户仅本人；管理员查全部并按用户/场景筛选 |
| 风险事件 | 风险事件列表 | 6.2 | 普通用户仅本人风险事件；管理员全平台 |
| 风险配置 | 场景风险阈值 | 5.4.1 | 网络/电力分别配置中/高风险阈值，范围 [0,1]、high>medium、实时生效、记录变更日志 |
| 态势展示 | 个人与全局态势 | 6.8 | 普通用户态势只统计本人数据；管理员统计全平台 |
| 报告生成 | 生成态势报告 | P1 | 普通用户基于本人数据；管理员可选全平台/指定用户，支持导出 Markdown |
| 模型管理 | 模型版本对比 | P1 | 对比不同算法/数据集版本/模型版本指标并高亮最优，普通用户仅比较已发布模型 |

---

## 二、页面清单

| 路由 | 页面 | 说明 | 权限 |
|:-----|:-----|:-----|:-----|
| `/login` | 用户登录 | 登录入口，含演示账号快捷登录 | 公开 |
| `/overview` | 全局总览 | 跨场景风险指标聚合、趋势、风险事件列表（按角色过滤） | 登录 |
| `/dashboard` | 首页大屏 | 态势感知大屏：攻击趋势、类型分布、Top 源、攻击轨迹动画 | 登录 |
| `/scenarios` | 场景中心 | 场景卡片列表，含接入状态标识 | 登录 |
| `/scenarios/:id/dashboard` | 场景大屏 | 单场景专属看板（按角色统计） | 登录 |
| `/datasets` | 数据集中心 | 按场景筛选数据集、字段预览、版本管理（管理员上传/停用/删除） | 登录 |
| `/inference` | 风险研判 | 已发布模型列表 → 默认推荐 → 动态字段 → 单条推理 | 登录 |
| `/inference-records` | 推理记录 | 本人/全部推理记录，输入特征查看 | 登录 |
| `/alerts` | 风险事件 | 统一 RiskEvent 列表（按角色过滤） | 登录 |
| `/risk` | 模型训练 | 管理员训练页：算法参数配置 → 训练生成 DRAFT | 仅 ADMIN |
| `/models` | 模型中心 | 模型生命周期管理：发布/下线/默认推荐 + 版本对比 | 登录（操作仅 ADMIN） |
| `/situation` | 态势分析 | 多维度风险趋势分析（个人/全局） | 登录 |
| `/reports` | 报告中心 | 报告列表、生成报告（本人/全平台/指定用户）、导出 | 登录 |
| `/users` | 用户管理 | 账号列表、创建/重置密码/启用禁用、修改本人密码 | 登录（管理仅 ADMIN） |
| `/settings` | 系统设置 | 按场景风险阈值 + 变更记录、场景启停、自动刷新、主题 | 登录（阈值修改仅 ADMIN） |

### 场景支持

| 场景 | ID | 接入状态 | 数据集 | 样本数 | 说明 |
|:-----|:---|:---------|:-------|:------:|:-----|
| 网络安全态势感知 | `network_security` | ✅ 已接入 | KDDTrain+ 20 Percent（41 字段） | 7556 | 完整功能 |
| 网络安全态势感知 | `network_security` | ✅ 已接入 | NF-UNSW-NB15-v2（41 字段） | 23897 | 完整功能 |
| 电力系统风险态势感知 | `power_system` | ✅ 已接入 | PowerGrid Knowledgebase（9 字段） | 2000 | 完整功能 |
| 航母甲板保障作业 | `flightdeck_operation` | ⏸️ 仅预留 | 无数据集 | — | 保留入口/接口，不使用虚构数据 |

---

## 三、演示账号

登录页提供演示账号快捷登录，**密码均为 `123456`**：

| 账号 | 角色 | 显示名 | 可执行操作 |
|:-----|:-----|:-------|:-----------|
| `admin` | 管理员 | 系统管理员 | 训练/发布/默认推荐模型、上传/停用数据集、管理用户、配置阈值、查看全平台数据 |
| `alice` | 普通用户 | 张梦琪 | 选已发布模型推理、查看本人推理记录/风险事件/态势、生成本人报告 |
| `bob` | 普通用户 | 李文昊 | 同上 |
| `carol` | 普通用户 | 陈晓宇 | 同上 |

---

## 四、技术栈

| 技术 | 用途 |
|:-----|:------|
| **Vue 3**（Composition API + `<script setup lang="ts">`） | 前端框架 |
| **TypeScript** | 类型安全 |
| **Vite 8.x** | 构建工具 |
| **vue-tsc** | TypeScript 类型检查 |
| **vue-router 4**（hash 模式） | 路由管理 + 登录守卫 |
| **Element Plus** | UI 组件库（表格、弹窗、标签、按钮、消息提示） |
| **CSS 自定义** | 暗色科幻主题（渐变背景、毛玻璃效果、科幻色板） |

---

## 五、数据架构

### 核心类型（`src/types/security.ts`）

#### `RiskEvent` — 风险事件（需求 5.2 最小 16 字段）

```typescript
interface RiskEvent {
  event_id: string;
  inference_record_id: string;   // 来源推理记录编号
  created_by_user_id: string;    // 发起推理的账号（用于访问控制）
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;       // 来源数据集版本
  algorithm_id: string;          // 来源算法
  model_version_id: string;
  original_label: string;        // 保留 anomaly / 1 等原始输出
  risk_type: string;             // NETWORK_SECURITY_RISK / POWER_SYSTEM_RISK
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  risk_score: number;
  occurred_at: string;
  status: '待处置' | '处理中' | '已处置';
  raw_features: Record<string, unknown>;
  description: string;
}
```

#### `ModelVersionRecord` — 模型版本（需求 6.7.1）

```typescript
interface ModelVersionRecord {
  model_version_id: string;
  scenario_id: ScenarioId;
  dataset_id: string;
  dataset_version: string;
  algorithm_id: string;                    // A2WNB / MAWNB / EMAWNB / DIWNB / PMWNB
  training_parameters: Record<string, unknown>;
  evaluation_metrics: EvaluationMetrics;   // Accuracy/Recall/Precision/Specificity/F1/G-mean
  trained_by: string;
  trained_at: string;
  status: ModelStatus;                     // TRAINING | FAILED | DRAFT | PUBLISHED | OFFLINE
  published_by?: string;
  published_at?: string;
  is_default: boolean;                     // 是否为「场景＋数据集」默认推荐模型
}
```

#### 其他 v2.0 新增类型

| 类型 | 说明 |
|:-----|:-----|
| `UserAccount / UserRole` | 用户账号（ADMIN / USER）、状态 |
| `AlgorithmDefinition / AlgorithmParamDef` | 算法注册 + 公开参数定义（默认值/类型/范围/校验） |
| `InferenceRecord` | 推理记录（含 `is_risk`、`risk_score`、`risk_level`） |
| `ThresholdConfig / ThresholdChangeLog` | 按场景阈值配置 + 变更日志（操作人/前后值/时间） |
| `DatasetVersion` | 数据集版本（上传人/时间/启用状态/是否被引用） |

### Mock 数据层（`src/services/mockApi.ts`）

所有接口通过 `simulateLatency`（~180ms）模拟异步延迟，函数签名与真实后端一致，后续替换时页面层无需修改。核心接口：

| 函数 | 返回 | 说明 |
|:-----|:-----|:-----|
| `login / logout / getCurrentUser` | `UserAccount` | 会话管理（localStorage 持久化） |
| `getUserList / createUser / resetUserPassword / setUserStatus / changeOwnPassword` | 用户管理 | 管理员账号管理 + 本人改密 |
| `getDatasetList(scenario?)` | `Dataset[]` | 数据集列表（普通用户仅见已发布模型相关且启用版本） |
| `getDatasetVersions / uploadDataset / disableDatasetVersion / deleteDatasetVersion` | `DatasetVersion[]` | 数据集版本管理（需求 2.3） |
| `getAlgorithms` | `AlgorithmDefinition[]` | 五种注册算法 |
| `getThresholds / saveThreshold / getThresholdChangeLogs` | 阈值配置 | 按场景阈值 + 变更记录（需求 5.4.1） |
| `trainModel(params)` | `ModelVersionRecord` | 训练 → 生成 DRAFT 模型版本 |
| `getModelVersions(scenario?, dataset?)` | `ModelVersionRecord[]` | 模型列表（普通用户仅 PUBLISHED） |
| `publishModel / offlineModel / rePublishModel / setDefaultModel` | — | 模型生命周期操作（需求 6.7） |
| `executeInference(params)` | `InferenceResult` | 单条推理 → 生成推理记录 + 风险类生成 RiskEvent |
| `getInferenceRecords(scenario?, userId?)` | `InferenceRecord[]` | 推理记录（按角色/用户过滤） |
| `getRiskEvents(scenario?)` | `RiskEvent[]` | 风险事件（按角色过滤） |
| `getScenarioList / getScenarioDetail / getGlobalOverview / getSituationData` | 态势数据 | 个人/全局态势（按角色统计） |
| `getReportList / generateReport` | `Report[]` | 报告列表 + 生成报告（本人/全平台/指定用户） |

### 数据集字段结构

严格遵循《用户分级v2.md》第 3 节 ARFF 文件定义，并录入枚举值域（需求 3.1.5 / 3.2.1 / 3.3.1 / 3.4.1）：

| 数据集 | 字段数 | 输入特征 | 标签字段 | 正类（风险） | 负类（正常） |
|:-------|:------:|:--------:|:---------|:-------------|:-------------|
| KDDTrain+ 20 Percent | 41 | 40 | `class` | `anomaly` | `normal` |
| NF-UNSW-NB15-v2 | 41 | 40 | `Label` | `1` | `0` |
| PowerGrid Knowledgebase | 9 | 8 | `Target_Event` | `1` | `0` |

### 风险等级生成（需求 5.4）

```
若模型结果为正常类：保存推理结果，不生成 RiskEvent
若模型结果为风险类：
    risk_score >= high_threshold      → HIGH
    medium_threshold <= risk_score < high_threshold → MEDIUM
    risk_score < medium_threshold     → LOW
```

阈值按场景隔离配置，调整只影响风险等级，不改变模型原始预测标签；历史 RiskEvent 不因阈值修改而重算。

---

## 六、项目结构

```
frontend/
├── src/
│   ├── api/                      # 真实后端 API 调用（预留）
│   ├── components/
│   │   ├── common/               # 通用组件（ScenarioSelector 等）
│   │   ├── DonutChart.vue        # 环形图
│   │   ├── LineTrendChart.vue    # 折线趋势图
│   │   └── RankingList.vue       # 排行列表
│   ├── router/
│   │   └── index.ts              # 路由配置（hash 模式）+ 登录守卫
│   ├── services/
│   │   ├── mockApi.ts            # Mock 数据层（用户/算法/模型/事件闭环）
│   │   └── modelApi.js           # 后端模型 API 封装
│   ├── types/
│   │   └── security.ts           # 核心类型定义
│   ├── utils/
│   │   └── request.js            # axios 实例（请求拦截器注入身份）
│   ├── views/
│   │   ├── Login.vue             # 用户登录
│   │   ├── Dashboard/            # 首页大屏
│   │   ├── Alert/                # 告警（风险事件）列表与详情
│   │   └── Model/
│   │       ├── OverviewView.vue      # 全局总览
│   │       ├── ScenarioCenter.vue    # 场景中心
│   │       ├── ScenarioDashboard.vue # 场景大屏
│   │       ├── DatasetCenter.vue     # 数据集中心（上传/版本管理）
│   │       ├── RiskAnalysis.vue      # 模型训练（管理员）
│   │       ├── ModelCenter.vue       # 模型中心（发布/默认推荐/对比）
│   │       ├── RiskInference.vue     # 风险研判（已发布模型推理）
│   │       ├── InferenceRecords.vue  # 推理记录
│   │       ├── SituationAnalysis.vue # 态势分析
│   │       ├── ReportCenter.vue      # 报告中心（生成/导出）
│   │       ├── UserManagement.vue    # 用户管理（管理员）
│   │       └── Settings.vue          # 系统设置（按场景阈值）
│   ├── App.vue                  # 应用外壳（顶栏导航 + 用户信息 + 退出）
│   ├── main.ts                  # 挂载入口
│   └── style.css                # 全局样式
└── public/
    └── maps/                    # SVG 地图底图
```

---

## 七、项目启动

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发环境

```bash
npm run dev
```

打开浏览器访问 `http://localhost:5173`（Vite 默认端口），使用演示账号登录。

### 3. 构建生产版本

```bash
npm run build
```

### 4. 类型检查（单独运行）

```bash
npm run type-check
```

---

## 八、如何接入真实后端

当前数据层位于 `src/services/mockApi.ts`，函数签名与真实接口一致。替换策略：

1. **创建真实 API 服务**（如 `src/services/realApi.ts`），使用 axios/fetch 调用后端
2. **保持函数签名不变**（输入参数、返回类型、异步 Promise 接口）
3. **在页面中替换 import 路径**（`mockApi` → `realApi`）

```typescript
// 当前（Mock）
import { getRiskEvents } from '@/services/mockApi';
const events = await getRiskEvents();

// 替换后（真实后端）
import { getRiskEvents } from '@/services/realApi';
const events = await getRiskEvents();
```

> 注意：需求 6.5.2 要求「所有权限校验必须在后端实现，前端隐藏按钮不能替代权限控制」。当前 Mock 层已模拟 `requireLogin / requireAdmin` 校验，接入真实后端时必须在服务端实现同等鉴权。

---

## 职责边界（前端 / 后端）

本项目只负责**前端**。以下文档 P0 硬性要求依赖**后端**实现，前端无法替代；前端已按相同函数签名在 Mock 层（`src/services/mockApi.ts`）预留接口契约，后端接入时按签名实现即可。

| 需求 | 说明 | 前端现状 |
|:-----|:-----|:---------|
| 6.5.2 权限校验在后端实现 | 前端 UI 已按角色隔离 + Mock 层模拟校验，但真实鉴权/数据隔离须由后端接口层校验 | `request.js` 请求拦截器已注入 `X-User-Id`；Mock 层 `requireLogin/requireAdmin` 模拟 |
| 5.4.1.3 / 2.3 / 6.7 持久化 | 阈值、数据集版本、模型版本、推理记录、风险事件需持久化保存，刷新不丢失 | 当前为内存 Mock，刷新即重置；登录 session 存 localStorage |
| 5.2 访问控制(3) 用户禁用后记录保留 | 历史推理记录/风险事件在用户禁用后仍应保留，管理员可查询 | Mock 层同 session 生命周期，待后端数据库承载 |

---

## 九、设计风格说明

### 暗色科幻主题

- **背景**：深色渐变 + 动态网格/粒子 canvas 背景
- **卡片**：玻璃拟态（`rgba` 半透明背景 + 发光边框）
- **主色**：贯穿全站的 `#5ba6ff` → `#407acc` 蓝色渐变
- **动画**：加载微动效、悬停高亮、平滑过渡

### Element Plus 组件覆盖

全站的 `el-table`、`el-dialog`、`el-tag`、`el-button` 均通过全局 `<style>` 覆盖为暗色主题（实色深色背景，避免亮色层透出），保持视觉一致。

---

## 十、构建验证

```bash
vue-tsc -b && vite build
# ✓ 0 TypeScript errors
# ✓ built in 1.29s
```

当前版本通过 `vue-tsc -b && vite build` 全量类型检查 + 构建，**零类型错误**。

---

## 十一、后续扩展方向

- [ ] 接入真实后端 API，服务端实现鉴权与数据隔离（需求 6.5.2）
- [ ] 接入真实数据库（MySQL / PostgreSQL / InfluxDB）
- [ ] 实时数据推送（WebSocket / SSE）
- [ ] 资产拓扑图与攻击路径回放
- [ ] 自定义可视化大屏布局（拖拽组件）
- [ ] 多语言支持（i18n）
- [ ] 航母甲板场景正式数据集接入（需求变更后启用训练/推理）
- [ ] 模型在线部署与实时推理管线
- [ ] AI 研判可解释性展示（SHAP / LIME）

---

## 许可

本项目为课程项目，仅供学习和演示用途。
