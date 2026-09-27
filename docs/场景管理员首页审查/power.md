# 场景管理员首页审查 · 电力系统（power_system / scenario_key=power）

- 审查对象：`/scenarios/:scenarioId/dashboard` → `AdminProfilePage.vue`（页眉 `Admin · Data Profile / 场景数据画像`）在 `scenario_key === 'power'` 时渲染的 `sections/ProfilePower.vue`。
- 后端：`GET /api/v1/dashboard/scenarios/{id}/profile` → `DashboardService.get_profile` + `_power_profile`。
- 对照物：场景用户首页 `sections/WorkspacePower.vue`（`GET .../workspace`）。
- 判定标准：
  - **C1 = 管理员总览视角**：服务「场景管理员管好这个场景」的决策（数据资产 / 数据质量 / 建模覆盖 / 成员与权限 / 流程积压的水位），不是执行端或个人的研判辅助。
  - **C2 = 跨数据集共性口径**：数字必须是该场景下**多个数据集共同/合并**体现的统计，或**按数据集横向对比同一口径**；只读某一个 `logical_id` 内部的分布 → 不满足。
- 判定合成规则（本文统一使用）：`满足` = C1、C2 均满足；`部分满足` = 一项满足、另一项部分满足，或两项均部分满足；`不满足` = 任一项为不满足。
- 本轮只做只读调查，未修改任何 `.vue` / `.py` / `.ts` 文件。

---

## 1. 场景与数据集清单

### 1.1 场景

| 项 | 值 | 证据 |
| --- | --- | --- |
| `scenario_code` | `power_system` | `backend/app/services/constants.py:88` |
| `scenario_name` | 电力系统态势 | `backend/alembic/versions/d6adba5112b8_seed_scenario_and_algorithm.py:34` |
| `scenario_key`（前端分发键） | `power` | `backend/app/services/dashboard_service.py:86`（`SCENARIO_CODE_KEYS`），前端 `AdminProfilePage.vue:33-35` |
| 统一风险类型 | `POWER_SYSTEM_RISK` | `backend/app/services/constants.py:262,311` |
| 正类（风险）标签 | `Target_Event = 1` | `backend/app/services/constants.py:274` |

### 1.2 画像接口实际会读到的数据集

`get_profile` 的查询条件（`dashboard_service.py:1045-1053`）：

```python
stmt = select(Dataset).where(Dataset.scenario_id == scenario_id,
                             Dataset.status == DATASET_STATUS_ACTIVE)
if role == SUPER_ADMIN:      stmt = stmt.where(visibility == "platform")
else:                        stmt = stmt.where(visibility.in_(("platform", "company")))
```

因此：

| 角色 | 可见数据集 | 说明 |
| --- | --- | --- |
| `SCENARIO_ADMIN`（power_admin） | `platform + company` | 至少 2 个数据集 |
| `SUPER_ADMIN`（带场景上下文） | 仅 `platform` | 只剩 1 个数据集 |
| `SCENARIO_USER` | 不渲染本页 | — |

电力场景实际登记的数据集（`tmp/_ds.txt:5-7`，2026-09-23 的真实库快照；与 `scripts/seed_production_data.py:76-80` 的种子配置一致）：

| dataset_id | logical_id | 可见性 | label_field | file_path | 证据 |
| --- | --- | --- | --- | --- | --- |
| 11 | `powergrid_knowledgebase` | platform | `Target_Event` | `data\power\powergrid_knowledgebase_dataset.arff` | `tmp/_ds.txt:5` |
| 16 | `power_grid_company_v1` | company | `Target_Event` | `data/power_system/powergrid_knowledgebase_dataset.arff` | `tmp/_ds.txt:6`、`seed_production_data.py:78` |
| 17 | `bob_sensor_personal_v1` | personal（bob 上传） | `Target_Event` | `data/power_system/powergrid_knowledgebase_dataset.arff` | `tmp/_ds.txt:7`、`seed_production_data.py:79` |

**关键事实（决定了电力场景 C2 的先天困难）**：这三份数据集指向的是**同一份数据文件**。已实测校验：

```
data/power/powergrid_knowledgebase_dataset.arff           180856 B  2013 行
data/power_system/powergrid_knowledgebase_dataset.arff    180856 B  2013 行
SHA256 相同 = True；逐行比较相同 = True
```

即：`id=16 / 17` 是把 `id=11` 的文件重新上传了一遍（`seed_production_data.py:78-79` 的 `rel_src` 都指向 `data/power/...`；上传落盘规则见 `backend/app/services/dataset_service.py:355-358`：`data/<scenario.code>/<filename>`）。

