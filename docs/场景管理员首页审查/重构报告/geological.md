# 地质风险 · 场景管理员首页 代码质量重构报告（R4）

- **唯一改动文件**：`frontend/src/views/Home/dashboard/sections/ProfileGeological.vue`
- **路由链路**：`#/scenarios/4/dashboard` → `DashboardHomeView.vue` →（`SCENARIO_ADMIN`）`AdminProfilePage.vue` → `sections/ProfileGeological.vue`
- **约束**：只改"怎么算 / 怎么组织"，不改任何渲染结果；不碰冻结共享面。
- **门控**：`cd frontend; npx vue-tsc --noEmit -p tsconfig.app.json` → 原始输出为空，`EXIT=0`
- **行数**：460 → 459（`git diff --numstat` = `58 insertions / 59 deletions`）

---

## 1. 改动摘要

| # | 改动 | 一句话说明 |
|---|---|---|
| 1 | 删 `rowsOrEmpty<T>()` 及 `roles` / `factorCoverage` / `modeling` 三个包装 computed | 三个字段在 `GeologicalProfile` 里是**必填**、后端也**无条件下发**，兜底恒不可达；改为直接读 `props.data.*` |
| 2 | 删 `modelingReady`（连带 KPI-4 的 `sub` 三元、S2 `models` 的 `&&` 门控、S3 `<p v-if="modelingReady">`） | `Array.isArray(props.data.modeling)` 恒真；留着它等于给"未建模数 / 数据白躺"多留一套永远为假的真假口径 |
| 3 | 删 3 个已无引用的类型导入 `FactorCoverageRow` / `ModelingStat` / `RoleRow` | 它们只被 `rowsOrEmpty<T>` 用到，随改动 1 一起消失 |
| 4 | 新增具名判据 `isWhiteLying(item: { total: number })` | S1"未建模数据集数"与 S3"数据白躺"原先各写一遍 `total === 0`，现共用同一口径 |
| 5 | 新增 S3 单一基底 `modelingRows`，`modelingBars` / `whiteLying` / `modelTotals` 全部由它派生 | 原先对 `modeling` 遍历 4 遍、`nameOf()` 重复查 6 次；现在展示名只解析一次 |
| 6 | `displayNames` 改为"先数重名、再据此生成展示名"两遍遍历 | 去掉 `names[index]` 这条"原始名数组与 `datasets` 下标对齐"的隐式不变量 |
| 7 | `factorRows` 删 `const ids = item.datasets ?? []` | `FactorCoverageRow.datasets` 必填，`?? []` 恒不生效 |
| 8 | 抽出 `activityTotal` computed，删 `Number(point.total ?? 0)` | `total` 类型就是 `number`，`Number()` / `?? 0` 是空转；顺手把求和从 KPI 计算里提出来具名 |
| 9 | `trendPoints` 的 `item.date.slice(5)` → `fmtDate(item.date)` | 复用 `dashFormat.ts`，输出逐字节相同 |

**净效果**：删除的全部是"恒不可达兜底 + 重复遍历 + 空转转换 + 无引用符号"，新增的是 1 个共用判据、1 个派生基底、1 个具名 computed 与相应注释。

---

## 2. 逐项审查结论

### A. 弃用写法（逐项经查无问题）

| 检查项 | 结论 | 检查方式与证据 |
|---|---|---|
| Options API 残留（`export default` / `data()` / `methods:` / `computed: {}` / `this.` / `mounted()` / `beforeDestroy` / `filters:`） | **经查无问题** | 本文件 grep `export default\|this\.\|beforeDestroy\|methods:\|filters` = 0 命中；文件为纯 `<script setup lang="ts">`，无组件对象 |
| Vue 2 模板语法（`.sync` / `slot-scope` / `v-on.native` / `$listeners` / `Vue.set`） | **经查无问题** | grep `\.sync\|\$listeners\|Vue\.set\|v-on\.native\|slot-scope` = 0 命中；插槽用 Vue 3 的 `<template #label_field="{ row }">` |
| 深层选择器弃用写法（`::v-deep` / `/deep/` / `>>>`） | **经查无问题** | 本文件**没有** `<style>` 块（grep `<style` = 0 命中），样式全部走 `dash.css` 的 `d-*` 类，不存在组件内样式穿透 |
| `console.*` / `debugger` / `TODO` / `FIXME` / `@ts-ignore` / `@ts-expect-error` | **经查无问题** | grep = 0 命中；无被压制的类型错误 |
| `any` 与非空断言 `!` | **经查无问题** | grep `: any\|as any\|any\[\]\|<any>\|!\.\|!\)\|!,\|!;` = 0 命中；`strict: true` 下无逃逸 |
| `recent_events`（执行端字段） | **经查无问题（有意不渲染）** | 仅出现在头部注释的设计说明（第 12 行）；代码与模板 0 引用。管理端不渲染派活清单是本页定位（见文件头注释） |
| 旧可视化组件（`DashDonut` / `DashColumns` / `DashRadar` 等已下线件） | **经查无问题** | grep = 0 命中；本页只用 `DashKpis` / `DashCard` / `DashBars` / `DashFunnel` / `DashLine` / `DashRows` / `DashTable`，均为现行组件 |
| 前端按标签字段猜正类（旧版 `is_risk_label` 过滤） | **经查无问题** | 代码 0 引用，仅剩两处注释里的历史说明（第 197、266 行）；S2 改为遍历全部 `datasets` 并用 `caliber_registered === false` 打「未登记风险口径」标签 |
| 已废弃的 `modelVersionApi` 自行归集模型数 | **经查无问题** | 本文件 0 引用；模型数一律取画像下发的 `modeling`（后端按 dataset 聚合），只有一套口径 |

