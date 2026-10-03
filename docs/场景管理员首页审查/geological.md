# 地质风险场景 · 场景管理员首页审查（geological_risk / scenario_key=geological）

- 审查对象：`/scenarios/:scenarioId/dashboard` → `frontend/src/views/Home/dashboard/DashboardHomeView.vue:42,50` → `frontend/src/views/Home/dashboard/AdminProfilePage.vue:80` → `frontend/src/views/Home/dashboard/sections/ProfileGeological.vue`
- 对照物（普通用户首页）：`frontend/src/views/Home/dashboard/sections/WorkspaceGeological.vue`（`DashboardHomeView.vue:40,51`）
- 后端：`GET /api/v1/dashboard/scenarios/{id}/profile` → `backend/app/services/dashboard_service.py:1039` `get_profile` / `:1262` `_geological_profile`；运行态 `GET .../workspace` → `:1299` `get_workspace`
- 判定标准（用户给定）：
  - **C1 = 管理员总览视角**：服务「管好这个场景」的决策（数据资产 / 数据质量 / 建模覆盖 / 成员与权限 / 流程与积压的总体水位），不能是执行端个人的研判辅助。
  - **C2 = 跨数据集共性口径**：数字必须是该场景下**多个数据集共同/合并**体现的统计，不能是**某一个单独数据集内部**的分布；按数据集横向对比同一指标（每行一个数据集、口径统一）算满足。
- 本报告只做只读调查，未修改任何 `.vue` / `.py` / `.ts` 文件。

---

## 1. 场景与数据集清单（含被 profile 漏掉的数据集）

### 1.1 磁盘上的数据文件

| 目录 | 文件 | 体积 |
| --- | --- | --- |
| `data/geological_risk/` | `DIS_raw_data.arff` | 1,831,958 B |
| `data/geological_risk/` | `DIS_Landslides.arff` | 857,884 B |
| `data/geological/` | `DIS_raw_data.arff` | 1,831,958 B（与上表同名文件同尺寸） |
| `data/geological/` | `DIS_Landslides.arff` | 857,884 B（与上表同名文件同尺寸） |
| `data/geological/` | `DIS_Landslide_Causative_Factors.arff` | 1,058,364 B |
| `data/geological/` | `DIS_Global_Landslide_Catalog_Export.arff` | 188,167 B |
| `data/geological/` | `DIS_guaruja_random.arff` | 22,164 B |

即：地质场景共 **5 份不同内容的 ARFF**（`geological/` 下 5 份；`geological_risk/` 下 2 份是其中两份的另一处存放）。`scripts/seed_test_data.py:119-124` 把 `geological_risk` 映射到 `data/geological/`。

### 1.2 logical_id 与标签口径（已登记常量）

| logical_id | 展示名（`constants.py:131-147`） | 标签字段 | 风险标签口径 | 在 `DATASET_RISK_TYPES`（`constants.py:308-319`） |
| --- | --- | --- | --- | --- |
| `dis_raw_data` | DIS_raw_data | `Label` | `{0,1}`（`constants.py:275`） | ✅ geological |
| `dis_landslides` | DIS_Landslides | `LS` | `{0,1}` | ✅ geological |
| `dis_causative_factors` | DIS_Landslide_Causative_Factors | `landslides` | `>0` 即风险（`constants.py:277,287`） | ✅ geological |
| `dis_global_catalog` | DIS_Global_Landslide_Catalog_Export | `landslide_size` | **非风险标签**（灾害规模多分类，`seed_test_data.py:63-68`） | ❌ 未登记 |
| `dis_guaruja_random` | DIS_guaruja_random | `class` | `{0,1}`（`constants.py:278`） | ✅ geological |
| `geo_slope_company_v1` | 上传文件名 `DIS_Landslides` | `LS` | 语义上是二分类风险标签，但 logical_id 未登记 → `is_risk_label=false` | ❌ 未登记 |
| `carol_slope_personal_v1` | 上传文件名 `DIS_raw_data` | `Label` | 个人数据集，管理员不可见 | — |

`geo_slope_company_v1` / `carol_slope_personal_v1` 见 `scripts/seed_production_data.py:100-101`；`constants.py:70` 定义 `company` 可见性语义（场景管理员上传、最外层不可见）。

### 1.3 profile 实际取到的数据集范围

`get_profile`（`dashboard_service.py:1045-1053`）：

```python
stmt = select(Dataset).where(Dataset.scenario_id == scenario_id, Dataset.status == DATASET_STATUS_ACTIVE)
if role == ROLE_SUPER_ADMIN:  stmt.where(Dataset.visibility == DATASET_VISIBILITY_PLATFORM)      # 1049-1050
else:                          stmt.where(Dataset.visibility.in_((PLATFORM, COMPANY)))             # 1052
```

- SCENARIO_ADMIN：`dis_raw_data` / `dis_landslides` / `dis_causative_factors` / `dis_global_catalog` / `dis_guaruja_random` + `geo_slope_company_v1`（company）共 **6 条**；`carol_slope_personal_v1`（personal）被排除（合理）。
- SUPER_ADMIN（带场景上下文，`AdminProfilePage.vue:39-41` 同样走 geological 分支）：**只有 platform 的 5 条**，看不到 `geo_slope_company_v1`。