### 1.3 被 `_power_profile` 硬编码漏掉的数据集（C2 不满足的直接证据）

```python
# dashboard_service.py:1147-1152
def _power_profile(cls, reader, by_logical):
    item = by_logical.get("powergrid_knowledgebase")   # ← 只取一份，写死
    fields, rows = cls._dataset_columns(reader, item)
```

`by_logical` 来自 `get_profile:1085`（`{item.logical_id: item for item in datasets}`，是**全量**可见数据集），而 `_power_profile` 只取 `powergrid_knowledgebase` 一项。结论：

- `power_grid_company_v1`（company，场景管理员自己上传）**永远不出现在任何一个组件里**——虽然它会被计入 `data.dataset_count` / `data.sample_count`（`dashboard_service.py:1068-1072`）。
- 任何后续新上传的数据集（无论 `logical_id` 叫什么）都不会进入任何一个电力组件；页面上唯一的痕迹是顶栏副标题的数据集数/样本量变大（`AdminProfilePage.vue:43-47`）。
- `bob_sensor_personal_v1`（personal）在权限上本就不对管理端可见（`dashboard_service.py:1052`），这不属于漏统计；但它同样说明**管理端画像里没有任何「成员上传的数据资产」维度**（见 §4.3）。
- 对照：同一份接口下，网络安全画像用了 `data.datasets` 做跨数据集对比（`ProfileNetwork.vue:67-69`），地质画像大量使用 `data.datasets`（`ProfileGeological.vue:42-43,140-144,177,217,264`）；**`ProfilePower.vue` 对 `data.datasets` / `data.groups` 的使用次数为 0**（全文 grep 无命中）。

### 1.4 目录里那份 `sample_demo.csv` 是什么

`data/power_system/` 下确实有两个文件：`powergrid_knowledgebase_dataset.arff`（= id 16/17 的上传落盘产物）与 `sample_demo.csv`。

`sample_demo.csv` **不是当前库中的数据集记录**，而是写入路径自清理验证留下的**孤儿文件**：

- 该文件由 `tmp/verify_platform_functions.py:431-437` 上传（`logical_id="tmp_roundtrip_power_v1"`、`scenario_id="2"`、`visibility="company"`、源文件 `data/power_data/sample_demo.csv`），随后同脚本 `:446-453` 停用并物理删除。
- `DatasetService.delete` 只删数据库行、不删磁盘文件（`dataset_service.py:496-499`），所以文件残留。
- 因此它既不在 `tmp/_ds.txt` 的快照里，也不会被画像统计。

**它仍然是极好的 C2 反证材料**：如果这条上传没有被删掉（真实用户上传新数据集就是这个流程），`data.datasets` 会多一行、`data.sample_count` 会变大，但 `ProfilePower.vue` 的 12 个组件一个都不会变。

---

## 2. 组件清单表

`ProfilePower.vue` 共 12 个可视组件（4 个 KPI + 7 张 DashCard，其中「电力系统分布与频率」内含 2 个不相关的图/表，拆为 2 个组件）。

| # | 组件（标题/类型） | 数据来源 | C1 | C2 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 1 | KPI「监测样本总量」（DashKpis 第 1 项） | **全部可见数据集**合并（`ProfileBase.sample_count` ← `_effective_counts`） | 满足 | 部分满足 | **部分满足** |
| 2 | KPI「故障样本数」（DashKpis 第 2 项） | 仅 `powergrid_knowledgebase`（`fault_count`） | 满足 | 不满足 | **不满足** |
| 3 | KPI「故障样本占比」（DashKpis 第 3 项） | 仅 `powergrid_knowledgebase`（`fault_rate`） | 满足 | 不满足 | **不满足** |
| 4 | KPI「监测设备类型」（DashKpis 第 4 项） | 仅 `powergrid_knowledgebase`（`components`） | 部分满足 | 不满足 | **不满足** |
| 5 | DashCard「电压 均值/范围（kV）」→ DashRows | 仅 `powergrid_knowledgebase`（`params`） | 部分满足 | 不满足 | **不满足** |
| 6 | DashCard「电流 均值/范围（A）」→ DashRows | 仅 `powergrid_knowledgebase`（`params`） | 部分满足 | 不满足 | **不满足** |
| 7 | DashCard「温度 均值/范围（℃）」→ DashRows | 仅 `powergrid_knowledgebase`（`params`） | 部分满足 | 不满足 | **不满足** |
| 8 | DashCard「问题类型分布」→ DashDonut | 仅 `powergrid_knowledgebase`（`issues`） | 部分满足 | 不满足 | **不满足** |
| 9 | DashCard「设备样本数量分布」→ DashColumns | 仅 `powergrid_knowledgebase`（`components`） | 部分满足 | 不满足 | **不满足** |
| 10 | DashCard「电力系统分布与频率」上半 → DashDonut（SystemName 分布） | 仅 `powergrid_knowledgebase`（`systems`） | 部分满足 | 不满足 | **不满足** |
| 11 | DashCard「电力系统分布与频率」下半 → DashRows（频率 4 项 + 平均遥测丢包率） | 仅 `powergrid_knowledgebase`（`params`） | 部分满足 | 不满足 | **不满足** |
| 12 | DashCard「各设备故障样本占比」→ DashBars（percent） | 仅 `powergrid_knowledgebase`（`device_fault_rates`） | 部分满足 | 不满足 | **不满足** |

