# 网络安全 · 场景管理员首页 代码质量重构报告（R1）

- **唯一改动文件**：`frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue`
- **路由链路**：`#/scenarios/1/dashboard` → `DashboardHomeView.vue` →（`SCENARIO_ADMIN`）`AdminProfilePage.vue` → `sections/ProfileNetwork.vue`
- **约束**：只改"怎么算 / 怎么组织"，不改任何渲染结果；不碰冻结共享面。
- **门控**：`cd frontend; npx vue-tsc --noEmit -p tsconfig.app.json` → 原始输出为空，`EXIT=0`
- **行数**：482 → 484（`git diff --numstat` = `73 insertions / 71 deletions`）
- **基线**：`HEAD=2a3c029`，分支 `0918重构`

---

## 1. 改动摘要

| # | 改动 | 一句话说明 |
|---|---|---|
| 1 | 删 `rowsOrEmpty<T>()` 及 `caliber` / `dimensionCoverage` / `modeling` 三个包装 computed | 三个字段在 `ProfileBase` / `NetworkProfile` 里是**必填**、后端也**无条件下发**，兜底恒不可达；改为直接读 `props.data.*` |
| 2 | 删 `modelingReady`（连带 S2 `models` 的 `&&` 门控、S3 脚注 `<p v-if="modelingReady">`） | `Array.isArray(props.data.modeling)` 恒真；留着它等于给"已发布 x / 共 y"和"数据白躺"多留一套永远为假的真假口径 |
| 3 | 删 3 个已无引用的类型导入 `CaliberRow` / `DimensionCoverage` / `ModelingStat` | 唯一消费者是 `rowsOrEmpty<T>`，随改动 1 一起消失（三个类型本身仍在 `dashboardApi.ts` 里，属 API 契约，未动） |
| 4 | 新增 8 个具名常量：`LIST_SEPARATOR` / `DEVIATION_DIGITS` / `DEVIATION_BASELINE` / `COVERAGE_SINGLE_SOURCE` / `MEMBER_PAGE_SIZE` / `ROLE_SCENARIO_ADMIN` / `ROLE_SCENARIO_USER` / `ACCOUNT_STATUS_ACTIVE` | 原先散落的 `'、'`、`toFixed(2)`、`> 1`、`=== 1`、`page_size: 200`、`'SCENARIO_ADMIN'`、`'active'` 各自出现 1–4 次，现单点定义；模板里的 `join('、')` 同步改用 `join(LIST_SEPARATOR)` |
| 5 | `deviationCell` 删掉 `Number(value)` / `const num` 中转 | 入参类型本就是 `number \| null \| undefined`（`CaliberRow.deviation`），`Number()` 是空转；`toFixed` 直接作用于入参，输出逐字节相同 |
| 6 | 抽出 `caliberSplitSub` computed | 原来 S1 第 4 格的 `sub` 内联了三层嵌套三元，现独立具名、带口径注释 |
| 7 | `displayNames` 改为"先数重名、再据此生成展示名"两遍自洽遍历 | 去掉 `names[index]` 这条"原始名数组与 `datasets` 下标对齐"的隐式不变量 |
| 8 | 头部注释补一段"扩展字段不做兜底"的裁定说明 | 把改动 1–2 的判定依据（类型 + 后端行号）写在被删代码的位置，避免下一位读者再把兜底加回来 |
| 9 | 抽出 `activityTotal` computed，删 `Number(point.total ?? 0)` | `activity_trend[].total` 的类型就是 `number`（`dashboardApi.ts:402`），`Number()` / `?? 0` 是空转；顺手把求和从 KPI 计算里提出来具名，与 R4 页保持同一写法 |

**净效果**：删除的全部是"恒不可达兜底 + 恒真门控 + 空转转换 + 无引用符号"；新增的是 8 个具名常量、2 个具名 computed（`caliberSplitSub` / `activityTotal`）与相应注释。行数净 +2（73 增 / 71 删）；符号数：删 5（`rowsOrEmpty`、`modelingReady`、`caliber`/`dimensionCoverage`/`modeling`）、加 3（常量组、`caliberSplitSub`、`activityTotal`）。

---

## 2. 逐项审查结论

### A. 弃用写法（逐项经查无问题）

| 检查项 | 结论 | 检查方式与证据 |
|---|---|---|
| Options API 残留（`export default` / `data()` / `methods:` / `computed: {}` / `this.` / `mounted()` / `beforeDestroy` / `filters:`） | **经查无问题** | 本文件 grep `export default\|this\.\|beforeDestroy\|methods:\|filters` = 0 命中；文件为纯 `<script setup lang="ts">`，无组件对象 |
| Vue 2 模板语法（`.sync` / `slot-scope` / `v-on.native` / `$listeners` / `Vue.set`） | **经查无问题** | grep `\.sync\|\$listeners\|Vue\.set\|v-on\.native\|slot-scope` = 0 命中；插槽用 Vue 3 的 `<template #label_field="{ row }">` |
| 深层选择器弃用写法（`::v-deep` / `/deep/` / `>>>`） | **经查无问题** | 本文件**没有** `<style>` 块（grep `<style` = 0 命中），样式全部走 `dash.css` 的 `d-*` 类 |
| `console.*` / `debugger` / `TODO` / `FIXME` / `@ts-ignore` / `@ts-expect-error` | **经查无问题** | grep = 0 命中；无被压制的类型错误 |
| `any` / `as unknown` | **经查无问题** | grep `: any\|as any\|any\[\]\|<any>\|as unknown` = 0 命中。全文只有 2 处含 `any` 子串，均为数据集名 `net_flow_company_v1`（注释第 163 行、`VISIBILITY_TEXT` 键 `company` 第 186 行） |
| 非空断言 `!` | **经查无问题** | grep `!\.\|!)\|!,\|!;` = 0 命中；`strict: true` 下无逃逸 |
| Element Plus 残留（`el-*` / 全局注册组件） | **经查无问题** | grep `el-` 仅 1 处命中，是 `DashBars` 的 `:label-width` 属性子串（第 456 行），非组件 |
| `recent_events`（执行端字段） | **经查无问题（有意不渲染）** | 仅出现在头部注释的设计说明（第 12 行）；代码与模板 0 引用。管理端不渲染派活清单是本页定位 |
| 旧可视化组件（`DashDonut` / `DashColumns` / `DashRadar` 等已下线件） | **经查无问题** | grep = 0 命中；本页只用 `DashKpis` / `DashCard` / `DashBars` / `DashFunnel` / `DashLine` / `DashRows` / `DashTable`，均为现行组件 |
| 前端按标签字段猜正类（旧版 `is_risk_label` 过滤） | **经查无问题** | 代码 0 引用，仅剩注释第 300 行的历史说明；S2 遍历全部 `datasets` 并用 `caliber_registered === false` 打「未登记风险口径」标签 |
| 已废弃的 `modelVersionApi` 自行归集模型数 | **经查无问题** | 本文件 0 引用；模型数一律取画像下发的 `modeling`（后端按 dataset 聚合），只有一套口径 |

