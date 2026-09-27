# F6a 审查报告 — `frontend/src/api/**` + `frontend/src/types/**`

> 分区：F6a（原 F6 拆分的后半）。审查范围**仅** `frontend/src/api/**`（14 个文件）+ `frontend/src/types/**`（2 个文件），共 **16 个文件 / 2971 行**（审查开始时的 HEAD 版本）。
> `stores/**`、`utils/**`、`style.css` 不属本分区，仅在「谁调用了这个 API」取证时被 grep 读取，未做代码分析。
> 依据：`docs/全项目代码审查/审查协议.md`。
> 环境：`vue-tsc` 自检通过（0 错误）；后端 12312 未被触碰；未执行任何构建/启动/DB 命令。

---

## 0. 结论速览

| 项目 | 结果 |
|---|---|
| 审查文件数 | 16（api 14 + types 2） |
| 修改文件数 | 6（全部在 `api/**`；`types/**` 未改动，见 §4 说明） |
| 代码增删 | **+88 / −104**（净 −16 行） |
| 删除的已导出函数 | **0**（硬约束：不得删除已导出函数/类型，全部转为提案，见 §3、§8） |
| 零引用（死）已导出 API 封装 | **14 个**（详见 §2） |
| 零引用已导出类型/工具函数 | **2 个**（`types/security.ts`，详见 §4.1） |
| `vue-tsc --noEmit` | **通过，0 错误**（全项目） |
| 跨区/跨文件提案 | 6 项（见 §8） |

**本分区最大的问题不是"代码写错"，而是"代码写了没人用"**：14 个已导出 API 封装在前端全仓零调用，且其后端接口全部仍然存活（不是接口下线留下的残骸，而是"页面改走异步任务接口后同步接口封装没删"这类历史堆积）。受硬约束限制，本报告只提供证据与可执行提案，不做删除。

---

## 1. 已改动的 6 个文件（行为等价重构）

全部为**分区内**改动，未触碰任何已导出类型的字段名/可选性/必填性，未删除任何已导出函数。

| 文件 | 行数 | 改动 |
|---|---|---|
| `api/datasetApi.ts` | 488 → 482 | ① 抽出模块私有 `invertScenarioCodeMap()`，替换 `ensureScenarioMaps()` catch 分支里手抄的逆向字面量；② 抽出模块私有 `fetchDatasetItems()`，消除 `getDatasetList` / `getDatasetRawList` 之间重复的取数+参数组装（约 20 行重复）；③ 场景种子表改为从 `scenarioApi` 导入 |
| `api/inferenceRecordApi.ts` | 298 → 295 | `getInferenceRecordList` 改为委托 `getInferenceRecordPage(params)` 后取 `.items`，消除同接口两套取数逻辑 |
| `api/reportApi.ts` | 252 → 243 | `getReportList` 改为委托 `getReportPage(params)` 后取 `.items`；场景种子表改为导入 |
| `api/riskThresholdApi.ts` | 102 → 95 | `SCENARIO_CODE_TO_ID` 改为由 `SCENARIO_CODE_BY_ID` 取逆生成，不再手写第二份映射；场景种子表改为导入 |
| `api/scenarioApi.ts` | 138 → 153 | **新增** `export const SCENARIO_CODE_BY_ID`（唯一权威种子表，见 §5.1） |
| `api/situationApi.ts` | 167 → 161 | 去掉 `buildDailyTrend` 里的非空断言 `byDay.get(day)!`，改为直接迭代 `byDay.entries()`（字典序与原来 `[...keys()].sort()` 一致）；场景种子表改为导入 |