**合计：满足 0 个，部分满足 1 个，不满足 11 个。**

---

## 3. 逐组件详述（证据）

### 3.0 数据来源总览

`get_profile` 下发的 JSON 由两部分拼成（`dashboard_service.py:1061-1094`）：

- `ProfileBase`（跨数据集口径，**电力页只用了其中 1 个字段**）：`dataset_count`(:1068)、`dataset_file_count`(:1069)、`sample_count`(:1070)、`risk_count`(:1071)、`risk_rate`(:1072)、`datasets`(:1073，逐数据集 `dataset_id/logical_id/name/version/label_field/is_risk_label/record_count/risk_count/risk_rate`，见 `_DatasetReader.describe:618-631`)、`groups`(:1074-1082，`group_id/datasets[]/record_count/deduplicated`)。
- `_power_profile`（**单数据集口径**，`dashboard_service.py:1147-1185`）：`params`(:1177)、`fault_count`(:1178)、`fault_rate`(:1179)、`issues`(:1180)、`components`(:1181)、`systems`(:1182)、`device_fault_rates`(:1183)。

前端类型定义与之一一对应：`frontend/src/api/dashboardApi.ts:95-109`（`ProfileBase`）、`:128-136`（`PowerProfile`）。

**这 12 个组件里，只有 #1 的字段来自 `ProfileBase`；其余 11 个的字段全部来自 `_power_profile`，也就是 100% 只读 `powergrid_knowledgebase` 一份文件。**

### 3.1 #1 KPI「监测样本总量」（`ProfilePower.vue:43`）

- 字段：`data.sample_count`，副标写死「电力数据集」。
- 来源：`get_profile:1057` → `_effective_counts(reader, datasets)`（`:654-662`）：按 `_effective_groups` 分组后对各组代表数据集求 `label_stats` 之和。
- C2 判定 **部分满足**：它确实是「全场景合并口径」（跨数据集求和），不是单数据集内部统计；但
  1. 合并是**朴素求和**，去重键 `_group_key`（`:634-636`）只把 `CARRIER_LOGICAL_IDS`（`:100-104`，仅航母三份）视为同源，电力场景的 3 份同源文件各算一组 → `sample_count` 把同一份 2000 行数据重复计入。实测：ARFF/CSV 均为 2000 行（`sample_demo.csv` 2001 行含表头；ARFF 2013 行含 13 行表头），因此 `SCENARIO_ADMIN` 看到 4000、`SUPER_ADMIN` 看到 2000。
  2. 它只是一个总量，没有「按数据集横向对比」的形态。
- C1 判定 **满足**：数据资产总量水位属于管理员视角。
- 附带缺陷：副标「电力数据集」（`:43`）与真实口径（多数据集合并）自相矛盾。

### 3.2 #2 KPI「故障样本数」（`ProfilePower.vue:44`）

- 字段：`data.fault_count`。
- 来源：`_power_profile:1150-1151` 取 `powergrid_knowledgebase` 的行，`:1161` 取 `Target_Event` 列，`:1174-1175` 用 `_label_is_risk` 统计正类。**单一数据集**。
- C2 **不满足**：`power_grid_company_v1` 完全未参与。
- 口径冲突（可直接观察到的页面自相矛盾）：本 KPI 的基数是 1 份文件（2000 行，故障 1594 行），而同一页 #1 的「监测样本总量」基数是 2 份（4000 行）。于是页面上会出现 `1594 / 4000 = 39.9%` 与 #3 的「故障样本占比 ≈ 79.7%」并存的观感矛盾——两个数字都"没错"，但基数不同、无法互相解释。
- C1 **满足**：故障样本总量属于数据质量/风险水位。