### B. 残留死代码（4 项删除 + 无死字段结论）

1. **`rowsOrEmpty<T>()`** —— 删除。本文件 0 引用，全 `frontend/src` 亦 0 引用（见 §4）。
2. **`modelingReady`** —— 删除。本文件 0 引用，全 `frontend/src` 亦 0 引用（另三页由 R2–R4 同步清理）。
3. **`caliber` / `dimensionCoverage` / `modeling` 三个包装 computed** —— 删除。使用点改为 `props.data.caliber_matrix` / `props.data.dimension_coverage` / `props.data.modeling`。
4. **`CaliberRow` / `DimensionCoverage` / `ModelingStat` 类型导入** —— 删除（唯一消费者是 `rowsOrEmpty<T>`）。
5. **行对象死字段**：**经查无死字段**。逐一核对"模板列 key + `rowKey` + 插槽用键"是否覆盖每个键：
   - D1 `caliberRows` 9 键 = 8 个 `caliberColumns.key`（`name`/`label_field`/`positive_labels`/`record_count`/`risk_count`/`risk_rate`/`deviation`/`registered`）+ `rowKey="logical_id"`；
   - D2 `dimensionRows` 5 键 = 4 个 `dimensionColumns.key`（`dimension`/`datasets`/`coverage`/`coverage_status`）+ `rowKey="key"`；
   - S2 `datasetRows` 9 键 = 8 个 `datasetColumns.key` + `rowKey="logical_id"` + 插槽条件用的 `unregistered`（非列 key，只被 `#label_field` 读）；
   - 三个列定义数组（`caliberColumns` / `dimensionColumns` / `datasetColumns`）自身无未被行对象填充的 key。
6. **未使用的导入 / 局部变量 / 参数**：**经查无问题**。`tsconfig.app.json` 开启 `noUnusedLocals` + `noUnusedParameters` + `strict`，`vue-tsc` `EXIT=0` ⇒ 编译期已证明零未使用符号。
7. **空 `<style>`、空 computed、恒真 / 恒假分支**：**经查无问题**（无 `<style>`；所有 computed 都有模板或其它 computed 消费；仅存的 `stat ? … : '—'` 是 Map 查空兜底，见 §3 与 D-6）。
8. **注释里的历史包袱**：保留（`recent_events`、`is_risk_label` 两处说明解释了"为什么不这么做"），不属死代码。

### C. 不必要的复杂度（逐项处理结论）

| # | 复杂度 | 处理 |
|---|---|---|
| C-1 | 三层间接：`rowsOrEmpty` → `caliber`/`dimensionCoverage`/`modeling` → 使用点 | **已压成一层** `props.data.*`，删 4 个符号 |
| C-2 | 魔法值散落：`'、'`（3 处）、`toFixed(2)`、`> 1`、`=== 1`、`page_size: 200`、`'SCENARIO_ADMIN'`/`'SCENARIO_USER'`、`'active'` | **已提为 8 个具名常量**（见 §1 改动 4）；模板里的分隔符同步走常量 |
| C-3 | `deviationCell` 里 `const num = Number(value)` 中转后再 `Number.isFinite(num)` | **已删**：入参类型即 `number \| null \| undefined`，直接判空 + `toFixed`；输出不变 |
| C-4 | S1 第 4 格 `sub` 的三层嵌套三元 | **已抽出**为 `caliberSplitSub` computed，语义与口径说明独立 |
| C-5 | `displayNames` 维护"原始名数组 + `datasets` 下标对齐"隐式不变量 | **已改为**两遍自洽遍历（第一遍计数、第二遍生成），不再有下标耦合 |
| C-6 | `displayNames` 与 `datasetRows` 各遍历一次 `datasets` | **有意保留，不合并**：`datasets` 规模 ≤3（本场景 2），合并需要先造一份"展示名 + 模型统计"基底 Map/数组，多一层中间结构却省不下一次有效遍历；两处各自语义单一，读起来比"基底 + 派生"更直白 |
| C-7 | `memberRows` 里三次 `filter` | **有意保留**：列表规模是个位数；三个计数本就是不同维度（角色 ×2、状态 ×1），声明式写法比手写单循环更易读 |
| C-8 | `modelingByDataset` 是只被 `datasetRows` 用一次的 computed | **有意保留**：它是 O(1) 查表；换成每行 `modeling.find(...)` 会变成 O(n²)，且"先建索引再逐行取"的意图更清楚 |
| C-9 | S4 活动量对 `total: number` 仍写 `Number(point.total ?? 0)`，且求和埋在 `runtimeKpis` 里 | **已处理**：抽 `activityTotal` computed 并直接 `reduce((sum, point) => sum + point.total, 0)`；去掉 `Number()` / `?? 0` 两处空转，`runtime === null` 时仍返回 `null`（D-1 的渲染问题另案） |
| C-10 | S3 脚注 `<p>` / `<span>` 的内联样式在四页重复 | **不在本页改**（改动 `dash.css` 属共享面）→ 见 §7.4 与 R4 报告的 `d-note` 提案 |
| C-11 | S4 运行态 + S5 成员的取数与派生逻辑在四页重复（本页 94 行） | **不在本页改**（需新建共享 composable）→ 见 §7 提案 |

### D. 正确性隐患（5 项"经查无问题"，4 项真实隐患只报不改）