### 1.4 被 profile「读了但只当分母」的数据集（C2 不满足的直接证据）

`_geological_profile`（`dashboard_service.py:1262-1293`）只做了**两处字段级聚合**：

| 聚合 | 代码位置 | 唯一数据源 |
| --- | --- | --- |
| 8 个地形因子均值 `factors` | `dashboard_service.py:1265-1272` | **仅 `dis_raw_data`** |
| 编目四分布 `catalog_distribution` | `dashboard_service.py:1274-1282` | **仅 `dis_global_catalog`** |

其余数据集**从未被任何字段级聚合读取**，只出现在 `data.datasets` 列表（`dashboard_service.py:1073`）里当作样本量/风险占比的行：

| 被漏掉的数据集 | 独有字段（ARFF 头部实测） | 现状 |
| --- | --- | --- |
| `dis_landslides` | `dist_roads, DEM, TWI, plan_curvature, profil_curvature, Slope, Geology, LandCover, LS` | 只出现在「各数据集样本量 / 数据集资产 / 各数据集风险样本占比」列表行，**无专属聚合** |
| `dis_causative_factors` | `Aspect, DF, DR, DW, LULC, Lithology, NDVI, PC, Precip, TPI, TWI, Temp, landslides` | 同上，**无专属聚合** |
| `dis_guaruja_random` | `twi, curvature, slope, elevation, aspect, lithology, land_use, class` | 同上，**无专属聚合** |
| `dis_global_catalog` | `location_accuracy, landslide_category, landslide_trigger, landslide_setting, fatality_count, injury_count, country_name, admin_division_population, gazeteer_distance, longitude, latitude, landslide_size` | 只服务 3 张「编目分布」卡片，**不参与任何跨数据集口径** |
| `geo_slope_company_v1` | 同 `DIS_Landslides`（`LS`） | 进入 `datasets` 列表，但被 `is_risk_label=false` 过滤（`ProfileGeological.vue:42`），**在「各数据集风险样本占比」中静默消失** |

字段证据（`Get-Content <file> -TotalCount 40` 只读头部）：`data/geological_risk/DIS_raw_data.arff`、`data/geological_risk/DIS_Landslides.arff`、`data/geological/DIS_Landslide_Causative_Factors.arff`、`data/geological/DIS_guaruja_random.arff`、`data/geological/DIS_Global_Landslide_Catalog_Export.arff`。

### 1.5 profile 返回但地质首页完全没用到的字段

`ProfileBase`（`frontend/src/api/dashboardApi.ts:95-109`）里的跨数据集合并口径字段，`ProfileGeological.vue` **一个都没用**（全文检索仅命中 `dataset_count`）：

| 字段 | 含义 | 谁在用 |
| --- | --- | --- |
| `sample_count` | 去重后全场景有效样本总量（`dashboard_service.py:1057` `_effective_counts`） | 只在页副标题 `AdminProfilePage.vue:46` |
| `risk_count` / `risk_rate` | 全场景风险样本量与统一风险占比（`:1070-1072`） | 只在副标题 `:46` |
| `groups` | 同源去重分组（`:1074-1082`） | 无人使用 |
| `factor_count` | 有统计值的因子个数（`:1286`） | 无人使用（`dashboardApi.ts:152`） |
| `dataset_file_count` | 未去重的数据集文件数（`:1069`） | 无人使用 |

对照：网络/电力/舰面三个场景都把合并样本量做成了 KPI（`ProfileNetwork.vue:32-34`、`ProfilePower.vue:43-45`、`ProfileFlightdeck.vue:87`），**只有地质把 KPI 位换成了运行态指标**，跨数据集合并口径被挤到副标题。

---

## 2. 组件清单表

（每个 `DashKpis` 指标块算 1 个组件；每个 `DashCard` 算 1 个组件。共 16 个。）

