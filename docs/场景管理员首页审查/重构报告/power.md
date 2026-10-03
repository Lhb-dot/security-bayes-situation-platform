# ProfilePower.vue 重构报告（电力系统 · 场景管理员首页）

- **文件**：`frontend/src/views/Home/dashboard/sections/ProfilePower.vue`
- **路由**：`#/scenarios/2/dashboard`（SCENARIO_ADMIN）
- **渲染链**：`DashboardHomeView.vue` → `AdminProfilePage.vue` → `sections/ProfilePower.vue`
- **基线**：HEAD `2a3c029`（重构前 459 行 → 重构后 421 行，净 **−38 行**；`git diff --numstat` = `+104 / −110`）
- **骨架未动**：S1 KPI×4 → D1★ → D2★ → S2 数据集明细 → S3 建模覆盖 → S4 运行态（DashKpis×3 + DashFunnel + DashLine）→ S5 成员与权限
- **类型检查**：`npx vue-tsc --noEmit -p tsconfig.app.json` → 无输出、`EXIT=0`（连续两次）

---

## 1. 改动摘要

| # | 改动 | 一句话说明 |
|---|---|---|
| 1 | 删除 `telemetry` / `componentMatrix` / `modeling` 三个包装 computed | `PowerProfile` 的 `telemetry_by_dataset` / `component_matrix` / `modeling` 都是**必填**字段（`dashboardApi.ts:153/252/254`），包装层只做 `?? []` 与三态判断，改为直接读 `props.data.*` |
| 2 | 删除 `modeling === null` 三态语义 | 后端 `get_profile` **无条件**下发 `modeling`（`dashboard_service.py:1386`）且每个可见数据集必有一行（`_modeling_stats` :1405-1434），三态分支不可达 |
| 3 | 删除随之不可达的 3 处假告警分支 | `s2Rows` 的 `model_count: null`、`modelingBars`/`idleDatasets` 的 `[]` —— 这些分支会把「没取到」渲染成「0 个模型 → 数据白躺」 |
| 4 | 新增 `datasetRows` 单一基底行 computed | `props.data.datasets` 由「S2 与 S3 各遍历一次 + 各自查一次 modelingMap」收敛为**只遍历一次**，S2 表格与 S3 柱状图/白躺清单都由它派生 |
| 5 | 重写 `displayNames` | 去掉与 `datasets` **位置耦合**的并行 `names` 数组（`names[index]`），改为单次计数 Map + 单次映射 |
| 6 | 提取具名常量 `SCENARIO_KEY` / `PARAM_KEYS` / `BASELINE_SOURCE` | 分别取代内联 `'power'`、三个内联后端参数 key、模板里内联的基线长文案 |
| 7 | `VISIBILITY_TEXT` 集中到「口径常量」区 | 值未变，只挪位置并补注释（后端存英文枚举，管理端要能直接读） |
| 8 | 复用共享格式化 `fmtDate` | `trendPoints` 的 `item.date.slice(5)` → `fmtDate(item.date)`；后端 `date.isoformat()` 恒为 `YYYY-MM-DD`，输出逐字节相同 |
| 9 | 删除 4 处冗余 `Number(x)` 强制转换 + 1 处不可达 `Number.isFinite` 分支 | 字段类型已是 `number`；`fmtNum` 内部已做 `Number()`+`isFinite` |
| 10 | 删除 7 处不可达的 `?? '—'` / `?? []` 兜底 | 必填字段无需兜底；`?? '—'`（visibility）对任意 string 恒不可达 |
| 11 | `memberRows` 用计数替代三个中间过滤数组 | 原先 `filter` 出 3 个数组只取 `.length` |
| 12 | 导入清理 | 删 `ComponentMatrixRow` / `ModelingStat`（不再需要），加 `fmtDate` |

---

## 2. 逐项审查结论

### A. 弃用写法

| 项 | 结论 | 依据 |
|---|---|---|
| A1 Vue 2 已删 API（`filters` / `$listeners` / `v-on.native` / `beforeDestroy` / `Vue.set` / `::v-deep` / `v-deep`） | **无** | 对本文件 grep 该 7 个模式：0 命中 |
| A2 Element Plus 弃用组件/属性 | **无** | 本文件不引入任何 Element Plus 组件（grep `el-`：0 命中），全部使用共享 `DashX` 组件与原生标签 |
| A3 项目内已弃用字段/组件 | **无** | `is_risk_label` 0 命中；`getModelVersionList` 0 命中；弃用组件 `DashDonut` / `DashColumns` / `DashRadar` 0 命中；`recent_events` **仅出现在注释**（第 371 行「不渲染 recent_events，那是执行端派活清单」），代码 0 引用 |
| A4 TS 逃逸写法（`any` / `as any` / `@ts-ignore` / `@ts-expect-error` / 非空断言 `!`） | **无** | grep `\bany\b`、`as any`、`@ts-`：0 命中；非空断言正则（标识符/`)`/`]` 后紧跟 `!` 且非 `!=`）：0 命中 |
| A5 `Number(x) || 0` 这类「用真值兜底掩盖类型」的写法 | **已删除 4 处** | 旧 102/105/339 行与 `Number(param.mean)`（旧 166）；字段类型已是 `number`，`|| 0` 会把合法的 `0` 与「非数值」混为一谈 |

