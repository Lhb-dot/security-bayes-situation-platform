# 项目长期备忘（security-bayes-situation-platform）

## 架构与启动
- 后端 FastAPI：`cd backend && python -m app.main`，监听 **12312**（`app/main.py` 里 `uvicorn.run(app, host='0.0.0.0', port=12312)`）。
- 前端 Vue3 + Vite：dev server **5173**，`vite.config.ts` 把 `/api` 代理到 `http://localhost:12312`。
- 数据库 PostgreSQL 16（`backend/app/.env` 的 `DATABASE_URL`），根目录 `docker-compose.yml` 可拉起。
- 一键启动脚本 `start_all.ps1`（会连带拉起 java 服务 12313/12314 等）。
- **后端无热重载**：改动 `backend/app/**` 后必须重启 `python -m app.main`，否则接口仍是旧代码。
- **进程启动统一走 `start_all.ps1`**，不要额外另起后端实例占用 12312 —— 否则 `start_all.ps1` 自己的 FastAPI
  会因端口被占启动失败，用户看到的就是登录 502；5183 也出现过两个 vite 实例并存（`vite` 与 `vite --host 0.0.0.0`），同样要避免重复启动。

## 故障速查
- **登录报 `Request failed with status code 502`** → 不是密码/代码问题，是 **12312 上没有 FastAPI 进程**：
  Vite 把 `/api` 代理到 12312，上游拒绝连接（curl 会看到 `upstream connect failed ... os error 10061`）。
  排查：`netstat -ano | grep 12312`、`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:12312/openapi.json`。
  修复：重新启动后端即可。
- 注意：本机 bash 有 `http_proxy=127.0.0.1:61324`，curl 请求会经该代理，因此连不通时会返回 502
  而不是 `connection refused` —— 别把代理的 502 误判成应用错误，可加 `--noproxy '*'` 直连对比。

## 本机账号
- 本机种子账号密码已被统一重置为 **123456**（`scripts/seed_test_data.py` 里写的 admin123 / alice123 等在本机不生效）。
- 账号：`admin`(SUPER_ADMIN)、`net_admin`(SCENARIO_ADMIN/场景1)、`zs`(SCENARIO_ADMIN/场景3)、`alice`(用户/场景1)、`bob`(用户/场景2)、`carol`(用户/场景4)。

## 首页看板（角色化首页）
- 页面 → 接口契约与字段口径的**唯一权威**是 `docs/首页字段口径说明.md`（由早期 `homepage-demo/字段来源说明.md` 迁入并去掉了对 demo 静态页的引用）。
- `homepage-demo/` 目录只是早期静态设计稿，**已不再被系统引用**，可直接删除；首页任何代码、注释、路由都不得再依赖它。
- 视觉系统集中在 `frontend/src/components/dashboard/dash.css`（类名 `d-` 前缀 + 挂在 `.dash-page` 下，避免与全局 `.card/.row` 冲突）。
- **首页形态由「角色 + 是否带场景上下文」共同决定**（`views/Home/dashboard/DashboardHomeView.vue`）：

  | 路由 | SUPER_ADMIN | SCENARIO_ADMIN | SCENARIO_USER |
  |---|---|---|---|
  | `/overview` | 平台运行总览 | （守卫拦截） | （守卫拦截） |
  | `/scenarios/:scenarioId/dashboard` | **场景数据画像** | 场景数据画像 | 我的工作台 |

  关键点：最外层管理员从「场景中心」点进某个场景时，看到的是**场景管理员的那个首页（场景数据画像）**，
  不是平台总览 —— 只有导航「首页」（`/overview`）才是平台运行总览。
- 路由参数 `scenarioId` 实际传的是**场景编码**（`network_security` 等，`scenarioStore` 把 `raw.code` 映射为 `scenario_id`），`resolveScenarioId` 同时兼容纯数字。

### 口径红线（改动 `backend/app/services/dashboard_service.py` 前必读）
1. 同源衍生文件去重：carrier 三份（`carrier_feature2_biaoqian` / `_lisan` / `carrier_paired_trail`）只计 1 个数据集，取 `biaoqian` 作代表（数值未离散化）。
2. 风险占比按真实标签字段**全量**统计，禁止只读前 N 行。
3. 风险分固定分箱 `0.5-0.7 / 0.7-0.9 / 0.9-1.0`（只在判风险时建事件 → 分数恒 ≥0.5）。
4. 高置信告警 = `risk_score ≥ 0.8`（不要用 ≥0.5，那等于告警总数）。
5. ARFF 离散区间取中点；解析数值必须 `math.isfinite` 过滤 —— `float('inf')` 会成功解析并让 `statistics.pstdev` 崩在 `.numerator`。
6. 地质无「区域」字段，一律按真实字段 `Slope` 分坡度档位。
7. 用户端接口按 `created_by_user_id` 强制过滤本人；不得聚合他人数据。
8. `DatasetStat.is_risk_label` 标记标签字段是否为风险标签：`dis_global_catalog` 的 label 是 `landslide_size`（灾害规模），必须排除出风险占比/先验画像。

### 数据态提示
`risk_event` 表当前为 0 行 → 用户端 4 个「我的工作台」运行态指标为 0 且带空态提示，属正常。跑一次「风险研判」并判定为风险后会自动有值。