| # | 项 | 结论 | 依据 |
|---|---|---|---|
| D-1 | **`/workspace` 请求失败时，S4 两格误报 `0`**（真实缺陷，**未修**） | `待处置积压` 传 `value: null`、`近 10 天活动` 传 `value: null`，而 `DashKpis` 对**非 `raw`** 项走 `fmtInt(value)`，`fmtInt(null)` = `Number(null)=0` → 渲染 `0条` / `0次`，不是 `—`。只有 `已处置率`（`raw: true`）会正确落到 `—` | `DashKpis.vue:27` `item.raw ? (item.value ?? '—') : fmtInt(item.value)`；`dashFormat.ts:7-11` `fmtInt`；`Number(null) === 0` |
| D-2 | **SUPER_ADMIN 视角 S5 多出一行假"未纳入统计"**（真实缺陷，**未修**） | 本页 `getUserList({ page_size: 200 })` **没传** `scenario_id`，只在前端过滤；`memberTotal` 取的是后端 `total`。`SCENARIO_ADMIN` 走后端强制过滤（`user_service.py:106-107`）⇒ `total=5`、`items=5`，不触发；但 `DashboardHomeView` 对**带场景上下文的 SUPER_ADMIN** 同样渲染 `AdminProfilePage`，此时 `total=21`（全平台）而过滤后 5 人 ⇒ 多出 `未纳入统计 16 人（超出单页 200 条）` | `user_service.py:106-107`（角色强制过滤）、`:120-121`（显式参数过滤）、`:124`（200 硬上限）、`:129/144`（权威 `total`）；契约 §7 要求 `getUserList({ scenario_id, page_size: 200 })`；`ProfileGeological.vue:70` 已按契约写法实现 |
| D-3 | **S1 第 4 格在 `caliber_matrix` 为空时渲染 `0套` 而非 `—套`**（潜在缺陷，**未修**，当前不可达） | `caliberLanguages` 空矩阵时返回 `null`，代码注释写的是"显示 `—`"，但该 KPI 没有 `raw: true`，`fmtInt(null)` 同样得到 `0` ⇒ 注释的意图**未达成**。当前网络场景 `caliber_matrix` 恒为 3 行（后端 `_network_caliber_matrix` 无条件下发），故不可达 | 同 D-1 的 `DashKpis` 证据；`dashboard_service.py:1486` |
| D-4 | 快速切换场景时的响应竞态（真实隐患，**未修**） | `watch(() => props.data.scenario_id, loadAll)` 没有请求令牌 / `AbortController`：A 场景的慢响应可能在切到 B 场景后覆盖 `runtime` / `members`，出现短暂的跨场景数据。修法要引入令牌或取消语义，超出"只改怎么算"的范围 | 本文件 `loadAll`（第 84-99 行）；无 `onUnmounted` 清理需求（本页无定时器 / 订阅） |
| D-5 | 空矩阵时 `sub` 文案"后端未下发风险口径矩阵"不准确（**未修**） | 该分支真正的触发条件是"矩阵为空数组"而非"未下发"，文案会误导排查方向。当前 `SHOW_DASH_HINTS=false` ⇒ `sub` **根本不渲染**，影响为 0 | `DashKpis.vue:30` `v-if="SHOW_DASH_HINTS && item.sub"` |
| D-6 | S2 `models` 的 Map 查空兜底 | **保留（真兜底，非恒真门控）**：`modelingByDataset.get(logical_id)` 类型是 `ModelingStat \| undefined`，类型层面不排除查空；且它给 `—` 而不是伪造 `已发布 0 / 共 0`，符合"取不到就不报数" | `dashboardApi.ts:153` 只保证 `modeling` 数组存在，不保证键存在 |
| D-7 | 运行态 / 成员请求失败时的降级 | **经查无问题**：`runtime === null` ⇒ 漏斗与折线给空集、`summary` 给 `null`；`members === null` ⇒ 渲染"成员数据未取到"（与"0 人"区分）。`Promise.allSettled` 保证两者互不阻塞 | 本文件 `loadAll`；`SHOW_DASH_HINTS = false` 只影响 `sub`/`source` 提示文字，不影响上述降级 |
| D-8 | `已处置率` 分母为 0 | **经查无问题**：`item && item.total ? fmtPercent(resolved / total) : null` 且 `raw: true` ⇒ `null` 正确渲染 `—`，不会出现 `0.0%` 假数 | `DashKpis.vue:27` 的 `?? '—'` |
| D-9 | XSS / 注入面 | **经查无问题**：无 `v-html`、无 `innerHTML`、无 `eval`；所有插值都是文本节点；数据集名 / 逻辑 ID 等外部字符串只经 `{{ }}` 输出 | grep + 模板逐行核对 |

---

## 3. 门控 / 兜底可达性裁定

| 可疑点 | 裁定 | 证据（类型 + 后端 + 运行时） |
|---|---|---|
| `rowsOrEmpty`（`?? []`）三处 | **死（不可达）** | **类型**：`ProfileBase.modeling: ModelingStat[]`（`dashboardApi.ts:153`）、`NetworkProfile.caliber_matrix: CaliberRow[]`（`:208`）、`dimension_coverage: DimensionCoverage[]`（`:210`）全部必填非可选。**后端**：`get_profile` 在 `dashboard_service.py:1386` 无条件写 `"modeling"`；`_network_profile` 在 `:1486` / `:1488` 无条件写 `"caliber_matrix"` / `"dimension_coverage"`；`_modeling_stats`（`:1405`）无数据集时返回 `[]` 而非 `None`。**运行时**：D1 实渲染 3 行、D2 5 行、S3 柱 5/12/0 ⇒ 三个数组实际都在场 |
| `modelingReady`（`Array.isArray`） | **死（恒真）** | 同上。运行时反证：S1 第 4 格实际渲染出数字（不是 `—`），S3 脚注实际渲染出"数据白躺 1 份"，说明它永远走 true 侧 |
| KPI-4 `sub` 的 `'后端未下发风险口径矩阵'` 分支 | **死** | 同 `modelingReady`。附加：`SHOW_DASH_HINTS = false` 使 `sub` 当前**根本不渲染**，删除它不可能改变任何可见输出 |
| S2 `models: modelingReady.value && stat ? … : '—'` | 前半 **死**、后半 **活** | 前半同 `modelingReady`（已删）；后半 `stat` 是 Map 查空，类型上确为 `ModelingStat \| undefined` ⇒ **保留** |
| S3 脚注 `<p v-if="modelingReady">` | **死（恒真）** | 同 `modelingReady`；脚注内容（白躺标签 / 名单 / 已发布合计）当前实际渲染，删掉门控后渲染结果逐字节不变 |
| `trendPoints` / `funnelItems` 的 `?? []` | **活（保留）** | `runtime.value?.activity_trend` / `?.status_funnel` 在运行态请求失败（`runtime === null`）时确实为 `undefined`，此时折线拿到空点集、漏斗拿到空列表 —— 真实可达的降级路径 |
| `summary` 的 `runtime.value?.summary ?? null` | **活（保留）** | 同上，请求失败时确实为 `null` |
| S5 `members === null` 分支 | **活（保留）** | `getUserList` 被 reject 时 `members = null` ⇒ 渲染"成员数据未取到"，与"确实 0 人"区分开 |
| `deviationCell` 的 `Number.isFinite` 判断 | **活（保留）** | `CaliberRow.deviation` 为 `number \| null`，判空必要；`Number.isFinite` 一并挡住异常数值，避免渲染成 `×NaN` |

