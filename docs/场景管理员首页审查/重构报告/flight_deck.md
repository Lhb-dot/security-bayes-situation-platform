# 舰面调度（flight_deck）· 场景管理员首页代码质量重构报告

- **场景**：舰面调度 `flight_deck`（`scenario_id = 3`）
- **路由**：`#/scenarios/3/dashboard` → `DashboardHomeView.vue` → `AdminProfilePage.vue`（SCENARIO_ADMIN 分支）→ `sections/ProfileFlightdeck.vue`
- **本轮唯一改动文件**：`frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue`
- **本报告**：`docs/场景管理员首页审查/重构报告/flight_deck.md`
- **基线**：`HEAD = 2a3c029 feat(dashboard): 四场景场景管理员首页差异化重构`
- **性质**：**代码质量重构**（去弃用写法、去残留死代码、降复杂度）。**不改变任何显示内容**——卡片标题/顺序、列名/列序、KPI 文案与单位、标签文案与配色语义、数字格式、空态文案一律不动。
- **行数**：`537 → 502`（`git diff HEAD --numstat` = `94 insertions(+), 129 deletions(-)`）
- **类型检查**：`npx vue-tsc --noEmit -p tsconfig.app.json` → **EXIT=0**（原始输出为空，见 §5）

---

## 1. 改动摘要（一行一条）

| # | 改动 | 类别 |
|---|------|------|
| 1 | 删除 `getModelVersionList` / `BackendModelVersion` 导入、`models` ref 及其全部兜底逻辑；`loadAll` 由 3 路 `Promise.allSettled` 降为 2 路 | B 死代码 |
| 2 | 删除 `modelingKnown`（恒为 `true`），并删除模板中因此不可达的空态 `<p v-else-if="!modelingKnown" class="d-src">…</p>` | B 死代码 |
| 3 | 删除 `redundancy` 的「前端按 `dataset_file_count / dataset_count` 现算」兜底分支，以及随后只做转发的 `redundancy` computed 包装本身；3 个使用点改为局部 `const stat = props.data.redundancy` | B 死代码 + C 复杂度 |
| 4 | 删除 `RedundancyStat` 类型导入（不再需要显式标注） | B 残留 |
| 5 | `caliber_registered: item.caliber_registered ?? item.is_risk_label` → `item.caliber_registered` | B 死代码 |
| 6 | `groupLabels` 去掉 `group_id` / `fingerprint` 双键登记、`Number(...)` 与 `?? (group.datasets ?? []).length` 兜底，只登记 `group_id` 一个键 | B 死代码 + C 复杂度 |
| 7 | 去掉对**必填**数组/字段的防御式兜底：`props.data.datasets ?? []`、`groups ?? []`、`encoding_family ?? []`、`Number(file_count ?? 0)`、`?? '—'` 等 | B 残留 |
| 8 | 新增 `datasetRows` 作为 S2/S3 共用的**唯一一次** `datasets` 遍历（一次算好展示名与模型覆盖），删除 `modelingRows` 与 `modelTextOf` | C 复杂度 |
| 9 | `modelTextOf` 的 `'—'` 字面量改为返回 `undefined`，交 `DashTable` 统一渲染 `—`（显示一致，少一处硬编码空态） | B 残留 |
| 10 | `trendPoints` 用 `dashFormat.fmtDate` 取代手写 `.slice(5)`，与其余 3 个场景管理员页 + 2 个用户工作台统一 x 轴口径 | A 弃用/重复实现 |
| 11 | 魔法值具名：`MEMBER_PAGE_SIZE`、`ROLE_SCENARIO_ADMIN`、`ROLE_SCENARIO_USER`、`ACCOUNT_STATUS_ACTIVE`（与已重构的 `ProfileNetwork.vue` 同一约定） | C 可读性 |
| 12 | 头部注释订正为「两段数据来源」并写明**为何不再保留兜底**（必填字段 + 后端无条件下发 + 只读探针实测）；关键 computed 补口径注释 | 文档 |

**未改动**：`<template>` 段除第 2 条删除的那一行不可达空态外，与 `HEAD` **逐字节相同**（见 §5.2）。

---

## 2. 逐项审查结论

### A 弃用写法（deprecated idioms）

| 检查项 | 结论 |
|--------|------|
| `console.log` / `debugger` | 无（grep 0 命中） |
| `TODO` / `FIXME` / `XXX` | 无（0 命中） |
| `@ts-ignore` / `@ts-expect-error` / `as any` / `: any` | 无（0 命中）。全文件类型收口在 `FlightdeckProfile` / `FlightdeckWorkspace` / `UserAccount` / `DashColumn` 上 |
| `::v-deep` / `slot-scope` / `.sync` / `$listeners` / `Vue.set` / `beforeDestroy` / `filters`（Vue 2 写法） | 无（0 命中） |
| Element Plus 组件混入（`el-*`） | 无。grep 命中的 2 处 `el-` 是 `label-width` 属性的子串，非组件 |
| 非空断言 `!` | 无。`modelStats` 未命中分支用 `undefined` 表达，而非 `map.get(k)!.total` |
| 手写日期切片替代既有格式化工具 | **有，已修**：`item.date.slice(5)` → `fmtDate(item.date)`（`dashFormat.ts:44`，实现即 `String(value ?? '').slice(5)`，输出逐字符相同，但避免本页自带第二份 MM-DD 口径） |
| `Record<string, unknown>` 行类型（弱类型） | **保留**：这是 `DashTable` 的既有契约（`rows: Array<Record<string, unknown>>`），列语义由 `DashColumn[]` 承担。改为强类型需动共享组件，属共享面，不在本轮范围 |

### B 残留与死代码（residue / dead code）