### B. 残留死代码（4 项删除 + 无死字段结论）

1. **`rowsOrEmpty<T>()`** —— 删除。本文件 0 引用，全 `frontend/src` 亦 0 引用（见 §4）。
2. **`modelingReady`** —— 删除。本文件 0 引用，全 `frontend/src` 亦 0 引用（另三页由 R1–R3 同步清理）。
3. **`roles` / `factorCoverage` / `modeling` 三个包装 computed** —— 删除。使用点改为 `props.data.roles` / `props.data.factor_coverage` / `props.data.modeling`。
4. **`FactorCoverageRow` / `ModelingStat` / `RoleRow` 类型导入** —— 删除（唯一消费者是 `rowsOrEmpty<T>`）。
5. **行对象死字段**：**经查无死字段**。逐一核对"模板列 key + `rowKey` + 插槽用键"是否覆盖每个键：
   - D1 `roleRows` 10 键 = 9 个 `roleColumns.key`（`name`/`role`/`attribute_count`/`label_field`/`label_kind`/`training`/`risk_events`/`record_count`/`risk_rate`）+ `rowKey="logical_id"`；
   - D2 `factorRows` 4 键 = 4 个 `factorColumns.key` + `rowKey="factor"`；
   - S2 `datasetRows` 10 键 = 8 个 `datasetColumns.key` + `rowKey="logical_id"` + 插槽条件用的 `unregistered`（非列 key，只被 `#label_field` 读）；
   - S3 `modelingRows` 4 字段（`name`/`published`/`draft`/`total`）全部被 `modelingBars`、`whiteLying`、`modelTotals` 消费。
6. **未使用的导入 / 局部变量 / 参数**：**经查无问题**。`tsconfig.app.json` 开启 `noUnusedLocals` + `noUnusedParameters` + `strict`（第 13–15 行），`vue-tsc` `EXIT=0` ⇒ 编译期已证明零未使用符号。
7. **空 `<style>`、空 computed、恒真 / 恒假分支**：**经查无问题**（无 `<style>`；所有 computed 都有模板或其它 computed 消费；仅存的 `stat ? … : '—'` 是 Map 查空兜底，见 §3 与 D-4）。
8. **注释里的历史包袱**：保留（`is_risk_label`、`recent_events` 两处说明解释了"为什么不这么做"），不属死代码。

### C. 不必要的复杂度（逐项处理结论）