> 裁定原则：**类型声明 + 后端下发路径 + 上一轮已验收的实际渲染** 三者同向才算"死"；只凭"看起来像兜底"一律判活。

---

## 4. 删除证据（零引用）

`grep` 范围：①本文件；②`frontend/src` 全量。

| 被删符号 | 本文件命中 | `frontend/src` 命中 | 说明 |
|---|---|---|---|
| `rowsOrEmpty` | **0** | **0** | 全前端已无此模式 |
| `modelingReady` | **0** | **0** | 另三页由 R2–R4 同步清理，全前端已无残留 |
| `caliber` / `dimensionCoverage` / `modeling`（本文件局部 computed） | **0** | n/a（局部符号） | 使用点已改为 `props.data.*` |
| `CaliberRow` / `DimensionCoverage` / `ModelingStat`（导入） | **0** | 6 处，**全部在 `dashboardApi.ts` 的定义/引用行**（`:62` `:153` `:157` `:183` `:208` `:210`） | 本文件不再导入；三个类型仍属 API 契约，未被删除 |
| `is_risk_label`（代码引用） | **0**（仅注释第 300 行） | — | 仅历史说明文字 |
| `recent_events`（代码引用） | **0**（仅注释第 12 行） | — | 仅历史说明文字 |
| `getModelVersionList` / `modelVersionApi` | **0** | — | 模型数统一取画像 `modeling` |
| `console.` / `TODO` / `FIXME` / `@ts-ignore` / `any` / 非空断言 | **0** | — | 见 §2 A |

**行数变化**：`HEAD:…ProfileNetwork.vue` = 482 行 → 工作区 = 484 行；`git diff --numstat` = `73 insertions / 71 deletions`（净 +2 行）。删除的 71 行全部是死兜底 / 恒真门控 / 空转转换 / 无引用符号；新增的 73 行里含 8 个具名常量、2 个具名 computed（`caliberSplitSub` / `activityTotal`）及说明"为什么删"的注释。

---

## 5. 函数清单

> 逐个符号：算什么 + 后端字段来源。

### 请求与状态

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `props` | `defineProps<{ data: NetworkProfile }>` | 画像数据由 `AdminProfilePage.vue` 用 `networkData` 收窄后传入 | `GET /dashboard/scenarios/{id}/profile`；**契约要求签名不变（未动）** |
| `runtime` | `ref<WorkspaceBase \| null>` | 运行态；本页不校验 `scenario_key`（只消费四场景同构的 `summary` / `activity_trend`） | `GET /dashboard/scenarios/{id}/workspace`（`getScenarioWorkspace`） |
| `members` | `ref<UserAccount[] \| null>` | 场景成员；`null` = 未取到（≠ 0 人） | `GET /users?page_size=200`（`getUserList`） |
| `memberTotal` | `ref<number \| null>` | `/users` 命中的账号总数；与单页条数不等时提示被分页截断 | `GET /users` 响应的 `total`（`user_service.py:129/144`） |
| `loadAll` | `async () => void` | 两接口 `Promise.allSettled` 并行 + 各自静默降级；成员在本地按 `scenario_id` 过滤 | 同上两接口 |
| `watch(() => props.data.scenario_id, loadAll)` | `watch` | 切换场景时重拉 | — |
| `onMounted(loadAll)` | 生命周期 | 首屏拉取 | — |
| `summary` | computed | `runtime.summary` | `EventSummary`（`pending`/`total`/`resolved`/`status_funnel`/…，`dashboardApi.ts:364`） |

### 口径常量（本次新增）

| 符号 | 值 | 用途 |
|---|---|---|
| `LIST_SEPARATOR` | `'、'` | D1 正类取值、D2 覆盖数据集、S3 白躺名单 + 模板 |
| `DEVIATION_DIGITS` | `2` | D1 `deviationCell` 的 `toFixed` 位数 |
| `DEVIATION_BASELINE` | `1` | D1 偏离色调分界（`>1` 高 / `<1` 低 / `=1` 持平） |
| `COVERAGE_SINGLE_SOURCE` | `1` | D2 覆盖状态判据（"仅一份数据支撑"） |
| `MEMBER_PAGE_SIZE` | `200` | `getUserList` 单页上限 + 溢出提示文案；后端硬上限见 `user_service.py:124` |
| `ROLE_SCENARIO_ADMIN` / `ROLE_SCENARIO_USER` | `'SCENARIO_ADMIN'` / `'SCENARIO_USER'` | S5 角色分组（`types/security.ts:376`） |
| `ACCOUNT_STATUS_ACTIVE` | `'active'` | S5"已禁用"判据（`types/security.ts:385`） |