| 检查项 | 结论 |
|--------|------|
| 旧版已删除卡片遗留的 helpers/常量/类型/导入（`DashRadar`、`fmtNum`、`distanceRows`、`approachRows`、`rangeRows`、`relativeRows`、`fluctuationRows`、`angleBars`、`collisionBars`、`radarSeries`） | 经 grep 全部 0 命中，`HEAD` 版本中即已清理干净，本轮无需再动 |
| `getModelVersionList` 兜底数据源 | **已删**（死分支，裁定见 §2.F1） |
| `models` ref / `BackendModelVersion` 导入 | **已删**（唯一消费者是上一条兜底） |
| `modelingKnown` | **已删**（恒真，见 §2.F1） |
| `modelTextOf` | **已删**（仅被 `assetRows` 使用，且其 `'—'` 语义由 `DashTable` 承担） |
| `modelingRows` | **已删**（仅被 `modelingBars` / `idleNames` 使用；改为直接投影 `datasetRows`，并顺带去掉模板从未使用的 `logical_id` 键） |
| `redundancy` 兜底分支 | **已删**（死分支，见 §2.F3） |
| `caliber_registered ?? is_risk_label` | **已删**（死分支，见 §2.F2） |
| `group_id` / `fingerprint` 双键登记 | **已删**（死分支，见 §2.F4） |
| 只做转发的 `redundancy` computed 包装 | **已删**（原为兜底逻辑的载体，兜底删除后退化为纯转发） |
| 模板不可达空态 `<p v-else-if="!modelingKnown">` | **已删**（随 `modelingKnown` 消失；该文案「模型版本数据未取到，暂不能判定「数据白躺」」在现后端下永不出现） |
| 对必填字段的 `?? []` / `Number(x ?? 0)` / `?? '—'` | **已删 12 处**。依据：`ProfileBase.datasets` / `groups` / `modeling`、`FlightdeckProfile.redundancy`、`DatasetStat.caliber_registered` 在 `dashboardApi.ts` 中均为**非可选**（`strict: true` 下若后端可能不返回，类型就不该这么写）；且父组件 `AdminProfilePage.vue` 仅在 `v-else-if="flightdeckData"` 内渲染本组件，`data` 永不为空 |
| `props.data` 的其他字段（`collision_count` / `distance` / `approach` / `total_distance` / `direction` / `relative_angle` / `distance_curve` / `collision_comparison`） | 本页不使用的**后端**字段，按实施契约 §5.3 有意保留（向后兼容），非前端残留，不动 |

### C 复杂度（unnecessary complexity）

| 检查项 | 结论 |
|--------|------|
| 同一份 `props.data.datasets` 被多个 computed 重复遍历 | **有，已修**：新增 `datasetRows`（唯一一次遍历，产出 `{item, name, model}`），`assetRows` / `modelingBars` / `idleNames` 全部改为对它的投影。此前 `datasets` 被 `displayNames`(×2 趟) + `assetRows` + `modelingRows` 共扫 4 趟，其中展示名与模型数在两处各算一次 |
| 只做转发的一层包装 | **有，已修**：`redundancy` computed 在兜底删除后退化为 `computed(() => props.data.redundancy)`，已删除，3 个使用点各自取局部 `stat` |
| 深层嵌套三元 | 无。全文件三元最深 1 层（`model ? … : undefined`、`item && item.total ? … : null`）。原 `modelingKnown ? … : …` 嵌套已随死代码消失 |
| `Map` / `find` 手写查找 | 保留 3 个 `Map`（`displayNames` / `groupLabels` / `modelStats`）。三者都是「按 key 高频查表」（每个数据集/每行查一次），用 `Map` 比 `array.find` 更直白也更快，非冗余抽象 |
| 重复的「角色计数」逻辑（S5） | 本页内已收敛为 3 个 `filter` + 1 个条件 `push`；跨 4 个场景管理员页的高度相似（`ProfileNetwork` 甚至多一个「未纳入统计」行）属**跨页共性**，抽 composable 需动共享面 → 仅提案（§6 P1），本轮不实施 |
| S4 的 `runtime.value?.summary ?? null` 链 | 保留。`runtime` 为 `null`（接口失败）与 `summary` 为 `null`（后端无运行态）语义不同，需分别驱动 KPI 的 `—` |
| 注释密度 | 本页注释解释**口径与取舍**（为何不兜底、为何不去重展示名、为何未登记数据集不隐藏），不重复代码字面语义；新增注释均为「删除理由」与「契约出处」 |

### D 正确性（correctness）

| 检查项 | 结论 |
|--------|------|
| `Promise.allSettled` 静默降级 | 保留且正确：运行态失败 → `runtime = null` → S4 三 KPI 全 `—`、漏斗与曲线空态；成员失败 → `members = null` → S5 空态。互不影响，也不影响 `/profile` 主画像 |
| `scenario_key === 'flight_deck'` 校验 | 保留。防止响应错位/串场景时把别的场景运行态画到本页（代价仅一次字符串比较） |
| 成员按 `scenario_id` 过滤 | 保留（**不可**改为只依赖服务端过滤）。证据：`backend/app/services/user_service.py:106-107` 只对 `SCENARIO_ADMIN` 自动收窄场景，`SUPER_ADMIN` 会拿到**全平台**账号（`user_routes.py:47` 的 `scenario_id` 参数是可选筛选）。本页对 SUPER_ADMIN 亦可访问，故客户端过滤是必要防线。已在代码注释中写明该理由 |
| 展示名去重（`displayNames`） | 逻辑**活着**：只读探针实测 `Feature2_Cleaning_lisan` 出现 2 次（其中一份与 `carrier_track_company_v1` 同源同内容），两份都会补 `（logical_id）` 后缀，与 `HEAD` 行为逐字相同 |
| `absorbedCount` 的 `Math.max(..., 0)` | 保留。防后端出现 `effective_group_count > file_count` 时显示负数 |
| `memberRows` 的「已禁用账号」条件行 | 保留。`disabled.length` 为 0 时不出行，与 `HEAD` 相同 |
| `DashTable` 空值语义 | 已核对 `DashTable.vue` 的 `asText`：`null` / `undefined` / `''` 一律渲染 `—`。因此 §1 第 9 条（`'—'` → `undefined`）与 §2.F4（去掉 `?? '—'`）**显示结果完全一致** |
| `DashTable` 数值列不加千分位 | **刻意不修**。`DashTable` 对 number 走 `asText` 原样输出（无 `fmtInt`）。给 `record_count` 等加 `fmtInt` 会改变显示（加千分位），违反硬约束 → 仅记录（§6 P3 之外的另一条，不提案，只说明现状） |
| `redundancy_rate` 分母为 0 | **发现真实边界显示问题，未修**（属显示变更，需 Lead 裁定）：`backend/app/services/dashboard_service.py:1851-1853` 在 `file_count == 0` 时返回 `redundancy_rate = 0.0`，本页会渲染「0.0%」而非「—」，语义上会被误读为「无冗余」。一行 diff 提案见 §6 P3 |
| S4「已处置率」分母为 0 | 已正确防御：`item && item.total ? fmtPercent(...) : null` → `—`，不下结论 |