### 3.3 #3 KPI「故障样本占比」（`ProfilePower.vue:45`）

- 字段：`data.fault_rate`（`_power_profile:1179`，`_percent(fault_count, len(target_values))`）。
- 与 `ProfileBase.risk_rate`（`:1072`，跨数据集合并口径）**是两个不同的字段**，页面选了单数据集的那个。
- C2 **不满足**；C1 **满足**（统一标签口径下的风险占比是管理员核心水位）。
- 另注：顶栏副标题的「风险占比」用的是 `risk_rate`（`AdminProfilePage.vue:46`），与卡片里的 `fault_rate` 是两套口径，二者只是碰巧因为"同一份文件被复制"而数值相同，属于脆弱的一致性。

### 3.4 #4 KPI「监测设备类型」（`ProfilePower.vue:46`，`data.components.length`，副标「按设备去重」）

- 来源：`_power_profile:1181` 的 `components` = `_top(_raw_values(rows, cmap.get("Component")), 8)`，来自单份 ARFF 的 `Component` 列（该列 7 个枚举值，见 `powergrid_knowledgebase_dataset.arff` 头部 `@attribute Component {...}`）。
- C2 **不满足**：单一数据集内部枚举基数。
- C1 **部分满足**：它描述了数据覆盖的设备类型广度（勉强算数据资产维度），但本质是**单表字段基数**，且与用户首页 KPI 同款同思路——`WorkspacePower.vue:32`「受影响设备 / 按设备去重」用的也是 `device_ranking.length`。二者唯一差别是数据源（告警事件 vs 全量数据行），对管理员决策没有新增信息。

### 3.5–3.7 #5/#6/#7 电压 / 电流 / 温度「均值·最小值·最大值·中位数」（`ProfilePower.vue:50-60`，行内容由 `paramRows()` `:20-30` 生成）

- 来源：`_power_profile:1154-1158` 遍历 `POWER_PARAMS`（`dashboard_service.py:137-143`：`VoltageLevel_kV / CurrentAmp / Temperature_C / PowerFrequencyHz / Sensor_Packet_Loss_%`）对**单份 ARFF** 求 `_stats`（`:285-298`：mean/min/max/median/std/range/count）。
- C2 **不满足**：单一数据集；且电力场景的另外两个数据集（company/personal）被 `:1150` 写死排除。
- C1 **部分满足**：字段级描述统计属于数据质量画像的合法内容，但这三张卡选取的字段与**用户首页研判口径完全同款**——`WorkspacePower.vue:36-51`「告警样本电参量均值」用 `DashGauge` 展示同样的 `VoltageLevel_kV / CurrentAmp / Temperature_C / PowerFrequencyHz`（`POWER_EVENT_PARAMS`，`dashboard_service.py:148`），并且 `WorkspacePower.vue:18-23` 还给了这四个量的「正常区间参考带」用于研判分色。管理员页把它们换成均值/范围表格，字段与用途未变。
- 结论 **不满足**（C2 失守）。

### 3.8 #8 DashCard「问题类型分布」（`ProfilePower.vue:63-65`，DashDonut，`data.issues`）

- 来源：`_power_profile:1180`，`_top(_raw_values(rows, cmap.get("IssueType")), 8)`，单份 ARFF 的 `IssueType` 列（6 个枚举值）。
- C2 **不满足**；C1 **部分满足**：它是数据构成描述，但同一字段在用户首页就是研判入口——`WorkspacePower.vue:65-75`「设备问题类型告警构成」按 `Component × IssueType` 交叉统计（后端 `_power_workspace:1418-1430`）。管理员页只是把交叉砍成单维。

### 3.9 #9 DashCard「设备样本数量分布」（`ProfilePower.vue:66-68`，DashColumns，`data.components`）

- 来源：同 #4（`_power_profile:1181`），单份 ARFF 的 `Component` 计数。
- C2 **不满足**（单数据集内部）；C1 **部分满足**：它最接近"覆盖度"话题，但维度选的是**设备**而不是**数据集**——管理员关心的是「这个场景有哪些数据集、各占多少」，不是「数据集内部 7 类设备各有多少条」。

### 3.10 #10 DashCard「电力系统分布与频率」上半 · DashDonut（`ProfilePower.vue:72-75`，`data.systems`）