### 判据与展示名

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `caliberLanguages` | computed `number \| null` | 全部数据集用了几种**不同的标签字段名**（口径分裂度） | `NetworkProfile.caliber_matrix[].label_field`（`_network_caliber_matrix`，`dashboard_service.py:1486`） |
| `caliberSplitSub` | computed `string` | KPI-4 的口径副标题（几套风险语言 / 未下发） | 同上；`SHOW_DASH_HINTS=false` 当前不渲染 |
| `displayNames` | computed `Map<string,string>` | `logical_id` → 去重展示名；重名补 `（logical_id）` | `DatasetStat.name`（后端 `dataset_display_name_of` 取上传文件名；本场景 `nf_unsw_nb15_v2` 与 `net_flow_company_v1` 同名） |
| `nameOf(logicalId, fallback?)` | 函数 | 展示名查表：去重表 → 行内 `name` → `logical_id` | `DatasetStat.name` / `CaliberRow.name` |
| `VISIBILITY_TEXT` / `visibilityText` | 常量表 + 函数 | 可见性中文（平台 / 公司 / 个人） | `DatasetStat.visibility` |
| `modelingByDataset` | computed `Map<string,ModelingStat>` | `logical_id` → 模型版本统计，供 S2「已发布 x / 共 y」 | `ProfileBase.modeling`（`_modeling_stats`，`dashboard_service.py:1405`） |

### S1 / D1 / D2 / S2

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `overviewKpis` | computed `KpiItem[]` | S1 四格：有效数据集数 / 有效样本总量 / 统一风险占比 / 风险口径分裂度 | `dataset_count`、`sample_count`、`risk_rate`（`fmtPercent`）、`dataset_file_count`（作 `sub`）、`caliberLanguages` |
| `caliberColumns` / `caliberRows` | `DashColumn[]` / computed | D1 数据集风险口径可比性矩阵（8 列，`rowKey=logical_id`） | `NetworkProfile.caliber_matrix`（`CaliberRow`：`logical_id`/`name`/`label_field`/`positive_labels`/`record_count`/`risk_count`/`risk_rate`/`deviation`/`registered`） |
| `deviationCell(value)` | `(number\|null\|undefined) => DashCell` | 偏离倍数单元格：`×2.00` 且按 >1 / <1 / =1 给 up / down / muted 色调，无基准给 `—` | `CaliberRow.deviation` |
| `dimensionColumns` / `dimensionRows` | `DashColumn[]` / computed | D2 流量统计维度覆盖矩阵（4 列，`rowKey=key`） | `NetworkProfile.dimension_coverage`（`DimensionCoverage`：`key`/`dimension`/`datasets`） |
| `coverageCell(count)` | `(number) => DashCell` | 覆盖状态：全覆盖（ok）/ 仅一份数据支撑（warn）/ 部分覆盖（muted） | `DimensionCoverage.datasets.length` 与 `ProfileBase.dataset_file_count` |
| `datasetColumns` / `datasetRows` | `DashColumn[]` / computed | S2 数据集资产明细（8 列 + 插槽标签，`rowKey=logical_id`） | `ProfileBase.datasets`（`DatasetStat`：`record_count`/`label_field`/`risk_rate`/`attribute_count`/`visibility`/`version`/`caliber_registered`）+ `modelingByDataset` |

### S3 / S4 / S5

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `modelingBars` | computed | 每数据集一根柱 = 模型版本总数 | `ModelingStat.total` |
| `whiteLying` | computed `string[]` | 白躺数据集展示名列表（`total === 0`） | `ModelingStat.total` |
| `modelTotals` | computed `{published, draft}` | 已发布 / 草稿合计 | `ModelingStat.published` / `.draft` |
| `activityTotal` | computed `number \| null` | 近 10 天活动量 = `activity_trend[].total` 之和；运行态缺失时 `null` | `WorkspaceBase.activity_trend`（`dashboardApi.ts:402`） |
| `runtimeKpis` | computed `KpiItem[]` | S4 三格：待处置积压 / 已处置率（`resolved ÷ total`，`fmtPercent`）/ 近 10 天活动（取 `activityTotal`） | `EventSummary.pending` / `.resolved` / `.total` + `activityTotal` |
| `funnelItems` | computed | 处置漏斗（待处置 → 处理中 → 已处置） | `EventSummary.status_funnel`（`dashboardApi.ts:379`） |
| `trendPoints` | computed | 折线点：`label = date.slice(5)`、`value = total`、`value2 = risk` | `WorkspaceBase.activity_trend`（`:402`） |
| `memberRows` | computed | S5 行：场景管理员 / 场景用户 / 合计（+ 有禁用时补"已禁用" + 被分页截断时补"未纳入统计"） | `UserAccount.role` / `.status` + `/users` 的 `total` |

**无 `ref` 之外的响应式状态、无 `provide/inject`、无 `emit`、无 `expose`、无生命周期钩子（仅 `onMounted`）、无定时器（故无需 `onUnmounted`）。**

---

## 6. 行为不变证明

### 6.1 类型检查（门控）

```
$ cd frontend; npx vue-tsc --noEmit -p tsconfig.app.json
<空>
EXIT=0
```

- 原始输出：**逐字节为空**（无任何 error / warning 行）。
- 退出码：`EXIT=0`。
- 说明：本次共跑四次（重构前基线一次、重构主体后一次、注释精简后一次、`activityTotal` 抽取后再一次），四次结果相同；`tsconfig.app.json` 开着 `strict` + `noUnusedLocals` + `noUnusedParameters`，因此 `EXIT=0` 同时证明"无未使用导入 / 局部变量 / 参数"（即 §4 的删除全部安全）。
- 未执行（按禁令）：`npm run build`、`vite build`、`npx vite`、任何服务启停、`pytest`、任何写 `dist` / `node_modules/.vite` / `*.tsbuildinfo` / DB 的命令。

### 6.2 行数

| | 行数 |
|---|---|
| `HEAD:frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue` | 482 |
| 工作区（重构后） | 484 |
| `git diff --numstat` | `73 insertions(+) / 71 deletions(-)` |

### 6.3 渲染不变逐项对照