### E 硬约束（hard constraints）

| 约束 | 结论 |
|------|------|
| 骨架 S1→D1★→D2★→S2→S3→S4→S5 顺序 | 未变（模板逐字节比对已证） |
| 卡片标题 / `source` 副标题 | 未变 |
| 列名与列序（D1 8 列、S2 8 列） | 未变（`familyColumns` / `assetColumns` 字面量未改） |
| KPI 文案、单位、`tone`、`sub`、`raw` | 未变（仅数据来源表达式简化） |
| 标签文案与配色（`一致/ok`、`不一致/up`、`未登记风险口径/d-tag--warn`、`数据白躺/d-tag--warn`） | 未变 |
| 数字格式（`fmtPercent` 用于风险占比/冗余率，其余原样） | 未变 |
| 空态文案（`DashTable` 的 `—`、`DashBars`/`DashFunnel` 的「暂无数据」） | 未变；本页自身不再硬编码 `'—'`，改由 `DashTable` 统一产出 |
| 未登记风险口径的数据集**不得过滤**（契约 §0.1） | 未变：`assetRows` 仍全量输出，`#label_field` 插槽仍按 `caliber_registered === false` 挂黄标签 |
| `defineProps` 签名 | 未变（`{ data: FlightdeckProfile }`） |
| 是否必须改共享面 | **不需要**。全部改动落在本文件内 |

### F 回退分支可达性裁定（活/死 + 证据）

判定依据三层：① TS 类型是否必填；② 后端是否**无条件**下发；③ 只读探针实测（SCENARIO_ADMIN `zs`，`scenario_id=3`）。

**F1 `getModelVersionList` 兜底（原 `models` ref + `modelStats` 的 `else` 分支 + `modelingKnown`）→ 死**

- 类型：`ProfileBase.modeling: ModelingStat[]`（`dashboardApi.ts:153`）**非可选**。
- 后端：`dashboard_service.py:1386` `"modeling": modeling` 位于 `get_profile` 的返回体构造中，**无条件**执行（无 `if` 包裹）。
- 探针：`[modeling] present=True is_list=True`，4 个数据集 → 4 行 `[{carrier_feature2_biaoqian,3,1,4},{carrier_feature2_lisan,0,1,1},{carrier_paired_trail,0,1,1},{carrier_track_company_v1,0,0,0}]`。
- 旁证：同批重构的 `ProfileGeological.vue:54-59` 已删除同一兜底并注明「模型数不再单独请求 modelVersionApi —— 后端画像已直接下发 `modeling`」。
- 结论：`Array.isArray(props.data.modeling)` 恒真 → `modelingKnown` 恒真 → `models.value !== null` 分支与模板 `v-else-if="!modelingKnown"` 均**不可达**。删除后 `modelingBars` 的 `[]` 退化分支与空态文案一并消失，现网显示不变。

**F2 `caliber_registered ?? is_risk_label` → 死**

- 类型：`DatasetStat.caliber_registered: boolean`（`dashboardApi.ts:58`）**必填**（`is_risk_label` 在 `:33` 亦为必填）。
- 后端：`dashboard_service.py` 的 `describe` 中 `:883` `"is_risk_label": registered` 与 `:899` `"caliber_registered": registered` 取**同一个局部变量**。
- 探针：`caliber_registered present for all: True`，`caliber_registered == is_risk_label for all: True`。
- 结论：两者恒等，`??` 右侧永不生效 → **死**。删除后本文件已无 `is_risk_label` 的代码引用（仅注释引用）。

**F3 `redundancy` 现算兜底 → 死**

- 类型：`FlightdeckProfile.redundancy: RedundancyStat`（`dashboardApi.ts:306`）**必填**。
- 后端：`_flight_profile` 中 `"redundancy": cls._flight_redundancy(...)`（`dashboard_service.py:~1786`）**无条件**下发。
- 探针：`[redundancy] present=True` → `{"file_count":4,"effective_group_count":1,"redundancy_rate":0.75,"raw_samples":2028,"deduped_samples":507}`（五字段齐全，数值自洽：`1 - 1/4 = 0.75`）。
- 结论：`if (raw) return raw;` 恒命中，兜底分支**不可达** → **死**。且该兜底是同一公式的第二份实现（`raw_samples` / `deduped_samples` 都用 `sample_count` 近似），保留只会在口径漂移时给出与后端不一致的数。

**F4 `groups[].group_id` / `groups[].fingerprint` 双键登记（及 `familyRows` 的 `?? '—'`）→ 死**

