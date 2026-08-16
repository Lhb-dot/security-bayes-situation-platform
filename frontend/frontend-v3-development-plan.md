# 多场景贝叶斯分类态势感知系统 — V3.0 前端改造开发任务说明书

> **适用对象：** Codex（后续执行开发）
> **依据文档：** `V3.0需求分析(1).md`（正式需求 v3.0，业务基线）
> **适用阶段：** 系统第一阶段（P0 必做，P1 增强）
> **基线约束：**
> - 保留现有 **Vue3 + TypeScript + Vite + Element Plus** 架构，不重构技术栈。
> - 不引入框架级重写；**ECharts 是本计划唯一允许新增的第三方依赖**。
> - 所有权限边界在后端，前端隐藏按钮/路由仅为体验，必须注释说明。
> - 已接入场景（四场景）不得使用虚构数据代替正式数据（航母甲板须基于 507 条真实轨迹样本形态）。

---

## 通用开发约定（所有 Task 生效）

1. **构建检查命令**：`npm run build`（= `vue-tsc -b && vite build`），每个 Task 完成必须零类型错误。
2. **类型单一来源**：业务类型只定义在 `src/types/security.ts`，禁止页面内重复声明 `interface`（页面内只允许"后端临时行类型"例外，如 RiskAnalysis 的 `DbScenario`）。
3. **数据入口唯一**：引入 Pinia 后，页面不得再直接 `import { xxx } from '@/services/mockApi'`，一律走 store；store 内部可调 mockApi（过渡期）或 API 层（后端就绪后）。
4. **场景编码**：`network_security` / `power_system` / `geological_risk` / `flightdeck_operation` 四场景，禁止硬编码数组散落页面，统一从 `scenarioStore` 注入。
5. **权限注释规范**：涉及角色判断的代码必须带 `// 需求 6.5.x：权限边界在后端，前端仅体验` 类注释。
6. **旧大屏/告警（Dashboard/Alert）** 不迁移、不入新逻辑，仅做导航隐藏。
7. **命名**：视图 `views/<模块>/<Xxx>.vue`，公共组件 `components/common/`，图表组件 `components/charts/`，场景看板 `views/Scenario/`。

---

## 总依赖关系

```
001 ─┬→ 002 ─→ 006 ─→ 007 ─→ 009
     ├→ 003 ─→ 004 ─→ 005
     ├→ 008 ─→ 009 ─→ 014
     ├→ 010 ─→ 012 ─→ 014
     └→ 011 / 013 / 015 / 016 / 017
```

**建议开发顺序**：001 → 003 → 008（基建可并行）→ 004 → 005 → 002 → 006 → 011 → 012 → 010 → 007 → 009 → 013 → 014 → 015 → 016 → 017。

---

## Task 001 基线缺陷修复与类型模型扩充（P0 · 无前置）

**目标：** 为 V3.0 四场景改造打地基：修复现有编译隐患（`App.vue` 全角分号），并把类型模型升级为四场景完整定义（新增 `geological_risk`、航母甲板实际接入字段、`fault_position`、用户-场景绑定、数据预览类型）。

**涉及文件：**
- 修改：`src/types/security.ts`
- 修改：`src/App.vue`

**需要新增：**
- `ScenarioId` 追加 `'geological_risk'`。
- `RiskEvent` 追加 `fault_position_x?: number | null`、`fault_position_y?: number | null`（需求 5.2 / 7.4.1，仅航母场景使用）。
- `UserAccount` 追加 `scenario_ids?: ScenarioId[]`（需求 1.1.6 用户-场景绑定）。
- 新类型：`DataRow`（`Record<string, string | number>`）、`DataPreview`（`{ total; page; page_size; rows: DataRow[]; label_field: string }`，需求 2.4）、`ScenarioDashboardData`（各场景看板聚合数据）。
- 风险等级显式类型：`RiskLevelUpper = 'HIGH' | 'MEDIUM' | 'LOW'`（现有 `RiskEvent.risk_level` 为大写），并补 `toRiskLevel()` 转换工具。

**需要修改：**
- `ScenarioId`、`RiskEvent`、`UserAccount` 扩展字段（向后兼容，新字段可选或带默认）。
- `App.vue` 第 10 行 `import AlertsView from './views/Alert/AlertsView.vue'；` 的全角分号 `；`（U+FF1B）改为半角 `;` —— 该字符会导致 vite 编译失败。

