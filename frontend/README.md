# 多场景贝叶斯分类态势感知系统 — 前端（V3.0 四场景）

基于 **Vue 3 + TypeScript + Vite + Element Plus + Pinia + ECharts** 构建的多场景贝叶斯分类态势感知平台前端，面向**网络安全、电力系统、地质风险、航母甲板保障作业**四个业务场景，严格对齐《V3.0需求分析(1).md》的 P0 功能与第 7 节场景差异化展示要求。

> 当前版本数据由本地 Mock 层驱动（`src/services/mockApi.ts`，经 Pinia store 注入页面）。登录、角色鉴权、场景-用户绑定、数据范围隔离等规则已在 Mock 层模拟；正式交付时须由后端实现同等鉴权与持久化（切换点见第八节）。

---

## 一、功能总览

### P0 业务闭环（需求 6.3）

```
┌─ 管理员闭环 ───────────────────────────────────────────────────┐
│  登录 → 场景中心 → 用户管理（创建账号并分配场景）→ 选择场景      │
│  → 数据集（含数据预览/上传/版本）→ 选择算法配置参数 → 训练      │
│  → DRAFT → 发布 → 设默认推荐模型 → 配置阈值 → 全平台态势        │
└───────────────────────────────────────────────────────────────┘

┌─ 普通用户闭环 ─────────────────────────────────────────────────┐
│  登录 → 首页（全局态势）→ 场景看板（仅绑定场景）→ 数据集         │
│  → 已发布模型（默认推荐自动选中）→ 字段表单推理 → 风险事件详情   │
│  → 本人推理记录 / 本人态势                                     │
└───────────────────────────────────────────────────────────────┘
```

### 已实现功能明细（对照需求）

| 模块 | 功能 | 需求条款 | 说明 |
|:-----|:-----|:---------|:-----|
| 用户与权限 | 用户登录 / 角色鉴权 | 6.2 / 6.5 | 全局路由守卫 + 角色落地页（ADMIN→场景中心，USER→首页）；mock 层强制校验，前端隐藏仅体验 |
| 用户与权限 | 普通用户账号管理 | 6.2 | 创建/重置密码/启用禁用；**创建与改绑均支持"分配场景"多选** |
| 用户与权限 | 数据范围隔离 | 6.8 | 普通用户仅本人记录/事件/态势；管理员全平台或按用户筛选 |
| 场景管理 | 场景列表 / 场景-用户绑定 | 1.1.6 / 6.5 | 四场景卡片；普通用户仅见绑定场景（mock 层强制过滤 + URL 直访拦截） |
| 数据集管理 | 列表与字段预览 | 6.2 / 3.1 | 按场景展示字段名/类型/角色/样例值/枚举值域 |
| 数据集管理 | 数据内容预览 | 2.4 | 详情页分页（每页 ≤50）、只读、标签列高亮、极宽表冻结首列 |
| 数据集管理 | 上传与版本管理 | 2.3 | 管理员上传/改版保留旧版/停用/删除（被引用只能停用） |
| 算法管理 | 算法代码注册 | 6.6 | A2WNB / MAWNB / EMAWNB / DIWNB / PMWNB，含参数定义 |
| 模型训练 | 训练 / 保存 / 发布 / 下线 | 6.7 | TRAINING→FAILED/DRAFT→PUBLISHED→OFFLINE 状态机；发布人/时间记录 |
| 模型管理 | 默认推荐模型 | 6.7.4 | 每"场景＋数据集"最多一个默认；自动选中可改选；下线自动取消默认 |
| 模型使用 | 已发布模型列表 | 6.7.5 | 推理页展示该范围全部已发布模型（含指标），默认推荐自动选中 |
| 风险研判 | 单条样本推理 | 6.2 / 7.4 | 动态字段表单；**carrier 279 字段按 6 族折叠分组**（默认仅首组挂载，防卡顿）；`?port=` 可预填端口 |
| 推理记录 | 本人推理记录 | 6.2 | 普通用户仅本人；管理员全部/按用户/按场景筛选 |
| 风险事件 | 列表 / 详情 | 5.7 / 6.2 | 五组信息（基本信息/模型溯源/推理详情/输入特征/可解释性文本）+ 处置流转；解释文本生成时固化 |
| 风险配置 | 场景风险阈值 | 5.4.1 | network/power/geological 三场景独立配置，[0,1]、high>medium、实时生效、变更日志；航母甲板预留卡 |
| 态势展示 | 首页（全局态势） | 7.0 | 普通用户登录落地页：大号数字卡 + 场景分布 + 健康度排行 + 趋势 + 场景快捷卡 |
| 态势展示 | 场景差异化看板 | 7.1–7.4 | 四看板指标卡/图表/交互按需求对齐（端口预填、设备筛选、数据集联动、热点图等） |
| 态势展示 | 场景中心 / 业务场景概览 | 7.0 | 三入口视觉明确区分；看板顶部内嵌其它场景快捷入口 |
| 态势展示 | 场景轻量算法 | 8.1–8.4 | 网络端口偏离度 + Z-score 突变检测、电力设备健康分 + 风险评分模型、地质易发性评分、甲板碰撞风险 + 轨迹偏差检测（`src/utils/scenarioAlgorithms.ts`） |
| 报告生成 | 生成态势报告 | P1 | 普通用户本人数据；管理员全平台/指定用户，支持导出 Markdown |
| 模型管理 | 模型版本对比 | P1 | 模型中心内联对比面板：选择 2-5 个模型，按 Accuracy/Recall/Precision/Specificity/F1/G-mean 逐项对比并高亮最优 |