- 后端：`dashboard_service.py:1375` `"group_id": group_key` 与 `:1381` `"fingerprint": group_key` 同源同值。
- 探针：`[groups] group_id==fingerprint for all: True`；唯一组 `{group_id/fingerprint: "carrier_shared_source", file_count: 4, datasets:[biaoqian, lisan, paired_trail, track_company_v1]}`。
- 结论：双键登记是同一个键写两遍 → **死**。`?? '—'` 亦为死分支（`source_group` 为 `string`，且 `DashTable` 已把 `''` 渲染成 `—`）。
- **保留**：`groupLabels.value.get(row.source_group) ?? row.source_group` 的 Map 未命中回退——这是**廉价防御**（`groups` 若因数据异常缺某组，至少仍显示原始 key，同组同值不丢信息），不是替代数据源。已在代码注释中说明。

**F5 `modelStats` 未命中的 ternary（`model ? … : undefined`）→ 实际不可达，保留为廉价防御**

- 后端 `_modeling_stats`（`dashboard_service.py:1405` 起）对**每一个** dataset 追加一行：`total, published = by_dataset.get(item.id, (0, 0))`，即无模型的数据集也产出 `total=0` 的行。
- 探针：4 个数据集 ↔ 4 行 modeling，一一对应。
- 结论：Map 未命中在实际数据下不发生。但 `Map.get` 的 `undefined` 是类型系统要求处理的分支（不用 `!` 断言），保留成本为一个三元表达式，且语义正确（显示 `—` 而非假装 0）。**保留，非死代码**。

**F6 `encoding_family[].collision_consistent === false` 的红色分支 → 数据相关，保留**

- 探针：4 行全部 `collision_consistent = true`，故当前**未触发**。
- 结论：这是**数据相关**分支（同源组内标签口径不一致时才出现），不是代码死分支，属该表的核心管理信号，**必须保留**。

---

## 3. 删除证据（grep 零引用）

| 删除物 | 删除前引用位置 | 删除后 grep 结果 |
|--------|----------------|------------------|
| `getModelVersionList` | 仅 `loadAll`（本文件 1 处） | `frontend/src` 内仅剩 `api/modelVersionApi.ts`（定义）与 `views/Model/ModelCenter.vue`、`views/Model/RiskInference.vue`（业务使用）→ **dashboard 目录 0 命中**；`modelVersionApi.ts` 未成孤儿模块 |
| `BackendModelVersion` | 仅 `models` ref 类型（本文件 1 处） | 同上（本文件 0 命中） |
| `modelingKnown` | `modelStats` / `assetRows` / `modelingBars` / `idleNames` / 模板 `v-else-if`（本文件 5 处） | 全仓 **0 命中** |
| `modelTextOf` | 仅 `assetRows`（本文件 1 处） | 全仓 **0 命中** |
| `modelingRows` | `modelingBars` / `idleNames`（本文件 2 处） | 本文件 **0 命中**（`ProfileGeological.vue:302` 是同名**局部** computed，属他人文件、独立存在，非我引入） |
| `is_risk_label`（代码引用） | `assetRows` 的 `??` 右侧（本文件 1 处） | 本文件 **0 处代码引用**；`dashboardApi.ts:33` 仍保留类型声明（共享面，见 §6 P2）；其余 3 个 Profile 页仅注释提及 |
| `RedundancyStat` | 本文件导入 + `computed<RedundancyStat>` 标注 | 本文件 **0 命中**；`dashboardApi.ts:280`（定义）与 `:306`（`FlightdeckProfile` 字段）仍在用 → 类型本身未成孤儿，**未删**（共享面） |
| `fmtDate` | — | 已存在于 `dashFormat.ts:44`，被 4 个 Profile 页 + 2 个 Workspace 页使用 → **复用既有工具，未新增共享代码** |
| 旧版研判图遗留（`DashRadar` / `fmtNum` / `radarSeries` 等 10 项） | `HEAD` 中已无 | 全仓 **0 命中**（`HEAD` 即已清理，本轮无操作） |
| 弃用写法（`console.log`/`TODO`/`FIXME`/`@ts-`/`any`/`::v-deep`/`slot-scope`/`.sync`/`$listeners`/`Vue.set`/`beforeDestroy`/`filters`） | — | 本文件 **0 命中** |

---

## 4. 函数清单（重构后，行号对应最终文件）