**实现要求：**
- 不得破坏现有类型；以可选字段方式扩展。
- 全部业务类型集中在 `security.ts`。
- 等级大小写双轨为历史包袱，改造期间禁止新增 `as any`，统一走 `toRiskLevel()`。

**验收标准：**
- `npm run build` 零类型错误。
- `security.ts` 中存在 `geological_risk`、`fault_position_x/y`、`scenario_ids`、`DataPreview`、`RiskLevelUpper`。
- `App.vue` 无全角标点。

**风险注意事项：**
- 全角分号导致编译失败的隐患必须最先修复。
- 类型修改会波及大量页面，需同步修正引用处的类型错误，禁止用 `any` 掩盖。

---

## Task 002 场景与数据集 Mock 数据扩充（P0 · 依赖 001）

**目标：** 让 `mockApi.ts` 覆盖四场景真实接入：地质风险 5 个数据集、航母甲板 3 个数据集（507 条真实轨迹样本形态），支撑后续所有页面开发。

**涉及文件：**
- 修改：`src/services/mockApi.ts`

**需要新增：**
- `SCENARIO_META` 增加 `geological_risk` 场景，字段严格对齐需求 3.6：
  - `dis_raw_data`：19 字段，标签 `Label`，5000 样本（正类 `1`）
  - `dis_landslides`：9 字段，标签 `LS`，5185 样本（正类 `1`）
  - `dis_causative_factors`：13 字段，标签 `landslides`，5000 样本（正类 `>0`，高度不平衡）
  - `dis_global_catalog`：12 字段，标签 `landslide_size`（多分类编目，1000 样本，**不参与二分类训练/事件生成**）
  - `dis_guaruja_random`：8 字段，标签 `class`，200 样本（正类 `1`）
- flightdeck 由 `status:'inactive'`、`datasets:[]` 改为 `active`，接入 3 数据集（字段结构对齐需求 3.5.1）：
  - `carrier_feature2_biaoqian`：279 字段，标签 `Collision`，507 样本
  - `carrier_feature2_lisan`：279 字段，标签 `Collision`，507 样本
  - `carrier_paired_trail_biaoqian`：281 字段（含 `PlaneID1`/`PlaneID2`），标签 `Collision`，507 样本
  - 279/281 字段用**循环程序化生成**（49 时间步的方向角/相对角/间距/派生统计量 + 标签），字段名严格按字段族命名（如 `Plane1_dir_angle_deg_1..49`）。
- `ENUM_VALUES`、`DATASET_DEF` 补新数据集；`riskTypeOf` 增加 `GEOLOGICAL_RISK`（`FLIGHT_DECK_OPERATION_RISK` 已存在）；`originalLabelOf` 对 carrier 返回 `0/1`（`Collision`）。
- 种子推理记录与风险事件：覆盖地质风险与航母甲板样本（carrier 事件按需求 7.4.1 计算 `fault_position_x/y`）。
- `thresholds` 初始化加入 `geological_risk`。

**需要修改：**
- `generateScenarioCard/Detail/Overview/Situation` 支持四场景统计，航母甲板不再硬编码为 0/空。

**实现要求：**
- 数据集字段名/类型/枚举值域/样例值必须与需求第 3 节一致，禁止自造列。
- carrier 大字段使用辅助函数生成，保证 `validateInputFeatures`（训练/推理校验）可正常通过。

**验收标准：**
- `getScenarioList()` 返回 4 个 `active` 场景。
- `getDatasetList('geological_risk')` 返回 5 个数据集；`getDatasetList('flightdeck_operation')` 返回 3 个数据集。
- carrier 数据集可完成字段校验与推理闭环。

**风险注意事项：**
- carrier 279 字段若全部渲染成表单 input 会卡顿——推理表单必须分组折叠（见 Task 010）。
- `dis_global_catalog` 为编目数据，禁止进入二分类训练与风险事件生成（需求 3.6.4 / 4.4 规则 3）。

---

## Task 003 API 层模块化（P0 基建 · 无前置）

**目标：** 把散落在 mockApi 的业务能力抽象为与后端 `/api/v1` 对齐的独立 API 模块，为 Pinia 与后端对接做准备。