等价性论证：
- `getInferenceRecordList` / `getReportList`：改动前后请求 URL、params、`unwrapData` 调用完全一致，返回值同为 `items`，且**原来就没有** `data.items ?? []` 的兜底（原实现直接返回 `data.items`），委托后语义不变。
- `fetchDatasetItems`：`getDatasetRawList` 原来传 `{scenario_id, page:1, page_size: params?.page_size ?? 200}`，抽取后显式传入同样三参；`getDatasetList` 原来传整个 `params`，抽取后传同一个对象（`page`/`page_size` 的 `?? 1` / `?? 200` 兜底留在被抽出的函数内，与原来一致）。
- `SCENARIO_CODE_BY_ID`：4 处本地字面量逐字相同（1 network_security / 2 power_system / 3 flightdeck_operation / 4 geological_risk），合并后运行期取值不变。

---

## 2. 【最高价值】死 API 封装清单（零调用）

### 2.1 判定方法

1. 正则提取 `api/**`、`types/**` 中所有 `export (const|function|async function|interface|type|class|enum) NAME`；
2. 以 `(?<![\w$.])NAME(?![\w$])` 对 **`frontend/src` 全目录**（`.ts` / `.vue` / `.js`，共 87 个文件）做计数；
3. 分 `self`（本文件内命中数，含定义行）与 `others`（其他文件命中）两桶；
4. `others == 0` 的再逐个人工复核，排除两类假阳性：
   - **命名空间式访问**（`import * as datasetApi` → `datasetApi.getDatasetDetail`）会被 `(?<![\w$.])` 的 `.` 排除 —— 全仓只有 2 处命名空间导入（`stores/datasetStore.ts` 的 `datasetApi`、`stores/userStore.ts` 的 `userApi`），其成员访问已全部人工列出核对（见 §2.3 的误判纠正）；
   - **同名符号跨文件干扰**（`trainingApi.trainModel` 与 `modelVersionApi.trainModel` 同名），已逐个查 import 语句确认。

### 2.2 死封装清单（14 个，证据为全仓 grep 唯一命中即定义行）

| # | 文件 | 行 | 导出函数 | 后端接口是否仍在 |
|---|---|---|---|---|
| 1 | `api/datasetApi.ts` | 285 | `getDatasetDetail` | 在（`GET /datasets/{id}`） |
| 2 | `api/datasetApi.ts` | 306 | `getDatasetFieldsSchema` | 在（`getDatasetFields` 的别名，同接口） |
| 3 | `api/inferenceRecordApi.ts` | 85 | `predictInferenceBatch` | 在（`POST /inference-records/predict-batch`） |
| 4 | `api/inferenceRecordApi.ts` | 95 | `predictInferenceBatchUpload` | 在（`POST /inference-records/predict-batch/upload`） |
| 5 | `api/inferenceRecordApi.ts` | 207 | `getInferenceRecordDetail` | 在（`GET /inference-records/{id}`） |
| 6 | `api/modelVersionApi.ts` | 78 | `getDefaultModel` | 在 |
| 7 | `api/modelVersionApi.ts` | 85 | `compareModelVersions` | 在（`GET /model-versions/compare`） |
| 8 | `api/modelVersionApi.ts` | 89 | `trainModel`（同步训练） | 在（`POST /model-versions/train`） |
| 9 | `api/modelVersionApi.ts` | 101 | `offlineModel` | 在（`POST /model-versions/{id}/offline`） |
| 10 | `api/modelVersionApi.ts` | 122 | `clearDefaultModel` | 在（`POST /model-versions/{id}/clear-default`） |
| 11 | `api/reportApi.ts` | 182 | `downloadReportFile`（同步导出） | 在（`GET /reports/{id}/export`） |
| 12 | `api/riskEventApi.ts` | 63 | `commentRiskEvent` | 在（`POST /risk-events/{id}/comment`） |
| 13 | `api/riskThresholdApi.ts` | 68 | `getRiskThreshold`（单场景） | 在（`GET /risk-thresholds/{scenario_id}`） |
| 14 | `api/trainingApi.js` | 35 | `trainModel`（同步训练） | 在（同上，走 `trainingApi` 的裸 axios） |

