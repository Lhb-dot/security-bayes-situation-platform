# F6b 分区审查报告 — stores/** + utils/**

- **分区**：F6b = `frontend/src/stores/**`（12 个文件）+ `frontend/src/utils/**`（5 个文件），共 **17 个文件 / 2117 行**（改前）。
- **不属本分区**：`frontend/src/api/**`、`frontend/src/types/**`、`frontend/src/style.css`（F6a / F6）；`views/**`、`components/**`、`App.vue`（其他分区，本报告只读不改）。
- **自检**：`cd frontend && npx vue-tsc --noEmit -p tsconfig.app.json --tsBuildInfoFile node_modules/.tmp/tsb-F6b.json` → **exit 0，零输出（全项目零类型错误）**。
- **本次改动**：6 个文件，`+80 / -25` 行（净 +55，多为解释性注释）。**未新建任何文件、未删除/重命名任何已导出的 store / action / getter / state**。
- 文件行数（改前 → 改后）：`trainingJobStore.ts` 325→340、`riskEventStore.ts` 59→69、`request.js` 105→124、`scrollChain.ts` 119→128、`scrollAnchor.ts` 78→80、`batchJobStore.ts` 334→334（2 行对调），其余 11 个文件未动。

---

## 1. 结论摘要

| # | 结论 | 级别 | 处置 |
|---|---|---|---|
| 1 | 三个 Job Store（1075 行）**共用一套引擎**：263 行物理代码属于逐字节重复，冗余副本 169 行；抽共享引擎可再消除约 240–250 行 | **高**（可维护性） | 提案（需新建文件） |
| 2 | `utils/jobSeen.ts` **不是重复实现**，是三个 Job Store 唯一的已读集合实现，分工清晰 | — | 保持 |
| 3 | **3 个整店死代码**：`reportStore.ts`、`situationStore.ts`、`thresholdStore.ts` 全项目零引用（`thresholdStore` 的功能已被 `views/Model/Settings.vue` 直连 api 取代） | **中** | 提案删除（硬约束禁止） |
| 4 | **19 个死导出成员**：死 action 11 个、死 getter 3 个、死 state 3 个、无外部消费者的类型/工具导出 7 个 | **中** | 提案删除（硬约束禁止） |
| 5 | `trainingJobStore` 存在**每秒重复弹通知**的隐患（状态被改成 PUBLISHED 等非 DRAFT/FAILED 时），已修（`settledIds` 幂等闸） | **中**（低概率高影响） | **已修** |
| 6 | `utils/request.js` 的 storage 访问**无 try/catch**：隐私模式下 401 分支会抛异常，`unauthorizedHandler()` 不执行 | **中** | **已修** |
| 7 | `request.js` 的响应拦截器把 axios 错误压成裸 `new Error(msg)`，丢掉 `response`/`status`；`views/Model/RiskAnalysis.vue:247,272` 的 `e.response?.data?.message` 分支因此成了死代码 | **中** | 提案（改动影响 `api/**` 与 `views/**`） |
| 8 | 轮询定时器 / 事件监听器**无泄漏**：三个 store 都在无在途任务时 `stopPolling`，`reset()` 兜底；`App.vue` 两个定时器都清了；`scrollChain` 的 wheel 监听在 `DataPreviewTable.vue` 里成对解绑 | — | 无问题 |
| 9 | 无 `console.log`、无 `@ts-ignore`、无 `any`、无 `var`、无未处理的 promise rejection | — | 无问题 |
| 10 | 魔法值：`scrollChain` 的 `16`/`1`、`scrollAnchor` 的 `0.5`、`request.js` 的 `timeout: 0`、`riskEventStore` 的伪类型断言 | 低 | 前三个**已修**，后两个提案 |

---

## 2. 【核心】三个 Job Store 的重复度分析与统一方案

三个文件分别是 `reportJobStore.ts`(416) / `trainingJobStore.ts`(325) / `batchJobStore.ts`(334)，合计 **1075 行**，都是「提交任务 → 1s 轮询 → 终态弹通知 → 已读集合（localStorage）→ 过期清理」这同一套引擎。

### 2.1 逐函数对照表

行号区间为**改前**行号；「关系」列只描述实现，不含业务字段差异。