| # | 复杂度 | 处理 |
|---|---|---|
| C-1 | 三层间接：`rowsOrEmpty` → `roles`/`factorCoverage`/`modeling` → 使用点 | **已压成一层** `props.data.*`，删 4 个符号 |
| C-2 | 同一判据写两遍：S1 `filter(item => item.total === 0)`、S3 `filter(item => item.total === 0)` | **已提为** `isWhiteLying`，一处定义两处使用 |
| C-3 | 同一数组 4 遍遍历 + 展示名重复解析：S3 的柱 / 白躺 / 合计各自 `modeling.map(...)` 再各查一次 `nameOf`，S2 另建一份 Map | **已合并**为 `modelingRows` 基底 + 3 个派生 computed，展示名只解析一次 |
| C-4 | `displayNames` 维护"原始名数组 + `datasets` 下标对齐"隐式不变量 | **已改为**两遍自洽遍历（第一遍计数、第二遍生成），不再有下标耦合 |
| C-5 | `activityTotal` 内联在 `runtimeKpis` 内且 `Number()` / `?? 0` 空转 | **已抽出**为具名 computed，返回 `number \| null`，直接对上 KPI 的 `—` 语义 |
| C-6 | `nameOf(logicalId, fallback?)` 的 `fallback` 参数 | **有意保留**：`displayNames` 与 `roles` 的 logical_id 集合一致时它恒不生效（后端 `roles` 与 `datasets` 都取自同一 `by_logical`），但它是"有更好的信息就用后端行内 `name`"的**降级**，不是伪造值；删掉反而会在集合不一致时把展示名退化成裸 `logical_id`。属刻意保留，非遗漏 |
| C-7 | `memberRows` 里三次 `filter` | **有意保留**：列表规模是个位数；三个计数本就是不同维度（角色 ×2、状态 ×1），声明式写法比手写单循环更易读 |
| C-8 | S3 脚注 `<p>` 的内联样式在四页重复 | **不在本页改**（改动 `dash.css` 属共享面）→ 见 §7 提案 |

### D. 正确性隐患（4 项"经查无问题"；2 项真实隐患只报不改 + 1 项有意保留）

| # | 项 | 结论 | 依据 |
|---|---|---|---|
| D-1 | **S5 成员统计会被单页 200 条静默截断**（真实潜在缺陷，**未修**） | 本页确实传了 `scenario_id`（`getUserList({ scenario_id, page_size: 200 })`），但**没有**任何"超出单页"提示，也**没有**用响应里的 `total`；成员超过 200 人时"合计 N 人"少报且无告警 | `user_routes.py:37` `page_size: int = Query(10, ge=1, le=200)`（200 是硬上限）；`user_service.py:124` `page_size = min(max(1, int(page_size or 10)), 200)`；`user_service.py:129/144` 另行算出并返回权威 `total`。修法必然改动渲染（分页拉全或改显示 `total` + 提示），超出"渲染不变"约束 → 留给 Lead 决策 |
| D-2 | 前端 `scenario_id` 再过滤冗余 | **保留（有意）**：后端对 `SCENARIO_ADMIN` 已强制 `AppUser.scenario_id == 自己场景`（`user_service.py:106-107`），又按显式参数再过滤一次（`120-121`），所以 `items.filter(item => item.scenario_id === scenarioId)` 恒不删任何行。保留理由：它是本页唯一声明"范围限本场景"的边界守卫，成本 1 行；删除不改变任何渲染 | 同上两处后端代码 |
| D-3 | `risk_rate` 分母为 0 时显示 `0.0%` 而非 `—`（后端口径，**未修**） | 属真实口径隐患但当前未触发：`_percent` 在 `total == 0` 时返回 `0.0`，`fmtPercent(0)` → `0.0%`。当前 5 个数据集样本量均 > 0。要改成 `—` 必须动后端（冻结面） | `dashboard_service.py:373-374` `return round(part / total, 4) if total else 0.0` |
| D-4 | S2 `models` 的 Map 查空兜底 | **保留（真兜底，非恒真门控）**：`modelingByDataset.get(logical_id)` 类型是 `ModelingStat \| undefined`，类型层面不排除查空；且它给 `—` 而不是伪造 `已发布 0 / 共 0`，符合"取不到就不报数" | `dashboardApi.ts:153` 只保证 `modeling` 数组存在，不保证键存在 |
| D-5 | `activityTotal` 新写法的边界 | **经查无问题（与旧写法等价）**：`WorkspaceBase.activity_trend` 为**必填**（`dashboardApi.ts:402`）且 `GeologicalWorkspace extends WorkspaceBase`（`:429`），所以 `runtime` 非空时它一定是数组 → 空数组给 0、有值给和，与旧 `(runtime.value.activity_trend ?? []).reduce(...)` 在所有可达状态下逐值相同；唯一差异在类型上不可能的 `undefined` 分支（旧 0 / 新 `—`），新写法更符合"取不到就不报数" | `dashboardApi.ts:402/429` |
| D-6 | 运行态 / 成员请求失败时的降级 | **经查无问题**：`runtime === null` ⇒ S4 KPI 给 `null`（渲染 `—`）、漏斗与折线给空集；`members === null` ⇒ 渲染"成员数据未取到"（与"0 人"区分）。`Promise.allSettled` 保证互不阻塞 | 本文件 `loadAll`；`dashHints.ts` 的 `SHOW_DASH_HINTS = false` 只影响 `sub`/`source` 提示文字，不影响上述降级 |
| D-7 | XSS / 注入面 | **经查无问题**：无 `v-html`、无 `innerHTML`、无 `eval`；所有插值都是文本节点；数据集名 / 因子名等外部字符串只经 `{{ }}` 输出 | grep + 模板逐行核对 |