**注意 #8 与 #14 是两个不同的同名函数**，两者都零引用：
- `modelVersionApi.trainModel`：`ModelCenter.vue:13-20` 从 `modelVersionApi` 只导入了 `deleteModelVersion / disableModel / enableModel / getModelVersionPage / publishModel / setDefaultModel`，没有 `trainModel`。
- `trainingApi.js trainModel`：`trainingApi` 的三个调用方（`ModelCenter.vue:12`、`RiskAnalysis.vue:30`、`trainingJobStore.ts:24`）都没有导入它；`RiskAnalysis.vue:30` 只导入 `trainModelAsync`。

### 2.3 grep 证据（全仓唯一命中 = 定义行）

```
### api/datasetApi.ts :: getDatasetDetail
  api/datasetApi.ts:285: export const getDatasetDetail = async (datasetId: string | number): Promise<Dataset> => {
### api/datasetApi.ts :: getDatasetFieldsSchema
  api/datasetApi.ts:306: export const getDatasetFieldsSchema = getDatasetFields;
### api/inferenceRecordApi.ts :: predictInferenceBatch
  api/inferenceRecordApi.ts:85: export const predictInferenceBatch = async (params: {
### api/inferenceRecordApi.ts :: predictInferenceBatchUpload
  api/inferenceRecordApi.ts:95: export const predictInferenceBatchUpload = async (params: {
### api/inferenceRecordApi.ts :: getInferenceRecordDetail
  api/inferenceRecordApi.ts:207: export const getInferenceRecordDetail = async (recordId: string): Promise<InferenceRecord> =>
### api/modelVersionApi.ts :: getDefaultModel
  api/modelVersionApi.ts:78: export const getDefaultModel = async (params: {
### api/modelVersionApi.ts :: compareModelVersions
  api/modelVersionApi.ts:85: export const compareModelVersions = async (modelIds: Array<string | number>): Promise<BackendModelVersion[]> =>
### api/modelVersionApi.ts :: offlineModel
  api/modelVersionApi.ts:101: export const offlineModel = async (modelId: string | number): Promise<BackendModelVersion> =>
### api/modelVersionApi.ts :: clearDefaultModel
  api/modelVersionApi.ts:122: export const clearDefaultModel = async (modelId: string | number): Promise<BackendModelVersion> =>
### api/reportApi.ts :: downloadReportFile
  api/reportApi.ts:182: export const downloadReportFile = async (
### api/riskEventApi.ts :: commentRiskEvent
  api/riskEventApi.ts:63: export const commentRiskEvent = async (eventId: string, comment: string): Promise<void> =>
### api/riskThresholdApi.ts :: getRiskThreshold
  api/riskThresholdApi.ts:68: export const getRiskThreshold = async (scenarioId: ScenarioId): Promise<ThresholdConfig | null> =>
### api/trainingApi.js :: trainModel / api/modelVersionApi.ts :: trainModel
  api/modelVersionApi.ts:89: export const trainModel = async (params: {
  api/trainingApi.js:5:  * trainModelAsync / getModelVersionDetail：
  api/trainingApi.js:10:  * 同步接口 POST /api/v1/model-versions/train 仍在（trainModel 保留作回退用），
  api/trainingApi.js:35: export const trainModel = async (payload) =>
  api/trainingApi.js:39: export const trainModelAsync = async (payload) =>
  views/Model/RiskAnalysis.vue:30: import { getScenarios, getDatasets, getAlgorithms, trainModelAsync } from '@/api/trainingApi';
  （→ 除各自定义行与一句注释外，无任何调用点）
```

### 2.4 复核中被排除的"假死"（重要，避免误删）