---

## 二、页面清单

| 路由 | 页面 | 说明 | 权限 |
|:-----|:-----|:-----|:-----|
| `/login` | 用户登录 | 登录入口，含演示账号快捷登录，副标题四场景 | 公开 |
| `/` | — | 按角色重定向（ADMIN→`/scenarios`，USER→`/home`） | — |
| `/home` | 首页（全局态势） | 普通用户全局驾驶舱（跨场景聚合） | 仅 USER |
| `/overview` | 全局总览 | 兼容路径（保留旧页） | 登录 |
| `/dashboard` | 旧版首页大屏 | 全平台演示大屏 | 仅 ADMIN |
| `/scenarios` | 场景中心 | 场景卡片（普通用户仅绑定场景；空态引导） | 登录 |
| `/scenarios/:id/dashboard` | 场景看板 | 四场景差异化看板（7.1–7.4） | 登录 |
| `/datasets` | 数据集中心 | 按场景筛选、字段预览、上传/版本管理、数据预览入口 | 登录 |
| `/datasets/:datasetId` | 数据集详情 | 字段结构 + 数据内容预览（分页/标签高亮/冻结首列） | 登录 |
| `/inference` | 风险研判 | 场景→数据集→已发布模型→字段表单→推理 | 登录 |
| `/inference-records` | 推理记录 | 本人/全部记录、输入特征查看、风险记录跳事件详情 | 登录 |
| `/events/:eventId` | 风险事件详情 | 五组信息 + 处置流转 | 登录 |
| `/alerts` | 旧版告警中心 | 旧大屏演示页（入口仅 ADMIN，不迁移新逻辑） | 仅 ADMIN |
| `/risk` | 模型训练 | 管理员训练页（走 `trainingApi` 真实后端，需后端运行） | 仅 ADMIN |
| `/models` | 模型中心 | 模型生命周期：发布/下线/默认推荐 | 登录（操作仅 ADMIN） |
| `/situation` | 态势分析 | 四场景风险趋势分析（按绑定场景注入） | 登录 |
| `/reports` | 报告中心 | 报告列表、生成（本人/全平台/指定用户）、导出 | 登录 |
| `/users` | 用户管理 | 账号列表、创建（含分配场景）、重置/启禁、分配场景、改本人密码 | 登录（管理仅 ADMIN） |
| `/settings` | 系统设置 | 三场景阈值 + 变更记录、场景启停（含地质） | 登录（阈值仅 ADMIN） |

### 场景与数据集