| 行 | 名称 | 类型 | 计算内容 / 职责 | 依据字段（后端） |
|----|------|------|------------------|------------------|
| 40 | `props` | `defineProps` | `{ data: FlightdeckProfile }`，父组件在 `v-else-if="flightdeckData"` 内渲染，故 `data` 永不为空 | `GET /api/v1/scenarios/{id}/profile` |
| 47 | `MEMBER_PAGE_SIZE` | 常量 `200` | 成员接口单页上限（后端硬上限 200，`user_service.py:124`） | `/users` `page_size` |
| 49 | `ROLE_SCENARIO_ADMIN` | 常量 | 账号角色字面量，S5 分类用 | `AppUser.role` |
| 50 | `ROLE_SCENARIO_USER` | 常量 | 同上 | `AppUser.role` |
| 52 | `ACCOUNT_STATUS_ACTIVE` | 常量 `'active'` | 「已禁用」判定基准 | `AppUser.status` |
| 58 | `runtime` | `ref` | 运行态水位；`null` = 未取到 | `GET /api/v1/scenarios/{id}/workspace` |
| 60 | `members` | `ref` | 本场景账号；`null` = 未取到（区别于「确实 0 人」） | `GET /api/v1/users` |
| 68 | `loadAll` | async 函数 | 2 路 `Promise.allSettled` 并行取运行态与账号，各自静默降级；运行态校验 `scenario_key === 'flight_deck'`；账号按 `scenario_id` 收窄（服务端只对 SCENARIO_ADMIN 收窄，SUPER_ADMIN 需客户端过滤） | `/workspace`、`/users` |
| 86 | `watch` | 侦听 | `props.data.scenario_id` 变化 → 重取额外两接口 | — |
| 87 | `onMounted` | 生命周期 | 首次挂载即取 | — |
| 100 | `displayNames` | computed `Map` | 数据集展示名去重：重名（同源副本）补 `（logical_id）`。探针实测 `Feature2_Cleaning_lisan` 重复 → 该逻辑**活着** | `datasets[].name` / `logical_id` |
| 114 | `nameOf` | 函数 | 展示名查表，未命中回退 `logical_id` | 同上 |
| 117 | `ENCODING_TEXT` | 常量 Map | 编码形态中文：`numeric/interval/paired/unknown` | `encoding_family[].encoding` |
| 125 | `VISIBILITY_TEXT` | 常量 Map | 可见性中文：`platform/company/personal` | `datasets[].visibility` |
| 142 | `assetKpis` | computed `KpiItem[4]` | S1：有效数据集数（含文件数副标题）、有效样本总量、统一风险占比、**同源冗余率** | `dataset_count` / `dataset_file_count` / `sample_count` / `risk_rate` / `risk_count` / `redundancy.*` |
| 189 | `groupLabels` | computed `Map` | 同源组 → `G{n} · {file_count} 份` 可读组名 | `groups[].group_id` / `file_count` |
| 197 | `familyColumns` | 常量 `DashColumn[8]` | D1 列定义（数据集/同源组/编码形态/字段数/样本量/正类数/正类一致性/已发布模型数） | — |
| 215 | `familyRows` | computed | D1 逐行：组名映射、编码中文、正类一致性标签（`一致/ok`、`不一致/up`） | `encoding_family[]`（`logical_id`/`source_group`/`encoding`/`attribute_count`/`record_count`/`risk_count`/`collision_consistent`/`published_model_count`） |
| 239 | `absorbedCount` | computed | 被同源吸收的数据集数 = 文件数 − 有效数据集数，下界 0 | `redundancy.file_count` / `effective_group_count` |
| 244 | `redundancyKpis` | computed `KpiItem[4]` | D2：同源冗余率、去重前样本、去重后样本、被吸收数据集数 | `redundancy.*` |
| 279 | `groupBars` | computed | D2 每同源组一根柱：标签 = 组内展示名以 ` / ` 连接，值 = 物理文件数 | `groups[].datasets` / `file_count` |
| 294 | `modelStats` | computed `Map` | `logical_id → {published,total}` | `modeling[].logical_id` / `published` / `total` |
| 307 | `datasetRows` | computed | **S2/S3 共用的唯一一次 `datasets` 遍历**：一次产出 `{item, name, model}`，下游只做投影 | `datasets[]` + `modeling[]` + `displayNames` |
| 315 | `assetColumns` | 常量 `DashColumn[8]` | S2 列定义（数据集名/样本量/标签字段/风险占比/字段数/可见性/已发布模型数/版本） | — |
| 334 | `assetRows` | computed | S2 行：`caliber_registered` 原值（供插槽挂「未登记风险口径」黄标签）、`fmtPercent(risk_rate)`、可见性中文、模型文案、`v{version}`；模型缺失给 `undefined` → `DashTable` 渲染 `—` | `datasets[]` |
| 350 | `modelingBars` | computed | S3 每数据集一根柱 = 模型版本总数（含草稿），行序同 S2/D1 | `modeling[].total` |
| 355 | `idleNames` | computed | 「数据白躺」= 模型版本总数为 0 的数据集展示名 | `modeling[].total` |
| 363 | `summary` | computed | 运行态摘要；`null` = 未取到 | `workspace.summary` |
| 366 | `trendTotal` | computed | 近 10 天推理量合计（与曲线同口径求和） | `workspace.activity_trend[].total` |
| 370 | `runtimeKpis` | computed `KpiItem[3]` | S4：待处置积压、已处置率（分母 0 → `—`）、近 10 天活动 | `summary.pending` / `resolved` / `total` |
| 399 | `funnelItems` | computed | 处置漏斗：待处置 → 处理中 → 已处置 | `summary.status_funnel[].label/count` |
| 404 | `trendPoints` | computed | 近 10 天曲线：x 轴 `fmtDate(date)`（MM-DD）、`value=total`、`value2=risk` | `workspace.activity_trend[].date/total/risk` |
| 417 | `memberRows` | computed | S5：场景管理员 / 场景用户 / 合计 人；`disabled>0` 时追加「已禁用账号」行 | `/users` `items[].role` / `status` / `scenario_id` |
| 模板 | `#label_field` 插槽 | 插槽 | `row.caliber_registered === false` → 追加 `d-tag d-tag--warn`「未登记风险口径」 | `datasets[].caliber_registered` |

**已消失的函数/常量**（连同其职责）：`models`、`modelingKnown`、`modelTextOf`、`modelingRows`、`redundancy`（computed 包装）。职责均有等价承接：`models`→`modeling` 字段；`modelingKnown`→恒真；`modelTextOf`→`assetRows` 内联 + `DashTable` 空值；`modelingRows`→`datasetRows`；`redundancy`→`props.data.redundancy` 直接访问。

---

## 5. 行为不变证明

### 5.1 类型检查（原始输出 + 退出码）

命令（在 `frontend/` 下执行，符合本轮允许的命令清单）：

```
npx vue-tsc --noEmit -p tsconfig.app.json
```

**原始输出**：无（stdout/stderr 均为空，无任何 error/warning 行）
**EXIT=0**

执行两次，结果一致：
1. 主重构完成后 → EXIT=0；
2. 最后 3 处收尾编辑（删除 `redundancy` 转发包装、`absorbedCount` / `redundancyKpis` 改局部 `stat`）后复跑 → EXIT=0。