| 位置 | 渲染要素 | 改前 | 改后 | 判定 |
|---|---|---|---|---|
| S1 | 卡片标题 / 顺序 | 无标题 KPI 行，4 格 | 同 | 不变（模板未改） |
| S1 | KPI 文案 + 单位 | 有效数据集数·个 / 有效样本总量·条 / 统一风险占比·% / 风险口径分裂度·套 | 同 | 不变（`label`/`unit`/`tone`/`raw` 一字未改） |
| S1 | KPI-4 数值 | `caliberLanguages`（矩阵里去重后的标签字段数） | 同 | 不变（包装 computed 只做 `?? []`，恒不生效） |
| S1 | KPI-4 `sub` | 三元的 true 侧文案 | 同一文案 | 不变（且 `SHOW_DASH_HINTS=false` 当前不渲染） |
| D1 | 卡片标题 / `source` | 数据集风险口径可比性矩阵 / 原文 | 同 | 不变 |
| D1 | 列名 + 顺序 + 对齐 | 数据集·标签字段·正类取值·样本量·风险样本·风险占比·与场景合并口径偏离·登记状态 | 同 | 不变（`caliberColumns` 未改） |
| D1 | 正类取值拼接 | `positives.join('、')`，空则 `未登记` | `positives.join(LIST_SEPARATOR)` | 不变（`LIST_SEPARATOR === '、'`） |
| D1 | 偏离单元格 | `×` + `toFixed(2)`；>1 up / <1 down / =1 muted / null `—` | 同 | 不变（仅去掉 `Number()` 中转，`deviation` 本就是 `number \| null`） |
| D1 | 登记状态标签 | 已登记(ok) / 未登记·不产事件(warn) | 同 | 不变 |
| D2 | 卡片标题 / `source` / 列名顺序 | 流量统计维度覆盖矩阵 / 维度·覆盖数据集·覆盖数·覆盖状态 | 同 | 不变（`dimensionColumns` 未改） |
| D2 | 覆盖数据集拼接 | `ids.map(nameOf).join('、')` | 同（常量分隔符） | 不变 |
| D2 | 覆盖状态标签 | 全覆盖(ok) / 仅一份数据支撑(warn) / 部分覆盖(muted) | 同 | 不变（判据改用具名常量，取值相同） |
| S2 | 卡片标题 / `source` / 列名顺序 | 数据集资产明细 / 8 列 | 同 | 不变 |
| S2 | `models` 文案 | `modelingReady && stat ? '已发布 x / 共 y' : '—'` | `stat ? … : '—'` | 不变（前半恒真；当前 2 行都命中 Map） |
| S2 | 未登记标签 | `d-tag d-tag--warn` + `未登记风险口径`（`caliber_registered === false`） | 同 | 不变（模板逐字未改） |
| S3 | 卡片标题 / `source` / `suffix` / `label-width` | 建模覆盖 / `260` / ` 个版本` | 同 | 不变 |
| S3 | 柱值 | 各数据集 `total` | 同 | 不变（直接读 `props.data.modeling`） |
| S3 | 脚注 | `数据白躺 N 份` + 名单 + `已发布合计 x / 草稿合计 y` | 同 | 不变（`whiteLying` / `modelTotals` 同口径同顺序；`modeling` 顺序即后端顺序，未排序） |
| S3 | `<p>` 渲染条件 | `v-if="modelingReady"`（恒真） | 无条件渲染 | 不变 |
| S4 | KPI 文案 / 单位 / 列数 | 待处置积压·条 / 已处置率·% / 近 10 天活动·次，`:columns="3"` | 同 | 不变 |
| S4 | 活动量 | `runtime ? reduce(sum + Number(point.total ?? 0)) : null` | `activityTotal`：`runtime ? reduce(sum + point.total) : null` | 数值不变（`total` 类型本就是 `number`，`Number()` / `?? 0` 恒不改变结果）；其 `null` 渲染问题见 D-1，只报不改 |
| S4 | 漏斗 / 折线 | `status_funnel` / `activity_trend`（label `date.slice(5)`） | 同 | 不变（`trendPoints` 逐字段搬运，未改） |
| S5 | 卡片标题 / `source` / 行序 | 场景成员与权限 / 场景管理员·场景用户·合计(+已禁用/+未纳入统计) | 同 | 不变（`memberRows` 逻辑未改；其范围问题见 D-2，只报不改） |
| S5 | 空态文案 | `成员数据未取到`（`members === null`） | 同 | 不变 |

**结论**：卡片标题与顺序、列名与顺序、KPI 文案与单位、标签文案与色调语义、数值格式结果、空态文案**全部逐字未变**。

### 6.4 模板逐行证据（机械比对）

把 `HEAD` 版与工作区版的 `<template>` 段逐行 `Compare-Object`（`HEAD` 的 `<template>` 在第 421 行、工作区在第 423 行，正好等于脚本段净增的 2 行），差异**恰好 2 行**：

```
$ Compare-Object (HEAD 的 <template> 段) (工作区的 <template> 段)
=>     <p style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
=>       <span v-if="whiteLying.length" style="margin-left: 6px">{{ whiteLying.join(LIST_SEPARATOR) }}</span>
<=     <p v-if="modelingReady" style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
<=       <span v-if="whiteLying.length" style="margin-left: 6px">{{ whiteLying.join('、') }}</span>
```

（`<=` = 只在 `HEAD` 侧，`=>` = 只在工作区侧。）

即：①删掉恒真的 `v-if="modelingReady"`；②分隔符改用常量（值仍是 `、`，插值结果逐字节相同）。模板段行数两侧同为 62 行 ⇒ 除这 2 行外模板**一字未动**。

### 6.5 未做的验证（诚实声明）

1. 本次**没有**重跑浏览器复验：验收所需的 `npm run build` / `vite build` / 起服务均在本任务禁令内。渲染不变性由三条静态证据支撑：①模板机械比对只有 2 行差异且语义等价（§6.4）；②计算层改动全部有类型 + 后端下发路径 + 上一轮已验收的实际渲染值三方对照（§3）；③`vue-tsc` `EXIT=0`。
2. **没有跑 `prettier --write`**：`npx prettier --check` 在本页与**未改动的**共享文件（`AdminProfilePage.vue`、`DashTable.vue`、`dashboardApi.ts`）上**都报 warn**，说明仓库基线本就不等于 prettier 默认输出；强行格式化会引入与本次重构无关的整文件改动，故保持仓库现有风格。
3. **没有跑单测 / 快照**：`frontend/tests/**` 属冻结面，且本任务未授权执行测试命令。

---

## 7. 共享面提案（**未实施**，需 Lead 决策）

### 7.1 背景：S4 运行态 + S5 成员在四页重复

| 文件 | "运行态与成员"取数段（`const runtime = ref<…>` → `summary`） | S4+S5 派生段（S4 banner → `memberRows` 结束） |
|---|---|---|
| `ProfileNetwork.vue` | 31 行（`:56-86`） | 61 行（`:358-417`） |
| `ProfileGeological.vue` | 31 行（`:50-80`） | 56 行（`:334-388`） |
| `ProfileFlightdeck.vue` | 结构位置不同（该段被拆开） | 71 行（`:396-465`） |
| `ProfilePower.vue` | 29 行（`:307-335`） | 94 行（`:304-396`） |