| # | 组件（标题/类型） | 数据来源 | C1 | C2 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | KPI「待处置积压」（DashKpis，`ProfileGeological.vue:87`） | `/workspace` → `summary.pending`；范围=场景内全部可见数据集的事件（`dashboard_service.py:1305-1308,1332`、`_event_scope:670-691`，`self_only=false` `:1334`） | 满足 | 满足（场景级合并，非单数据集；仅覆盖被推理过的数据集） | 满足 |
| 2 | KPI「已处置率」（`:88-93`） | 同上 `summary.resolved/total` | 满足 | 满足（同上） | 满足 |
| 3 | KPI「已发布模型」（`:94-101`） | `getModelVersionList({scenario_id, page_size:100})`（`:63`）过滤 `status==='PUBLISHED'`；后端 `model_version_service.py:635-651` 场景级返回 | 满足 | 满足（场景内跨数据集模型合并计数） | 满足（注：100 条分页上限） |
| 4 | KPI「数据集」（`:102`） | `data.dataset_count` = `_effective_counts` 的去重数据集数（`dashboard_service.py:1057,1068`、`_effective_groups:639-643`） | 满足 | 满足（全部数据集合并去重口径） | 满足 |
| 5 | DashCard「风险事件处置进度」（DashFunnel，`:253-255`） | `/workspace` `summary.status_funnel`（`dashboard_service.py:761-763`） | 满足 | 满足（场景级合并） | 满足 |
| 6 | DashCard「近 10 天活动趋势」（DashLine，`:256-258`） | `/workspace` `activity_trend`；`_activity_trend:1350-1375`，管理员分支按 `ModelVersion.scenario_id`（`:1358-1361`）= 场景内全部模型的推理记录 | 满足 | 满足（跨数据集合并；但无数据集维度） | 满足 |
| 7 | DashCard「各数据集样本量」（DashBars，`:262-268`） | `data.datasets[].record_count`（`dashboard_service.py:1073` → `describe:618-631`） | 满足 | 满足（每行一个数据集、同一口径横向对比） | 满足 |
| 8 | DashCard「数据集资产」（DashRows，`:269-278`） | `data.datasets[]`（`record_count/label_field/risk_rate`）+ `models` 按 `dataset_logical_id` 归集（`:152-162,176-192`） | 满足 | 满足（数据集级质量与建模覆盖横向对比） | 满足（本页最好的一块） |
| 9 | DashCard「场景成员」（DashRows，`:282-284`） | `getUserList({page_size:200})`（`:64`）按 `scenario_id` 过滤（`:74`）；后端 `user_service.py:104-107` 对 SCENARIO_ADMIN 已限本场景 | 满足 | 不适用（非数据集口径，但也不是单数据集内部统计） | 满足（C2 不适用） |
| 10 | DashCard「数据质量提示」（DashRows，`:285-291`） | `data.datasets[]` 的 `risk_rate` + `label_field/record_count/risk_count` 同源重复签名比对（`:215-246`） | 满足 | 满足（跨数据集同源重复检测，本质就是跨数据集比对） | 满足 |
| 11 | DashCard「近期待处置事件 · 按风险分排序」（DashEvents，`:294-300`） | `/workspace` `recent_events[:20]` 中 `PENDING` 按 `risk_score` 降序取 6（`:121-126`；后端 `dashboard_service.py:1332`） | **不满足**（单条事件明细＝执行端派活清单） | **不满足**（单条事件级，非数据集共性统计） | **不满足** |
| 12 | DashCard「8 个地形因子均值」（DashBars，`:303-305`） | `data.factors` ← **仅 `dis_raw_data`**（`dashboard_service.py:1265-1272`，`GEO_FACTORS:134`） | 部分满足（单数据集字段画像，不是管理水位） | **不满足**（只读 1 个数据集） | **不满足** |
| 13 | DashCard「各数据集风险样本占比（%）」（DashBars，`:306-312`） | `data.datasets.filter(is_risk_label)`（`:42`；`is_risk_label` 定义 `dashboard_service.py:627`） | 部分满足（与用户首页同款同思路，见 §3.13） | 部分满足（横向对比成立，但 `is_risk_label` 过滤静默丢弃未登记数据集） | **部分满足** |
| 14 | DashCard「地质灾害触发因素分布」（DashDonut，`:315-324`） | `catalog_distribution.trigger` ← **仅 `dis_global_catalog`**（`dashboard_service.py:1278`） | 部分满足（编目数据内部构成，无管理动作指向） | **不满足**（只读 1 个数据集） | **不满足** |
| 15 | DashCard「灾害类型分布」（DashBars，`:325-328`） | `catalog_distribution.category` ← **仅 `dis_global_catalog`**（`:1279`） | 部分满足（同上） | **不满足**（只读 1 个数据集） | **不满足** |
| 16 | DashCard「规模分布与国家 TOP」（DashColumns+DashBars，`:329-337`） | `catalog_distribution.size` / `.country` ← **仅 `dis_global_catalog`**（`:1280-1281`） | 部分满足（同上） | **不满足**（只读 1 个数据集） | **不满足** |

统计：**满足 10 / 部分满足 1 / 不满足 5**。

---

## 3. 逐组件详述

### 3.1 KPI「待处置积压」（`:87`）

- 数据来源：`runtime.value.summary.pending`（`ProfileGeological.vue:81,87`），`runtime` 来自 `getScenarioWorkspace(scenarioId)`（`:62,67-70`）。
- 范围：`get_workspace`（`dashboard_service.py:1299-1308`）用 `_event_scope`（`:670-691`）构造事件查询；SCENARIO_ADMIN 分支（`:679-686`）按 `RiskEvent.scenario_id == bound` 且 `Dataset.visibility ∈ (platform, company)`，**不按 `created_by_user_id` 过滤**；`scope.self_only = (role == SCENARIO_USER)`（`:1334`）→ 场景管理员拿到 **self_only=false**（整场景）。
- C1：满足。这是「流程与积压的总体水位」，管理端语义明确。
- C2：满足，但为**运行态事件口径**而非数据集口径：事件由多份数据集的推理产生（`scripts/seed_production_data.py:99` 地质场景 infer = `dis_raw_data` / `dis_landslides` / `dis_guaruja_random` 三份），是合并计数，不是单数据集内部统计。附注：未被推理的数据集（`dis_causative_factors`、`dis_global_catalog`）不会贡献事件，所以「跨数据集」的覆盖面天然是部分的（推测：取决于运行时实际推理过的数据集）。