> 说明：`tsconfig.app.json` 开启 `strict` / `noUnusedLocals` / `noUnusedParameters`。因此「删除后仍 0 error」同时证明了：① 类型收窄正确（去掉 `?? []` / `Number(...)` 后未产生 `possibly undefined` 报错）；② 无遗留未使用导入/局部变量（`RedundancyStat`、`models` 等若未清干净会直接报 `noUnusedLocals`）。

### 5.2 渲染不变（模板逐字节比对）

- 文件行数：`537 → 502`；`git diff HEAD --numstat` = `94 insertions(+), 129 deletions(-)`（537 − 129 + 94 = 502 ✓）。
- hunk 分布：`git diff -U0` 共 40 个 hunk，其中**落在 `<template>` 段的只有 1 个**：`@@ -519 +484,0 @@`，内容为删除 `<p v-else-if="!modelingKnown" class="d-src">模型版本数据未取到，暂不能判定「数据白躺」</p>`（该行由 §2.F1 判定为不可达）。其余 39 个 hunk 全部位于 `<script>` 段（原文件行号 ≤ 460）。
- 结论：卡片集合与顺序、`title` / `source` 文案、`DashTable` 的 `columns`/`rows`/`row-key`/`dense`、插槽名与插槽内容、KPI/柱/漏斗/曲线/行的绑定与静态属性、空态结构——**逐字节相同**。

### 5.3 数值口径不变（只读探针交叉验证）

以 SCENARIO_ADMIN `zs`（`user_id=13`，`scenario_id=3`）实测数据逐项对照重构前后的表达式：

| 显示项 | 后端实测 | 重构前表达式 | 重构后表达式 | 输出 |
|--------|----------|--------------|--------------|------|
| 有效数据集数 | `dataset_count=1` | `props.data.dataset_count` | 同 | `1 个` |
| 同源冗余率（S1/D2） | `redundancy_rate=0.75` | 兜底命中 → `fmtPercent(raw)` | `fmtPercent(stat.redundancy_rate)` | `75.0%` |
| 被吸收数据集数 | `4 − 1` | `Number(4)−Number(1)` | `4 − 1` | `3 个` |
| 同源组名 | `group_id=fingerprint=carrier_shared_source`, `file_count=4` | 双键写入同值 | 单键写入 | `G1 · 4 份` |
| D1 同源组列 | `source_group=carrier_shared_source` | Map 命中 | Map 命中 | `G1 · 4 份` |
| 已发布模型数（S2） | `carrier_feature2_biaoqian: 3/4` | `modelingKnown=true` → `modelTextOf` | `model ? … : undefined` | `已发布 3 / 共 4` |
| 数据白躺（S3） | `lisan/paired_trail/track_company_v1: total=0` | `modelingRows.filter(total===0)` | `datasetRows.filter(model?.total ?? 0 === 0)` | `数据白躺 3 份` + 3 个名字 |
| 近 10 天曲线 x 轴 | `date="2025-xx-xx"` | `item.date.slice(5)` | `fmtDate(item.date)` = `String(date).slice(5)` | `xx-xx`（同） |
| 成员分组 | 本场景 2 个账号 | 按 `role` 过滤 + `disabled` 条件行 | 同（仅字面量具名） | 文案与行数同 |

> 探针为**只读 SELECT**（`backend/app/db.py` → `127.0.0.1:5432/situation_platform`），未写库；本轮未启动/停止任何服务，未执行 `pytest` / `npm run build` / `vite build`，未写 `frontend/dist`、`.vite`、`*.tsbuildinfo`。

---

## 6. 共享面提案（**均未实施**）

### P1 跨页共性：S4/S5 抽 `useScenarioRuntime` composable（建议但不实施）

**动机**：4 个场景管理员页的 S4（`summary` / `trendTotal` / `runtimeKpis` / `funnelItems` / `trendPoints`）与 S5（`memberRows`）逻辑高度同构，本页 S5 与 `ProfileNetwork.vue:401-421` 几乎逐行相同（后者多一行「未纳入统计」）。抽共享 composable 可消除 4 份复制。

**精确 diff（提案，未应用）**——新增 `frontend/src/composables/useScenarioRuntime.ts`：