与 Network 逐行 `Compare-Object` 的差异量：Geological 的取数段差 26 行、S4/S5 段差 **5 行**（只差 Network 独有的"未纳入统计"溢出提示）；Flightdeck 差 48 行；Power 差 87 行（该区间还含 Power 页内专属的 KPI 计算）。

四页**完全相同**的部分是"取数 + 三个 KPI/漏斗/折线/成员行的搬运"，**不同**的部分只有三处：①是否校验 `scenario_key`（地质页校验）；②`getUserList` 是否传 `scenario_id`（地质页传，网络页不传）；③是否有"超出单页"溢出提示（只有网络页有）。合计约 92 行 × 4 页 ≈ 370 行的重复。

### 7.2 精确 diff（提案，**未 apply**）

**新建** `frontend/src/views/Home/dashboard/useScenarioRuntime.ts`（属 `frontend/src/views/Home/dashboard/**`，跨页共享，故仅提案）：

```ts
import { computed, onMounted, ref, watch, type Ref } from 'vue';
import { getScenarioWorkspace, type WorkspaceBase } from '@/api/dashboardApi';
import { getUserList } from '@/api/userApi';
import type { UserAccount } from '@/types/security';
import { fmtPercent } from '@/components/dashboard/dashFormat';
import type { KpiItem } from '@/components/dashboard/DashKpis.vue';

const MEMBER_PAGE_SIZE = 200;
const ROLE_SCENARIO_ADMIN = 'SCENARIO_ADMIN';
const ROLE_SCENARIO_USER = 'SCENARIO_USER';
const ACCOUNT_STATUS_ACTIVE = 'active';

export interface ScenarioRuntimeOptions {
  /** 运行态要求匹配的 scenario_key；不传则不校验（网络/电力/驾驶舱现状） */
  key?: string;
  /** 是否按后端 total 提示"超出单页"行（网络页需要） */
  memberOverflow?: boolean;
}

/** 四场景共用的运行态 + 成员取数与派生（提案，未落地） */
export function useScenarioRuntime(scenarioId: () => number, options: ScenarioRuntimeOptions = {}) {
  const runtime = ref<WorkspaceBase | null>(null);
  const members = ref<UserAccount[] | null>(null);
  const memberTotal = ref<number | null>(null);

  const loadAll = async () => {
    const id = scenarioId();
    const [runtimeResult, memberResult] = await Promise.allSettled([
      getScenarioWorkspace(id),
      getUserList({ scenario_id: id, page_size: MEMBER_PAGE_SIZE }),
    ]);
    runtime.value =
      runtimeResult.status === 'fulfilled' &&
      (!options.key || runtimeResult.value.scenario_key === options.key)
        ? runtimeResult.value
        : null;
    members.value =
      memberResult.status === 'fulfilled'
        ? memberResult.value.items.filter((item) => item.scenario_id === id)
        : null;
    memberTotal.value = memberResult.status === 'fulfilled' ? memberResult.value.total : null;
  };

  watch(scenarioId, loadAll);
  onMounted(loadAll);

  const summary = computed(() => runtime.value?.summary ?? null);
  const activityTotal = computed(() =>
    runtime.value ? runtime.value.activity_trend.reduce((sum, point) => sum + point.total, 0) : null,
  );
  const runtimeKpis = computed<KpiItem[]>(() => {
    const item = summary.value;
    return [
      { label: '待处置积压', value: item ? item.pending : null, unit: '条', tone: 'danger' },
      {
        label: '已处置率',
        value: item && item.total ? fmtPercent(item.resolved / item.total) : null,
        tone: 'success',
        raw: true,
      },
      { label: '近 10 天活动', value: activityTotal.value, unit: '次', tone: 'primary' },
    ];
  });
  const funnelItems = computed(() =>
    (summary.value?.status_funnel ?? []).map((item) => ({ label: item.label, count: item.count })),
  );
  const trendPoints = computed(() =>
    (runtime.value?.activity_trend ?? []).map((item) => ({
      label: item.date.slice(5),
      value: item.total,
      value2: item.risk,
    })),
  );
  const memberRows = computed(() => {
    const list = members.value;
    if (list === null) return [];
    const rows = [
      { label: '场景管理员', value: `${list.filter((i) => i.role === ROLE_SCENARIO_ADMIN).length} 人` },
      { label: '场景用户', value: `${list.filter((i) => i.role === ROLE_SCENARIO_USER).length} 人` },
      { label: '合计', value: `${list.length} 人` },
    ];
    const disabled = list.filter((i) => i.status !== ACCOUNT_STATUS_ACTIVE).length;
    if (disabled) rows.push({ label: '已禁用', value: `${disabled} 人` });
    const overflow = options.memberOverflow ? (memberTotal.value ?? 0) - list.length : 0;
    if (overflow > 0) {
      rows.push({ label: '未纳入统计', value: `${overflow} 人（超出单页 ${MEMBER_PAGE_SIZE} 条）` });
    }
    return rows;
  });

  return { runtime, members, memberTotal, summary, activityTotal, runtimeKpis, funnelItems, trendPoints, memberRows };
}
```

对应 `ProfileNetwork.vue` 的用法（同样**未实施**，仅在提案内示意）：

```diff
@@ 取数段（本页 :74-104）
-const runtime = ref<WorkspaceBase | null>(null);
-const members = ref<UserAccount[] | null>(null);
-const memberTotal = ref<number | null>(null);
-const loadAll = async () => { /* …31 行… */ };
-watch(() => props.data.scenario_id, loadAll);
-onMounted(loadAll);
-const summary = computed(() => runtime.value?.summary ?? null);
+const { members, runtimeKpis, funnelItems, trendPoints, memberRows } =
+  useScenarioRuntime(() => props.data.scenario_id, { memberOverflow: true });

@@ S4/S5 派生段
-const activityTotal = computed(() => /* …3 行… */);
-const runtimeKpis = computed(() => { /* …14 行… */ });
-const funnelItems = computed(() => /* …3 行… */);
-const trendPoints = computed(() => /* …7 行… */);
-const memberRows = computed(() => { /* …21 行… */ });
```