| 职责 | reportJobStore | trainingJobStore | batchJobStore | 关系 |
|---|---|---|---|---|
| 常量 `POLL_INTERVAL_MS = 1000` | 56 | 35 | 29 | **值完全相同** |
| 常量 `MAX_FINISHED = 20` | 64 | 43 | 33 | **值完全相同** |
| 常量 `FINISHED_TTL_MS = 24h` | 75 | 53 | 43 | **值完全相同** |
| 常量 `POLL_TIMEOUT_MS` | 62（20min） | 41（65min） | 31（40min） | 仅数值不同 → 可作参数 |
| 模块级 `pollTimer` / `polling` | 77-78 | 80-81 | 69-70 | **逐字节相同** |
| `currentUid()` | 80 | 94 | 72 | **逐字节相同** |
| `toMillis()` / `parseServerTime()` | 83-87 | 101-105 | 74-77 | report 与 batch **逐字节相同**；training 多补 `+08:00` |
| `messageOf()` | 106-107 | 107-108 | 79-80 | **逐字节相同** |
| `isTerminal()` | 109 | 113 | 82 | 仅任务类型名不同 |
| `state.jobs` / `state.seenIds` | 113/115 | 121/123 | 86/88 | 结构相同 |
| `state.completedTick` | 117 | — | 90 | report/batch 相同 |
| getter `runningJobs` | 121 | 137 | 100 | **逐字节相同（除类型名）** |
| getter `finishedJobs` | 124 | 140 | 103 | 同上 |
| getter `unseenJobs` | 127-131 (5行) | 143-147 (5行) | 112-116 (5行) | 结构相同，id 字段名不同 |
| getter `running` / `activeJob` | — | 128 / 131-135 | 97 / 106-110 | training 与 batch 相同 |
| `startPolling()` | 184-187 | 165-169 | 136-140 | **逐字节相同** |
| `stopPolling()` | 190-195 | 171-177 | 142-148 | **逐字节相同** |
| `syncSeen()` | 198-199 | 179-180 | 150-151 | **逐字节相同** |
| `reset()` | 212-221 | 193-203 | 164-175 | 骨架相同（batch 多清 `lastResult`） |
| `markAllSeen()` | 224-238 | 206-220 | 177-193 | 骨架相同，仅 id 字段名不同 |
| `resumePending()` | 242-284 (43行) | 223-241 (19行) | 195-222 (28行) | 骨架相同：`reset → 读已读集合 → 列任务 → 逐行登记 → catch 静默 → purgeExpired` |
| `_tick()` | 287-326 (40行) | 243-274 (32行) | 224-266 (43行) | 骨架相同：重入锁 → 取在途 → 空则停表 → 逐条算 elapsed → 超时 → 取远端状态 → 判终态 → 单条 try/catch → 尾部停表 → finally 解锁 |
| `_settle()` | 328-352 (25行) | 275-297 (23行) | 267-291 (25行) | `_trimFinished + ElNotification` 骨架相同，通知分支不同 |
| `_trimFinished()` | 354-371 (18行) | 299-316 (18行) | 293-310 (18行) | **仅 id 字段名不同** |
| `purgeExpired()` | 373-380 (8行) | 318-328 (11行) | 312-322 (11行) | 骨架相同 |
| `_timeout()` | 406-416 (11行) | 330-340 (11行) | 324-334 (11行) | 仅文案 / 字段名不同 |
| 业务独有 | `_track`/`trackGenerate`/`trackExport`/`safeFileName`/`saveBlob`/`_downloadExport`/`runningExportIds`/`runningTitles` | `track`/`STATUS_*`/`trainingJobTitle`/`parseServerTime` | `track`/`lastResult`/`BatchStatus` | 应当保留在各店 |

### 2.2 量化

对三个文件做「去空行、去注释、折叠空白、丢弃长度 < 8 的短行」后的规范化代码行统计：

- 规范化代码行：report 198 + training 149 + batch 166 = **513 行**（对应 1075 物理行）。
- 在 ≥2 个文件中**逐字节出现**的不同代码行：**106 行**。
- 这些行占用的**物理行实例：263 行**（即 1075 行里有 263 行身处重复块中）。
- 减去各自保留一份后的**冗余副本：169 行**（可直接消除的下限）。
- 按函数粒度（上表）估算：把 `pollTimer/polling`、`currentUid`、`messageOf`、`isTerminal`、四个常量、`startPolling/stopPolling/syncSeen/reset/markAllSeen/_trimFinished/purgeExpired/_timeout` 以及 `_tick/_settle/resumePending/track` 的公共骨架合起来，**可消除约 240–250 行（≈23%）**。

> 说明：统一引擎本身要新增约 150–180 行，所以**净减只有约 70–95 行**。真正的收益不是行数，而是「轮询/清理/已读只有一份实现」——当前任何一处逻辑修正（例如下面第 8 节的幂等闸、超时口径）都要在三个文件里各改一遍，已经出现过 `isTerminal` 与 `isTerminalStatus` 这种同文件内重复。

### 2.3 统一方案（提案：新增 `frontend/src/stores/jobQueue.ts`）

**推荐：工厂函数（闭包持有定时器），而不是「共享模块级变量 + 混入 actions」。**

关键坑（必须写进实现里）：三个 store 现在各自持有**模块级**的 `let pollTimer` / `let polling`。若把它们搬进一个共享模块，三个 store 会共用同一个定时器槽位——A 店在轮询时 B 店 `startPolling()` 会被 `if (pollTimer !== null) return;` 直接吞掉，**B 店永远不轮询**。所以共享实现必须让每个 store 拿到自己的槽位，工厂闭包天然满足：