### 3.2 KPI「已处置率」（`:88-93`）

同 §3.1，`summary.resolved / summary.total`（`dashboard_service.py:744-747`）。C1/C2 同结论。满足。

### 3.3 KPI「已发布模型」（`:94-101`）

- 数据来源：`getModelVersionList({scenario_id, page_size: 100})`（`ProfileGeological.vue:63`），前端过滤 `status === 'PUBLISHED'`。
- 后端 `model_version_service.get_list`（`:635-651`）对 SCENARIO_ADMIN 返回本场景全部模型（排除系统管理员未发布模型），因此该计数是**场景级跨数据集合并**。
- C1：满足（建模覆盖水位）。C2：满足（合并计数，非单数据集内部）。
- 风险（非判定项）：`page_size: 100`（`:63`）配合 `paginate`（`model_version_service.py:672`）——模型数 >100 时会少算；同理「数据集资产」的模型列也受影响（`:152-162`）。

### 3.4 KPI「数据集」（`:102`）

- 数据来源：`props.data.dataset_count`，即 `_effective_counts`（`dashboard_service.py:654-662`）返回的**去重后**数据集数（`:1057,1068`）；地质场景没有 carrier 同源组（`CARRIER_LOGICAL_IDS` 只含航母三份，`dashboard_service.py:100-104`），所以等于文件数 5 或 6。
- C1：满足（数据资产总量）。C2：满足（全部数据集合并去重口径）。
- 附注：KPI 只给了「个数」，没给「有效样本总量」，而后者已在响应里（`sample_count`）且被三个兄弟场景用作 KPI——见 §1.5。

### 3.5 DashCard「风险事件处置进度」（DashFunnel，`:253-255`）

`summary.status_funnel` = `PENDING/PROCESSING/RESOLVED` 三态计数（`dashboard_service.py:761-763`）。C1 满足（流程水位），C2 满足（场景级合并）。满足。

### 3.6 DashCard「近 10 天活动趋势」（DashLine，`:256-258`）

- `trendPoints` 取 `runtime.activity_trend`（`:112-118`），`total`=推理量、`risk`=其中判定为风险的量。
- `_activity_trend`（`dashboard_service.py:1350-1375`）：SCENARIO_USER 只看本人（`:1356-1357`）；**其他角色按 `ModelVersion.scenario_id == dataset.scenario_id`（`:1358-1361`）取整个场景的推理记录**，其中 `dataset` 是 `get_workspace` 取的本场景第一条 ACTIVE 数据集（`:1313-1321`）。
- C1：满足（使用量/资源水位）。C2：满足（跨数据集合并；但组件没有数据集维度，"共性"体现为场景汇总而非横向对比）。满足。

### 3.7 DashCard「各数据集样本量」（DashBars，`:262-268`）

- `data.datasets.map(item => ({value: displayNames.get(item.logical_id), count: item.record_count}))`，`record_count` 由 `describe`（`dashboard_service.py:618-631`）经 `label_stats` 全量统计。
- C1：满足（数据资产分布，管理员看哪些数据集大）。C2：满足（每行一个数据集、同一口径）。
- 附注（口径纯度）：`dis_global_catalog`（1000 条**编目数据**，不参与二分类训练，`seed_test_data.py:66`）与其余**建模样本**混在同一张「样本量」柱状图里，条与条之间口径其实不同一；`displayNames`（`:139-149`）只能解决重名，解决不了口径混淆。建议后续在标签上标注「编目数据」。满足（附改进建议）。

### 3.8 DashCard「数据集资产」（DashRows，`:269-278`）

- 每行一个数据集：`样本量 · 标签字段 · 风险占比 · 模型数`（`:176-192`），模型数来自 `modelCountByDataset`（`:152-162`，按 `dataset_logical_id` 归集）。
- 注释 `:164-175` 明确拒绝用 `is_risk_label` 推断「是否参与建模」，只展示真实 `label_field`，判断交给读者——口径处理是四个场景里最严谨的。
- C1：满足（数据资产 + 建模覆盖 + 标签口径，正是管理员要的）。C2：满足（数据集级横向对比）。满足。

### 3.9 DashCard「场景成员」（DashRows，`:282-284`）

- `memberRows`（`:195-209`）按角色汇总 `members`，`members` 来自 `getUserList({page_size: 200})` 后按 `scenario_id` 过滤（`:64,74`）。
- 后端 `user_service.get_list`（`:104-107`）要求 `require_scenario_admin`，且 SCENARIO_ADMIN 已被限定为本场景；`:124` 把 `page_size` 上限压到 200，因此前端 `.filter` 是冗余但无害的。
- C1：满足（成员与权限水位）。C2：**不适用**——它本来就不是数据集统计，也不违反「不能是某一个单独数据集内部的分布」。结论：满足。
- 附注：若某场景成员 >200 人，「合计」会少算（`user_service.py:124`）；`getUserList` 失败时 `members=null`，该卡整块消失（`:72-75,282`），属静默降级。