**涉及文件：**
- 新增：`src/api/userApi.ts`、`scenarioApi.ts`、`datasetApi.ts`、`algorithmApi.ts`、`modelVersionApi.ts`、`inferenceRecordApi.ts`、`riskEventApi.ts`、`riskThresholdApi.ts`、`reportApi.ts`、`situationApi.ts`
- 修改：`src/api/trainingApi.js`（对齐统一模式，注意实际文件是 `.js` 非 `.ts`）、`src/utils/request.js`（如需统一 unwrap 工具）
- 遗留：`src/api/modelApi.js` 标注 deprecated，新代码禁止引用

**需要新增：**
- 每个模块导出与后端路由一一对应的薄封装函数（对照 `backend/app/api/v1/endpoints/`）：
  - `userApi`：me / list / create / changePassword / resetPassword / setStatus
  - `scenarioApi`：list / detail
  - `datasetApi`：list / detail / fieldsSchema / upload / createVersion / disable / remove
  - `algorithmApi`：list
  - `modelVersionApi`：list / default / compare / train / publish / offline / setDefault / clearDefault
  - `inferenceRecordApi`：predict / list / detail / remove
  - `riskEventApi`：list / detail / updateStatus / comment
  - `riskThresholdApi`：get / update
  - `reportApi`：list / detail / generate / remove
  - `situationApi`：**预留**（后端暂无态势路由，仅定义函数签名 + `// TODO 后端待提供`）
- 统一 `unwrapData`（`{code,data,message}` 剥壳，非零 code 抛错），与 `trainingApi` 一致。

**需要修改：**
- 无破坏性修改；新页面走新 API，旧页面保持 mock，避免一次性大迁移。

**实现要求：**
- 函数签名使用 `types/security.ts` 类型。
- API 层保持薄封装，禁止放业务逻辑（过滤/权限）。
- 后端不存在的接口（登录、态势）标注 `// TODO` 预留，前端继续走 mock。

**验收标准：**
- `npm run build` 通过；模块可被 store 引用。
- 每个后端既有路由都有对应前端 API 函数。

**风险注意事项：**
- 后端无 `/auth/login`、无态势路由——登录与态势暂保留 mock，API 层只留占位不切换。
- 不要在同一 Task 里把全部页面切到真实 API，避免后端未就绪导致页面全挂。

---

## Task 004 Pinia 状态管理接入（P0 基建 · 依赖 003）

**目标：** 引入 Pinia，把"用户/场景/数据集/模型/推理/事件/态势/报告/阈值"集中到响应式 store，替代页面各自 `ref` + 直接调用 mockApi，解决跨页同步依赖 `App.vue` 全量刷新问题。

**涉及文件：**
- 修改：`package.json`（新增 `pinia`）、`src/main.ts`（注册 `createPinia()`）
- 新增：`src/stores/userStore.ts`、`scenarioStore.ts`、`datasetStore.ts`、`modelStore.ts`、`inferenceStore.ts`、`riskEventStore.ts`、`situationStore.ts`、`reportStore.ts`、`thresholdStore.ts`

**需要新增：**
- 每个 store：state / getters / actions；action 内部优先调 API 层，后端未就绪时调 mockApi。
- `userStore` 接管全局会话：`currentUser`、`isAdmin`、`login/logout/changePassword`、可见场景 `scenario_ids`。

**需要修改：**
- `main.ts` 注册 Pinia。
- `App.vue` 顶部栏用户/角色改由 `userStore` 派生。
- 页面逐步改接 store（与后续页面任务并行）。

**实现要求：**
- 每个 store 单一职责；跨 store 引用显式（如 `inferenceStore` 读 `modelStore` 的选中模型）。
- store 为唯一数据入口，页面禁止再直接 `import mockApi`。

**验收标准：**
- 登录/退出后 `userStore` 响应式更新顶部栏。
- Dataset / Model / RiskEvent 至少三个页面改由 store 驱动。

**风险注意事项：**
- 过渡期"mockApi + store"双写易漂移：以 store 为准，mockApi 只作为 store 内部的数据源。
- 旧大屏（dashboard/alerts）数据不迁移，保持现状。

---

## Task 005 角色化路由与导航（P0 · 依赖 004）

**目标：** 落地"登录落地页区分 + 菜单角色可见 + 未登录拦截 + 管理员无首页"（需求 6.5.3 / 6.5.4 / 7.0）。

**涉及文件：**
- 修改：`src/router/index.ts`、`src/App.vue`、`src/views/Login.vue`
- 新增：`src/router/guards.ts`（守卫拆分，可选）