### B. 死代码与残留

| 项 | 结论 |
|---|---|
| B1 包装 computed `telemetry` / `componentMatrix` / `modeling`（旧 80-84） | **删除**。仅做 `?? []` 与三态判断，无其他逻辑；字段必填 |
| B2 辅助函数 `modelingStatOf`（旧 270-273） | **删除**。只被 S2/S3 调用；其「缺项补 0」逻辑内联进 `datasetRows` 一处 |
| B3 `s2Rows` | **删除并并入 `datasetRows`**（该 computed 同时服务 S2 表格与 S3 建模覆盖，原名已不达意） |
| B4 未使用的 import | **删除 `ComponentMatrixRow` / `ModelingStat`**。`tsconfig.app.json` 打开 `noUnusedLocals` + `noUnusedParameters`，`EXIT=0` 即机器证明本文件零未使用局部变量/导入/参数 |
| B5 注释掉的代码 / `console.log` / TODO / FIXME / 空 `<style>` | **无**。grep 0 命中；本文件**根本没有 `<style>` 块**（grep `<style`：0 命中），样式全部来自共享 `dash.css` |
| B6 行对象里模板不读的 key | **1 处，已披露**：`datasetRows` 的 `models`（建模三元组）只被脚本（`modelingBars` / `idleDatasets`）读，不被表格列读；`logical_id` 被 `DashTable` 的 `row-key` 读。取舍：拆成「纯表格行 + 独立投影」会重新引入二次遍历，故保留并在注释中标注字段用途 |
| B7 与 `dashboardApi.ts` 重复的类型定义 | **无**。本文件不声明任何 interface/type，全部从 `dashboardApi.ts` / `DashKpis.vue` / `DashTable.vue` 导入（`PARAM_KEYS` 是**值**常量，不是类型） |

### C. 不必要的复杂度

| 项 | 结论 |
|---|---|
| C1 同一数组多次遍历 | **已收敛**。`props.data.datasets` 原被 S2、S3 各遍历一次、并对每项查 `modelingMap` 2 次（S2 一次、S3 一次）；现只遍历一次 |
| C2 `telemetry_by_dataset` 仍被遍历 2 次 | **故意保留**。`frequencyPassRate`（加权成一个标量）与 `d1Rows`（造 8 列单元格）合并需要可变累加器，收益为负；已在注释中说明 |
| C3 深层嵌套三元 | **最深的一处已随死分支删除**（`model_count: modeling === null ? null : ...`）；余下三元均为单层，且都是「二选一文案」（`kind === 'system' ? '系统' : '设备'`、`param.unit ? ... : ...`、`frequencyPassRate === null ? null : ...`） |
| C4 魔法字符串 / 魔法数字 | **字符串已提常量**：`'power'` → `SCENARIO_KEY`；`VoltageLevel_kV`/`CurrentAmp`/`Temperature_C` → `PARAM_KEYS`；模板内联基线文案 → `BASELINE_SOURCE`。**数字阈值无可提取项**：300–700 kV 等只作为**文案**出现，比较逻辑在后端 `_power_baseline_violated`，前端不做数值比较。**`tone` 字面量保留内联**：它是 `KpiItem.tone` 联合类型的取值，每处只出现一次，抽常量只增加间接层 |
| C5 重复实现共享格式化 | **无**。`fmtPercent` / `fmtNum` / `fmtDate` 均复用 `dashFormat`。**刻意不使用 `fmtInt`**：KPI 数值由 `DashKpis` 内部格式化、表格数值列由 `DashTable` 原样渲染，若在此处 `fmtInt` 会把 `2000` 变成 `2,000`，违反渲染不变约束 |
| C6 命名 | `s2Rows` → `datasetRows`（同时服务 S2/S3）；`models` 明确为「建模版本三元组」；`SCENARIO_KEY` / `PARAM_KEYS` / `BASELINE_SOURCE` 自解释 |
| C7 巨型 computed | **最大的 `datasetRows` 是单一「行形状」定义**，每个字段在注释里逐个说明来源；`kpis` / `runtimeKpis` 是字面量数组（4 项 / 3 项），拆分只会增加跳转 |
| C8 手写查找/Map 反模式 | `displayNames` 的「并行数组 + 下标耦合」（`names[index]`）已消除；`modelingStatOf` 的重复 Map 查询已消除 |