```ts
// frontend/src/stores/jobQueue.ts（提案，本分区不新建文件）
export interface JobQueueJob { status: string; error: string | null; startedAt: number; elapsed: number; }

export function createJobQueue<T extends JobQueueJob>(config: {
  id: string;                                  // defineStore 的 id，只用于日志
  keyOf: (job: T) => string;                   // 已读 / 去重 / 通知幂等用的业务 id
  terminalStatuses: string[];
  pollTimeoutMs: number;
  extraState?: () => Record<string, unknown>;  // completedTick / lastResult
  extraGetters?: Record<string, (state: any) => unknown>;
  fetchOne: (job: T) => Promise<Partial<T>>;   // _tick 里取远端状态
  listPending: () => Promise<T[]>;             // resumePending 里的列表接口
  onSettle?: (job: T, store: any) => void;     // 通知 / 下载导出 / 写 lastResult
  onTick?: (job: T, store: any) => void;       // 逐条额外同步（processed/total）
}) { /* 内部持有 let pollTimer / let polling / const settled = new Set<string>() */ }
```

工厂内部提供（全部为现在的公共骨架）：`startPolling`、`stopPolling`、`syncSeen`、`reset`、`markAllSeen`、`resumePending`、`_tick`、`_settle`、`_trimFinished`、`purgeExpired`、`_timeout`，以及 getter `runningJobs`/`finishedJobs`/`unseenJobs`/`running`/`activeJob`。

迁移后每个 store 只剩：类型声明 + 状态 + 业务取数/映射 + `onSettle` 文案 + 自己的独有 action（`trackGenerate`/`trackExport`/`_downloadExport`/`lastResult`）。预计三文件 1075 → **450–550 行**。

**必须保持的行为契约（迁移时的验收点）**：
1. `defineStore` 的 id 不变（`'reportJob'`/`'trainingJob'`/`'batchJob'`，调试工具与持久化依赖它）。
2. 三个 store 的**导出名一个都不能变**：`useReportJobStore`、`useTrainingJobStore`、`useBatchJobStore`，以及 `App.vue`、`views/Model/{ReportCenter,RiskAnalysis,RiskInference}.vue` 用到的全部 action/getter 名（详见第 4 节的反向证据）。
3. `POLL_TIMEOUT_MS` 各店不同（20/65/40 分钟），必须参数化而不是取一个「统一值」。
4. `resumePending()` 里「先 `reset()` 再拉」的顺序不能动，否则上一个账号的残留会挂进当前账号的顶栏。
5. `markAllSeen` 只写 id 不删行（顶栏面板正在展示这些行）。

**渐进路线（推荐）**：先只抽 6 个模块级纯函数（`currentUid`/`messageOf`/`isTerminal`/`toMillis` + 4 个常量，约 30 行），再抽 8 个骨架 action，最后再合并 `_tick/_settle/resumePending`。每步都可独立验证。

---

## 3. `utils/jobSeen.ts` 与三个 Job Store 的关系

**结论：不是重复实现，是这三个 store 唯一共享的底层设施，分工正确，无需改动。**

- `jobSeen.ts`(114 行) 只负责「按账号分桶的已读 id 集合」：`readSeenIds(uid)`、`markSeenIds(uid, ids)`、`onSeenIdsChange(cb)`；key `bayes_seen_job_ids`，`MAX_IDS=400`、`MAX_ACCOUNTS=8`，带 `{uid,ids}` 旧格式迁移，localStorage 全部包在 try/catch 里，模块级只注册 **1 个** `storage` 监听（`listening` 标志守卫，避免热更新重复注册）。
- 三个 store 各自只做：`syncSeen()` 读一次、`markAllSeen()` 写一次、`unseenJobs` 用它过滤。三份调用点逐字节相同（各 2 行），属于第 2 节引擎骨架的一部分。
- `App.vue` 订阅 `onSeenIdsChange` 后转调 `syncSeen()`，实现跨标签页已读同步；`onBeforeUnmount` 里调 `stopSeenSync()` 解绑。**没有重复实现，也没有泄漏。**
- 唯一可挑剔处：`MAX_IDS=400` / `MAX_ACCOUNTS=8` 是硬编码上限，超出后按 LRU 丢弃（代码已注释说明），可接受。

---

## 4. 死代码清单（全部经全项目 grep 验证，**受硬约束一律只报告不删除**）

grep 范围：`frontend/src/**/*.{ts,vue,js}`，排除符号自身的定义文件；命令用 `Select-String -SimpleMatch`（避免把 `userStore.isAdmin` 这类点号当正则）。

### 4.1 整店死代码（3 个文件 / 124 行）

| 文件 | 导出 | 外部引用数 | 证据 |
|---|---|---|---|
| `stores/reportStore.ts`(38行) | `useReportStore` | **0** | 全项目仅自身文件出现 |
| `stores/situationStore.ts`(34行) | `useSituationStore` | **0** | 同上（首页态势数据走 `api/situationApi.ts` + `views/Home/**` 自己取） |
| `stores/thresholdStore.ts`(52行) | `useThresholdStore` | **0** | 功能已被 `views/Model/Settings.vue:271,307` 直连 `getRiskThresholds` / `getRiskThresholdAuditLogs` 取代 |

> `reportStore` 与 `reportJobStore` **不是重复关系**：前者是同步报告列表/详情的普通 store，后者是后台任务队列；前者没人用，后者被 `App.vue` + `ReportCenter.vue` 使用。同理 `situationStore` 与 `riskEventStore` 也不重复（后者被 `RiskEventDetailView.vue` 使用）。

### 4.2 死 action（11 个）