---

## 3. 门控 / 兜底可达性裁定

| 可疑点 | 裁定 | 证据（类型 + 后端 + 运行时） |
|---|---|---|
| `rowsOrEmpty`（`?? []`）三处 | **死（不可达）** | **类型**：`ProfileBase.modeling: ModelingStat[]`（`dashboardApi.ts:153`）、`GeologicalProfile.roles: RoleRow[]`（`:353`）、`factor_coverage: FactorCoverageRow[]`（`:355`）全部必填非可选。**后端**：`get_profile` 在 `dashboard_service.py:1386` 无条件写 `"modeling"`；`_geological_profile`（`:1859`）在 `:1940` / `:1942` 无条件写 `"roles"` / `"factor_coverage"`；`_modeling_stats`（`:1405`）无数据集时返回 `[]` 而非 `None`。**运行时**：S3 柱状图实渲染 `4/0/0/0/0/0 个版本`（6 行都在）、脚注"数据白躺 5 份"、D1 6 行、D2 8 行 ⇒ 三个数组实际都在场 |
| `modelingReady`（`Array.isArray`） | **死（恒真）** | 同上。运行时反证：S1 第 4 项 KPI 实际渲染出数字 `5`（不是 `—`），说明它永远走 true 侧 |
| KPI-4 `sub` 的 `'后端未下发建模统计'` 分支 | **死** | 同 `modelingReady`。附加：`dashHints.ts` 的 `SHOW_DASH_HINTS = false` 使 `sub` 当前**根本不渲染**，删除它不可能改变任何可见输出 |
| S2 `models: modelingReady.value && stat ? … : '—'` | 前半 **死**、后半 **活** | 前半同 `modelingReady`（已删）；后半 `stat` 是 Map 查空，类型上确为 `ModelingStat \| undefined` ⇒ **保留** |
| `factorRows` 的 `item.datasets ?? []` | **死** | **类型**：`FactorCoverageRow.datasets: string[]` 必填（`dashboardApi.ts:338`）。**后端**：`_geological_profile` 为每个 `GEO_FACTORS` 都构造 `datasets` 列表（`:1859` 函数内，`:1942` 一并返回），为空也是 `[]` |
| `Number(point.total ?? 0)` | **死（空转）** | **类型**：`WorkspaceBase.activity_trend: Array<{ date: string; total: number; risk: number }>`（`dashboardApi.ts:402`）⇒ `total` 必为 `number` |
| `item.date.slice(5)` → `fmtDate(item.date)` | **等价** | `dashFormat.ts` 的 `fmtDate = (v) => String(v ?? '').slice(5)`，输入是 `string` ⇒ 输出逐字节相同（`MM-DD`） |
| `trendPoints` / `funnelItems` 的 `?? []` | **活（保留）** | `runtime.value?.activity_trend` / `?.status_funnel` 在运行态请求失败（`runtime === null`）时确实为 `undefined`，此时折线拿到空点集、漏斗拿到空列表 —— 真实可达的降级路径 |
| S5 `members === null` 分支 | **活（保留）** | `getUserList` 被 reject 时 `members = null` ⇒ 渲染"成员数据未取到"，与"确实 0 人"区分开 |

> 裁定原则：**类型声明 + 后端下发路径 + 上一轮已验收的实际渲染** 三者同向才算"死"；只凭"看起来像兜底"一律判活。

---

## 4. 删除证据（零引用）

`grep` 范围：①本文件；②`frontend/src` 全量。

| 被删符号 | 本文件命中 | `frontend/src` 命中 | 说明 |
|---|---|---|---|
| `rowsOrEmpty` | **0** | **0** | 全前端已无此模式 |
| `modelingReady` | **0** | **0** | 另三页由 R1–R3 同步清理，全前端已无残留 |
| `roles` / `factorCoverage` / `modeling`（本文件局部 computed） | **0** | n/a（局部符号） | 使用点已改为 `props.data.*` |
| `FactorCoverageRow` / `ModelingStat` / `RoleRow`（导入） | **0** | n/a（局部导入） | 唯一消费者是 `rowsOrEmpty<T>` |
| `is_risk_label`（代码引用） | **0**（仅注释 2 处） | — | 仅历史说明文字 |
| `getModelVersionList` / `modelVersionApi` | **0** | — | 模型数统一取画像 `modeling` |
| `console.` / `TODO` / `FIXME` / `@ts-ignore` / `any` / 非空断言 | **0** | — | 见 §2 A |