- 来源：`_power_profile:1182`，`_top(_raw_values(rows, cmap.get("SystemName")), 8)`，单份 ARFF 的 `SystemName` 列（4 个枚举值：Load Balancing System / Fault Detection System / Topology Mapping Unit / Power Quality Analyzer，见 ARFF 头部）。
- C2 **不满足**；C1 **部分满足**：这是最典型的"数据集内部字段分布"，与「管好场景」的决策动作（数据资产/质量/建模覆盖/成员权限/流程积压）没有对应关系。

### 3.11 #11 DashCard「电力系统分布与频率」下半 · DashRows（`ProfilePower.vue:74`，行内容由 `frequencyRows()` `:32-37` 生成）

- 内容：`PowerFrequencyHz` 的均值/最小值/最大值/中位数 + `Sensor_Packet_Loss_%` 的平均值（由 `paramRows('PowerFrequencyHz')` 追加一行构成）。
- 来源：`_power_profile:1154-1158`，单份 ARFF。
- C2 **不满足**；C1 **部分满足偏满足**：`Sensor_Packet_Loss_%`（遥测丢包率）本质是**数据质量指标**，方向正确；但 (a) 它只统计一份文件，(b) 它与「频率分布」被塞进同一张卡，语义不相关（这也是本文把它拆成两个组件的原因），(c) 丢包率是"数据集内部一列的均值"，不是"跨数据集质量对照"。

### 3.12 #12 DashCard「各设备故障样本占比」（`ProfilePower.vue:76-81`，DashBars percent，`data.device_fault_rates`）

- 来源：`_power_profile:1160-1172`，按 `Component` 分组、对 `Target_Event` 求 `_percent(positives, len(values))`，单份 ARFF。
- C2 **不满足**。
- C1 **部分满足，且带一条自证无效的注释**：`ProfilePower.vue:5` 明确写着「原『设备健康度排行』因 7 类设备故障占比均在 77%~82%（无区分度）已剔除，改为『设备 × 故障占比』」——问题不是呈现方式，而是**维度选错了**：在 7 类设备上做故障率排行，本质上仍是执行端研判式的"设备排行"（与 `WorkspacePower.vue:60-62`「设备告警数排行」同型同维度），所以换皮之后依然无区分度。

### 3.13 与普通用户首页（`WorkspacePower.vue`）的"同款/同思路"对照

| 普通用户首页组件（`WorkspacePower.vue`） | 管理员页对应组件（`ProfilePower.vue`） | 同款程度 |
| --- | --- | --- |
| KPI 组 4 项（`:27-34`） | KPI 组 4 项（`:41-48`） | **版式同款**，只有数据源不同（事件 vs 数据行） |
| 「受影响设备 / 按设备去重」（`:32`） | 「监测设备类型 / 按设备去重」（`:46`） | **口径同款**（都是按 `Component` 去重计数） |
| 「告警样本电参量均值」DashGauge ×4（`:36-51`，含正常区间分色 `:18-23`） | 电压/电流/温度 三张 DashRows（`:50-60`） | **字段同款**（同样 4 个电参量），只是统计量从 gauge 换成表 |
| 「设备告警数排行」DashBars（`:60-62`） | 「各设备故障样本占比」DashBars percent（`:76-81`） | **图表+维度同款**（都是按设备排行的横条） |
| 「设备问题类型告警构成」DashBars（`:65-75`） | 「问题类型分布」DashDonut（`:63-65`） | **字段同款**（同为 `IssueType`），只是交叉维度被砍掉 |
| 「风险分区间分布」DashDonut（`:54-59`） | — | 管理页无对应 |
| 「最近告警」DashEvents（`:77-79`） | — | 管理页无对应（这点是对的） |

即：管理页**没有**出现"我的待处置告警 / 最近告警 / 风险分区间"这类纯执行端组件（这部分做对了），但它把用户首页的**电参量、设备、问题类型**三块统计原样搬了过来，只换了统计基数。

---

## 4. 替代组件方案（每个不满足组件一节）

替代方案的设计原则：全部改成「**每行一个数据集 + 统一口径**」或「**全场景合并口径**」，即 C2 要求的两种形态之一；同时把维度从"设备/电参量"换成"数据集资产 / 质量 / 覆盖 / 口径纳入状态"，以满足 C1。

可直接复用的现成结构（无需后端改动）：`ProfileBase.datasets[]`（`dashboard_service.py:1073` + `_DatasetReader.describe:618-631`；前端 `dashboardApi.ts:95-109`）与 `ProfileBase.groups[]`（`:1074-1082`）。已有先例：`ProfileNetwork.vue:67-69`（「数据集规模对比」DashColumns）、`ProfileGeological.vue:264`。

### 4.1 替代 #2「故障样本数」