| store | action | 外部引用 | 备注 |
|---|---|---|---|
| `datasetStore` | `fetchVersions` | 0 | 仅被同店 4 个死 action 内部调用 |
| `datasetStore` | `uploadDataset` | 0 | 页面走 `api/datasetApi.uploadDatasetFile`（`DatasetCenter.vue:16,161`） |
| `datasetStore` | `createVersion` | 0 | 页面走 `api/datasetApi.createDatasetVersion`（`DatasetCenter.vue:17,213`） |
| `datasetStore` | `disableVersion` | 0 | 页面走 `api/datasetApi` 直连（`DatasetCenter.vue:255` 的 `handleDisableVersion`） |
| `datasetStore` | `removeVersion` | 0 | 无任何引用 |
| `riskEventStore` | `fetchEvents` | 0 | 列表页 `AlertsView.vue` 走 `api/riskEventApi` 直连 |
| `riskEventStore` | `clearDetail` | 0 | 详情页用 `fetchDetail` 覆盖，不显式清 |
| `inferenceStore` | `fetchRecords` | 0 | **仅被同店 `executeInference` 内部调用一次**（见 5.4） |

（另 3 个：`inferenceStore` 的 `records` 状态与 `lastResult` 状态无任何读取方，见 4.3。）

> 这一簇是典型的「store 写了一半、页面改用 api 直连」的残留：`datasetStore` 的 5 个死 action 互相调用形成闭环（`uploadDataset`→`fetchVersions`→…），**外部零入口**，整体可删。

### 4.3 死 getter / 死 state

| store | 成员 | 类型 | 外部引用 | 备注 |
|---|---|---|---|---|
| `userStore` | `isAdmin` | getter | **0** | 各页面用本地 `computed` 自行判断（30 处 `isAdmin` 全是本地变量） |
| `userStore` | `isScenarioAdmin` | getter | **0** | 同上（`Settings.vue` 的 2 处也是本地变量） |
| `datasetStore` | `datasetsByScenario` | getter | 0 | 页面自己 `datasets.filter(...)`（`RiskInference.vue:99`） |
| `riskEventStore` | `eventsByScenario` | getter | 0 | — |
| `riskEventStore` | `highRiskCount` | getter | 0 | — |
| `inferenceStore` | `records` | state | 0 | 无任何读取方 |
| `inferenceStore` | `lastResult` | state | 0 | 注意：`RiskInference.vue:491` 读的是 **`batchJobStore.lastResult`**，不是它 |
| `datasetStore` | `loading` | state | 0 | 只写不读 |
| `scenarioStore` | `loading` | state | 0 | 只写不读 |
| `riskEventStore` | `loading` | state | 0 | 只写不读 |
| （对照）`userStore.loading` | state | 1 | `UserManagement.vue:22` 在读 → **不是死代码** |

### 4.4 无外部消费者的导出（7 个，可降级为非导出）

`reportJobStore`：`ReportJobKind`、`ReportJobStatus`、`BackgroundReportJob`；`trainingJobStore`：`BackgroundTrainingJob`、`trainingJobTitle`；`batchJobStore`：`BackgroundBatchJob`、`BatchJobResult` —— 全部 0 外部引用，只在各自文件内使用。删 `export` 即可（**不删定义**，风险为零），但同样属于「改导出面」，列为提案。

### 4.5 已确认**不是**死代码（防止后续误删）

`useUserStore`(21 个消费文件)、`useSettingsStore`、`useDatasetStore`、`useScenarioStore`、`useRiskEventStore`、`useInferenceStore`(仅 `executeInference`)、`useTrainingJobStore`/`useReportJobStore`/`useBatchJobStore`(均被 `App.vue` + 页面使用)、`jobSeen` 三个导出、`formatExplanation`/`shortExplanation`、`keepScroll`(7 个文件)、`attachOuterFirstWheel`、`unwrapData`(14 个 api 文件)、`setUnauthorizedHandler`(`main.ts`)、`setCsrfToken`(`api/userApi.ts`)。

---

## 5. `utils/request.js` 专项（唯一的 .js 文件，105→124 行）

### 5.1 错误吞掉 / 后端 detail 泄漏 —— **部分已修，其余提案**

现状：响应拦截器 `error => Promise.reject(new Error(await extractErrorMessage(error)))`。

- `extractErrorMessage` 的实际顺序是：Blob 解包 → `data.message`(string) → `data.detail`(string) → `data.detail`(数组，逐项取 `msg`/`message` 后用 `; ` 连接) → `data.detail.message`(对象) → `error.message` → `'请求失败'`。它把**后端原文**（含 Pydantic 校验细节、内部字段名）直接展示给用户。风险等级：中低（同一系统内部平台，后端文案已中文友好），**不建议在本轮改动**，因为 `views/**` 大量 `catch (err) { ElMessage.error(err.message) }` 依赖这层文案，改口径会波及多个分区。
- **真正的类型损失**：`new Error(msg)` 丢掉了 `response`/`status`/`code`。直接后果：`views/Model/RiskAnalysis.vue:247` 与 `:272` 的 `e.response?.data?.message` 分支**永远取不到值**（`e` 是裸 `Error`），已成死代码。修法（提案，见第 11 节）是在 `Error` 上挂回 `status`/`code`，属于**加法**，向后兼容。
- `extractErrorMessage` 对 `Blob` 响应做了 JSON 解包（导出接口 4xx 时后端返回 JSON 而 axios 按 `responseType:'blob'` 收到 Blob），这个处理是必要的，保留。