**行数变化**：`HEAD:…ProfileGeological.vue` = 460 行 → 工作区 = 459 行；`git diff --numstat` = `58 insertions / 59 deletions`（净 −1 行）。删除的 59 行全部是死兜底 / 重复遍历 / 空转转换 / 无引用符号；新增的 58 行里含 1 个派生基底、1 个具名 computed、1 个共用判据及说明"为什么删"的注释。

---

## 5. 函数清单

> 逐个符号：算什么 + 后端字段来源。

### 请求与状态

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `props` | `defineProps<{ data: GeologicalProfile }>` | 画像数据由 `AdminProfilePage.vue` 用 `geologicalData` 收窄后传入 | `GET /dashboard/scenarios/{id}/profile`；**契约要求签名不变** |
| `runtime` | `ref<GeologicalWorkspace \| null>` | 运行态；仅当 `scenario_key === 'geological'` 才接受（防跨场景串数据） | `GET /dashboard/scenarios/{id}/workspace`（`getScenarioWorkspace`） |
| `members` | `ref<UserAccount[] \| null>` | 场景成员；`null` = 未取到（≠ 0 人） | `GET /users?scenario_id=&page_size=200`（`getUserList`） |
| `loadAll` | `async () => void` | 两接口 `Promise.allSettled` 并行 + 各自静默降级 | 同上两接口 |
| `watch(() => props.data.scenario_id, loadAll)` | `watch` | 切换场景时重拉 | — |
| `onMounted(loadAll)` | 生命周期 | 首屏拉取 | — |
| `summary` | computed | `runtime.summary` | `EventSummary`（`pending`/`total`/`resolved`/`status_funnel`/…） |

### 判据与展示名

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `isWhiteLying` | `(item: { total: number }) => boolean` | `total === 0`；S1 与 S3 共用判据 | `ModelingStat.total`（`:70` 注释即"为 0 表示「数据白躺」"），由 `_modeling_stats`（`dashboard_service.py:1405`）产出 |
| `unmodeledCount` | computed `number` | `modeling` 中 `total === 0` 的条数 → S1 KPI-4 | 同上 |
| `displayNames` | computed `Map<string,string>` | `logical_id` → 去重展示名；重名补 `（logical_id）` | `DatasetStat.name`（后端 `dataset_display_name_of` 取上传文件名；`dis_landslides` 与 `geo_slope_company_v1` 同名 `DIS_Landslides`） |
| `nameOf(logicalId, fallback?)` | 函数 | 展示名查表：去重表 → 行内 `name` → `logical_id` | `DatasetStat.name` / `RoleRow.name` |
| `LABEL_KIND_TEXT` / `labelKindText` | 常量表 + 函数 | 标签类型中文（二分类/多分类/数值/未知），纯描述性 | `RoleRow.label_kind`（后端 `_label_kind`） |
| `VISIBILITY_TEXT` / `visibilityText` | 常量表 + 函数 | 可见性中文（平台/公司/个人） | `DatasetStat.visibility` |
| `modelingByDataset` | computed `Map<string,ModelingStat>` | `logical_id` → 模型版本统计，供 S2「已发布 x / 共 y」 | `ProfileBase.modeling`（`_modeling_stats`） |

### S1 / D1 / D2 / S2

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `overviewKpis` | computed `KpiItem[]` | S1 四格：有效数据集数 / 有效样本总量 / 统一风险占比 / 未建模数据集数 | `dataset_count`、`sample_count`、`risk_rate`（`fmtPercent`）、`dataset_file_count`（作 `sub`） |
| `roleColumns` / `roleRows` | `DashColumn[]` / computed | D1 数据集角色分工矩阵（9 列，`rowKey=logical_id`） | `GeologicalProfile.roles`（`RoleRow`：`logical_id`/`name`/`role`/`attribute_count`/`label_field`/`label_kind`/`participates_in_training`/`produces_risk_events`/`record_count`/`risk_rate`） |
| `factorColumns` / `factorRows` | `DashColumn[]` / computed | D2 地形因子跨数据集覆盖矩阵（4 列，`rowKey=factor`） | `GeologicalProfile.factor_coverage`（`FactorCoverageRow`：`factor`/`datasets`/`consistent_binning`） |
| `datasetColumns` / `datasetRows` | `DashColumn[]` / computed | S2 数据集资产明细（8 列 + 插槽标签，`rowKey=logical_id`） | `ProfileBase.datasets`（`DatasetStat`：`record_count`/`label_field`/`risk_rate`/`attribute_count`/`visibility`/`version`/`caliber_registered`） |