- **建议标题 / 图表类型**：「全场景风险样本数（合并口径）」— 复用 `DashKpis`。
- **数据来源与聚合口径**：改用 `ProfileBase.risk_count`（`dashboard_service.py:1071`，由 `_effective_counts:654-662` 跨全部可见数据集求和），副标写「按 N 个数据集合并（去重后 M 组）」。**不要**用 `_power_profile.fault_count`。
- **为什么满足 C1**：场景级风险水位是管理员的总体把控项。
- **为什么满足 C2**：数值本身即多数据集合并结果，不来自任何单个 `logical_id` 的内部列。
- **可行性**：字段已下发（`dashboardApi.ts:105`），前端一行替换即可；无需新增后端字段。

### 4.2 替代 #3「故障样本占比」

- **建议标题 / 图表类型**：「全场景风险占比（统一标签口径）」— 复用 `DashKpis`。
- **数据来源与聚合口径**：`ProfileBase.risk_rate`（`dashboard_service.py:1072`），并注明「分子=各数据集 `Target_Event=1` 之和，分母=各数据集有效样本之和」。
- **为什么满足 C1/C2**：同 4.1；且与顶栏副标题口径统一（`AdminProfilePage.vue:46`），消除同页两套口径。
- **可行性**：字段已下发（`dashboardApi.ts:106`）。

### 4.3 替代 #4「监测设备类型」

- **建议标题 / 图表类型**：「数据资产结构（平台 / 公司 / 个人）」— 复用 `DashKpis`（3 项）或 `DashRows`。
- **数据来源与聚合口径**：`ProfileBase.datasets[]` 按 `visibility` 分组计数与样本量求和，得到「平台 1 个 / 2000 条、公司 1 个 / 2000 条」。需在 `_DatasetReader.describe`（`dashboard_service.py:618-631`）新增 `visibility`、`uploader_role`、`uploaded_by` 三个字段（数据源已存在：`backend/app/models/dataset.py:34,37,38`）。
- **为什么满足 C1**：这是"谁上传了什么级别的数据资产"的盘点，属管理员专属决策项（决定哪些数据可作场景基线、哪些要推动纳管）。
- **为什么满足 C2**：每行一个数据集、按同一可见性口径归类汇总，是跨数据集横向口径。
- **可行性**：`Dataset.visibility/uploader_role/uploaded_by` 是 ORM 现成列；只需在 `describe()` 返回值里多带 3 个键（`get_profile` 已按可见性过滤，:1049-1052）。

### 4.4–4.6 替代 #5/#6/#7（电压 / 电流 / 温度 三张参数卡，合并为一张）

- **建议标题 / 图表类型**：「数据集质量与完整性对照」— 复用 `DashBars`（percent）或 `DashRows`（每数据集一行：字段数 / 缺失单元格数 / 缺失率）。
- **数据来源与聚合口径**：逐数据集用 `_DatasetReader.rows(dataset)`（`dashboard_service.py:519-550`）统计 `?`/空单元格占比；分母用 `record_count × 字段数`（字段数取 `Dataset.fields_schema`，`backend/app/models/dataset.py:31`）。建议在 `describe()` 增加 `field_count` / `missing_cells` / `missing_rate` / `label_missing_rate`。缺失判定沿用现有常量 `_NUM_MISSING`（`dashboard_service.py:160`）与 `_raw_values` 跳过 `?` 的既有规则（`:249-259`）。
- **为什么满足 C1**：数据完整性/可用性直接决定"能不能建模、要不要让上传方返工"，是场景管理员的核心职责。
- **为什么满足 C2**：每行一个数据集、同一缺失率口径，横向可比。
- **可行性**：`rows()` 已能给出全量单元格；需后端新增 3-4 个字段。**必须同时修一处硬伤**：`_DatasetReader.rows` 只调用 `read_arff`（`dashboard_service.py:534`），对 CSV 文件返回空（`backend/app/utils/arff_reader.py:117-160` 无 `@ATTRIBUTE`/`@DATA` 即返回空表），而 `label_stats:585-588` 在无表头时直接记 0 —— 这就是为什么电力场景里上传 CSV 的数据集在画像里样本量会变成 0。修法：按扩展名分流到 `utils/dataset_file_reader.read_csv`（`:41`）。

### 4.7 替代 #8「问题类型分布」