### 5.2 token / storage —— **已修**

`setCsrfToken`、`currentCsrfToken`、401 分支的 `localStorage.removeItem` 三处原先**裸调 storage**。隐私模式 / 禁用 Cookie 的浏览器会抛 `SecurityError`；在 401 分支里 `setCsrfToken(null)` 一抛，后面的 `unauthorizedHandler()`（`main.ts` 注册，负责跳登录页）就**不会执行**，用户卡在「已登出但界面以为还在登录」。

已改为统一的 `safeStorage(run, fallback)` 降级包装（`+19` 行含注释）。CSRF 令牌本身有 cookie 兜底（`readCookie` 优先），读不到只退化成「本标签页不带 `X-CSRF-Token`」，与后端 `same-site` cookie 校验配合仍可用。

`bayes_session_user_id` 这个 localStorage key：**全项目只有这一处 `removeItem`，没有任何写入方**，是历史遗留清理。保留（不确定是否有旧版本残留需要清），只加了 try/catch 与注释。

### 5.3 `timeout: 0` —— 提案

`axios.create({ timeout: 0 })` 表示**永不超时**。后端批量研判走异步任务接口（见 `api/inferenceRecordApi.ts` 注释），同步接口最坏十几分钟，所以不能设小值；但「永不超时」会让断网/nginx 挂起时请求永久悬挂、`loading` 永远不结束。提案：设为 0 之外的一个大值（如 15 分钟）或对长任务接口单独放宽。**涉及全局行为，不改。**

### 5.4 `.js` → `.ts` 提案

`request.js` 是 `utils/` 与 `api/` 里唯一的 JS 文件，14 个 api 文件 `import { unwrapData } from '@/utils/request'`。改成 `request.ts` 后 import 路径不变，可获得 `AxiosResponse` 泛型与 `unwrapData<T>` 的类型推导（现在 `unwrapData` 返回值是 `any`，是 `api/**` 里类型断言的来源之一）。**新建/重命名文件属提案，本轮不做。**

### 5.5 已确认无问题的点

- 请求拦截器只在有令牌时加 `X-CSRF-Token`，无令牌不写空串。
- `unwrapData` 对 `res.code !== 0` 抛后端 `message`，`res.data` 为 `undefined` 时也能正常走到抛错分支。
- `setUnauthorizedHandler` 单槽位覆盖式注册，`main.ts` 只注册一次，符合预期。

---

## 6. `scrollChain.ts`(119→128) vs `scrollAnchor.ts`(78→80)

**职责不重叠，但有一处真实重复（已修）。**

| | `scrollChain.ts` | `scrollAnchor.ts` |
|---|---|---|
| 用途 | 「外层先滚到底，再滚内层」的滚轮穿透（表格嵌在弹窗里时） | 数据刷新后按业务锚点（行 id / 记录 id）恢复滚动位置 |
| 消费方 | `DataPreviewTable.vue` 的 `attachOuterFirstWheel` | 7 个页面的 `keepScroll` |
| 监听器 | 加 `{passive:false}`，返回的 detach 用 `removeEventListener(type, handler)` 解绑 | 不加监听器，只读 `scrollTop` 后写回 |

- **重复项（已修）**：两处各写了一份 `const SCROLLABLE_OVERFLOW = /^(auto|scroll|overlay)$/`，`scrollAnchor.ts` 里用注释「与 scrollChain.ts 保持一致」靠人工同步。已改为 `scrollChain.ts` 导出该正则、`scrollAnchor.ts` import 复用。
- **监听器泄漏：无**。`DataPreviewTable.vue` 在 ref watcher 与 `onBeforeUnmount` 两处都调了 `detachWheel?.()`；解绑时 `removeEventListener(type, handler)` 不带 options 也能正确移除（`capture` 默认 false，与添加时一致）。
- **魔法值（已修）**：`scrollChain` 的 `deltaY * 16`（行模式像素估算）→ `LINE_HEIGHT_PX`；`> 1` / `<= 1` 的溢出容差（3 处）→ `SCROLL_EPSILON_PX`；`scrollAnchor` 的 `> 0.5` → `POSITION_EPSILON_PX`。
- 潜在风险（低，未改）：`findInnerScroller` 用 `document.elementFromPoint` 做命中测试，若指针已在视口外会返回 `null`（已有 `if (!hit) return` 兜底）；`scrollAnchor.restore` 连做 3 次恢复（立即 / `nextTick` / `rAF`）是应对虚拟列表渲染时序的必要手段，但**三次都会写 `scrollTop`**，在长列表上可能引起 3 次重排。属于性能可选项，不作为缺陷。

---

## 7. `explanationText.ts`(64 行)