```ts
// 新增文件（共享面）：frontend/src/composables/useScenarioRuntime.ts
import { computed, onMounted, ref, watch, type Ref } from 'vue';
import { getScenarioWorkspace, type WorkspaceBase } from '@/api/dashboardApi';
import { getUserList } from '@/api/userApi';
import type { UserAccount } from '@/types/security';
import { fmtDate, fmtPercent } from '@/components/dashboard/dashFormat';

const MEMBER_PAGE_SIZE = 200;
const ROLE_SCENARIO_ADMIN = 'SCENARIO_ADMIN';
const ROLE_SCENARIO_USER = 'SCENARIO_USER';
const ACCOUNT_STATUS_ACTIVE = 'active';

export function useScenarioRuntime(scenarioId: Ref<number>) {
  const runtime = ref<WorkspaceBase | null>(null);
  const members = ref<UserAccount[] | null>(null);
  const loadAll = async () => {
    const [r, m] = await Promise.allSettled([
      getScenarioWorkspace(scenarioId.value),
      getUserList({ page_size: MEMBER_PAGE_SIZE }),
    ]);
    runtime.value = r.status === 'fulfilled' ? r.value : null;
    members.value =
      m.status === 'fulfilled'
        ? m.value.items.filter((item) => item.scenario_id === scenarioId.value)
        : null;
  };
  watch(scenarioId, loadAll);
  onMounted(loadAll);

  const summary = computed(() => runtime.value?.summary ?? null);
  const trendTotal = computed(() =>
    (runtime.value?.activity_trend ?? []).reduce((s, p) => s + Number(p.total ?? 0), 0),
  );
  const runtimeKpis = computed(() => {
    const item = summary.value;
    return [
      { label: '待处置积压', value: item ? item.pending : null, unit: '条', tone: 'danger' as const, sub: '全场景待处置风险事件' },
      { label: '已处置率', value: item && item.total ? fmtPercent(item.resolved / item.total) : null, tone: 'success' as const, raw: true, sub: '已处置 / 事件总数' },
      { label: '近 10 天活动', value: runtime.value ? trendTotal.value : null, unit: '次', tone: 'primary' as const, sub: '近 10 天风险推理调用合计' },
    ];
  });
  const funnelItems = computed(() =>
    (summary.value?.status_funnel ?? []).map((i) => ({ label: i.label, count: i.count })),
  );
  const trendPoints = computed(() =>
    (runtime.value?.activity_trend ?? []).map((i) => ({ label: fmtDate(i.date), value: i.total, value2: i.risk })),
  );
  const memberRows = computed(() => {
    const list = members.value;
    if (list === null) return [];
    const rows: Array<{ label: string; value: string }> = [
      { label: '场景管理员', value: `${list.filter((i) => i.role === ROLE_SCENARIO_ADMIN).length} 人` },
      { label: '场景用户', value: `${list.filter((i) => i.role === ROLE_SCENARIO_USER).length} 人` },
      { label: '合计', value: `${list.length} 人` },
    ];
    const disabled = list.filter((i) => i.status !== ACCOUNT_STATUS_ACTIVE).length;
    if (disabled) rows.push({ label: '已禁用账号', value: `${disabled} 人` });
    return rows;
  });
  return { runtime, members, summary, trendTotal, runtimeKpis, funnelItems, trendPoints, memberRows };
}
```

本文件侧对应替换（4 个 Profile 页各一次，示意）：

```diff
-import { computed, onMounted, ref, watch } from 'vue';
-import { getScenarioWorkspace, type FlightdeckProfile, type FlightdeckWorkspace } from '@/api/dashboardApi';
-import { getUserList } from '@/api/userApi';
-import type { UserAccount } from '@/types/security';
+import { computed } from 'vue';
+import type { FlightdeckProfile } from '@/api/dashboardApi';
+import { useScenarioRuntime } from '@/composables/useScenarioRuntime';
@@
-const runtime = ref<FlightdeckWorkspace | null>(null);
-const members = ref<UserAccount[] | null>(null);
-const loadAll = async () => { /* … 15 行 … */ };
-watch(() => props.data.scenario_id, loadAll);
-onMounted(loadAll);
+const scenarioId = computed(() => props.data.scenario_id);
+const { runtimeKpis, funnelItems, trendPoints, memberRows } = useScenarioRuntime(scenarioId);
```

**影响**：4 个 `Profile*.vue` 各减约 45 行 + 新增 1 个共享文件。
**为何本轮不做**：① 触碰共享面（新增 composable）并跨 4 个 agent 的独占文件（`ProfileNetwork/Geological/Power.vue` 属其他 agent，写入即冲突）；② 四页 S5 文案存在**已知差异**（`ProfileNetwork` 的「未纳入统计」行、本页的「已禁用账号」），统一口径会**改变显示**，违反本轮硬约束；③ 本页对运行态做 `scenario_key` 校验而 `ProfileNetwork` 不做，统一需裁定哪一种是正确口径（见 §7）。

### P2 共享类型清理：`DatasetStat.is_risk_label` 已无代码引用（提案，未实施）

**现状**：`frontend/src/api/dashboardApi.ts:33` 仍声明 `is_risk_label: boolean`；4 个 Profile 页重构后均只以注释形式提及它（本文件 §2.F2 已删除其唯一代码使用点）。

**提案 diff**：

```diff
--- a/frontend/src/api/dashboardApi.ts
+++ b/frontend/src/api/dashboardApi.ts
@@ -31,8 +31,6 @@ export interface DatasetStat {
   label_field: string;
   /** 该数据集是否已登记风险口径（与 caliber_registered 同值，保留仅为兼容） */
-  is_risk_label: boolean;
   /** 是否已登记风险口径 */
   caliber_registered: boolean;
```

**为何不做**：共享面（`dashboardApi.ts`），且需确认后端 `describe` 是否仍需输出该字段（后端 `:883` 目前无条件输出，删前端类型不影响运行）。属「可选清理」，需 Lead 决定是否连同后端一起收。

### P3 真实边界显示问题：`file_count == 0` 时冗余率渲染成 `0.0%`（提案，未实施）

**证据**：`backend/app/services/dashboard_service.py:1851-1853`

```python
redundancy_rate = round(1 - effective_group_count / file_count, 4) if file_count else 0.0
```

即 `file_count == 0`（无文件）时后端给 `0.0`，本页 `fmtPercent(0)` → **`0.0%`**，读者会理解为「零冗余」而非「无数据可算」。

**提案 diff（本文件内，一行）**：

```diff
--- a/frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
+++ b/frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
@@ -167,7 +167,7 @@
     {
       label: '同源冗余率',
-      value: fmtPercent(stat.redundancy_rate),
+      value: stat.file_count > 0 ? fmtPercent(stat.redundancy_rate) : null,
       tone: 'warning' as const,
       raw: true,
```

（`DashKpis` 在 `raw: true` 时渲染 `item.value ?? '—'`，`null` 即 `—`。）

**为何不做**：这是**显示变更**，违反本轮硬约束「渲染必须逐字节不变」；且 S1 与 D2 两处都要改才一致。**提请 Lead 裁定**：若认可，建议改**后端**（`file_count == 0` 时下发 `null`）以免四页各自打补丁。同类：D2 的「去重前/后样本」在无文件时也会显示 `0 条`（语义正确，无需改）。