### 3.10 DashCard「数据质量提示」（DashRows，`:285-291`）

- `qualityRows`（`:215-246`）两条规则：① `risk_rate < 0.05` 且 `risk_count > 0` 的类别极不平衡数据集；② `label_field|record_count|risk_count` 三元签名相同的**同源重复**数据集组。
- 第 ② 条本身就是**跨数据集比对**（同源重复会重复计入样本总量，是纯管理问题）。
- C1：满足（数据质量，管理端独有）。C2：满足（规则 ② 是跨数据集口径；规则 ① 逐数据集但同一口径）。满足。

### 3.11 DashCard「近期待处置事件 · 按风险分排序」（DashEvents，`:294-300`）——**不满足**

- `pendingEvents`（`:121-126`）：从 `runtime.recent_events`（后端只给最近 20 条，`dashboard_service.py:1332`）中筛 `PENDING`，按 `risk_score` 降序取 6 条。
- C1 **不满足**：用户明确把「近期待处置事件清单」「某条告警的风险分」列为执行端研判辅助的典型。卡片标题与内容就是一条条带 `risk_score` / `occurred_at` 的待办明细（`DashEvents`），是「谁去处理哪条」的执行视角；而且它取自「最近 20 条」的子集，连积压总量都不代表（卡片 `source` 自己承认 `:297`），对「管好这个场景」的决策增量极低——真正的积压水位已由 KPI 1 与漏斗卡覆盖。
- C2 **不满足**：单条事件明细既不是数据集统计，也没有任何跨数据集横向对比。
- 附注：注释 `:11` 声称「事件列表只保留待处置中风险分最高的几条（＝需要先派活的）」——这正是执行端（派活）语义，与该组件自称的「管理端」定位自相矛盾。

### 3.12 DashCard「8 个地形因子均值」（DashBars，`:303-305`）——**不满足**

- 数据来源：`data.factors`，后端 `_geological_profile`（`dashboard_service.py:1265-1272`）：
  ```python
  main = by_logical.get("dis_raw_data")            # 1265
  for name in GEO_FACTORS:                          # 1270
      stats = _stats(_nums(main_rows, cmap.get(name)))
  ```
  `GEO_FACTORS = ("Slope","TWI","Elevation","Relief","SPI","Dis2roads","Dis2fault","Dis2river")`（`:134`）。**唯一数据源 = `dis_raw_data` 一个数据集**。
- C2 **不满足**：直接命中用户的标准——「这个字段是只读了某一个 logical_id（单个数据集）算出来的」。
- C1 部分满足：它是单个数据集内部字段画像，不指向任何管理动作（既不是资产总量，也不是质量告警，也不是建模覆盖）。另外它和普通用户首页「关键因子贡献排行」（`WorkspaceGeological.vue:29-32`，同样基于 `GEO_FACTORS`）是**同思路**——只是用户版归一化成贡献度、管理版取均值。
- 额外口径缺陷（`文件:行号` 证据）：`DIS_raw_data.arff` 的 8 个因子列**全部是 Weka 离散区间**（`@attribute Slope {'(-inf-2.145]','(2.145-4.785]',...}`，见 `data/geological_risk/DIS_raw_data.arff` 头部），而 `_num` 对区间串走 `_mid_of_interval`（`dashboard_service.py:188-199,234`）：单边区 `(-inf-b]` 取**有限端点 b**，双边区取**中点**。所以这张图显示的不是「地形因子真实均值」，而是「各样本所属离散档位的代表值均值」，`_source` 文案「按地形因子全量统计」（`:303`）与实际口径不符。

### 3.13 DashCard「各数据集风险样本占比（%）」（DashBars，`:306-312`）——**部分满足**

- 数据来源：`riskDatasets()`（`:42`）= `data.datasets.filter(item => item.is_risk_label)`；`is_risk_label` 的后端定义是 `dataset.logical_id in DATASET_RISK_TYPES`（`dashboard_service.py:627`）。
- C2 部分满足：**形式上是跨数据集横向对比**（每行一个数据集、统一 `risk_rate` 口径，`describe:618-631`），这部分达标；但**覆盖不完整**：
  - `dis_global_catalog` 被排除是**正确**的（标签是灾害规模 `landslide_size`，不是风险标签，`:41` 注释、`seed_test_data.py:66`）；
  - `geo_slope_company_v1`（`seed_production_data.py:100`，标签 `LS`，实际是二分类风险数据）因 logical_id 未登记在 `DATASET_RISK_TYPES` 而被**静默丢弃**。`ProfileGeological.vue:171-174` 的注释已经意识到 `is_risk_label` 对新数据集会误判，但只在该处回避了推断，**没有修正这张图的过滤条件**。