- **建议标题 / 图表类型**：「风险口径纳入状态（数据集 × 标签字段）」— 复用 `DashRows`（label=数据集名，value=`label_field` + 是否纳入统一风险口径）或 `DashBars`。
- **数据来源与聚合口径**：`ProfileBase.datasets[].label_field` / `is_risk_label`（`dashboard_service.py:625-627`；前端 `dashboardApi.ts:107`）。每行一个数据集。
- **为什么满足 C1**：`constants.py:107-109` 明确写着「未登记的数据集默认不生成风险事件，需在 `DATASET_RISK_TYPES` 中补充映射」——也就是说「哪些数据集还没纳入统一风险口径」是管理员必须看见的待办项，漏看会直接导致该数据集的风险事件永远不产生。
- **为什么满足 C2**：每行一个数据集、同一"是否纳入风险口径"判据，横向可比。
- **可行性**：字段已下发，前端即可实现；建议同时展示 `version`（`dashboard_service.py:624`）以暴露同 `logical_id` 多版本。

### 4.8 替代 #9「设备样本数量分布」

- **建议标题 / 图表类型**：「数据集规模对比」— 复用 `DashColumns`。
- **数据来源与聚合口径**：`data.datasets.map(d => ({ label: d.name || d.logical_id, value: d.record_count }))`，与 `ProfileNetwork.vue:67-69` 完全同款。
- **为什么满足 C1**：数据集规模是数据资产盘点的基础项（哪个数据集撑起了场景样本量）。
- **为什么满足 C2**：每行一个数据集、同一 `record_count` 口径。
- **可行性**：`datasets[].record_count` 已下发（`dashboard_service.py:628`）。**注意**：受 §4.4 的 CSV 解析问题影响，CSV 数据集的 `record_count` 目前为 0，需一并修复。

### 4.9 替代 #10「电力系统分布（DashDonut）」

- **建议标题 / 图表类型**：「建模覆盖（数据集 × 已发布模型版本数）」— 复用 `DashBars` 或 `DashFunnel`。
- **数据来源与聚合口径**：对当前场景的 `ModelVersion` 按 `dataset_id` 分组统计 `status = PUBLISHED` 的数量（`backend/app/models/model_version.py:39` 有 `dataset_id`），在 `get_profile` 内新增 `model_coverage` 列表（或写进 `describe()`）。已有同类分组查询先例：`dashboard_service.py:821-828`（`published_by_scenario`）。
- **为什么满足 C1**：建模覆盖是管理员"管好这个场景"的第一号决策（哪些数据集还没有可用模型、要不要补训），比"数据集内部系统名分布"重要得多。
- **为什么满足 C2**：每行一个数据集、同一"已发布模型数"口径，横向可比。
- **可行性**：`ModelVersion.dataset_id` 存在；需后端新增一个分组查询与字段（新增字段：`datasets[].published_model_count` 或顶层 `model_coverage`）。

### 4.10 替代 #11「频率 / 丢包率 DashRows」

- **建议标题 / 图表类型**：「数据资产与质量水位」— 复用 `DashRows`（纯现成字段版）。
- **数据来源与聚合口径**（全部用已下发字段，零后端改动）：
  - 有效数据集数 = `dataset_count`（`:1068`，同源去重口径）
  - 登记文件数 = `dataset_file_count`（`:1069`）
  - 合并有效样本量 = `sample_count`（`:1070`）
  - 合并风险样本量 = `risk_count`（`:1071`）
  - 合并风险占比 = `risk_rate`（`:1072`）
  - 同源重复组数 = `groups.filter(g => g.deduplicated).length`（`:1074-1082`）
- **为什么满足 C1**：一屏交代"这个场景的数据资产有多少、风险水位多高、有没有重复/同源冗余"，正是管理员总览。
- **为什么满足 C2**：每一项都是跨数据集合并或按数据集分组的结果（`groups` 是按 `group_id` 分组的结构）。
- **可行性**：字段全部已下发。**建议一并修 `_group_key`**（`dashboard_service.py:634-636`）：把"同源"判定从"仅航母三份"扩展为"同源文件"（如按 `file_path` 的 basename+size 或内容哈希归组），否则电力场景 `deduplicated` 恒为 `false`、`sample_count` 恒为 2×N（见 §3.1）。新增字段：`groups[].source_key`（可选）。

### 4.11 替代 #12「各设备故障样本占比」