| 符号 | 初判 | 实际 | 证据 |
|---|---|---|---|
| `datasetApi.disableDataset` | DEAD | **活**（本文件内被 `disableDatasetVersion` 调用） | `api/datasetApi.ts:473: disableDataset(versionId);` |
| `datasetApi.removeDataset` | DEAD | **活**（本文件内被 `deleteDatasetVersion` 调用） | `api/datasetApi.ts:482: removeDataset(versionId);` |
| `userApi.getMe` | DEAD | **活**（命名空间式访问，被正则的 `.` 前瞻漏掉） | `stores/userStore.ts:39: this.currentUser = await userApi.getMe();` |
| `userApi.resetPassword` | DEAD | **活**（同上） | `stores/userStore.ts:105: await userApi.resetPassword(userId, newPassword);` |
| `userApi.UserListParams` | DEAD | **活**（类型被命名空间限定使用 4 次） | `stores/userStore.ts:73/90/99/110` |
| `situationApi.getSceneSituation` | DEAD | **活**（本文件内被 `getSituationData` 调用） | `api/situationApi.ts:70: const sit = await getSceneSituation(scenarioId);` |

> 教训：任何"零引用"结论都必须排除 `import * as X` + `X.member` 的访问形式，以及同名符号跨文件干扰。上表 4 条若直接删就是线上事故。

---

## 3. 【优先级 2】`DatasetStat.is_risk_label` 复核结论：**后端仍在返回，不能删**

**结论：另一位 agent 提出的"删除 `is_risk_label`"不成立，本项投反对票。** 它确实在前端已无代码读取，但**后端仍在返回该字段**，且它是 `caliber_registered` 的同值重复字段。

前端侧证据（`frontend/src` 全仓）：

```
api/dashboardApi.ts:33:  is_risk_label: boolean;        ← 唯一代码声明
views/Home/dashboard/sections/ProfileGeological.vue:194/263  ← 注释
views/Home/dashboard/sections/ProfileFlightdeck.vue:17/329   ← 注释
views/Home/dashboard/sections/ProfileNetwork.vue:300         ← 注释
```
即前端除类型声明外**没有任何读取点**（`Profile*.vue` 里那 5 处都是"旧版用 `is_risk_label` 过滤"的说明性注释）。

后端侧证据（`backend/app` 全仓 grep `is_risk_label` 共 9 处）：

```
backend/app/services/dashboard_service.py:906:  "is_risk_label": registered,
backend/app/services/dashboard_service.py:922:  # 口径登记状态：与 is_risk_label 同值，语义更明确（未登记 → 不产风险事件）
backend/app/services/dashboard_service.py:923:  "caliber_registered": registered,
```

两者由同一个局部变量 `registered` 赋值，**值恒等**。因此：
- 这是**前端契约里保留的后端冗余字段**，不是"后端已下线的字段"；
- 删除它会改变 `DatasetStat` 的形状（违反本分区硬约束），且一旦后端哪天只留一个字段，前端就会缺字段；
- 正确处理路径是**后端先删 `is_risk_label`**（B6 分区），前端再跟进 —— 属跨区提案，见 §8。

---

## 4. `types/security.ts`（534 行，未改动）

**本文件一个字未改**，原因：所有发现都落在"已导出类型/函数"上，而本分区硬约束明确禁止改动已导出类型的字段名/可选性/必填性、禁止删除已导出函数。全部转为提案。

### 4.1 零引用（真死）

| 符号 | 行 | 证据 |
|---|---|---|
| `toRiskLevel()` | 147 | 全仓仅 2 处命中：定义行 + 第 138 行的注释"统一走 toRiskLevel 转换"。**零代码调用**。`RiskLevelUpper` 的"大小写双轨转换统一入口"这个设计意图从未落地。 |
| `ScenarioDashboardData` | 527 | 全仓仅定义行。连带 `ScenarioDashboardCharts`(502)、`RadarComparePoint`(495)、`DataRow`(483) 也只被它引用 → 整条链死。 |

### 4.2 `export` 冗余（仅在定义文件内部被引用，无需导出）

去掉 `export` 关键字即可（不删类型本身，风险更低）：
`HistoryPoint`(9)、`MetricItem`(28)、`ClassProb`(191)、`ViewDistribution`(197)、`ClassContribution`(203)、`FeatureEvidence`(211)、`ReportFeature`(259)、`DataRow`(483)、`RadarComparePoint`(495)、`ScenarioDashboardCharts`(502)、`ScenarioDashboardData`(527)。