| 场景 | ID | 数据集 | 字段 | 标签 |
|:-----|:---|:-------|:----:|:-----|
| 网络安全 | `network_security` | KDDTrain+ 20 Percent（7556） | 41 | `class` |
| 网络安全 | `network_security` | NF-UNSW-NB15-v2（23897） | 41 | `Label` |
| 电力系统 | `power_system` | PowerGrid Knowledgebase（2000） | 9 | `Target_Event` |
| 地质风险 | `geological_risk` | DIS_raw_data（5000）/ DIS_Landslides（5185）/ DIS_Causative_Factors（5000）/ DIS_Global_Catalog（1000，编目）/ DIS_guaruja_random（200） | 19/9/13/12/8 | Label / LS / landslides / landslide_size / class |
| 航母甲板 | `flightdeck_operation` | carrier_feature2_biaoqian / carrier_feature2_lisan / carrier_paired_trail_biaoqian（各 507） | 279/279/281 | `Collision` |

---

## 三、演示账号（密码均为 `123456`）

| 账号 | 角色 | 显示名 | 绑定场景 |
|:-----|:-----|:-------|:---------|
| `admin` | 管理员 | 系统管理员 | 全部 4 场景（角色放行） |
| `alice` | 普通用户 | 演示用户A | 网络安全 |
| `bob` | 普通用户 | 演示用户B | 电力系统 |
| `carol` | 普通用户 | 演示用户C | 地质风险 + 航母甲板 |

---

## 四、技术栈

| 技术 | 用途 |
|:-----|:------|
| **Vue 3**（Composition API + `<script setup lang="ts">`） | 前端框架 |
| **TypeScript**（strict） | 类型安全 |
| **Vite 8.x / vue-tsc** | 构建与类型检查 |
| **vue-router 4**（hash 模式） | 路由 + 角色守卫 |
| **Pinia** | 全局状态（页面数据唯一入口，不直连 mockApi） |
| **Element Plus** | UI 组件库 |
| **ECharts**（按需引入） | 柱/饼/折线/雷达图封装 |
| **CSS 自定义** | 暗色科幻主题 |

---

## 五、数据架构

### 数据流

```
页面 → Pinia Store（src/stores/） → mockApi（过渡期）→ 后端 API 层（src/api/，联调切换点）
```

### 核心类型（`src/types/security.ts`）

- 四场景标识：`ScenarioId = 'network_security' | 'power_system' | 'geological_risk' | 'flightdeck_operation'`
- `RiskEvent`：16+ 必填字段 + 可选 `fault_position_x/y`（航母热点图坐标，基准 1000px）
- `UserAccount.scenario_ids?`：用户-场景绑定（需求 1.1.6）
- `RiskLevelUpper` / `toRiskLevel()`：风险等级大小写双轨统一入口
- `DataRow` / `DataPreview`：数据预览分页类型（需求 2.4）
- `ScenarioDashboardData`：场景看板聚合数据

### Store（`src/stores/`）

`userStore`（会话/用户管理/可见场景）、`scenarioStore`、`datasetStore`、`modelStore`、`inferenceStore`、`riskEventStore`、`situationStore`、`reportStore`、`thresholdStore`。

### API 层（`src/api/`）

10 个模块与后端 `/api/v1` 路由一一对应（薄封装 + 统一 `unwrapData`）；`situationApi` 为占位（后端无态势路由）。联调时在 store 内部替换数据源即可。

### Mock 数据层（`src/services/mockApi.ts`）

覆盖四场景 11 数据集、5 算法、模型生命周期、推理/事件闭环、阈值、数据预览（确定性生成）、场景绑定访问控制（`canAccessScenario` / `assertScenarioAccess`）。

### 风险等级生成（需求 5.4）

```
正常类 → 仅保存推理结果，不生成 RiskEvent
风险类 → risk_score >= high_threshold → HIGH
         medium <= risk_score < high → MEDIUM
         risk_score < medium          → LOW
```

阈值按场景隔离、实时生效、历史事件不重算；变更记录含操作人/场景/时间/前后值。

---

## 六、项目结构