### S3 / S4 / S5

| 符号 | 类型 | 算什么 | 后端字段 / 来源 |
|---|---|---|---|
| `modelingRows` | computed | **S3 单一基底**：每数据集一行（`name`/`published`/`draft`/`total`） | `ProfileBase.modeling` |
| `modelingBars` | computed | 每数据集一根柱 = 版本总数 | `ModelingStat.total` |
| `whiteLying` | computed `string[]` | 白躺数据集展示名列表（`total === 0`） | `ModelingStat.total` |
| `modelTotals` | computed `{published, draft}` | 已发布 / 草稿合计 | `ModelingStat.published` / `.draft` |
| `activityTotal` | computed `number \| null` | 近 10 天活动量 = `activity_trend[].total` 之和；运行态缺失时 `null`（KPI 显示 `—`） | `WorkspaceBase.activity_trend`（后端 `_activity_trend`，`dashboard_service.py:2000`） |
| `runtimeKpis` | computed `KpiItem[]` | S4 三格：待处置积压 / 已处置率（`resolved ÷ total`，`fmtPercent`）/ 近 10 天活动 | `EventSummary.pending` / `.resolved` / `.total` + `activityTotal` |
| `funnelItems` | computed | 处置漏斗（待处置 → 处理中 → 已处置） | `EventSummary.status_funnel` |
| `trendPoints` | computed | 折线点：`label = fmtDate(date)`、`value = total`、`value2 = risk` | `WorkspaceBase.activity_trend` |
| `memberRows` | computed | S5 行：场景管理员 / 场景用户 / 合计（+ 有禁用时补"已禁用"） | `UserAccount.role`（`SCENARIO_ADMIN`/`SCENARIO_USER`）、`.status`（`active`/`disabled`） |

**无 `ref` 之外的响应式状态、无 `provide/inject`、无 `emit`、无 `expose`、无生命周期钩子（仅 `onMounted`）。**

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
- 说明：本次共跑两次（重构完成后一次、注释精简后再一次），两次结果相同；`tsconfig.app.json` 开着 `strict` + `noUnusedLocals` + `noUnusedParameters`（第 13–15 行），因此 `EXIT=0` 同时证明"无未使用导入 / 局部变量 / 参数"。
- 未执行（按禁令）：`npm run build`、`vite build`、`npx vite`、任何服务启停、`pytest`、任何写 `dist` / `node_modules/.vite` / `*.tsbuildinfo` / DB 的命令。

### 6.2 行数

| | 行数 |
|---|---|
| `HEAD:frontend/src/views/Home/dashboard/sections/ProfileGeological.vue` | 460 |
| 工作区（重构后） | 459 |
| `git diff --numstat` | `58 insertions(+) / 59 deletions(-)` |

### 6.3 渲染不变逐项对照