### 4.3 疑似死字段 → 后端复核后**不建议删**

| 字段 | 前端引用 | 后端复核 | 结论 |
|---|---|---|---|
| `Report.file_url` (362) | 0 | `file_url` 在 `backend/app` 全仓 **0 处命中** | **真死字段**，前端自造。建议随提案清理 |
| `InferenceExplain.prediction_label`(250)、`class_distribution`(252)、`views`(253)、`view_weights`(254)、`feature_evidence`(255) | 0 | 后端**仍在产出**：`explanation_contract.py:202-205`、`explanation_service.py:298-315`、`inference_record_service.py:338` | **保留**。虽标着 "Legacy fields retained for report compatibility"，但它们是 Java 算法契约的真实字段，删了就丢保真度 |
| `ThresholdChangeLog` 旧 mock 字段（`log_id`/`changed_at`/`old_*_threshold`…） | 有（`views/Model/Settings.vue:312-361,663` 做双轨兜底） | — | **保留**，仍在被读取 |

### 4.4 类型精度问题（提案）

`dashboardApi.CaliberRow.label_kind` / `RoleRow.label_kind` 声明为 `string`，而同一文件 `DatasetStat.label_kind` 是联合类型 `'binary'|'multiclass'|'numeric'|'unknown'`；`CaliberRow` 的注释还明确写了"标签类型：binary / multiclass / numeric / unknown"。收紧为联合类型能拿到编译期保护，但属**收窄已导出类型**，需跨区确认 `Profile*.vue` 的赋值点，故仅提案。

### 4.5 类型重复

- `HistoryPoint`(9-15) 与 `TrendPoint`(1-7) **字段完全相同**（`label: string; value: number`）。`HistoryPoint` 仅被 `SituationData.score_history` 使用。提案：`type HistoryPoint = TrendPoint;`（或直接改用 `TrendPoint`）。
- `ScenarioId` 在 17 个文件里被引用（本分区内 `datasetApi.ts` 18 次、`riskThresholdApi.ts` 10 次），定义只有一处，无重复定义问题。
- 无 `api/**` 内部重复定义 `types/security.ts` 中同名类型的情况（已逐符号比对）。

---

## 5. 重复定义 / 重复逻辑

### 5.1 场景种子映射（已在本次修复）

改动前 `1=network_security / 2=power_system / 3=flightdeck_operation / 4=geological_risk` 这张表被**手写了 4 遍**，且命名各不相同：

| 文件 | 原名称 | 类型 |
|---|---|---|
| `api/datasetApi.ts` | `SCENARIO_CODE_BY_ID` | `Record<number, ScenarioId>` |
| `api/reportApi.ts` | `SCENARIO_BY_ID` | `Record<number, ScenarioId>` |
| `api/riskThresholdApi.ts` | `SCENARIO_ID_TO_CODE` + 手写逆向 `SCENARIO_CODE_TO_ID` | 同上 |
| `api/situationApi.ts` | `SCENARIO_CODE_BY_ID` | `Record<number, string>`（弱类型） |

风险：种子顺序一旦调整（例如插入新场景），四个模块会各自漂移，出现"dataset 认为 3 是甲板、report 认为 3 是地质"的口径分叉，且不会有任何编译报错。
**已修复**：唯一权威表移到 `api/scenarioApi.ts:18` 并导出，其余 4 个文件改为导入；`situationApi` 侧顺带从 `string` 收紧为 `ScenarioId`。行为等价（4 处字面量逐字相同）。

### 5.2 SSE 流式解析重复（提案）

`api/inferenceRecordApi.ts:249-295`（`streamInferenceExplanation`）与 `api/modelEvaluationApi.ts:37+`（`streamModelEvaluation`）各有一份几乎逐行相同的 SSE 读取循环：`fetch` + `credentials:'include'` + `X-CSRF-Token` + `getReader` + `TextDecoder` + `\r?\n\r?\n` 分块 + `event:`/`data:` 正则 + `JSON.parse` + 事件分发，约 45 行 × 2。