### D. 正确性风险

| # | 风险 | 结论 |
|---|---|---|
| D1 | **`DashKpis` 把非 `raw` 的 `null` 渲染成 `0`** —— `DashKpis.vue:27` 为 `item.raw ? (item.value ?? '—') : fmtInt(item.value)`，而 `fmtInt(null)` 走 `Number(null)=0`（有限）→ `"0"`。本页 S4 的「待处置积压」「近 10 天活动」是**非 raw**，运行态请求失败时（`runtime===null`）会显示 **「0 条」「0 次」**，与页面注释声明的「失败显示占位符」相反，是误导性的管理结论（假「无积压」）。 | **报告，不改**（共享面 1 行改法见 §6 提案 1）。已处置率因 `raw: true` 不受影响，正常态下显示也不变 |
| D2 | **工频合格率可能显示假的 `0.0%`** —— 后端 `frequency_pass_rate = _percent(passed, len(frequency_values))`（`dashboard_service.py:1672`），而 `_percent` 在分母为 0 时返回 `0.0`（:373-374）。若某数据集没有 `PowerFrequencyHz` 字段，其 `record_count` 非 0 但合格率为 `0.0`，加权后 KPI 显示「0.0%」；前端无法区分「真的 0%」与「字段缺失」。 | **报告，不改**。前端把 `0` 当 `null` 会把真实的 0% 误显示为「—」，属口径变更；根治需后端把「无数据」与「0%」分开（如 `null`） |
| D3 | **S5 成员列表的请求口径与契约不一致** —— 契约 `实施指南.md:364` 写 `getUserList({ scenario_id, page_size: 200 })`（服务端过滤），本页实际是 `getUserList({ page_size: 200 })` + 客户端 `item.scenario_id === scenarioId`。**但已核实后端对 SCENARIO_ADMIN 调用者本就强制 `AppUser.scenario_id == current_user.scenario_id`**（`user_service.py:106-107`），且 `require_scenario_access` 保证只能看本场景 → 两种写法对本页调用者是**同一个 predicate**，无行为差异。真正的残留风险是 **`page_size` 被服务端硬上限 200 截断**（`user_service.py:124`），且页面忽略响应里的 `total` → 场景成员 > 200 时列表与「合计 N 人」会少算。 | **报告，不改**（分页/改用 `total` 属行为变更，且四页一致口径） |
| D4 | **D2 表 `row-key="value"` 可能撞 key** —— 后端把设备与系统分别聚合后拼接（`_power_component_matrix` :1680+），若某设备与某系统同名，两行的 `value` 相同 → Vue 重复 key 警告、DOM 复用错位。 | **报告，不改**。修法（后端给唯一键，或前端 `kind:value` 拼 key）属跨页一致口径，交 Lead |
| D5 | **无请求取消 / 无 stale 响应保护** —— `watch(() => props.data.scenario_id, loadAll)` 在快速切换场景时可能两次 `loadAll` 乱序落地（后发先至）。本页 `scenario_id` 实际恒定；组件内**无定时器、无 observer、无事件监听**，`watch` 随组件作用域自动停止 → **无泄漏，不需要 `onUnmounted`**。 | **记录为低风险，不改** |
| D6 | **`Promise.allSettled` 降级链** —— 已逐条验证：两个请求都在 `loadAll` 内部 `await`；主画像来自 `props.data`（父组件传入），**不被 `loadAll` 阻塞**；`allSettled` 永不 reject，其后代码无抛点（`userApi.getUserList` 内部已把 `items` 归一化为数组）→ **无未处理 rejection**。`runtime` / `members` 的 `null` 语义**保留**（请求失败真实可达，与「确实 0 条 / 0 人」区分开） | **验证通过，保留** |
| D7 | **可空字段可追溯** —— `packet_loss_mean === null` → 单元格 `null` → `DashTable` 渲染 `—`；`param.mean === null` → `meanText` 返回 `null` → `—`；`summary === null` → 「待处置积压/近 10 天活动」显示 `0`（**见 D1**）、「已处置率」显示 `—`（`raw`）；`status_funnel` 空 → `DashFunnel` 暂无数据；`activity_trend` 空 → `DashLine` 暂无数据 | **通过**（除 D1 已单列） |

### E. 硬约束（渲染不变）