净效果：本页删约 94 行、加 3 行；四页合计删约 375 行、加约 10 行，S4/S5 只有一份实现。

### 7.3 影响面

- 需改：**新建** 1 个文件 + 四页各删一段（本页 1 处取数段 + 4 个 computed）。属 `frontend/src/views/Home/dashboard/**` 与跨页共享面，**超出本 agent 写权限**。
- **会顺带修掉 D-2**：composable 统一传 `scenario_id`（契约 §7 写法，`ProfileGeological.vue:70` 已是此形），因此 `SUPER_ADMIN` 视角那行假的"未纳入统计 16 人"会消失 —— **这是渲染变化**，需 Lead 明确同意；若要求严格零渲染变化，则 composable 必须保留"不传 `scenario_id`、只在前端过滤"的旧路径，D-2 另案处理。
- 风险点：`runtime` 的 `scenario_key` 校验从"每页自定"变成可选参数，若不传即等价于现状（网络页现状即不校验）；`memberRows` 的"已禁用"文案与顺序保持不变。

### 7.4 替代方案（我更倾向的默认选项）

**先只抽"取数段"（`runtime`/`members`/`memberTotal`/`loadAll`/`watch`/`onMounted`/`summary`，约 30 行 × 4 页），S4/S5 的派生 computed 暂不抽。** 理由：取数段四页语义一致、差异只有"是否传 `scenario_id`"与"是否校验 `key`"两个布尔开关，抽象收益高、风险低；而 S4/S5 派生段在 Power 页夹带了页内专属计算（差 87 行），强行合并需要更多 options 分支，容易把"四页一致"变成"四页都得看 options 才懂"，属于"为去重付耦合"。若 Lead 选择全量抽取，建议同时采纳 §7.3 的 D-2 修正并单独记录渲染变化。

> 另注：R4 报告 §7 提出的 `dash.css` 的 `d-note` 类提案（脚注内联样式去重）与本提案不重叠，可独立决策。

---

## 8. 未解决存疑

1. **S4 两格在 `/workspace` 失败时误报 `0`**（§2 D-1）：真实缺陷。修法（**未 apply**）：
   ```diff
   -    { label: '待处置积压', value: item ? item.pending : null, unit: '条', tone: 'danger' as const },
   +    { label: '待处置积压', value: item ? item.pending : '—', unit: '条', tone: 'danger' as const },
   -    { label: '近 10 天活动', value: activityTotal.value, unit: '次', tone: 'primary' as const },
   +    { label: '近 10 天活动', value: activityTotal.value ?? '—', unit: '次', tone: 'primary' as const },
   ```
   `fmtInt('—')` → `Number('—')` 为 `NaN` → 返回 `—`；成功路径逐字节不变。属渲染变化，交 Lead 裁决。
2. **SUPER_ADMIN 视角 S5 多一行假"未纳入统计"**（§2 D-2）：真实缺陷。修法（**未 apply**）：`getUserList({ scenario_id: scenarioId, page_size: MEMBER_PAGE_SIZE })`（即契约 §7 与 `ProfileGeological.vue:70` 的写法）。`SCENARIO_ADMIN` 视角渲染不变；`SUPER_ADMIN` 视角那行消失。
3. **KPI-4 空矩阵时渲染 `0套`**（§2 D-3）：潜在缺陷，当前不可达（网络场景 `caliber_matrix` 恒 3 行）；若 Lead 要"零隐患"，一行改为 `value: caliberLanguages.value ?? '—'`（可达路径渲染不变）。
4. **切换场景的响应竞态**（§2 D-4）：无请求令牌，A 场景慢响应可能覆盖 B 场景数据。修法需引入令牌 / `AbortController`，超出"渲染不变"范围。
5. **`sub` 文案与触发条件不符**（§2 D-5）：`SHOW_DASH_HINTS=false` 时不渲染，影响为 0；若将来开启提示，文案应改为"风险口径矩阵为空"。
6. **未做浏览器复验**（§6.5）：受禁令限制，仅以静态证据 + 模板机械比对 + `vue-tsc` 支撑渲染不变。
7. **`prettier --check` 基线不干净**（§6.5）：本页与未改动的共享文件同样报 warn，故未做格式化；若 Lead 希望全仓统一格式，应作为独立任务一次性处理。
8. **跨页一致性不属本页范围**：`ProfilePower.vue` 把 `modeling` 收窄成 `ModelingStat[] | null` 并配 `?? 0` 兜底，与"必填"契约不符 —— 由 R2 负责，本报告仅记录。

---

## 9. 声明

**我未修改任何共享面文件。**

本次仅改动 1 个文件：`frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue`，外加本报告 `docs/场景管理员首页审查/重构报告/network.md`。未触碰 `frontend/src/components/dashboard/**`（`DashTable.vue` / `dash.css` / `DashKpis.vue` / `DashCard.vue` / `DashBars.vue` / `DashRows.vue` / `DashFunnel.vue` / `DashLine.vue` / `dashFormat.ts` 等）、`frontend/src/api/**`、`AdminProfilePage.vue`、`DashboardHomeView.vue`、另三个 `Profile*.vue`、`backend/**`、`scripts/**`、`frontend/tests/**`、数据库与 `实施契约.md`；§7 的共享面提案**只写不改**。

`git status --short`（写入本报告后；中文路径 git 以八进制转义输出，此处按可读形式还原）：

```
 M frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
 M frontend/src/views/Home/dashboard/sections/ProfileGeological.vue
 M frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue
 M frontend/src/views/Home/dashboard/sections/ProfilePower.vue
 M frontend/src/views/Model/DatasetCenter.vue
 M frontend/src/views/Model/ModelCenter.vue
 M frontend/src/views/Model/ReportCenter.vue
 M frontend/src/views/Model/RiskInference.vue
 M frontend/src/views/Model/UserManagement.vue
?? "docs/全项目代码审查/"
?? "docs/场景管理员首页审查/重构报告/"
```

> 说明：`Profile{Flightdeck,Geological,Power}.vue`、`frontend/src/views/Model/*.vue`（另一条并行任务）与 `docs/全项目代码审查/` 均**非本 agent 所为**；本 agent 的改动只有 `ProfileNetwork.vue` 与本报告 `docs/场景管理员首页审查/重构报告/network.md`。