差异仅在 URL 与 `onXxx` 回调名。抽取一个 `readSseStream(response, handlers)` 放到 `utils/**` 即可（`utils/**` 不属本分区，且新建文件违反协议 §1.7）→ **跨区提案**。

### 5.3 `trainingApi.js` 与其它 api 模块功能重叠（提案）

`api/trainingApi.js` 的 7 个导出中，4 个与已有模块重复：

| `trainingApi.js` | 重复对象 | 差异 |
|---|---|---|
| `getScenarios` | `scenarioApi.getScenarioList` | 返回裸后端结构 vs 映射后的 `Scenario[]` |
| `getAlgorithms` | `algorithmApi.getAlgorithms` | 同接口 |
| `getDatasets` | `datasetApi.getDatasetList` | 返回裸结构 vs 映射后的 `Dataset[]` |
| `trainModel` | `modelVersionApi.trainModel` | 同接口，两者都零引用（§2.2 #8/#14） |

即同一个后端接口存在两套前端封装、两套返回形状，调用方（`ModelCenter.vue` / `RiskAnalysis.vue`）拿到的类型不同，容易在字段名上踩坑。

---

## 6. `api/trainingApi.js` 混语言评估（优先级 4）

**事实**：全分区 14 个 api 文件中唯一 `.js`，61 行，无任何类型标注；7 个导出全部隐式 `any`。`tsconfig.app.json` 开了 `allowJs: true` 但**未开** `checkJs`，所以这个文件完全不受类型检查覆盖。

**影响面**：`views/Model/ModelCenter.vue:12`、`views/Model/RiskAnalysis.vue:30`、`stores/trainingJobStore.ts:24` 三个调用点全部拿到 `any`。其中 `RiskAnalysis.vue:235` 把 `trainModelAsync()` 的返回值直接断言成 `ModelVersionRow`，这条链路上没有任何编译期校验。

**判断**：属**历史遗留**（文件头注释自述"同步接口…仍在（trainModel 保留作回退用）"，是早期训练的入口，后来异步任务接口 `modelVersionApi` 起来后没回收），不是刻意的设计选择。

**为什么不直接改**：`.js` → `.ts` 需要新建 `.ts` 文件 + 删除 `.js` 文件，违反协议 §1.7「不得创建/删除文件」→ 仅提案（§8）。若后续获准，建议**同时做**：① 重命名为 `.ts` 并补类型；② 删掉零引用的 `trainModel`；③ 把 `getScenarios/getAlgorithms/getDatasets` 换成对应模块的封装（需同步改 3 个调用点，属跨区）。

---

## 7. 封装质量与代码卫生

### 7.1 `any` 使用点（本分区共 6 处代码 + 1 处注释）

| 位置 | 内容 | 处理 |
|---|---|---|
| `api/modelEvaluationApi.ts:7,17,21,22,71` | `Record<string, any>` ×5 | **提案**。改为 `unknown` 会立刻打断 `views/Model/ModelCenter.vue`（非本分区文件）的字段读取，必须与该分区协同 |
| `types/shims-vue.d.ts:3` | `DefineComponent<{}, {}, any>` | **保留**。Vue SFC 类型 shim 的社区标准写法，收紧没有收益 |
| `api/trainingApi.js` 全部导出 | 隐式 `any`（无类型标注） | 见 §6 |
| `types/security.ts:143` | 注释里的"禁止用 `as any` 绕过" | 非代码 |

**全分区无一处 `@ts-ignore` / `@ts-expect-error`，无 `as any`**（已 grep 验证：`as any` 唯一命中是上面那条注释）。

### 7.2 非空断言 `!`