**需要新增：**
- 路由 `meta`：`{ requiresAdmin?: boolean; userOnly?: boolean; hiddenForUser?: boolean; title: string }`。
- 角色化重定向：`/` → `ADMIN ? '/scenarios' : '/home'`；登录成功跳转同上。
- 新增路由：`/home`（HomeView，见 Task 007）。

**需要修改：**
- `App.vue` 顶部导航按角色 + meta 渲染：
  - 普通用户隐藏：态势监控大屏、告警中心、AI 模型训练、用户管理。
  - 管理员隐藏：首页（/home）。
- 路由守卫补充：`requiresAdmin` 页面 USER 访问 → 重定向；`/home` 对 ADMIN → 重定向 `/scenarios`。
- 保留 `/overview` 为兼容路径（重定向到 `/home` 或 `/scenarios`）。

**实现要求：**
- 前端隐藏仅为体验，注释标明真正鉴权在后端（需求 6.5.2 末段）。
- 旧大屏/告警路由保留但入口隐藏（是否下线由业务确认）。

**验收标准：**
- alice（USER）登录 → 进入 `/home`，导航不含"用户管理/告警中心/AI模型训练/首页大屏"。
- admin 登录 → 进入 `/scenarios`，无"首页(/home)"入口。
- 未登录访问任意业务路由 → 跳 `/login`。

**风险注意事项：**
- `App.vue` 为 502 行单体组件，只改导航渲染逻辑，不做布局重构，控制改动面。

---

## Task 006 场景可见性与用户-场景绑定（P0 · 依赖 001/005）

**目标：** 实现需求 1.1.6 / 6.5：普通用户仅见被分配场景，不展示未分配入口/数据；管理员可见全部并可切换。

**涉及文件：**
- 修改：`src/services/mockApi.ts`、`src/components/common/ScenarioSelector.vue`、`src/views/Model/ScenarioCenter.vue`、`src/views/Model/UserManagement.vue`、`src/views/Model/DatasetCenter.vue`、`src/views/Model/ModelCenter.vue`、`src/views/Model/RiskInference.vue`、`src/views/Model/InferenceRecords.vue`

**需要新增：**
- mock 用户记录增加绑定场景（admin=全部；alice=network_security；bob=power_system；carol=geological_risk 等）。
- `ScenarioSelector` 增加按当前用户可见范围过滤选项的能力（`v-model` 不变）。

**需要修改：**
- `getScenarioList()` 对 USER 只返回绑定场景。
- 数据集/模型/推理/风险事件的按场景筛选，对 USER 在 mock 层强制限制在绑定场景内。
- 用户管理弹窗增加"分配场景"多选，创建/编辑用户时写入 `scenario_ids`。
- 场景中心：普通用户只渲染被分配场景卡片；无分配场景时给兜底引导页。

**实现要求：**
- 所有列表接口对 USER 做服务端（mock 层）二次强制过滤，不依赖前端参数。
- 绑定数据写入 `UserAccount.scenario_ids`。

**验收标准：**
- alice 登录场景中心仅见网络安全；直接改 URL 访问 `/scenarios/power_system/dashboard` 不显示电力数据（mock 层过滤）。
- 管理员创建用户时可勾选场景，保存后该用户可见对应场景。

**风险注意事项：**
- 安全边界在后端；mock 层过滤只是前端联调基线，注释声明。
- 绑定场景为空的普通用户必须有兜底提示，避免白屏。

---

## Task 007 首页（全局态势）HomeView（P0 · 依赖 005/008）

**目标：** 新增普通用户登录落地页"首页（全局态势）"——跨场景聚合驾驶舱（大号数字卡片、各场景风险等级分布、近期告警趋势、场景健康度排行），与"场景中心/业务场景概览"样式明显区分（需求 7.0 / 6.2）。

**涉及文件：**
- 新增：`src/views/Home/HomeView.vue`
- 修改：`src/router/index.ts`（`/home`）、`src/App.vue`（pageTitle / isHomePage）、`src/services/mockApi.ts`、`src/stores/situationStore.ts`
- 复用：`MetricCard`（Task 009 产出）、ECharts 图表、`RiskEventList`（Task 009 产出）

**需要新增：**
- mockApi `getGlobalCockpit()`：基于当前用户数据范围聚合（`{ total_events, by_scenario_level, recent_trend, health_ranking }`）。
- `situationStore.getGlobalCockpit()` action。