| 项 | 结论 |
|---|---|
| E1 卡片标题/顺序、列名/列序、KPI 文案与单位、标签文案与配色语义、数字格式化结果、空态文案 | **未变**。机器比对：本文件字符串字面量集合旧/新均为 **134 个**，差异仅 4 处模板属性名（`s2Rows`→`datasetRows`、新增 `BASELINE_SOURCE` 绑定）与 1 处**不可达**的 `'—'`；逐块等价论证见 §5.4 |
| E2 `defineProps<{ data: PowerProfile }>()` 签名 | **未动**（第 47 行原样） |
| E3 新增依赖 / 新增组件 / 模板结构 | **无新增依赖、无新增组件**；模板结构未变，仅把 D1 的 `source` 由内联字符串改为常量绑定（文本逐字节相同） |
| E4 共享面文件 | **未修改任何共享面文件**（见 §8） |

---

## 3. 删除证据（逐项 grep / 编译证明）

命令：在 `frontend/src` 下用 ripgrep 检索；「本文件 0 命中」= 对重构后的 `ProfilePower.vue` 检索。

| 删除项 | 原位置 | 零引用证据 | 结论 |
|---|---|---|---|
| `telemetry` computed | 旧 80 | 本文件 grep `telemetry\.value`：**0 命中**；`noUnusedLocals` 下 `EXIT=0` | 删（字段必填，包装无意义） |
| `componentMatrix` computed | 旧 81 | 本文件 grep `componentMatrix`：**0 命中** | 删 |
| `modeling` 三态 computed | 旧 82-84 | 本文件 grep `modeling\.value`：**0 命中**；后端 `data["modeling"] = modeling` 无条件下发（`dashboard_service.py:1386`） | 删（三态不可达） |
| `modelingStatOf()` | 旧 270-273 | 全 `frontend/src` grep `modelingStatOf`：**0 命中** | 删（逻辑内联进 `datasetRows`） |
| `s2Rows` | 旧（S2 行 computed） | 全 `frontend/src` grep `s2Rows`：**0 命中**（其余三页亦无此符号，可排除同名误判） | 删（并入 `datasetRows`） |
| `import type { ComponentMatrixRow }` | 旧 29 | 全 `frontend/src` 仅 `dashboardApi.ts:234/254`（类型定义与字段声明）命中 → 契约类型保留，仅本文件不再显式引用 | 删 import |
| `import type { ModelingStat }` | 旧 30 | 全 `frontend/src` 仅 `dashboardApi.ts:62/153` 命中 | 删 import |
| `Number(x)` 强制转换 ×4 | 旧 102、105、339、166 | 本文件 grep `Number\(`：**0 命中** | 删（类型已是 number） |
| `Number.isFinite` 守卫 | 旧 167 | 本文件 grep `isFinite`：**0 命中** | 删（`fmtNum` 内部已守卫，输出同为 `—`） |
| `?? []`（必填数组） ×5 | 旧 80、81、164、175(D2 counts)、D1 `violations` | 本文件 grep `params \?\?` / `counts \?\?` / `violations \?\?`：**0 命中** | 删 |
| `?? '—'`（visibility / dataset_file_count） | 旧 117、S2 visibility | 本文件 grep `dataset_file_count \?\?`：**0 命中**；字符串 `'—'` 已从本文件字面量集合中整体消失（§5.3） | 删（不可达） |
| `modeling === null` 三处分支 | 旧 `s2Rows` / `modelingBars` / `idleDatasets` | 见上「三态不可达」证据 | 删（消除假「数据白躺」告警路径） |
| `names` 并行数组 | 旧 `displayNames` | 本文件 grep `name: names\[`：**0 命中** | 删（消除下标耦合） |
| `admins` / `users` / `disabled` 中间数组 | 旧 387-389 | 本文件 grep `\.forEach\(`：**0 命中**；三处 `.filter(...)` 数组已改为计数 | 删 |

**未删除任何后端字段的消费**：`params` / `counts` / `violations` / `modeling` / `telemetry_by_dataset` / `component_matrix` / `dataset_file_count` / `caliber_registered` / `packet_loss_mean` / `baseline_ok` 全部仍在渲染链路上被读取（见 §4 函数清单），只去掉了不可达兜底。

---

## 4. 函数清单（重构后全量）

### 4.1 常量