- C1 部分满足：内容是「数据集静态标签分布」，属数据质量/资产口径（可接受），但它与普通用户首页的「各数据集风险占比」（`WorkspaceGeological.vue:55-64`，`DashColumns` + `dataset_prior`）**同款同思路**——同一组数字在管理员页和用户页各画一遍，管理增量低。
- 另附：该卡与「数据集资产」（§3.8）的「风险 xx%」列信息重复，只是换了图型。

### 3.14 / 3.15 / 3.16 三张编目卡片（`:315-338`）——**不满足**

| 卡片 | 字段 | 后端行号 |
| --- | --- | --- |
| 地质灾害触发因素分布（DashDonut） | `catalog_distribution.trigger` ← `landslide_trigger` | `dashboard_service.py:1278` |
| 灾害类型分布（DashBars） | `catalog_distribution.category` ← `landslide_category` | `:1279` |
| 规模分布与国家 TOP（DashColumns+DashBars） | `catalog_distribution.size` / `.country` ← `landslide_size` / `country_name` | `:1280-1281` |

- 三张卡全部来自 `catalog_item = by_logical.get("dis_global_catalog")`（`:1274-1276`），**只读一个数据集**。
- C2 **不满足**：这是「某一个单独数据集内部的分布」，正是用户禁止的口径。
- C1 部分满足/不满足：这是全球滑坡**编目**数据的分类构成，对「管好本场景的数据资产/质量/建模覆盖」没有动作指向；而触发因素分布还与用户首页「触发因素分布」（`WorkspaceGeological.vue:33-36`，同字段 `landslide_trigger`）**同名同思路**（区别只是用户版基于告警事件的 `raw_features`，管理版基于编目文件）。
- 附注：`dis_global_catalog` 是**唯一**非风险标签数据集，把它 3 个字段拆成 3 张卡片，等于把全页近 1/4 的版面给了 1 个不参与建模的数据集（`seed_test_data.py:66`「不参与二分类训练」）。

---

## 4. 替代组件方案

以下每个方案都同时满足 C1（管理员总览）与 C2（跨数据集共性口径）。除注明「需后端新增字段」者外，均可**零后端改动**实现。

### 4.1 替代 #12「8 个地形因子均值」→「场景数据资产总览」KPI 组

- **标题 / 图表类型**：「场景数据资产总览」— `DashKpis`（4 个指标块，复用 `DashKpis.vue`）。
- **数据来源与口径**：直接复用 `ProfileBase`（`dashboardApi.ts:95-109`）已返回的跨数据集合并口径：
  - 有效样本总量 = `data.sample_count`（`dashboard_service.py:1057,1070`，`_effective_counts:654-662` 按 `_effective_groups:639-643` 去重后求和）；
  - 风险样本总量 = `data.risk_count`（`:1071`）；
  - 统一风险占比 = `data.risk_rate`（`:1072`，`_percent:331-332`）；
  - 有效数据集数 = `data.dataset_count`（`:1068`）。
  副标题可挂 `data.groups`（`:1074-1082`）说明去重情况。
- **为什么满足 C1**：这是「数据资产总体水位」——全场景有多少可用样本、风险样本占比多少、几个数据集，正是管理员做资源与建模决策的第一屏。
- **为什么满足 C2**：数字由**全部**可见数据集在**同一风险标签口径**（`_label_is_risk`，`dashboard_service.py:321-323`，0/normal/no/false 为负类）下合并得出，且对同源重复做了去重；不是任何单个数据集内部的分布。
- **可行性证据**：字段已存在于响应（`dashboard_service.py:1070-1072`）与前端类型（`dashboardApi.ts:104-106`），且**已在页副标题渲染**（`AdminProfilePage.vue:46`），无任何后端改动；兄弟场景已这样做（`ProfileNetwork.vue:32-34`、`ProfilePower.vue:43-45`、`ProfileFlightdeck.vue:87`）。
- **可选加强（需后端新增字段）**：「跨数据集地形因子字段覆盖矩阵」`DashRows`——每行一个数据集，列出是否具备 `Slope/TWI/Elevation/Relief/SPI/Dis2roads/Dis2fault/Dis2river` 8 个因子，用于回答「这份数据能不能按统一因子口径建模」。需在 `_geological_profile` 新增 `factor_coverage: [{logical_id, name, present_factors: [...], hit_count, record_count}]`（用 `_DatasetReader` 的表头缓存取字段名，`dashboard_service.py:394-395` 已有 `_HEADER_CACHE`）。字段确实存在：`dis_raw_data` 含全部 8 个；`DIS_Landslides.arff` 含 `Slope/TWI/DEM/dist_roads/plan_curvature/profil_curvature`；`DIS_Landslide_Causative_Factors.arff` 含 `TWI/TPI/Precip/...`；`DIS_guaruja_random.arff` 含 `twi/slope/elevation/...`（大小写不同，需按 `scenario_feature_catalog.py:41-50` 已有的双写别名表做归一，例如 `Slope`/`slope`、`TWI`/`twi`）。

### 4.2 替代 #14「地质灾害触发因素分布」→「各数据集正/负样本构成对比」