**需要修改：**
- `OverviewView`（/overview）内容并入 HomeView；`/overview` 保留为兼容重定向。
- 普通用户登录落地 `/home`；管理员访问 `/home` 重定向 `/scenarios`。

**实现要求：**
- 首页以"全局驾驶舱"风格呈现（大号数字卡、跨场景对比图表、健康度排行）。
- 普通用户数据仅本人范围。

**验收标准：**
- USER 登录落 `/home`，展示聚合指标与各场景分布，点击进入对应场景看板。
- ADMIN 访问 `/home` 被重定向 `/scenarios`。

**风险注意事项：**
- 需求 7.0 强调首页/场景中心/业务场景概览三者 UI 不得雷同——禁止直接复制 OverviewView 布局。

---

## Task 008 ECharts 图表组件封装（P0 基建 · 无前置）

**目标：** 引入 ECharts（需求 7.5 指定标准图表库），封装统一 Vue 包装器，支撑柱/饼/折线/雷达等场景看板。

**涉及文件：**
- 修改：`package.json`（新增 `echarts`）
- 新增：`src/components/charts/EChartBase.vue`、`BarChart.vue`、`PieChart.vue`、`LineChart.vue`、`RadarChart.vue`

**需要新增：**
- `EChartBase`：props `option`，自动 `init / dispose / setOption`，`ResizeObserver` 自适应，暗色主题。
- 各类型图表对 EChartBase 的薄封装（data 输入 → option 映射）。

**需要修改：**
- 现有手写 SVG 图表（`DonutChart`/`LineTrendChart`/`RankingList`）保留兼容，新看板统一走 ECharts。

**实现要求：**
- 不引入地图引擎 / WebSocket / 动画引擎（需求 7.5 约束）。
- 配色与现有 `style.css` 一致（#5ba6ff / #53e5c8 / #ff7b72 / #ffd166）。
- 推荐 `echarts/core` 按需引入（Tree-shaking），控制体积。

**验收标准：**
- 组件可独立渲染柱/饼/折线/雷达示例；窗口缩放图表自适应。
- `npm run build` 通过。

**风险注意事项：**
- ECharts 为唯一允许新增的第三方依赖；若业务反对则退化为手写 SVG，但柱/雷达实现成本显著上升。

---

## Task 009 四场景定制化看板（P0 · 依赖 008/006）

**目标：** 按需求第 7 节实现四场景差异化态势看板，统一"卡片 + 图表 + 列表"三件套与三区布局（顶部指标行 / 中部图表 / 底部推理结果 + 事件）。

**涉及文件：**
- 新增：`src/views/Scenario/ScenarioDashboardContainer.vue`、`NetworkScenarioDashboard.vue`、`PowerScenarioDashboard.vue`、`GeologicalScenarioDashboard.vue`、`FlightdeckScenarioDashboard.vue`
- 新增：`src/components/common/MetricCard.vue`、`RiskEventList.vue`、`EventTimeline.vue`、`ScenariosQuickNav.vue`（业务场景概览快捷入口，内嵌看板顶部，需求 7.0）
- 修改：`src/views/Model/ScenarioDashboard.vue`（改为容器转发）、`src/router/index.ts`（`/scenarios/:scenarioId/dashboard` 指向容器）、`src/services/mockApi.ts`、`src/stores/scenarioStore.ts`

**需要新增（各场景特有）：**
- 网络安全（需求 7.1）：核心指标 4 卡（总连接数/异常数/风险率/今日告警）；TOP 端口横向柱状图（按 `L4_DST_PORT`）；流量分布饼图（`TCP_FLAGS` 或包长区间五段）；风险事件列表（等级颜色 + 按等级筛选）。交互：点击端口预填推理表单、事件跳详情。
- 电力系统（需求 7.2）：电参量 4 卡（电压/电流/温度/频率）；设备健康度柱状图（按 `Component`）；IssueType 分布环形图；风险事件时间线（标注 IssueType/设备）。交互：点击设备筛选。
- 地质风险（需求 7.3）：区域风险统计 3 卡（高/中/低）；数据集风险占比堆叠柱状图；关键因子贡献条形图（坡度/TWI/距断层等）；风险事件时间线（标注触发因素）。交互：点数据集联动、按触发因素筛选。
- 航母甲板（需求 7.4）：KPI 4 卡（碰撞概率/最小间距/接近率/总航程）；间距变化折线（49 步）；方向角对比雷达图；风险事件列表（带碰撞概率）。热点图见 Task 014。