### P4 成员列表分页截断（提案，未实施）

**现状**：`getUserList({ page_size: 200 })` 取单页（后端硬上限 200，`user_service.py:124`）。SCENARIO_ADMIN 视角下服务端已收窄到本场景，200 足够；但 **SUPER_ADMIN** 视角下服务端返回全平台账号，>200 时 S5 会静默少算且无提示。`ProfileNetwork.vue:415-419` 已用「未纳入统计」行显式披露该情况。

**提案**：本页 S5 增补同样的「未纳入统计」行（需同时取 `total`）。**为何不做**：会**新增一行显示**，违反硬约束；且属跨页共性，宜随 P1 一起统一。

### P5 `sources` 字段后端下发但 TS 类型未声明（观察，未实施）

后端 `get_profile` 返回体含 `sources`，`ProfileBase` 未声明该字段（本页不用）。补类型属共享面且无消费方，不做。仅记录以备后续审查。

### P6 `scenario_key` 校验口径跨页不一致（观察，未实施）

本页在 `loadAll` 中校验 `runtime.scenario_key === 'flight_deck'`（不一致则整块显示 `—`）；`ProfileNetwork.vue:72-76` 的注释明确主张**不校验**（「多一层 key 校验只会在后端换 key 时把整块静默变空」），并因此改用 `WorkspaceBase` 类型。

**裁定建议**：两者各有权衡（本页防串场景，Network 页防静默空白）。本轮**保持本页现状**（不校验会导致 `as FlightdeckWorkspace` 断言风险，且校验是既有行为，改动即行为变更）。建议随 P1 统一。

---

## 7. 未解决 / 存疑

1. **未做真实浏览器回归**：本轮禁止 `npm run build` / `vite build` / 启停服务，故未在 `#/scenarios/3/dashboard` 上做像素级复核。渲染等价性由三重证据支撑：① 模板逐字节比对（§5.2）；② `vue-tsc` EXIT=0（§5.1）；③ 只读探针逐项对照表达式（§5.3）。若 Lead 需要，建议在合并后由统一回归环节复核。
2. **探针样本有限**：仅覆盖 `scenario_id=3`（1 个同源组、4 个数据集、4 行 modeling）。「死分支」裁定同时依赖**后端代码的无条件性**（`dashboard_service.py:1386` / `:1786` / `:1375`+`:1381` / `:883`+`:899`），已逐行核对；但未穷举全部场景数据。
3. **`collision_consistent === false` 分支**：当前数据下不触发（探针 4/4 为 `true`），保留为数据相关分支（§2.F6）。无法用现有数据验证其渲染。
4. **`modelStats` Map 未命中分支**：后端保证每数据集一行（`_modeling_stats`），实际不可达；保留为廉价防御（§2.F5）。这是「不可达但成本极低」的取舍，非替代数据源。
5. **`DashTable` 数值列不加千分位**：`record_count` 等大数（如 `2028`）原样输出。加 `fmtInt` 会更美观但**改变显示**，本轮不做，也未提案（属共享组件语义，需产品裁定）。
6. **`redundancy_rate` 分母为 0**（§6 P3）与**成员分页截断**（§6 P4）：均为**真实问题**，因涉及显示变更而**未修**，提请 Lead 裁定。
7. **后端 `/users` 的 `scenario_id` 筛选参数未被本页使用**：本页保留客户端过滤（理由见 §2.D）。若未来统一改为服务端筛选，需注意 SUPER_ADMIN 场景（`user_service.py:106-107` 只对 SCENARIO_ADMIN 自动收窄）。

---

## 8. 收尾声明

**我未修改任何共享面文件。**

本轮仅写入 2 个文件：
1. `frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue`（本场景独占，F3 写入范围）
2. `docs/场景管理员首页审查/重构报告/flight_deck.md`（本报告）

未触碰（只读引用/核对）：`frontend/src/components/dashboard/**`（`DashTable.vue` / `DashKpis.vue` / `DashCard.vue` / `DashBars.vue` / `DashFunnel.vue` / `DashLine.vue` / `DashRows.vue` / `dashFormat.ts` / `dash.css`）、`frontend/src/api/dashboardApi.ts`、`frontend/src/api/modelVersionApi.ts`、`frontend/src/api/userApi.ts`、`frontend/src/types/security.ts`、`AdminProfilePage.vue`、`DashboardHomeView.vue`、其他三个 `Profile*.vue`、`backend/**`、`scripts/**`、`frontend/tests/**`、数据库、`docs/场景管理员首页审查/实施契约.md`。

`git status --short`（写入本报告后立即执行，逐字输出）：

```
 M frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
 M frontend/src/views/Home/dashboard/sections/ProfileGeological.vue
 M frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue
 M frontend/src/views/Home/dashboard/sections/ProfilePower.vue
?? docs/全项目代码审查/
?? docs/场景管理员首页审查/重构报告/
```

- 第 1 行 = 本轮的 `ProfileFlightdeck.vue`。
- 第 2–4 行 = 另外三个 agent 各自独占的 `Profile*.vue`（非我改动）。
- `docs/全项目代码审查/` 与 `docs/场景管理员首页审查/` 下的其他新增文件非我创建（本报告位于后者目录内）。

**未执行**（按本轮禁令）：`npm run build`、`vite build`、`npx vite`、任何服务启停（含 uvicorn）、`pytest`、任何写 `frontend/dist` / `frontend/node_modules/.vite` / `*.tsbuildinfo` 的命令、任何写库命令。
**已执行且要求执行**：`npx vue-tsc --noEmit -p tsconfig.app.json`（EXIT=0，两次）、`git diff` / `git status` / `git show`（只读）、`grep`（只读）、后端只读 SELECT 探针（只读）。