## 全站名称规范（2026-09-15 用户确认「全站统一」）
- 英文品牌名 = **`AI Security Operations Center`**，只允许这一个写法，且必须出现在：
  `frontend/index.html` + `frontend/dist/index.html` 的 `<title>`（静态、**不随路由变化**）、
  `App.vue` 顶栏 eyebrow、`Login.vue` 登录卡 eyebrow。禁止再写回 `ai-` / `Bayes Situation Awareness Platform`。
- 中文产品名 = **`多场景贝叶斯分类态势感知系统`**（`Login.vue` 大标题 + `ReportCenter.vue` 报告落款 +
  `App.vue` `pageTitle` 兜底），不要再出现孤立的 `态势感知与威胁可视化平台`。
- 页面 h1（`pageTitle`）按路由各不相同是**设计如此**，那属于页面标题，不属于品牌名，不要强行统一。
- 标签页宽度参考（13px Segoe UI 实测）：全名 169px / `AI SOC` 40px / `AI 安全运营中心` 93px；单标签可用约 184px。

## 场景卡片唯一数据源（场景中心 + 平台运行总览）
- **`GET /api/v1/scenarios/overview` 是场景卡片的唯一数据源**，两处页面都消费它：
  场景中心 `scenarioStore.fetchScenarioOverview()`；平台运行总览 `getGlobalOverview()`（已重写为薄映射）。
  **禁止**再在前端 `datasets.filter(scenario_id === code).length` 计数 —— 那条老路径没有同源去重，
  会让舰面调度显示 3 个数据集（正确值是 1）。后端聚合在 `DashboardService.get_scenario_overview`。
- 契约映射只允许有一处：`frontend/src/api/scenarioApi.ts` 的 `toScenarioCard()`。
- 返回字段：每个场景含
  `dataset_count`(去重) / `sample_count`(去重) / `risk_sample_count` / `risk_sample_rate` /
  `published_model_count` / `event_count` / `high_risk_count` / `risk_score`(0-100) / `risk_level`；
  `totals` 含 `scenario_count / effective_dataset_count / effective_sample_count /
  published_model_count / event_count / high_risk_count / risk_score / risk_level`。
- **口径约定**：本接口下「模型」= **已发布**（`status=PUBLISHED`）模型版本数（`model_count` 与
  `published_model_count` 同值）；「数据集/样本量」走 carrier 同源去重；风险分 = 所辖风险事件
  `risk_score` 均值 ×100，无事件记 0。
- 实测（2026-09-15，admin）：网络 2/6/31,453、电力 1/0/2,000、舰面 1/0/507、地质 5/0/16,385；
  totals 4 场景 / 9 数据集 / 50,345 样本 / 6 已发布模型。整页请求约 1.2s（要读 ARFF 标签列）。
- ⚠️ **FastAPI 路由顺序坑**：`/scenarios/overview` 必须声明在 `/scenarios/{scenario_id}` 之前，
  否则 `overview` 会被 `/{scenario_id}`（str 正则）吃掉再因 int 解析失败返回 **422**（不是 404）。
- 场景中心卡片三项指标（用户 2026-09-15 确认）：**数据集（去重）/ 已发布模型 / 有效样本量**；
  「风险评分：N」已按用户要求从卡片上**删除**（不要加回来）。

## 前端：嵌套滚动容器一律用 scrollChain（2026-09-16 起）
- `frontend/src/utils/scrollChain.ts` 的 **`attachOuterFirstWheel(wrapEl)`**（返回卸载函数）：
  **向下滚时外层页面优先**（页面到底后余量才给内层，一格可分摊：页面 106 + 表格 14）；
  **向上滚不接管**，交还浏览器默认的「内层优先」（表格先回顶，再滚回页面）。用户 2026-09-16 明确选此非对称口径。
- 浏览器默认是「内层优先」，`overscroll-behavior` 只能禁止链式滚动、无法反转，所以必须自己接管
  `wheel`（`{ passive: false }`）。向下方向必须**始终自己处理余量**（`preventDefault` + 写 `inner.scrollTop`）：
  一旦页面被推动，表格就从指针下方移开，交还原生滚动会因命中点不在滚动体上而整格失效。
- 任何 `el-table height/max-height` 都等于多了一个内层滚动容器（真正的滚动体是 `.el-scrollbar__wrap`，
  `.el-table__body-wrapper` 是 `overflow: hidden`）。页面里内嵌这类定高表格时，都应挂这个监听。
  已接入：`components/common/DataPreviewTable.vue`（数据集详情 → 数据内容预览）。
- 弹窗（`el-dialog`）内的表格**不要**挂 —— 弹窗不该把滚动甩给背后的页面。
- 挂载时机：包裹层往往只在「加载完成」后才渲染，用 `watch(ref, ...)` 挂/卸，不要用 `onMounted`。

## 环境坑（本机）
- Bash 工具 PATH 被裁剪，`ls/head/grep/sed` 不可用：临时 `export PATH="/usr/bin:/bin:$PATH"`。
- PowerShell 工具 stdout 不回显 → 写文件再 Read；`Invoke-WebRequest -SessionVariable` 在非交互模式报错 → 本地 HTTP 校验用 `curl` 或 Python `requests`。
- PowerShell 的 `Start-Process` 启动的长驻服务会在工具调用返回后被杀 → 长驻进程用 Bash 工具的 `run_in_background: true`。