- 两个导出都有消费方，**无死分支**：`formatExplanation` → `views/Event/RiskEventDetailView.vue`（2 处）；`shortExplanation` → `views/Alert/AlertsView.vue`（3 处）。
- `RAW_SCORE = /(风险评分：)(\d+\.\d{6,})/g` 用 6 位以上小数来识别「未经格式化的原始分数」——**依赖后端把浮点原样拼进中文文案**。这是个脆弱契约：后端一旦把 `0.123456` 改成 `0.1235`（4 位），正则不再命中，界面上就会直接显示 `风险评分：0.1235` 这种原始值。建议（提案，跨区）后端统一用固定文案模板，或前端改为按数值格式化而不是正则替换。
- `VERDICT_HEAD` / `ADVICE_TAIL` 是纯常量切分标记，实现正确；`shortExplanation` 的截断长度是硬编码（若与 UI 宽度不匹配只会显示省略号，无功能风险）。
- 正则带 `g` 标志且用于 `String.replace`（非 `test`/`exec`），**无 `lastIndex` 状态残留问题**。

---

## 8. 正确性隐患

### 8.1 【已修】`trainingJobStore` 终态通知不幂等 → 每秒重复弹窗

`_tick` 的判据是「状态不再是 `TRAINING` 就 `_settle`」，而 `isTerminal` 只认 `DRAFT`/`FAILED`。两个口径不一致：当版本状态变成 `PUBLISHED`/`OFFLINE`/`DISABLED`（管理员在轮询间隔内改状态，或接口返回空状态 `''`）时，该任务**既不算终态**（继续留在 `runningJobs` 里被轮询、顶栏一直显示「训练中」），**又每一拍都满足 `_settle` 条件** → 每秒弹一条通知，持续到 `POLL_TIMEOUT_MS`（65 分钟）超时。

- 可达性：需要 1 秒窗口内状态被改成非 `DRAFT`/`FAILED`，**概率低但非零**（后端 `list_training_jobs` 只会返回 `TRAINING/DRAFT/FAILED`，所以**恢复路径不可达**，只有轮询路径存在该竞态）。
- 已修：新增模块级 `const settledIds = new Set<number>()`，`_settle` 开头「已通知过就直接返回」，`reset()` 里 `settledIds.clear()`。**不改变任何导出面**。
- 残留（已记录，未修）：上述竞态下任务仍会留在在途列表直到 65 分钟超时。彻底修法需要把「在途」判据改成 `status === TRAINING`（与「终态」判据解耦），会改变 `runningJobs`/`finishedJobs` 的语义，列为提案。

### 8.2 轮询定时器清理 —— **无泄漏**

- `startPolling()` 有 `if (pollTimer !== null) return` 单例守卫；`stopPolling()` 清 `setInterval` 并置 `null`；三个 store 的 `_tick` 尾部都有「没有在途任务就 `stopPolling()`」，`reset()` 第一句也是 `stopPolling()`。
- `App.vue` 的 60s `expiryTimer` 与 `onSeenIdsChange` 订阅都在 `onBeforeUnmount` 里清理。
- `jobSeen.ts` 的 `storage` 监听是**应用生命周期**级别的单例（`listening` 守卫），设计如此，非泄漏。
- 唯一注意点：`_tick` 是 `async`，`stopPolling()` 只清定时器**不会取消在途请求**；靠模块级 `polling` 重入锁避免叠加请求，行为正确（`stopPolling` 后当前这一拍仍会跑完并可能再次 `_settle`——已由 8.1 的幂等闸覆盖）。

### 8.3 全局可变状态

- 三个 store 的模块级 `pollTimer`/`polling`：单例 store 场景下正确（见 2.3 的迁移警告）。
- `trainingJobStore.settledIds`（本次新增）：模块级 `Set`，随 `reset()` 清空；长期不登出且训练很多时会缓慢增长（每个 id 一个数字，量级可忽略）。
- 无其他模块级可变状态。

### 8.4 未处理的 promise rejection —— 无

`startPolling` 用 `window.setInterval(() => void this._tick(), ...)`：`void` 只是显式丢弃返回值，`_tick` 内部整体包了 `try/finally`，逐条请求又有内层 `try/catch`，**不会产生未捕获 rejection**。`App.vue` 里 `void reportJobStore.resumePending()` 同理（`resumePending` 内部 try/catch）。`resumePending` 的 `catch {}` 是空块，但都带注释说明「恢复失败不影响页面」，属于有意静默，可接受。

### 8.5 `localStorage` / `sessionStorage` 无 try/catch

- 已修：`request.js` 三处（见 5.2）。
- 原本就安全：`jobSeen.ts`、`settingsStore.ts` 全部包了 try/catch。
- 其余 store 不碰 storage。

### 8.6 其他已确认无问题

- `toMillis`：`Number.isFinite(createdAt) && createdAt > 0 ? createdAt * 1000 : Date.now()`，**无条件按 epoch 秒 ×1000**（后端统一返回秒），非法/缺失时回落到当前时间。注意它不区分秒与毫秒——若后端某天改成返回毫秒，时间轴会放大 1000 倍；`api/inferenceRecordApi.ts` 的 `created_at` 注释已明确写「epoch 秒」，属于有文档支撑的隐式契约，不改。
- `parseServerTime` 对 `'YYYY-MM-DD HH:mm:ss'` 补 `+08:00` 再 `new Date()`，正确处理了「无时区的北京时间字符串」在 UTC 环境被当成 UTC 的坑；非法输入返回 `null` 由调用方兜底。
- `safeFileName` 去掉 `\/:*?"<>|` 与控制字符、去首尾点空格、截断 60 字符，与后端 `report_export.safe_filename` 同口径。
- `saveBlob` 用完 `URL.revokeObjectURL`，无内存泄漏。
- `batchJobStore._tick` 只在 `status === DONE && view.result` 时 `_settle`；若后端出现 `DONE` 但 `result === null`（接口注释保证不会），任务会静默停在在途列表直到超时——已记录，不作为缺陷。