| 符号 | 形态 | 含义 | 后端字段来源 |
|---|---|---|---|
| `SCENARIO_KEY` | `const string` | 运行态接口 `scenario_key` 的期望值，用于确认拿到的是本场景数据（防串场景） | `_scenario_key()`（`dashboard_service.py:521`）→ `get_workspace` 的 `data.scenario_key`（:1973-1978） |
| `VISIBILITY_TEXT` | `const Record<string,string>` | 数据集可见性枚举 → 管理端中文（平台/公司/个人） | `Dataset.visibility`（`platform`/`company`/`personal`），经画像 `datasets[].visibility` 下发 |
| `PARAM_KEYS` | `const {voltage,current,temperature}` | D1 三个电参量列 → `params[].key` | 后端 `POWER_PARAMS`（`dashboard_service.py:167-173`）：`VoltageLevel_kV` / `CurrentAmp` / `Temperature_C` |
| `BASELINE_SOURCE` | `const string` | D1 卡片基线口径文案（`DashCard.source`；当前 `SHOW_DASH_HINTS=false` 不渲染） | 后端 `POWER_BASELINE`（:191-197）逐项对应 |
| `d1Columns` | `DashColumn[]` | D1 表 8 列：数据集/样本量/电压均值/电流均值/温度均值/工频合格率/遥测丢包率/结论 | 列语义 = `telemetry_by_dataset` 的 `name`/`record_count`/`params`/`frequency_pass_rate`/`packet_loss_mean`/`violations` |
| `d2Columns` | `DashColumn[]` | D2 表 4 列：设备/系统、类型、覆盖数据集、覆盖数 | 列语义 = `component_matrix` 的 `value`/`kind`/`counts` |
| `s2Columns` | `DashColumn[]` | S2 表 8 列：数据集名/样本量/标签字段/风险占比/字段数/可见性/已发布模型数/版本 | 列语义 = 画像 `datasets[]` + `modeling[]` |

### 4.2 计算属性 / 函数 / 引用

| 符号 | 形态 | 含义（一行） | 后端字段来源 |
|---|---|---|---|
| `displayNames` | `computed<Map<string,string>>` | 展示名去重：同名（同源重复注册）时补 `（logical_id）` 以区分 | `datasets[].name`（`dataset_display_name_of`）+ `logical_id` |
| `nameOf(logicalId, fallback?)` | 函数 | 取展示名：去重表 → 接口自带 `name` → `logical_id` 三级兜底 | 同上 |
| `modelingMap` | `computed<Map<string,ModelingStat>>` | `logical_id` → 该数据集建模统计 | `modeling[]`（`_modeling_stats` :1405-1434） |
| `frequencyPassRate` | `computed<number\|null>` | 按 `record_count` 加权的 `frequency_pass_rate` 平均；样本总量为 0 → `null`（显示 `—`） | `telemetry_by_dataset[].record_count` / `.frequency_pass_rate`（:1670-1672） |
| `kpis` | `computed<KpiItem[]>` | S1 四张 KPI：有效数据集数 / 有效样本总量 / 统一风险占比 / 工频合格率 | `dataset_count` / `dataset_file_count` / `sample_count` / `risk_rate`（`_effective_counts` + `_percent`）+ `frequencyPassRate` |
| `meanText(row, key)` | 函数 | 取某电参量均值文案：`mean===null` → `null`（渲染 `—`），否则 `数值 单位` | `params[].{key,mean,unit}`（:1645-1652） |
| `verdictOf(row)` | 函数 | 结论标签：达标（绿 `ok`）/ 越界项列表（红 `up`） | `baseline_ok` / `violations`（:1660-1674） |
| `d1Rows` | `computed` | D1 表格行（含 `logical_id` 作 row-key） | `telemetry_by_dataset` |
| `d2Rows` | `computed` | D2 表格行：类型中文、覆盖串 `名称(条数, 风险占比)`、覆盖数 | `component_matrix[].{value,kind,counts[]}`（`_component_matrix_rows` :461-486） |
| `datasetRows` | `computed` | **S2 表格行 + S3 建模三元组**：`datasets` 单次遍历产出（含 `unregistered = caliber_registered === false`、`model_count` 文案、`models{published,draft,total}`） | 画像 `datasets[]`（`name`/`logical_id`/`record_count`/`label_field`/`risk_rate`/`attribute_count`/`visibility`/`version`/`caliber_registered`）+ `modelingMap` |
| `modelingBars` | `computed` | S3 柱状图：每数据集一根柱 = 模型版本总数，标签写「已发布 P / 草稿 D」 | `modeling[].{published,draft,total}` |
| `idleDatasets` | `computed` | 「数据白躺」清单：`total === 0` 的数据集展示名 | `modeling[].total` |
| `runtime` | `ref<PowerWorkspace\|null>` | 运行态数据；`null` = 未取到 | `getScenarioWorkspace(id)` → `/workspace`（`get_workspace` :1949-1998） |
| `members` | `ref<UserAccount[]\|null>` | 场景成员；`null` = 未取到（与「确实 0 人」区分） | `getUserList({page_size:200})` → `/users`（`user_service.list_users` :95-144） |
| `loadAll()` | `async` 函数 | 两接口 `Promise.allSettled` 并行、各自静默降级，任一失败只让对应块显示占位符 | 同上两接口 |
| `watch(() => props.data.scenario_id, loadAll)` | 副作用 | 切换场景时重取运行态/成员 | — |
| `onMounted(loadAll)` | 副作用 | 首次挂载即取 | — |
| `summary` | `computed` | 风险事件汇总对象（`null` = 未取到） | `summary`（`_event_summary` :1019-1057） |
| `activityTotal` | `computed<number>` | 近 10 天活动 = `activity_trend[].total` 求和 | `activity_trend`（`_activity_trend` :2000-2025） |
| `runtimeKpis` | `computed<KpiItem[]>` | S4 三张 KPI：待处置积压 / 已处置率 / 近 10 天活动 | `summary.{pending,resolved,total}` + `activityTotal` |
| `funnelItems` | `computed` | 处置漏斗项（`{label,count}`） | `summary.status_funnel[]`（:1053-1055） |
| `trendPoints` | `computed` | 折线点：`{label: fmtDate(date), value: total, value2: risk}` | `activity_trend[].{date,total,risk}` |
| `memberRows` | `computed` | S5 行：场景管理员 N 人 / 场景用户 N 人 / 合计 N 人 /（有则）已禁用 N 人 | `members[]` 的 `role` / `status` |