| 位置 | 渲染要素 | 改前 | 改后 | 判定 |
|---|---|---|---|---|
| S1 | 卡片标题 / 顺序 | 无标题 KPI 行，4 格 | 同 | 不变（模板未改） |
| S1 | KPI 文案 + 单位 | 有效数据集数·个 / 有效样本总量·条 / 统一风险占比·% / 未建模数据集数·个 | 同 | 不变（`label`/`unit`/`tone`/`raw` 一字未改） |
| S1 | KPI-4 数值 | `modelingReady ? 5 : null` → `5` | `5` | 不变（`modelingReady` 恒真，可达值唯一） |
| S1 | KPI-4 `sub` | 三元的 true 侧文案 | 同一文案 | 不变（且 `SHOW_DASH_HINTS=false` 当前不渲染） |
| D1 | 卡片标题 / `source` | 数据集角色分工矩阵 / 原文 | 同 | 不变 |
| D1 | 列名 + 顺序 + 对齐 | 数据集·角色·字段数·标签字段·标签类型·参与训练·产生风险事件·样本量·风险占比 | 同 | 不变（`roleColumns` 未改） |
| D1 | 标签文案 + 色调语义 | 已建模(ok) / 未建模(warn)；是(ok) / 未登记·不产事件(warn) | 同 | 不变 |
| D1 | 数值格式 | `fmtInt(record_count)` / `fmtPercent(risk_rate)` | 同 | 不变 |
| D2 | 卡片标题 / `source` / 列名顺序 | 地形因子跨数据集覆盖矩阵 / 因子·覆盖数据集·覆盖数·分箱一致性 | 同 | 不变（`factorColumns` 未改） |
| D2 | `datasets` 拼接 | `ids.map(nameOf).join('、')` | `item.datasets.map(nameOf).join('、')` | 不变（`ids` 与 `item.datasets` 同一数组） |
| D2 | 分箱标签 | 一致(ok) / 不一致(up) | 同 | 不变 |
| S2 | 卡片标题 / `source` / 列名顺序 | 数据集资产明细 / 8 列 | 同 | 不变 |
| S2 | `models` 文案 | `modelingReady && stat ? '已发布 x / 共 y' : '—'` | `stat ? … : '—'` | 不变（前半恒真；当前 5 行都命中 Map，均显示 `已发布 x / 共 y`） |
| S2 | 未登记标签 | `d-tag d-tag--warn` + `未登记风险口径`（`caliber_registered === false`） | 同 | 不变（模板逐字未改） |
| S3 | 卡片标题 / `source` / `suffix` / `label-width` | 建模覆盖 / `250` / ` 个版本` | 同 | 不变 |
| S3 | 柱值 | 各数据集 `total` | 同 | 不变（`modelingRows` 逐字段搬运） |
| S3 | 脚注 | `数据白躺 N 份` + 名单 + `已发布合计 x / 草稿合计 y` | 同 | 不变（`whiteLying` / `modelTotals` 同口径同顺序；`modeling` 顺序即后端顺序，未排序） |
| S3 | `<p>` 渲染条件 | `v-if="modelingReady"`（恒真） | 无条件渲染 | 不变 |
| S4 | KPI 文案 / 单位 / 列数 | 待处置积压·条 / 已处置率·% / 近 10 天活动·次，`:columns="3"` | 同 | 不变 |
| S4 | 活动量 | `runtime ? reduce(sum + Number(total ?? 0)) : null` | `points ? reduce(sum + total) : null` | 不变（`total` 必为 number；可达状态下逐值相同） |
| S4 | 漏斗 / 折线 | `status_funnel` / `activity_trend`（label `date.slice(5)`） | 同（label `fmtDate(date)`） | 不变（`fmtDate` 即 `String(v ?? '').slice(5)`） |
| S5 | 卡片标题 / `source` / 行序 | 场景成员与权限 / 场景管理员·场景用户·合计(+已禁用) | 同 | 不变（`memberRows` 逻辑未改） |
| S5 | 空态文案 | `成员数据未取到`（`members === null`） | 同 | 不变 |

**结论**：卡片标题与顺序、列名与顺序、KPI 文案与单位、标签文案与色调语义、数值格式结果、空态文案**全部逐字未变**；唯一"条件表达式"层面的变化是删掉了恒真的门控，其可达取值集合不变。

### 6.4 未做的验证（诚实声明）

本次**没有**重跑浏览器复验：验收所需的 `npm run build` / `vite build` / 起服务均在本任务禁令内。渲染不变性由三条静态证据支撑：①模板逐字未改（除删恒真 `v-if`）；②计算层改动全部有类型 + 后端下发路径 + 上一轮已验收的实际渲染值三方对照（§3）；③`vue-tsc` `EXIT=0`。

---

## 7. 共享面提案（**未实施**，需 Lead 决策）

### 7.1 背景

S3 脚注的排版样式在四页各写一遍内联 `style`，且**四页并不完全一致**（地质/网络用 `margin: 12px 0 0`，电力/驾驶舱用 `margin: 10px 0 0`）：

```
ProfileGeological.vue:431  <p style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
ProfileNetwork.vue:457     <p style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
ProfilePower.vue:432       <p v-if="idleDatasets.length" style="margin: 10px 0 0; font-size: 11.5px; line-height: 1.7">
ProfileFlightdeck.vue:481  <p v-if="idleNames.length" style="margin: 10px 0 0; font-size: 11.5px; line-height: 1.7">
```

另有 `margin-left: 6px`（四页共 5 处，标注标签/名单间隔）与 `margin-left: 8px; color: rgba(220, 234, 255, 0.5)`（地质/网络各 1 处）同属重复内联样式。

### 7.2 精确 diff（提案，**未 apply**）