---

## 9. 代码卫生

- **`console.log` / `debugger` / `TODO`：0 处**（`stores/**` + `utils/**` 全量 grep）。
- **`any`：0 处**；`as any`：0 处；`@ts-ignore` / `@ts-expect-error`：0 处；`var`：0 处。
- **非空断言 `!`**：0 处（`?.` 与 `??` 使用规范）。
- **伪类型断言（已修一处）**：`riskEventStore.updateStatus` 原先 `(STATUS_VALUE[status] ?? status) as RiskEvent['status']`——把英文枚举断言成中文联合类型。根因是 `api/riskEventApi.ts:59` 把参数类型声明成了 `RiskEvent['status']`（中文），而后端 `PUT /risk-events/{id}/handle` 收的是 `PENDING/PROCESSING/RESOLVED`。已把 `STATUS_VALUE` 收紧为 `Record<RiskEvent['status'], string>`（穷举，状态增删会直接编译报错）并去掉不可达的 `?? status` 兜底，断言处加了 ⚠️ 注释指向跨区提案。
- **魔法值（已修 5 处）**：`scrollChain` 的 `16`、`1`×3，`scrollAnchor` 的 `0.5`。剩余（提案）：`request.js` 的 `timeout: 0`、`reportJobStore.safeFileName` 的 `.slice(0, 60)`、`jobSeen` 的 `MAX_IDS/MAX_ACCOUNTS`（已有注释说明）、`explanationText` 的截断长度。
- **`noUnusedLocals`/`noUnusedParameters` 已开启**且 `vue-tsc` 零错误 → 不存在未使用的 import / 局部变量（这是免费的死代码探测器，本次改动后仍为 0）。

---

## 10. 本次实际改动清单（6 个文件，`+80/-25`）

| 文件 | 改动 | 理由 |
|---|---|---|
| `utils/request.js` | 新增 `safeStorage(run, fallback)`；`setCsrfToken`、`currentCsrfToken`、401 分支的 `localStorage.removeItem` 全部走它；补注释 | 隐私模式抛 `SecurityError` 会阻断 `unauthorizedHandler()`；storage 里存的都是可再生缓存（5.2） |
| `stores/trainingJobStore.ts` | ① `isTerminal` 改为委托 `isTerminalStatus`（消除同文件内重复函数体）② 新增模块级 `settledIds` 幂等闸 + `reset()` 清空（修 8.1）③ `_tick` 用现成的 `runningJobs` getter 与 `running` getter 替代内联 filter/some | 正确性 + 去重，导出面零变化 |
| `stores/batchJobStore.ts` | `_tick` 用现成的 `runningJobs` / `running` getter 替代内联 filter/some | 与 `reportJobStore` 写法对齐，为统一引擎铺路 |
| `stores/riskEventStore.ts` | `STATUS_VALUE` 收紧为穷举 `Record<RiskEvent['status'], string>`；去掉不可达 `?? status`；断言处加 ⚠️ 说明 | 类型安全；让状态增删变成编译错误而不是静默漏发 |
| `utils/scrollChain.ts` | `SCROLLABLE_OVERFLOW` 改为导出；新增 `SCROLL_EPSILON_PX`、`LINE_HEIGHT_PX` 常量并替换 5 处魔法值 | 去重 + 可读性 |
| `utils/scrollAnchor.ts` | 改为 import 复用 `SCROLLABLE_OVERFLOW`；新增 `POSITION_EPSILON_PX` 替换 `0.5` | 去重 + 可读性 |

**未改动**：`reportJobStore.ts`、`jobSeen.ts`、`userStore.ts`、`datasetStore.ts`、`scenarioStore.ts`、`settingsStore.ts`、`inferenceStore.ts`、`reportStore.ts`、`situationStore.ts`、`thresholdStore.ts`、`explanationText.ts`。

---

## 11. 跨区变更提案（需要其他分区/负责人执行）

### 提案 1：`utils/request.js` 错误对象带回 `status` / `code`（影响 `api/**`、`views/**`）

现状：`views/Model/RiskAnalysis.vue:247,272` 的 `e.response?.data?.message` 永远取不到值（拦截器已把 axios 错误压成裸 `Error`）。修法是加法，向后兼容：

```diff
--- a/frontend/src/utils/request.js
+++ b/frontend/src/utils/request.js
@@
-    return Promise.reject(new Error(await extractErrorMessage(error)));
+    // 保留 HTTP 状态与业务 code：视图层要按 401/403/409 做分支，
+    // 只给一句 message 会让它们只能靠中文文案做字符串比较。
+    const wrapped = new Error(await extractErrorMessage(error));
+    wrapped.status = error?.response?.status ?? null;
+    wrapped.code = error?.response?.data?.code ?? null;
+    return Promise.reject(wrapped);
```
（TS 版本需把 `wrapped` 断言为 `Error & { status?: number; code?: number }`。）同步清理 `views/Model/RiskAnalysis.vue:247,272` 的死分支属于视图分区。