---

## 5. 行为不变证明

### 5.1 类型检查（原始输出）

命令（工作目录 `frontend/`）：

```
npx vue-tsc --noEmit -p tsconfig.app.json
```

- 第 1 次：输出为空，`EXIT=0`
- 第 2 次（复核，排除并发写入干扰）：输出为空，`EXIT=0`

`tsconfig.app.json` 打开 `strict` / `noUnusedLocals` / `noUnusedParameters`，因此 `EXIT=0` 同时证明：**本文件零类型错误、零未使用局部变量、零未使用导入、零未使用参数**。

### 5.2 行数

| | 行数 |
|---|---|
| 重构前（`git show HEAD:…`） | **459** |
| 重构后 | **421** |
| 净变化 | **−38**（`git diff --numstat`：`+104 / −110`） |

### 5.3 字符串字面量集合机器比对

方法：对旧/新版本分别抽取所有 `'…'` / `"…"` 字面量，去重排序后 `Compare-Object`。

```
old literals: 134  new literals: 134
---- only in OLD ----   ---- only in NEW ----
—                       BASELINE_SOURCE
s2Rows                  datasetRows
```

- `'—'`：旧版 S2 可见性兜底 `VISIBILITY_TEXT[x] ?? '—'` 中的**不可达**字面量（见 §5.4）。
- `s2Rows` / `datasetRows` / `BASELINE_SOURCE`：**模板属性名**，不是渲染文本。

结论：**所有卡片标题、列名、KPI 文案与单位、标签文案、口径说明、空态文案的字面量逐字节未变**。

模板字符串（反引号）比对同样逐条等价（差异仅为变量改名，取值相同）：

| 旧 | 新 | 等价性 |
|---|---|---|
| `${admins.length} 人` | `${adminCount} 人` | 同一 predicate 的计数 |
| `${users.length} 人` | `${userCount} 人` | 同上 |
| `${members.value.length} 人` | `${list.length} 人` | 同一数组长度 |
| `${disabled.length} 人` | `${disabledCount} 人` | 同上 |
| `${fmtNum(num)} ${param.unit}` | `${fmtNum(param.mean)} ${param.unit}` | `num = Number(param.mean)`，`fmtNum` 内部再次 `Number()` |
| `${nameOf(item.logical_id, item.name)}（已发布 ${stat.published} / 草稿 ${stat.draft}）` | `${row.name}（已发布 ${row.models.published} / 草稿 ${row.models.draft}）` | `row.name = nameOf(item.logical_id, item.name)`；`row.models` = `stat` 的 `?? 0` 三元组（后端恒有该行，值相同） |
| `含 ${props.data.dataset_file_count ?? '—'} 份文件` | `含 ${props.data.dataset_file_count} 份文件` | `dataset_file_count: number` 必填，`??` 不可达 |

### 5.4 逐块等价论证