**需要修改：**
- mockApi `getScenarioDetail` 扩展为按场景返回看板聚合数据（端口统计/设备健康度/因子贡献/轨迹序列等）。
- `scenarioStore.fetchDashboard(scenarioId)`。

**实现要求：**
- 遵循三区布局；实现需求列出的主交互项。
- 无数据场景显示"暂无数据"空态，不得用虚构数据。

**验收标准：**
- 四个场景 `/scenarios/:id/dashboard` 各自呈现特有图表，数据为对应场景真实（mock）数据。
- 普通用户看板仅本人数据；管理员可看全平台。

**风险注意事项：**
- 航母甲板推理区 279 字段必须折叠/分步（结合 Task 010）。
- 图表数据来自 `raw_features` 聚合，字段缺失时图表空态降级。

---

## Task 010 风险研判页四场景扩展（P0 · 依赖 006）

**目标：** `RiskInference` 支持四场景（当前硬编码仅 network/power），并处理航母甲板 279 字段输入表单性能。

**涉及文件：**
- 修改：`src/views/Model/RiskInference.vue`、`src/services/mockApi.ts`
- 复用：`ScenarioSelector`、`scenarioStore`

**需要新增：**
- 可选：`src/components/common/FeatureFieldGroup.vue`（大字段按字段族分组/分步渲染：方向角族 / 间距族 / 统计量族 / 标签）。

**需要修改：**
- `scenarioOptions` 从 `scenarioStore` 可见场景注入（替换硬编码数组）。
- 保持"选场景 → 选数据集 → 已发布模型（默认推荐自动选中，可改选）→ 动态字段表单 → 推理"闭环（需求 6.3.2 / 6.7.4 / 6.7.5）。
- 大字段表单：默认值填充、按字段族折叠、展开查看全部。
- 推理结果区增加"查看风险事件详情"跳转（配合 Task 012）。

**实现要求：**
- 普通用户仅看到被绑定场景；无已发布模型时提示"暂无可用模型"（需求 6.7.4.7）。

**验收标准：**
- 四场景均可走通推理闭环；carrier 数据集可选、可填、可推理且无明显卡顿（折叠展开）。

**风险注意事项：**
- 279 个 DOM input 一次性渲染会卡顿——必须分组折叠或虚拟滚动。
- 航母甲板推理必须基于真实轨迹数据形态，前端只做输入与展示，不伪造结果来源（需求 1.1.5）。

---

## Task 011 数据集详情与数据内容预览（P0 · 依赖 003/006）

**目标：** 实现需求 2.4：数据集详情页展示前 100 条真实数据，表格分页（每页最多 50）、只读、标签列高亮；管理员全量可见、普通用户仅可见与已发布模型关联的数据集。

**涉及文件：**
- 新增：`src/views/Dataset/DatasetDetailView.vue`、`src/components/common/DataPreviewTable.vue`
- 修改：`src/views/Model/DatasetCenter.vue`（增加"数据预览/详情"入口）、`src/router/index.ts`（`/datasets/:datasetId`）、`src/services/mockApi.ts`、`src/types/security.ts`（DataPreview 类型，Task 001 已含）

**需要新增：**
- mockApi `getDatasetPreview(datasetId, { page, page_size })`：返回分页数据 + `label_field`；对 USER 仅允许与已发布模型关联且启用的数据集。
- `DataPreviewTable`：列用正式字段名，标签列按 `label_field` 高亮，el-table 分页。

**需要修改：**
- DatasetCenter 保留字段预览弹窗，另加"数据预览"入口跳详情页；详情页含"字段结构 + 数据内容预览"两个页签。

**实现要求：**
- 单次最大返回 100 条（需求 2.4.5 后端约束），前端每页最多 50。
- 只读，禁止在预览界面修改数据。

**验收标准：**
- 打开 KDDTrain 数据集详情，可分页浏览前 100 行，`class` 列高亮。
- 普通用户看不到未发布模型关联数据集的预览（mock 层拦截）。

**风险注意事项：**
- carrier 279 列极宽——预览表需横向滚动 + 冻结首列。
- 分页上限由后端强制，前端不做全量拉取。

---

## Task 012 风险事件详情页（P0 · 依赖 003）