```diff
--- a/frontend/src/components/dashboard/dash.css
+++ b/frontend/src/components/dashboard/dash.css
@@
+/* 卡片脚注：柱状图/漏斗下方的补充说明行（四页共用） */
+.d-note {
+  margin: 12px 0 0;
+  font-size: 11.5px;
+  line-height: 1.7;
+}
+/* 电力 / 驾驶舱的脚注上间距为 10px，用修饰类保留各自原值 */
+.d-note--tight {
+  margin-top: 10px;
+}
+/* 脚注内的弱化文字（如"已发布合计 x / 草稿合计 y"） */
+.d-note__muted {
+  margin-left: 8px;
+  color: rgba(220, 234, 255, 0.5);
+}
+/* 脚注内相邻片段的小间隔 */
+.d-note__gap {
+  margin-left: 6px;
+}
```

对应本页的用法（同样**未实施**，仅在提案内示意）：

```diff
-    <p style="margin: 12px 0 0; font-size: 11.5px; line-height: 1.7">
+    <p class="d-note">
       <span
         v-if="whiteLying.length"
         class="d-tag d-tag--warn"
       >数据白躺 {{ whiteLying.length }} 份</span>
-      <span v-if="whiteLying.length" style="margin-left: 6px">{{ whiteLying.join('、') }}</span>
-      <span style="margin-left: 8px; color: rgba(220, 234, 255, 0.5)">
+      <span v-if="whiteLying.length" class="d-note__gap">{{ whiteLying.join('、') }}</span>
+      <span class="d-note__muted">
         已发布合计 {{ modelTotals.published }} / 草稿合计 {{ modelTotals.draft }}
       </span>
     </p>
```

### 7.3 影响面

- 需改：`dash.css`（新增 4 个类）+ 四页的脚注模板（本页 1 处 `<p>` + 2 处 `<span>`；另三页由 R1–R3 各自决定是否采纳）。
- 渲染影响：**零**（`--tight` 保留电力/驾驶舱的 `10px`，其余属性逐值相同）。若四页不统一采纳，样式仍保持各自现状。
- 为何不改：`dash.css` 属冻结共享面，且该改动跨四页、跨 agent 写权限。

### 7.4 替代方案（我更倾向的默认选项）

**保持现状**。内联样式只有 3 个属性、只出现在脚注一处，抽象收益有限；而引入 `dash.css` 新类会给"卡片脚注"这一纯排版细节增加跨页耦合，且四页上间距本就有 10/12 两种取值，统一需要额外的修饰类，属于"为一致性付耦合"。

---

## 8. 未解决存疑

1. **S5 成员 >200 时静默少报**（§2 D-1）：真实缺陷，修法必然改渲染 → 交 Lead 决定是"分页拉全"还是"显示 `total` + 截断提示"。当前场景 5 人，未触发。
2. **`risk_rate` 分母为 0 显示 `0.0%`**（§2 D-3）：后端口径问题，需改 `dashboard_service.py`（冻结面）。
3. **未做浏览器复验**（§6.4）：受禁令限制，仅以静态证据 + `vue-tsc` 支撑渲染不变。
4. **`nameOf` 的 `fallback` 参数**（§2 C-6）：当前恒不生效，保留为有意降级；若 Lead 要求"零冗余"，可删（代价是集合不一致时展示名退化为 `logical_id`）。
5. **跨页一致性不属本页范围**：`ProfilePower.vue` 把 `modeling` 收窄成 `ModelingStat[] | null` 并配 `?? 0` 兜底，与"必填"契约不符 —— 由 R2 负责，本报告仅记录。

---

## 9. 声明

**我未修改任何共享面文件。**

本次仅改动 1 个文件：`frontend/src/views/Home/dashboard/sections/ProfileGeological.vue`，外加本报告 `docs/场景管理员首页审查/重构报告/geological.md`（新建目录）。未触碰 `frontend/src/components/dashboard/**`、`frontend/src/api/**`、`AdminProfilePage.vue`、`DashboardHomeView.vue`、另三个 `Profile*.vue`、`backend/**`、`scripts/**`、`frontend/tests/**`、数据库与 `实施契约.md`。

`git status --short`（写入本报告后）：

```
 M frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
 M frontend/src/views/Home/dashboard/sections/ProfileGeological.vue
 M frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue
 M frontend/src/views/Home/dashboard/sections/ProfilePower.vue
?? "docs/全项目代码审查/"
?? "docs/场景管理员首页审查/重构报告/"
```

> 说明：三个 `Profile{Network,Power,Flightdeck}.vue` 与 `docs/全项目代码审查/` 是 R1–R3 的并行改动，非本 agent 所为；本 agent 的改动只有 `ProfileGeological.vue` 与本报告目录。