- **标题 / 图表类型**：「各数据集正负样本构成」— `DashColumns`（分组柱，复用已有组件；`DashColumns` 已支持 `percent-value`，见 `WorkspaceGeological.vue:59-63`）。
- **数据来源与口径**：`data.datasets`（**全量**，不做 `is_risk_label` 过滤）逐数据集画「风险样本 `risk_count` vs 正常样本 `record_count - risk_count`」，横轴=数据集（用 `displayNames`，`ProfileGeological.vue:139-149`），纵轴=条数；对 `dis_global_catalog` 这类非风险标签数据集在标签上显式标注「编目数据（标签=灾害规模）」，而不是隐藏它。
- **为什么满足 C1**：回答管理员的核心问题「每份数据的正负类构成如何、哪份不能直接拿来训二分类模型」——数据质量与建模可用性。
- **为什么满足 C2**：每行一个数据集、统一 `record_count/risk_count` 口径（后端 `describe:618-631` 对每个数据集都算了 `risk_count/risk_rate`），是跨数据集横向对比；且不再有数据集被静默丢弃。
- **可行性证据**：`datasets[]` 里每个元素都带 `record_count` / `risk_count` / `risk_rate` / `label_field`（`dashboard_service.py:620-631`、`dashboardApi.ts:25-37`），零后端改动。

### 4.3 替代 #15「灾害类型分布」→「建模覆盖：数据集 → 模型对应表」

- **标题 / 图表类型**：「建模覆盖与模型发布状态」— `DashRows`。
- **数据来源与口径**：`data.datasets`（全量，含 `geo_slope_company_v1`）× `models`（`getModelVersionList({scenario_id, page_size: 100})`，`:63`）按 `dataset_logical_id` 归集（现成逻辑 `modelCountByDataset`，`:152-162`）。每行：`数据集名 · 样本量 · 模型总数 · 已发布数 · 最近训练时间/状态`；末尾追加一行汇总「已建模数据集 N / M（覆盖率 x%）」「完全未建模的数据集清单」。
- **为什么满足 C1**：直接对应「建模覆盖」这一管理指标——哪份数据白躺着没人用、哪份模型还没发布，是管理员要推动的事。
- **为什么满足 C2**：以数据集为行、同一口径跨数据集统计，并给出场景级覆盖率；不是任何单数据集内部构成。
- **可行性证据**：模型记录含 `dataset_logical_id` 与 `status`（`model_version_service.py:130`；前端 `ProfileGeological.vue:152-162` 已在用），数据集侧 `datasets[].logical_id/record_count` 已有。若需要「最近训练时间」再加字段时，`ModelVersion` 已有 `created_at/updated_at`（`model_version_service._to_dict` 已输出），仍无需新增后端聚合。

### 4.4 替代 #16「规模分布与国家 TOP」→「各数据集风险水位 × 规模散点」

- **标题 / 图表类型**：「数据集风险水位与样本规模」— `DashScatter`（已有组件 `DashScatter.vue`）。
- **数据来源与口径**：x = `datasets[].record_count`（样本量），y = `datasets[].risk_rate × 100`（统一风险标签口径下的风险占比），每点一个数据集，点标签用 `displayNames`；非风险标签数据集（`dis_global_catalog`）以不同样式/备注呈现或排除并在图注说明。
- **为什么满足 C1**：一眼定位「样本大但风险占比低（正类稀缺）」与「样本小但风险占比高（统计不稳）」的数据集，直接指导「先补哪份数据、哪份适合训练」的管理决策。
- **为什么满足 C2**：每个点是一个数据集，两轴口径对所有数据集统一（`record_count` + `risk_rate`），本质就是跨数据集横向对比。
- **可行性证据**：两轴字段均在 `datasets[]` 中现成（`dashboard_service.py:628-630`、`dashboardApi.ts:34-36`），零后端改动。

### 4.5 替代 #11「近期待处置事件 · 按风险分排序」→「积压按数据集分布」

- **标题 / 图表类型**：「处置积压 · 按数据集分布」— `DashColumns` 或 `DashRows`（复用）。
- **数据来源与口径**：每行一个数据集，列出 `待处置 / 处理中 / 已处置 / 合计`，用于回答「积压集中在哪份数据上」。**需后端新增聚合**：在 `get_workspace` 的地质分支（`dashboard_service.py:1346-1347` → `_geological_workspace:1468`）新增字段
  `pending_by_dataset: [{logical_id, name, total, pending, processing, resolved}]`，
  在 `_geological_workspace` 内用 `Counter` 按 `event.dataset_id` 分组，再用 `Dataset.logical_id` / `dataset_display_name_of` 映射名称。
- **为什么满足 C1**：管理端要的是「积压的结构与水位」（哪些数据集/流程环节堵住、要不要加人加算力），而不是「我该点开哪一条」；这才是资源调度视角。
- **为什么满足 C2**：把全场景事件按数据集拆开并横向对比同一组状态口径，是跨数据集共性统计；且与 KPI 1（总积压）形成「总量 → 分布」的管理闭环。
- **可行性证据**：`RiskEvent.dataset_id` 存在且已被 `_event_scope` 用于 `join(Dataset, Dataset.id == RiskEvent.dataset_id)`（`dashboard_service.py:674,683`），`Dataset.logical_id` 与 `dataset_display_name_of`（`constants.py:157`）均已可用；`_geological_workspace` 已接收 `events` 与 `dataset` 参数（`:1469`），只需再加一个 `dataset_id → logical_id` 的映射（可通过 `dataset.scenario.datasets`，该用法已存在于 `:1511-1517`）。若暂不改后端，可先**直接删除该卡片**（积压总量与漏斗已由 §3.1/§3.5 覆盖），这是零成本的合规化处理。