| 块 | 旧写法 | 新写法 | 输出等价理由 |
|---|---|---|---|
| S1 有效数据集数 `sub` | `dataset_file_count ?? '—'` | `dataset_file_count` | `dashboardApi.ts` 标注 `dataset_file_count: number`（必填），后端恒下发 |
| S1 工频合格率 | `Number(x) \|\| 0` 两处 | `x` | 字段类型 `number`，后端 `_percent` 恒返回 float |
| D1 电压/电流/温度均值 | `params ?? []` + `Number(param.mean)` + `Number.isFinite` 守卫 | `params.find` + `param.mean === null` | `params` 必填；`fmtNum` 内部 `Number()`+`isFinite`，非有限值同样输出 `—` |
| D1 遥测丢包率 | `packet_loss_mean === null ? null : …` | 同 | 未变（`null` → `—`） |
| D1 结论 | `baseline_ok === true` / `violations ?? []` | `baseline_ok` / `violations` | `baseline_ok: boolean`、`violations: string[]` 均必填，无第三态 |
| D2 覆盖串 | `counts ?? []` | `item.counts` | `counts` 必填数组；拼接模板逐字符相同 |
| S2 可见性 | `VISIBILITY_TEXT[x] ?? '—'` | `VISIBILITY_TEXT[x] ?? x` | 对任意 `string` 型 `x`，`?? x` 恒非空 → `'—'` 不可达；且即便为空串，`DashTable` 的 `asText` 也渲染 `—` |
| S2 已发布模型数 | `modeling === null ? null : \`…\`` | 直接模板串 | 后端恒下发 `modeling`，且每个可见数据集必有一行（无模型时计 0） |
| S3 柱状图 / 白躺清单 | `modeling === null ? [] : props.data.datasets.map/filter(...)` | `datasetRows.map/filter(...)` | `modeling` 恒非 null；遍历对象仍是 `props.data.datasets`（顺序、名称、计数来源相同） |
| S4 近 10 天活动合计 | `Number(point.total) \|\| 0` | `point.total` | 后端按天累加的 int 计数 |
| S4 折线 label | `item.date.slice(5)` | `fmtDate(item.date)` | `fmtDate = String(v ?? '').slice(5)`；后端 `date` 为 `date.isoformat()`（`dashboard_service.py:2014/2025`）恒为 `YYYY-MM-DD` |
| S5 成员计数 | `filter` 出 3 个数组取 `.length` | 3 个计数 | 同 predicate、同数组 |
| 模板 | D1 `source="电力基线：…"` 内联 | `:source="BASELINE_SOURCE"` | 常量文本与旧内联文本逐字节相同（§5.3 字面量集合未出现该串差异） |

### 5.5 未能做到的验证（诚实声明）

- **未做浏览器实测**：本次任务禁止 `npm run build` / `vite build` / 启停服务，因此「渲染逐字节不变」是**静态论证**（字面量集合机器比对 + 表达式逐条等价 + 类型约束 + 后端字段必填性核查），**不是**截图/DOM 比对。建议 Lead 在四页汇总后跑一次浏览器回归。
- **未重跑后端测试 / 未探测接口**：`pytest` 与接口探测均在本任务的禁止清单内，因此 D1/D2 的结论基于源码与既有验收数据（`dataset_count=1 / dataset_file_count=2 / sample_count=2000 / risk_count=1594 / frequency_pass_rate=0.324`）的静态推导。

---

## 6. 共享面提案（**未应用**，交 Lead 决策）

### 提案 1：`DashKpis.vue:27` —— 非 `raw` 的 `null` 应显示 `—` 而不是 `0`

问题（§2 D1）：`fmtInt(null)` → `Number(null) = 0` → 显示 `"0"`，使「待处置积压」「近 10 天活动」在运行态请求失败时显示假的 `0 条 / 0 次`。

```diff
--- a/frontend/src/components/dashboard/DashKpis.vue
+++ b/frontend/src/components/dashboard/DashKpis.vue
@@ -24,7 +24,7 @@
   <section class="d-kpis" :style="columns ? { gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` } : undefined">
     <div v-for="item in items" :key="item.label" class="d-kpi" :class="`d-kpi--${item.tone || 'primary'}`">
       <span class="d-kpi-v">
-        {{ item.raw ? (item.value ?? '—') : fmtInt(item.value) }}<em v-if="item.unit">{{ item.unit }}</em>
+        {{ item.raw || item.value === null || item.value === undefined ? (item.value ?? '—') : fmtInt(item.value) }}<em v-if="item.unit">{{ item.unit }}</em>
       </span>
       <span class="d-kpi-l">{{ item.label }}</span>
       <span v-if="SHOW_DASH_HINTS && item.sub" class="d-kpi-sub">{{ item.sub }}</span>