### 提案 2：`api/riskEventApi.ts` 处置状态参数类型（影响 F6a 分区）

```diff
--- a/frontend/src/api/riskEventApi.ts
+++ b/frontend/src/api/riskEventApi.ts
@@
 export const updateRiskEventStatus = async (
   eventId: string,
-  params: { new_status: RiskEvent['status']; comment?: string }
+  // 后端 handle 接口收的是英文枚举；这里原先写成 RiskEvent['status']（中文口径），
+  // 逼得 stores/riskEventStore.ts 只能加断言绕过。
+  params: { new_status: 'PENDING' | 'PROCESSING' | 'RESOLVED'; comment?: string }
 ): Promise<RiskEvent> => unwrapData(await request.put(`/api/v1/risk-events/${eventId}/handle`, params));
```
改完后 `stores/riskEventStore.ts` 里那句 `as RiskEvent['status']` 可直接删除。

### 提案 3：统一 Job 轮询引擎（新增 `frontend/src/stores/jobQueue.ts`）

见第 2.3 节。涉及新建文件，需负责人批准后由一个 agent 独占实施（三个 store + `App.vue` 的联调验证）。

### 提案 4：删除死代码（3 个整店 + 11 个 action + 3 个 getter + 3 个 state + 7 个 `export` 降级）

见第 4 节。**每一处都附了零引用证据**。建议合并为一次独立提交，并在提交前重新跑一遍 grep（其他分区可能正在新增引用）。

### 提案 5：`inferenceStore.executeInference` 里的无效请求

```diff
--- a/frontend/src/stores/inferenceStore.ts
+++ b/frontend/src/stores/inferenceStore.ts
@@
       const result = await predictSingle(payload);
       this.lastResult = result;
-      // 顺手刷新一下记录列表（列表页自己会拉，这里只是让返回时数据是新的）
-      await this.fetchRecords();
       return result;
```
理由：`fetchRecords` 的产物 `this.records` 全项目零读取（4.3 已证），这次额外 `GET /inference-records` 纯属浪费，且失败时会**覆盖**上面成功的推理结果（内层 try 抛错会让 `executeInference` 整体 reject）。属于行为变更，故列为提案。

### 提案 6：视图层直接写 store 状态（视图分区）

`views/Model/RiskInference.vue:299,306` 直接 `datasetStore.datasets = []`，绕过了 action。建议改为调用 `datasetStore.resetDatasets()` 之类的 action（需在 `datasetStore` 新增 action，同样属于接口变更）。

---

## 12. 未及细查的项（时间盒内主动放弃，非「已确认无问题」）

1. **`userStore` 的角色判定与后端权限矩阵是否一致**：`isAdmin`/`isScenarioAdmin` 两个 getter 已死，但页面里 30 处本地 `role === 'SUPER_ADMIN'` 判断是否覆盖了全部角色（如 `SCENARIO_ADMIN` 是否应看到某入口）未逐页核对——属于视图分区 + 后端权限的交叉验证。
2. **`RiskEventDetailView.vue:76` 读 `userStore.users` 但从不调 `fetchUsers()`**：直接打开事件详情页（未经用户管理页）时 `users` 为空，创建者会退化成显示 `user_id`。代码注释承认了这个兜底，是否为可接受体验需产品确认；修法（详情页补一次 `fetchUsers`）在视图分区。
3. **`datasetStore` 与 `api/datasetApi` 的字段映射是否完全一致**（`uploadDataset` 手工逐字段拷贝 `DatasetVersion`，与 `mapDatasetVersion` 可能漂移）——该 action 已死，未深究。
4. **`explanationText` 正则与后端文案模板的契约**未与后端代码交叉验证（只在第 7 节标注了风险）。
5. **`settingsStore` 的 `ALLOWED_INTERVALS` 与 `App.vue` 自动刷新实际使用的间隔**是否一一对应，未逐一核对。
6. **三个 Job Store 的 `POLL_TIMEOUT_MS` 数值（20/65/40 分钟）是否与后端任务真实超时匹配**未验证（需要读后端任务超时配置，超出本分区）。
7. **`request.js` 的 `extractErrorMessage` 对 `data.detail` 为对象数组以外的形态**（如嵌套对象）覆盖不全，未构造用例穷举。

---

## 13. 自检

```
cd frontend
npx vue-tsc --noEmit -p tsconfig.app.json --tsBuildInfoFile node_modules/.tmp/tsb-F6b.json
→ exit 0（无任何输出）
```

- 全项目（含其他分区的 `views/**`、`components/**`）零类型错误。
- 未执行任何被禁止的命令（无 `npm run build`/`vite build`/`dev`/`preview`、未触碰 `dist`、未动后端与数据库、未做任何 git 写操作）。
- 改动文件全部落在本分区写权限内；报告为本分区唯一新增文件。