唯一一处在 `api/situationApi.ts:109` 的 `byDay.get(day)!`（`buildDailyTrend`），**已修复**：改为 `[...byDay.entries()].sort(([a],[b]) => a<b?-1:a>b?1:0)` 后直接拿到 `arr`，非空断言消失且少一次 Map 查询。排序口径与原来的 `[...keys()].sort()`（默认字典序）一致。

### 7.3 其它质量观察

1. **`getDatasetDetail` 重复调用 `ensureScenarioMaps()`**（`api/datasetApi.ts:285-`）：函数开头调一次，内部又走 `resolveDatasetPk` → `getDatasetRawList` → `ensureScenarioMaps()`。有缓存所以只是冗余不是 bug；该函数本身零引用（§2.2 #1），不建议为它单独优化。
2. **`reportApi.ts` 用动态 `import('@/api/scenarioApi')`**（第 103 行 `buildGeneratePayload` 内）：同一文件顶部已经有静态 `import`，动态导入在 api 层没有代码分割价值（该模块本来就会被加载），属无意义复杂度。未改动的理由：去掉它需要把 `resolveScenarioId` 提到顶部静态导入，属行为无关但会动到 `reportApi` 的模块加载图，收益不足以承担回归风险 → 记入提案。
3. **魔法数字/字符串**：
   - `datasetApi.getDatasetRawList` / `fetchDatasetItems` 默认 `page: 1, page_size: 200`；
   - `riskThresholdApi.getRiskThresholdAuditLogs` 硬编码 `{page: 1, page_size: 200}`；
   - `reportApi` / `inferenceRecordApi` 分页默认 `page_size: 20`（`getInferenceRecordPage` 兜底）。
   建议提取具名常量（`DEFAULT_PAGE_SIZE = 20` / `MAX_PAGE_SIZE = 200`），属分区内低风险改动，本次**未做**（优先级低于死代码清理，且会扩大 diff）。
   - `reportApi.EXPORT_EXT` 已有具名常量（好例子）。
4. **URL 拼接**：全部为模板字符串直接拼，无重复拼接工具；`/api/v1` 前缀在每个函数里重复出现（16 个文件 × N 处），属"约定优于抽象"，不建议改动。
5. **错误处理**：全分区统一依赖 `utils/request` 的 axios 拦截器（非 0 code 抛异常），api 层无 try/catch 样板，**无重复错误处理**。两处 `catch` 均为"降级到种子映射"的有意兜底（`datasetApi.ensureScenarioMaps`、`riskThresholdApi.ensureScenarioMaps`），保留。
6. **未使用的 import**：无（`noUnusedLocals` 已开启，`vue-tsc` 通过即为证据）。
7. **`riskEventApi.ts:17` 遗留 `// TODO 联调对齐` 注释**：接口 `getRiskEventList` 已在实际使用（`situationApi` + `riskEventStore`），TODO 已过期，建议清理（未做，纯注释）。

---

## 8. 跨区 / 跨文件提案（需 Lead 裁决，本分区未执行）

| # | 提案 | 影响分区 | 说明 |
|---|---|---|---|
| P1 | 删除 §2.2 的 **14 个零引用 API 封装** | 本分区（api） | 硬约束禁止本 agent 删除已导出函数。证据齐备，可直接删；建议 Lead 统一执行并复跑 `vue-tsc` |
| P2 | 删除 `types/security.ts` 的 `toRiskLevel()` 与 `ScenarioDashboardData`（连带 `ScenarioDashboardCharts`/`RadarComparePoint`/`DataRow`） | 本分区（types） | 同上，零引用证据见 §4.1 |
| P3 | 删除 `Report.file_url` 字段 | 本分区（types） | 后端全仓 0 处产出该字段（§4.3），前端 0 处读取 |
| P4 | 后端删除 `DatasetStat.is_risk_label`，前端跟进 | **B6（后端）** + 本分区 | 与 `caliber_registered` 同值重复；**顺序必须是先后端后前端**，见 §3 |
| P5 | 抽取 SSE 解析公共函数（§5.2） | `utils/**` 或新建文件 | 新建文件违反协议 §1.7；需 Lead 授权 |
| P6 | `trainingApi.js` → `.ts` 并合并重复封装（§5.3、§6） | 本分区 + `views/Model/ModelCenter.vue`、`views/Model/RiskAnalysis.vue`、`stores/trainingJobStore.ts` | 重命名需新建/删除文件；合并需同步改 3 个调用点 |
| P7 | `modelEvaluationApi.ts` 的 5 处 `Record<string, any>` → `unknown` | 本分区 + `views/Model/ModelCenter.vue` | 会打断 ModelCenter 的字段读取，须协同 |