**目标：** 实现需求 5.7：事件详情页展示基本信息 / 模型溯源 / 推理详情 / 输入特征 / 可解释性文本五大信息组，并补强 `description` 的场景化生成（需求 5.7.2）。

**涉及文件：**
- 新增：`src/views/Event/RiskEventDetailView.vue`
- 修改：`src/router/index.ts`（`/events/:eventId`）、`src/services/mockApi.ts`（`getRiskEventById` + 可解释性生成）、`src/stores/riskEventStore.ts`、`src/components/common/RiskEventList.vue`（点击跳详情）、`src/views/Model/InferenceRecords.vue`

**需要新增：**
- mockApi `getRiskEventById(eventId)`；风险事件 `description` 按场景模板生成（网络→异常端口/协议/重传；电力→设备/系统/IssueType；地质→坡度/TWI/距断层；甲板→最小间距/接近率/方向角偏差）。
- `riskEventStore.fetchDetail / updateStatus`。

**需要修改：**
- 事件列表项可点击进入详情；详情页展示五组信息 + 处置状态操作（待处置 → 处理中 → 已处置）。
- `raw_features` 以可读键值表展开；同时展示 `original_label` 与 `risk_score` 对照（需求 5.7.3.2）。

**实现要求：**
- 解释文本在事件生成时固化存储，前端不现场拼接、不因阈值修改重算（需求 5.7.3.1 / 5.7.3.4）。
- 普通用户仅能查看本人事件详情（mock 层校验，需求 5.2 访问控制）。

**验收标准：**
- 点击任意风险事件进入详情，五组信息齐全，解释文本含场景特征信息。
- 处置状态可更新并回写列表。

**风险注意事项：**
- 解释文本生成规则需与需求 5.7.2 示例对齐，避免技术术语堆砌（需求 5.7.3.3）。

---

## Task 013 风险阈值配置扩展（P0 · 依赖 001）

**目标：** 阈值配置支持地质风险场景（需求 5.4.1：每接入场景独立维护 medium/high、范围 [0,1]、high>medium、实时生效、变更记录），航母甲板仍为预留。

**涉及文件：**
- 修改：`src/views/Model/Settings.vue`、`src/services/mockApi.ts`（`thresholds` 增加 `geological_risk`）、`src/types/security.ts`（ThresholdConfig 已按 ScenarioId，无需改类型）

**需要新增：**
- 无独立新文件；Settings 的 `activeScenarios` 加入 `geological_risk`。

**需要修改：**
- mock `thresholds` 初始化加入 `geological_risk`（如 `{ medium: 0.5, high: 0.8 }`）。
- `executeInference` 风险等级计算已按 `thresholds[model.scenario_id]`，自动覆盖新场景，无需额外改动。

**实现要求：**
- 变更记录保留操作人/场景/时间/前后值（需求 5.4.1.5）。
- 修改实时生效，历史事件不重算（需求 5.4.1.4）。

**验收标准：**
- Settings 页可对 network / power / geological 三场景分别保存阈值，变更记录可见；航母甲板仍为预留卡。

**风险注意事项：**
- 阈值默认值以业务确认为准，代码仅给占位。

---

## Task 014 航母甲板热点图（P1 · 依赖 012）

**目标：** 实现需求 7.4.1：甲板底图上按 `fault_position_x/y` 渲染红色故障点，缩放自适应、悬停 tooltip、点击跳详情。

**涉及文件：**
- 新增：`src/components/Deck/DeckHeatMap.vue`、`src/assets/deck/carrier-deck.png`（占位底图，美工后替换）
- 修改：`src/views/Scenario/FlightdeckScenarioDashboard.vue`、`src/services/mockApi.ts`（carrier 风险事件生成时计算坐标）、`src/types/security.ts`（Task 001 已含字段）

**需要新增：**
- mock 中 carrier 风险事件按业务规则计算坐标（如碰撞时刻双机中点映射，基准宽度 1000px）。
- 红点定位：`实际坐标 = 原始坐标 × (当前渲染宽度 / 1000)`，`resize` 监听重算。

**需要修改：**
- Flightdeck 看板中部左侧嵌入 `DeckHeatMap`；红点 tooltip 显示风险评分 / 碰撞概率 / 发生时间。

**实现要求：**
- CSS `position: absolute` 定位 + 底图容器 `max-width: 100%`。
- 非 carrier 场景/坐标为空的事件不渲染红点（需求 7.4.1 规则 3）。