```

- **影响面**：四场景所有 KPI。仅当 `value` 为 `null`/`undefined` 且非 `raw` 时输出由 `"0"` 变为 `"—"`；正常态（有数据）逐字节不变。
- **风险**：若某页**故意**用 `null` 表示「0」，该页输出会变 → 需 Lead 确认四页无此用法（本页无此用法）。
- **本页替代方案（同样未应用）**：在本文件内把这两个 KPI 改成 `raw: true` + `fmtInt(...)`，可不动共享面且正常态文本不变；代价是 KPI 数字格式化职责从组件泄漏到页面，且与另外三页写法不一致。

### 提案 2：`dash.css` —— D1 宽表最后一列在窄视口被滚动容器边缘裁掉

**已核实的 CSS 事实**（只读检查，未改）：

- `.d-table-wrap { overflow-x: auto }`（`dash.css:304-306`）是表格唯一的裁剪边界；
- `.d-table td { white-space: nowrap }`（:325-330）**没有** `overflow` / `text-overflow`；`.d-tag` 同样只有 `white-space: nowrap`（:359-365）；
- 带 `overflow:hidden + text-overflow:ellipsis` 的规则分别属于 `.d-hbk`（横向条标签 :203-210）、`.d-lgk`（图例键 :262-268）、`.d-evb strong`（事件卡标题 :396-402），**都不是表格单元格或标签**。

**结论**：D1 的「结论」列标签文本**不可能被 CSS 省略号截断**；观感上的「少一个字」只可能是**列超出 `.d-table-wrap` 可视宽度、被滚动边界裁掉**（右滑即可看到全文本）。8 列 + 长数据集名在 1440px 内容宽度下确有溢出可能。

**可选改法（未应用，需四页一起评估）**：

```diff
--- a/frontend/src/components/dashboard/dash.css
+++ b/frontend/src/components/dashboard/dash.css
@@ -340,5 +340,9 @@
 .dash-page .d-table--dense th,
 .dash-page .d-table--dense td {
   padding: 6px 8px;
   font-size: 11.5px;
 }
+.dash-page .d-table--dense th:first-child,
+.dash-page .d-table--dense td:first-child {
+  white-space: normal;
+  max-width: 220px;
+}
```

- 让「数据集」列换行以回收宽度，把最后一列拉回可视区。
- **影响面**：四场景所有 `dense` 表格的首列换行行为（其它三页 D1/D2 也用了 `dense`）→ 属跨页视觉口径，须 Lead 统一决定。
- **保守选项**：不改。横向滚动本身是 `.d-table-wrap` 的设计意图，若 Lead 判定可接受，则本条无需处理。

---

## 7. 未解决 / 存疑

1. **D1（`DashKpis` 非 raw `null` → `0`）未修**：修法在共享面（提案 1）。本页在运行态请求失败时仍会显示「待处置积压 0 条 / 近 10 天活动 0 次」。
2. **D2（工频合格率假 `0.0%`）未修**：根因在后端 `_percent` 把「分母为 0」与「真实 0%」都返回 `0.0`（`dashboard_service.py:373-374`）。当前验收数据两个数据集都有 `PowerFrequencyHz`，未触发；但若未来接入缺该字段的数据集，KPI 会显示假 `0.0%`。
3. **D3（S5 成员 200 上限）未修**：`user_service.py:124` 硬上限 `page_size = min(…, 200)`，页面忽略响应 `total`；成员 > 200 时「合计 N 人」少算。同时页面用客户端 `scenario_id` 过滤（对 SCENARIO_ADMIN 调用者与契约写法的 predicate 等价，已核实）。
4. **D4（D2 `row-key="value"` 撞 key）未修**：需后端给唯一键或四页统一改 key 口径。
5. **D5（无 stale 响应保护）**：`watch(scenario_id)` 的并发重入未加序号/`AbortController`。本页 `scenario_id` 实际恒定、组件无定时器与监听器，故按「记录不改」处理。
6. **未做浏览器实测**（禁止构建/启停服务）：渲染不变的结论为静态论证，建议 Lead 汇总后统一回归。
7. **并发写入**：本次重构期间另外三个 `Profile{Network,Flightdeck,Geological}.vue` 也在被并行修改，`git status` 中的其它三个文件不是我的改动（见 §8）；`vue-tsc` 两次 `EXIT=0` 说明复核时全仓库无类型错误，但其它文件的中间态不受我控制。

---

## 8. 隔离声明

我未修改任何共享面文件

只写入 2 个文件：`frontend/src/views/Home/dashboard/sections/ProfilePower.vue`（重构）与 `docs/场景管理员首页审查/重构报告/power.md`（本报告）。未触碰 `frontend/src/components/dashboard/**`、`frontend/src/api/**`、`AdminProfilePage.vue`、`DashboardHomeView.vue`、另外三个 `Profile*.vue`、`backend/**`、`scripts/**`、`frontend/tests/**`、数据库，未执行 `npm run build` / `vite build` / `pytest` / 任何启停服务命令。

`git status --short`（原始输出，含另外三个并行 agent 的改动，非我所致）：

```
 M frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
 M frontend/src/views/Home/dashboard/sections/ProfileGeological.vue
 M frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue
 M frontend/src/views/Home/dashboard/sections/ProfilePower.vue
?? "docs/\345\205\250\351\241\271\347\233\256\344\273\243\347\240\201\345\256\241\346\237\245/"
?? "docs/\345\234\272\346\231\257\347\256\241\347\220\206\345\221\230\351\246\226\351\241\265\345\256\241\346\237\245/\351\207\215\346\236\204\346\212\245\345\221\212/"
```