```
frontend/
├── src/
│   ├── api/                      # API 层模块（10 个，与 /api/v1 对齐）
│   ├── components/
│   │   ├── charts/               # ECharts 封装（EChartBase + Bar/Pie/Line/Radar）
│   │   ├── common/               # 通用组件（ScenarioSelector / RiskLevelTag / DataPreviewTable）
│   │   ├── scenario/             # 四场景看板 + ScenarioMetricCard + EventTimeline + ScenariosQuickNav
│   │   ├── Deck/                 # 甲板热点图（DeckHeatMap）
│   │   └── ...                   # 旧 SVG 图表（保留兼容）
│   ├── router/
│   │   ├── index.ts              # 路由 + meta
│   │   └── guards.ts             # 角色守卫
│   ├── services/
│   │   └── mockApi.ts            # Mock 数据层（四场景）
│   ├── stores/                   # Pinia（9 个）
│   ├── types/security.ts         # 业务类型唯一来源
│   ├── utils/request.js          # axios 实例 + unwrapData
│   ├── views/
│   │   ├── Login.vue
│   │   ├── Home/                 # 首页（全局态势）
│   │   ├── Scenario/             # 场景看板容器
│   │   ├── Dataset/              # 数据集详情（预览）
│   │   ├── Event/                # 风险事件详情
│   │   ├── Model/                # 场景中心/数据集/模型/推理/记录/态势/报告/用户/设置/训练
│   │   ├── Dashboard/            # 旧大屏（保留）
│   │   └── Alert/                # 旧告警（保留）
│   ├── App.vue / main.ts / style.css
└── public/
```

---

## 七、项目启动

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # vue-tsc -b && vite build
```

---

## 八、如何接入真实后端

当前数据入口统一为 **Pinia store → mockApi**；后端就绪后的切换点：

1. **store 内部替换**：把 store action 中 `mockApi.xxx()` 替换为 `src/api/` 对应模块（函数签名已对齐 `/api/v1`）。
2. **登录**：后端无 `/auth/login` 路由，暂走 mock；后端提供后由 `userStore.login` 切换。
3. **态势**：`situationApi` 为占位（`getGlobalCockpit` TODO），联调时实现并切换 `situationStore`。
4. **`/risk` 训练页**：已走 `trainingApi`（真实后端数据库版），需后端运行（`http://127.0.0.1:12312`）。

> 权限边界（需求 6.5.2）：真实鉴权必须在后端实现，前端隐藏/过滤仅为体验；Mock 层 `requireLogin / requireAdmin / assertScenarioAccess` 模拟，接入后端时须在服务端实现同等校验。

---

## 九、设计风格

- 暗色科幻主题：深色渐变 + 玻璃拟态卡片 + `#5ba6ff` 蓝色渐变主色。
- ECharts 统一暗色主题（`bayes-dark`），配色与 `style.css` 一致（#5ba6ff / #53e5c8 / #ff7b72 / #ffd166）。
- Element Plus 组件（el-table / el-dialog / el-tabs / el-collapse / el-button）全局覆盖为暗色。
- 场景看板样式命名空间 `scenario-*`，与 `home-*` / `ov-*` 隔离。

---

## 十、构建验证

```bash
vue-tsc -b && vite build
# ✓ 0 TypeScript errors
```

当前版本零类型错误；仅存在既有 chunk 体积告警（>500kB，建议后续代码分割优化）。

## 更新记录

- [8.14所做修改.md](8.14所做修改.md)：补齐需求第 8 节场景轻量算法、`/overview` 权限对齐 6.5.2、甲板热点图 SVG 底图升级。
- [8.13所做修改.md](8.13所做修改.md)：V3.0 四场景改造（Task 001–017）与需求第 7 节看板规格对齐的完整汇报。
- [前端更新（8.8所做修改）.md](前端更新（8.8所做修改）.md)：v2 后续修补记录。
- [前端更新（8.5前端修补）.md](前端更新（8.5前端修补）.md)：用户分级 v2 审查后的权限隔离、数据集版本绑定等修补。
- [前端更新（8.4对齐用户分级）.md](前端更新（8.4对齐用户分级）.md)：v2 P0/P1 功能初始实现记录。

---

## 十一、后续扩展方向

- [ ] 接入真实后端 API（登录/态势/管理接口），服务端鉴权与持久化
- [ ] 真实 ARFF 数据替换 mock（含 507 条航母轨迹），热点图替换美工底图
- [ ] 实时数据推送（WebSocket / SSE）
- [ ] chunk 代码分割优化（ECharts 动态路由已初步分离）

---

## 许可

本项目为课程项目，仅供学习和演示用途。