---

## 9. 自检

```
$ cd frontend
$ npx vue-tsc --noEmit -p tsconfig.app.json --tsBuildInfoFile node_modules/.tmp/tsb-F6a.json
EXIT=0
--- ALL ERRORS ---
(无)
--- MY PARTITION (api/ + types/) ---
(无)
```

全项目 0 错误。补充说明：自检过程中曾出现 1 条 `src/views/Model/Settings.vue(420,15): error TS2540: Cannot assign to 'value' because it is a read-only property`，该文件不在本分区（当时正被其它 agent 改动），后续复跑已消失，与本分区改动无关。

本分区**未执行**任何被协议 §1.3 禁止的命令（无 build / dev / preview / 服务启停 / pytest / DB 写入 / `git commit|checkout|stash|reset|clean`）。

---

## 10. 未及细查的项（明确留白，非"已确认无问题"）

1. **`types/security.ts` 与 `backend/app/schemas/**` 的逐字段对照未做全量比对**。本次只对 7 个高风险字段做了定向核对（`file_url` / `fault_position_x,y` / `class_distribution` / `view_weights` / `feature_evidence` / `is_risk_label` / `caliber_registered`）。`ReportData`（272-347 行，70+ 字段）与 `GlobalOverview` / `SituationData` 未逐字段核对。
2. **`api/dashboardApi.ts` 的 17 个"仅内部引用"类型未逐一判定其内部引用是否真实有效**（例如 `CountItem` 被 `AdminTotals`/`NetworkProfile` 等引用，是否每个引用字段后端都真的会下发，未核）。
3. **后端返回的字段可选性与前端类型的 `?` 是否一致**未系统核对（需要逐接口读 `backend/app/schemas/**`）。
4. **`getInferenceExplain` / `getModelEvaluation` 的返回结构与 Java 侧 `/predict` 实际输出的对齐**未核（只核到 Python 侧 `explanation_contract.py`）。
5. `api/**` 与后端路由的**逐条 URL 比对**只抽查了 14 个死封装涉及的路由（全部命中），未做 87 个导出函数的全量 URL 核对。
6. 本次未做**运行时验证**（协议禁止启动服务/构建），所有等价性结论均基于静态阅读与类型检查。

---

## 附：任务书行数已过期

任务书给出的各文件行数与仓库实际（HEAD）不一致，本报告一律以实测为准：

| 文件 | 任务书 | 实测 HEAD |
|---|---|---|
| `datasetApi.ts` | 454 | 488 |
| `dashboardApi.ts` | 419 | 459 |
| `types/security.ts` | 476 | 534 |
| `trainingApi.js` | 43 | 61 |
| `inferenceRecordApi.ts` | 260 | 298 |
| `reportApi.ts` | 208 | 252 |
| `situationApi.ts` | 155 | 167 |
| `modelEvaluationApi.ts` | 80 | 87 |
| `riskEventApi.ts` | 69 | 77 |
| `riskThresholdApi.ts` | 93 | 102 |
| `modelVersionApi.ts` | 104 | 123 |
| `userApi.ts` | 128 | 143 |
| `scenarioApi.ts` | 113 | 138 |
| `aiSettingApi.ts` | 27 | 27 |
| `algorithmApi.ts` | 10 | 11 |

（差异疑为任务书使用了"非空行数"口径；本报告用文件总行数。）