- **建议标题 / 图表类型**：「数据集风险占比横向对比」— 复用 `DashBars`（`:percent="true"`）。
- **数据来源与聚合口径**：`data.datasets.map(d => ({ value: d.name || d.logical_id, count: d.risk_rate }))`，`percent` 模式；行内可附 `risk_count / record_count` 原始分子分母。
- **为什么满足 C1**：统一标签口径下"哪个数据集风险更高"，是管理员判断数据分布与基线合理性的依据（而不是设备维度的执行端排行）。
- **为什么满足 C2**：每行一个数据集、同一 `risk_rate` 口径，标准横向对比。
- **可行性**：`datasets[].risk_rate` 已下发（`dashboard_service.py:630`）。**诚实提示**：电力场景当前 3 份数据集是同一份文件（SHA256 相同，见 §1.2），这张图会呈现"两行完全一样"——这本身是对管理员有价值的信号（提示存在同源重复登记），配合 §4.10 的同源去重口径一起看即可；一旦场景引入真正不同的数据集，这张图立即恢复区分度。

### 4.12 替换后的整页建议布局（一屏管理员总览）

1. KPI ×4：`全场景有效样本总量（去重后）` / `全场景风险样本数（合并口径）` / `全场景风险占比（统一标签口径）` / `数据资产结构（平台·公司·个人）`
2. `DashColumns`：数据集规模对比（每数据集 `record_count`）
3. `DashBars(percent)`：数据集风险占比横向对比（每数据集 `risk_rate`）
4. `DashRows`：风险口径纳入状态（每数据集 `label_field` / `is_risk_label` / `version`）
5. `DashBars`：建模覆盖（每数据集已发布模型数）← 需后端新增聚合
6. `DashBars(percent)`：数据集质量与完整性（每数据集缺失率）← 需后端新增字段
7. `DashRows`：数据资产与质量水位（合并口径汇总）

即：**从"数据集内部 7 类设备 / 4 类系统 / 5 个电参量"转为"数据集 × {规模、风险占比、标签口径、建模覆盖、质量}"**。

---

## 5. 整体结论

**该场景首页整体上是「数据画像（数据集内部统计）」，不是「管理员总览（跨数据集共性）」。**

判定依据：

1. **12 个组件中 11 个的数据字段 100% 来自单一数据集**。`_power_profile` 在 `dashboard_service.py:1150` 写死 `by_logical.get("powergrid_knowledgebase")`，后续 `params / fault_count / fault_rate / issues / components / systems / device_fault_rates`（`:1176-1184`）全部由这一份 ARFF 的 2000 行算出；而 `data.datasets` 是**全量**（`:1073`）。
2. **真正的跨数据集结构在前端被完全弃用**。`ProfileBase.datasets` / `ProfileBase.groups` 是现成的"每数据集一行、口径统一"结构，`ProfileNetwork.vue:67-69` 与 `ProfileGeological.vue:42-43,140-144,177,217,264` 都在用；`ProfilePower.vue` 对二者的使用次数为 **0**。
3. **唯一一个跨数据集字段（#1 `sample_count`）也不可靠**：`_group_key`（`:634-636`）只对航母三份去重，电力场景三份同源文件（SHA256 相同，见 §1.2）被当成 3 个独立数据集求和，导致 `SCENARIO_ADMIN` 页面把 2000 条样本显示成 4000 条；同时该字段与 #2/#3 的单数据集基数混用，同页出现两套不可互推的分母。
4. **管理端画像对"新数据集"完全不敏感**：管理员上传的新数据集会进入 `data.datasets` 与 `sample_count`，但不会出现在任何一个组件里（`data/power_system/sample_demo.csv` 就是这类上传留下的孤儿文件，见 §1.4）。这与用户诉求中"不能是单独一个数据集的数据，而应该是大家的共性数据"直接冲突。
5. **C1 层面的问题相对较轻但真实存在**：页面已剔除"我的待处置告警 / 最近告警 / 风险分区间"等纯执行端组件（这部分是对的），但把用户首页的电参量（`WorkspacePower.vue:36-51` ↔ `ProfilePower.vue:50-60`）、设备排行（`:60-62` ↔ `:76-81`）、问题类型（`:65-75` ↔ `:63-65`）三块统计原样搬了过来，只换了统计基数——正是用户所说的"和普通用户一样偏向研判统计"。
6. **另需一并修复的两处数据口径缺陷**（否则任何跨数据集组件都会失真）：
   - CSV 数据集在画像里恒为 0 条样本：`_DatasetReader.rows` 只用 `read_arff`（`dashboard_service.py:534`），`label_stats:585-588` 无表头即记 0，而上传侧是支持 CSV 的（`dataset_service.py:350-352`、`utils/dataset_file_reader.py:41`）。
   - 同源去重只覆盖航母：`_group_key`（`:634-636`）需要按同源文件（路径/大小/哈希）归组，否则电力场景的"合并口径"就是重复计数。