**验收标准：**
- 底图上红点位置与事件坐标一致，窗口缩放红点不偏移；悬停有 tooltip，点击跳事件详情。

**风险注意事项：**
- 底图需美工提供；先用纯色占位 + 网格坐标系开发，避免阻塞。
- 坐标基准 1000px 需与后端约定一致。

---

## Task 015 场景前端轻量算法（P1 · 依赖 008）

**目标：** 实现需求第 8 节场景轻量算法，作为贝叶斯二分类前/后的辅助判断层，驱动看板附加指标。

**涉及文件：**
- 新增：`src/services/lightAlgorithms.ts`
- 修改：四场景看板组件、`src/services/mockApi.ts`（提供算法所需基线/历史数据）

**需要新增：**
- 网络安全：`zScoreAnomaly(windowSeries)`、`portDeviationScore(currentProfile, baseline)`
- 电力系统：`deviceHealthScore(overrunRate, offset)`、`powerRiskScore(packetLoss, anomalies)`
- 地质风险：`susceptibilityScore(terrainFactors)`、`regionRiskRank(regions)`
- 航母甲板：`collisionRiskScore(minDist, closureRate)`、`trajectoryDeviationScore(trajectory, baseline)`

**需要修改：**
- 看板调用算法填充附加卡片/图表（如甲板 KPI 卡碰撞风险分、地质易发性评分）。

**实现要求：**
- 纯 TS 函数、无副作用、输入输出有类型、可单测。
- 结果标注"辅助研判"，不替代、不与后端二分类结果冲突（并列展示）。

**验收标准：**
- 每算法对样例输入输出合理数值并在对应看板可见；不依赖后端。

**风险注意事项：**
- 算法为演示级，参数口径需业务确认。

---

## Task 016 推理记录/态势分析/报告等页面场景扩充（收尾 · 依赖 006）

**目标：** 消除全局硬编码 2 场景残留，全部页面支持四场景与角色数据范围。

**涉及文件：**
- 修改：`src/views/Model/InferenceRecords.vue`、`src/views/Model/SituationAnalysis.vue`、`src/views/Model/ReportCenter.vue`、`src/views/Login.vue`（副标题/欢迎语提及四场景）、`src/App.vue`（pageTitle 补 /home、/datasets/:id、/events/:id）

**需要新增：**
- 无独立新文件；场景选项统一从 `scenarioStore` 注入。

**需要修改：**
- 推理记录场景筛选、态势分析场景集合、报告生成场景下拉均扩展为四场景。
- 所有 `scenarioLabel` 映射补充 `geological_risk`。

**实现要求：**
- 页面不再出现硬编码场景数组（用 `grep` 校验）。
- 普通用户报告仅本人数据、管理员可全平台/指定用户（需求 6.8.5，保持现状）。

**验收标准：**
- 四场景数据在记录/态势/报告页一致呈现；无硬编码场景数组残留。

**风险注意事项：**
- mock 中 `situation` 对 carrier 的空数组处理要保证图表不出现 NaN。

---

## Task 017 全量验收与回归（P0 · 依赖全部）

**目标：** V3.0 前端改造整体验收，保证管理员与普通用户双闭环贯通（需求 6.3）。

**涉及文件：**
- 全量检查：`npm run build`、路由走查、角色走查（按结果修补，不强制造文件）

**需要新增：**
- 无。

**需要修改：**
- 按走查结果修补。

**实现要求：**
- 管理员闭环（需求 6.3.1）：登录 → 场景中心 → 用户管理（含场景绑定）→ 选场景 → 数据集（含数据预览）→ 算法训练 → DRAFT → 发布 → 设默认 → 阈值 → 全平台态势。
- 普通用户闭环（需求 6.3.2）：登录 → 首页 → 场景看板 → 数据集 → 已发布模型（默认推荐）→ 推理 → 事件详情 → 本人记录/态势。
- 四场景看板图表与交互可用；航母热点图如为 P1 未做则明确标注状态。

**验收标准：**
- `npm run build` 零错误零告警。
- 双闭环全链路演示通过；四场景均为已接入，不使用虚构数据。
- 待后端接口（登录 / 态势）明确演示模式与联调模式的切换点。

**风险注意事项：**
- 依赖后端未提供接口（登录 / 态势）时，联调以 mock 为准，标注切换点。