### 4.6 修正 #13「各数据集风险样本占比（%）」

- **标题 / 图表类型**：保留 `DashBars`，或并入「数据集资产」表作为一列。
- **数据来源与口径**：把 `riskDatasets()`（`ProfileGeological.vue:42`）的 `is_risk_label` 过滤**改为全量 `data.datasets`**，图注标注哪些行是「编目数据（标签非风险标签，不计入风险占比）」。若担心把 `dis_global_catalog` 混入，可用 `label_field` 而非 `is_risk_label` 判定（例如「标签字段 ∈ {Label, LS, landslides, class}」），避免 `geo_slope_company_v1` 这类未登记 logical_id 的新数据集被丢掉。
- **为什么满足 C1**：修正后它成为「数据集级数据质量一览」，与「数据质量提示」（§3.10）互补而非重复；同时避免管理员误以为场景只有 4 份数据。
- **为什么满足 C2**：横向对比保留，覆盖补齐到**全部**可见数据集，不再有静默丢弃。
- **可行性证据**：`describe`（`dashboard_service.py:618-631`）对**每个**数据集都算了 `risk_count/risk_rate`，与 `is_risk_label` 无关；`ProfileGeological.vue:171-174` 的注释已论证 `is_risk_label` 会误判新数据集。零后端改动。

---

## 5. 整体结论

**地质风险场景管理员首页整体上是「数据画像（数据集内部统计）」，而不是「管理员总览（跨数据集共性）」。**

支撑判断的四条硬证据：

1. **字段级聚合只有两处，且各自只读一个数据集**：`_geological_profile`（`dashboard_service.py:1262-1293`）的全部专属聚合 = `dis_raw_data` 的 8 因子 + `dis_global_catalog` 的 4 个分类分布。页面上 **5 个不满足组件里有 4 个**直接源于这两个单数据集聚合（`:1265`、`:1274-1282`）。
2. **3 份数据集完全没有字段级聚合**：`dis_landslides`、`dis_causative_factors`、`dis_guaruja_random` 只作为 `datasets[]` 列表行出现（样本量/风险占比），它们的字段（`DEM/dist_roads/Geology`、`DF/DR/DW/Precip/TPI`、`twi/curvature/slope`）从未被读取；`geo_slope_company_v1` 更因 `is_risk_label=false`（`dashboard_service.py:627`）被风险占比卡静默丢弃（`ProfileGeological.vue:42`）。
3. **跨数据集合并口径被挤出组件层**：`sample_count / risk_count / risk_rate / groups` 这些真正体现「多数据集合并」的字段（`:1070-1082`）在本页**一个组件都没用**，只出现在副标题（`AdminProfilePage.vue:46`）；而网络/电力/舰面三个兄弟场景都把 `sample_count` 做成了 KPI（`ProfileNetwork.vue:32-34`、`ProfilePower.vue:43-45`、`ProfileFlightdeck.vue:87`）。
4. **存在与普通用户首页同款/同思路的组件**：管理页「各数据集风险样本占比」（`:306-312`）≈ 用户页「各数据集风险占比」（`WorkspaceGeological.vue:55-64`，同一组 `risk_rate` 数字）；管理页「8 个地形因子均值」（`:303-305`）与用户页「关键因子贡献排行」（`WorkspaceGeological.vue:29-32`）同源同因子；管理页「地质灾害触发因素分布」（`:315-324`）与用户页「触发因素分布」（`WorkspaceGeological.vue:33-36`）同字段 `landslide_trigger`。

值得肯定的部分（不满足之外的地基是好的）：

- 运行态四块（KPI 1/2、漏斗、趋势）经 `_event_scope`（`dashboard_service.py:670-691`）与 `scope.self_only=false`（`:1334`）确认拿到的是**整场景**范围，C1/C2 都站得住，是合格的「流程与积压总体水位」。
- 「数据集资产」（`:269-278`）与「数据质量提示」（`:285-291`）是**真正满足 C1+C2 的管理员组件**：数据集级横向对比、含建模覆盖与同源重复检测，且 `:164-175` 的注释主动拒绝了会误判的 `is_risk_label` 推断。这两块应该保留并作为其余卡片的改写范式。
- 「场景成员」（`:282-284`）C1 满足，C2 不适用（本就不是数据集统计），可保留。

一句话总评：**页面的运行态（流程/积压）与资产清单部分已是管理员总览，但数据侧仍停留在「两个数据集的画像拼盘」——4 张单数据集分布图 + 1 张执行端待办清单需要替换，1 张与用户首页同款的横向占比图需要补齐覆盖面。**
