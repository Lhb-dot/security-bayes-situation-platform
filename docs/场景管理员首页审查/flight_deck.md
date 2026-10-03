# 舰面调度场景（flight_deck / flightdeck_operation）场景管理员首页审查

> 审查性质：**只读调查**。未修改任何 `.vue` / `.py` / `.ts`，未启动前后端服务，未写数据库。
> 审查日期基准：仓库当前工作区状态。
> 证据形式：`文件:行号` 为静态代码证据；「运行时实测」指在**只读**前提下于本机进程内直接调用
> `DashboardService.get_profile`（PostgreSQL 只读 SELECT + ARFF 只读解析），用于校验代码推演出的数字。
> 凡属推测的内容均显式标注「推测」。

---

## 0. 审查范围与判定规则

### 0.1 页面链路

| 环节 | 位置 |
| --- | --- |
| 路由 → 页面 | `/scenarios/:scenarioId/dashboard` → `AdminProfilePage.vue` |
| 场景分发 | `frontend/src/views/Home/dashboard/AdminProfilePage.vue:79`（`flight_deck` → `ProfileFlightdeck`） |
| 页眉口径条 | `AdminProfilePage.vue:43-47`（`subtitle`：`数据集全量统计 · N 个有效数据集 · M 条样本 · 风险占比 X%`）、`AdminProfilePage.vue:67-75`（`DashShell`） |
| 主体组件 | `frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue`（全文 139 行） |
| 数据接口 | `GET /api/v1/dashboard/scenarios/{id}/profile` → `backend/app/services/dashboard_service.py:1038-1094`（`get_profile`） |
| 舰面分支 | `dashboard_service.py:1090-1091` → `_flight_profile`（`dashboard_service.py:1187-1260`） |
| 普通用户对照 | `frontend/src/views/Home/dashboard/sections/WorkspaceFlightdeck.vue`（全文 89 行） / `dashboard_service.py:1299-1348` + `_flight_workspace`（`1436-1466`） |

### 0.2 C1 / C2 判定规则（本次审查的操作化口径）

- **C1 = 管理员总览视角**：组件服务「场景管理员管好这个场景」的决策（数据资产、数据质量、建模覆盖、
  成员与权限、流程与积压的总体水位）。凡是「要干活的人看的东西」（单样本极值、特征分布、
  特征区分度、时序特征曲线），即使范围是全场景，也判 C1 不满足。
- **C2 = 跨数据集共性口径**：组件的**维度必须是「数据集」**——即每行/每片/每条序列是一个数据集，
  且所有数据集在同一口径下合并或横向对比（`datasets` / `groups` 派生）。
  只要组件是「某一个数据集内部的字段分布」，就判 C2 不满足。
  - 判定依据一律追到后端：看该字段在 `_flight_profile` 里读的是哪个 `Dataset` 对象。
- **结论判定规则**（本报告统一使用，避免「部分满足」含义漂移）：
  - C1 满足 且 C2 满足 → **满足**
  - C1 部分满足 且 C2 不满足 → **部分满足**（有管理味道但硬伤在 C2）
  - 其余（含 C1 不满足） → **不满足**

### 0.3 一个贯穿全篇的后端事实（C2 的直接证据）

`_flight_profile` 取数据集的方式是**硬编码单一 logical_id**：

```python
# dashboard_service.py:1187-1191
def _flight_profile(cls, reader, by_logical):
    """舰面调度数据画像：以去重后的载体数据集为准（同源三份只算一份）。"""
    item = by_logical.get(CARRIER_CANONICAL) or next(iter(by_logical.values()), None)
    fields, rows = cls._dataset_columns(reader, item)
```

其中 `CARRIER_CANONICAL = "carrier_feature2_biaoqian"`（`dashboard_service.py:106`，
`CARRIER_LOGICAL_IDS` 见 `:100-104`）。**该函数的全部返回值只来自这一个数据集对象**，
并在响应里自我声明：

```python
# dashboard_service.py:1256-1259
"sources": {
    "dataset": item.logical_id if item is not None else None,
    "note": "carrier 三份为同源衍生，本页只按其中一份统计，避免 3 倍重复计数",
},
```

运行时实测（SCENARIO_ADMIN）该字段为 `{"dataset": "carrier_feature2_biaoqian", ...}` ——
即整页 12 个图表组件的数字全部出自 dataset_id=6 一份文件。

---

## 1. 场景与数据集清单

### 1.1 DB 实测：`scenario_id=3` 的 ACTIVE 数据集（只读 SELECT）

| dataset_id | logical_id | 展示名 | visibility | uploader_role | 物理文件 | 行数 | 正类(Collision=1) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 6 | `carrier_feature2_biaoqian` | Feature2_Cleaning_biaoqian | platform | — | `data\carrier\Feature2_Cleaning_biaoqian.arff` | 507 | 129 |
| 7 | `carrier_feature2_lisan` | Feature2_Cleaning_lisan | platform | — | `data\carrier\Feature2_Cleaning_lisan.arff` | 507 | 129 |
| 8 | `carrier_paired_trail` | paired_TrailData_feature2_biaoqian | platform | — | `data\carrier\paired_TrailData_feature2_biaoqian.arff` | 507 | 129 |
| 18 | `carrier_track_company_v1` | Feature2_Cleaning_lisan | company | SCENARIO_ADMIN | `data/flightdeck_operation/Feature2_Cleaning_lisan.arff` | 507 | 129 |
| 19 | `deck_user01_trail_personal_v1` | paired_TrailData_feature2_biaoqian | personal | SCENARIO_USER | `data/flightdeck_operation/paired_TrailData_feature2_biaoqian.arff` | 507 | 129 |

- 代码侧对应的登记清单：`backend/app/services/constants.py:110-122`（`DATASET_LOGICAL_IDS`）、
  `constants.py:143-146`（展示名）、`constants.py:308-319`（`DATASET_RISK_TYPES`，三份 carrier 均映射
  `FLIGHT_DECK_OPERATION_RISK`）、`constants.py:279-281`（`DATASET_POSITIVE_LABELS`，三份均为 `{"1"}`）。
- `data/flightdeck_operation/` 目录只有 2 个文件、`data/carrier/` 目录有 3 个文件（目录实测）；
  其中 `carrier/Feature2_Cleaning_lisan.arff` 与 `flightdeck_operation/Feature2_Cleaning_lisan.arff`
  **MD5 完全一致**（`77CB74B69EC73DEDC78D3EA04A3FB6CD`），
  `carrier/paired_TrailData_feature2_biaoqian.arff` 与 `flightdeck_operation/` 同名文件
  **MD5 完全一致**（`1C95B0A5E4A34320C10681B3E34BE731`）。
  → id7/id18 是同一份文件、id8/id19 是同一份文件（同内容重复上传）。

### 1.2 可见性过滤后各角色实际拿到的数据集

`get_profile` 的查询条件（`dashboard_service.py:1045-1053`）：

```python
stmt = select(Dataset).where(Dataset.scenario_id == scenario_id,
                             Dataset.status == DATASET_STATUS_ACTIVE)
if role == SUPER_ADMIN:   visibility == platform
else:                     visibility in (platform, company)
```

| 角色 | 可见数据集 | `dataset_file_count` | `dataset_count`(去重) | `sample_count` | `risk_count` |
| --- | --- | --- | --- | --- | --- |
| SCENARIO_ADMIN（实测用户 `zs`, id=13） | 6, 7, 8, 18 | **4** | **2** | **1014** | **258** |
| SUPER_ADMIN（实测用户 `admin`, id=1） | 6, 7, 8 | 3 | 1 | 507 | 129 |

（上表为运行时实测值，非推演。`risk_rate` 两者均为 `0.2544`。）

- id19 属 `personal`，被 `dashboard_service.py:1049-1052` 按角色排除 —— **这是权限设计，不是缺陷**。
- 场景管理员首页的目标角色是 SCENARIO_ADMIN，故后文以 **4 份数据集 / 2 个去重组** 为准。

### 1.3 被 `_flight_profile` 硬编码漏掉的数据集（C2 不满足的直接证据）

| 被漏掉 | 对 SCENARIO_ADMIN | 对 SUPER_ADMIN | 依据 |
| --- | --- | --- | --- |
| id7 `carrier_feature2_lisan` | 漏 | 漏 | `_flight_profile` 只读 `CARRIER_CANONICAL`（`:1190`） |
| id8 `carrier_paired_trail` | 漏 | 漏 | 同上 |
| id18 `carrier_track_company_v1`（company 副本） | 漏 | 不可见 | 同上 |
| id19 `deck_user01_trail_personal_v1` | 按权限排除（非缺陷） | 不可见 | `:1049-1052` |

补充：`data.datasets`（`:1073`）与 `data.groups`（`:1074-1082`）是**全量**下发的，
但 `ProfileFlightdeck.vue` 全文**从未引用** `data.datasets` / `data.groups`
（`ProfileFlightdeck.vue:16-81` 只读 `sample_count`/`collision_*`/`distance`/`approach`/
`total_distance`/`direction`/`relative_angle`/`distance_curve`/`collision_comparison`，
类型定义见 `frontend/src/api/dashboardApi.ts:138-148`）。
→ **跨数据集口径的数据其实已经传到前端了，页面只是没用它。**

### 1.4 三份同源数据集去重后算「1 个」还是「多个」？「同源只取一份」算不算共性统计？

**判定一：按 `groups` 去重后 = 1 个数据集（1 个统计群体），不是 3 个。**
证据（ARFF 实测，逐列比对）：

| 对比项 | biaoqian | lisan | paired_trail | 结论 |
| --- | --- | --- | --- | --- |
| 行数 / 正类数 | 507 / 129 | 507 / 129 | 507 / 129 | 同群体 |
| 字段数 | 279 | 279 | 281 | paired_trail 多 `PlaneID1`/`PlaneID2`（值 `Plane1/Plane2/Plane3`） |
| `Collision` 列序列 MD5 | `8a188c1ccb94` | `8a188c1ccb94` | `8a188c1ccb94` | **逐行完全相同** |
| `inter_dist_min` 列 MD5 | `a9d4880455ba` | （区间串） | `a9d4880455ba` | biaoqian 与 paired_trail **逐行相同** |
| `Plane1_total_distance` 列 MD5 | `87a22787cf36` | （区间串） | `87a22787cf36` | 同上 |
| lisan 数值列形态 | 原始数值 | `'(7055.878574-8059.038169]'` 形式 ARFF 区间 | 原始数值 | lisan = 同一群体的**离散化版本** |

→ 三份文件是**同一 507 条样本的三种编码**（原始 / 离散化 / 原始+机号），不是三个独立数据集。
`_effective_groups`（`:639-643`）把它们并为一组、`_representative`（`:646-651`）优先取未离散化的
biaoqian 做数值统计，**这个口径本身是正确的、也是必要的**（否则 3 倍重复计数）。

**判定二：「同源只取一份」在 C2 下不构成「跨数据集共性统计」，但也不等于「单数据集内部统计」——它是
「本场景唯一统计群体」的统计。**

- 严格按 C2 字面（必须由多个数据集共同/合并体现）→ 本场景**不可能**产出真正的多数据集共性口径，
  因为不存在第二个统计群体。
- 但 C2 的举例明确包含「全场景有效样本总量」这类**以数据集清单为单位的场景级聚合**，故本报告采用
  0.2 节的操作化规则：**维度是「数据集」（每行一个数据集 / 合并口径）→ 满足 C2；维度是「某数据集的
  字段取值」→ 不满足 C2**。
- 按此规则：`sample_count` / `risk_rate` / `datasets` / `groups` 满足 C2；`_flight_profile` 的
  12 个图表字段**全部不满足**（它们是 id6 内部的字段分布）。
- 附带结论（重要，见 §4-A2）：本场景做「按数据集的横向对比」会得到 4 行几乎同值的柱子
  （507 / 129 / 25.44% 全部相同）。这不是设计失败，而恰恰是**本场景最重要的管理事实**——
  同一份数据被重复接入了 4 次。横向对比组件在本场景依然有管理价值，它的作用就是把这个重复暴露出来。

### 1.5 去重口径缺陷：页眉数字与卡片数字自相矛盾

- 去重键 `_group_key` 只认白名单 logical_id：

```python
# dashboard_service.py:634-636
def _group_key(dataset: Dataset) -> str:
    return "carrier_shared_source" if dataset.logical_id in CARRIER_LOGICAL_IDS else dataset.logical_id
```

- id18（company 副本，物理文件与 id7 逐字节相同）不在 `CARRIER_LOGICAL_IDS` 白名单里，
  于是被当成独立组，`_effective_counts`（`:654-662`）把同一份 507 条**又加了一遍**：
  运行时实测 SCENARIO_ADMIN `sample_count=1014`、`risk_count=258`。
- 而页面所有卡片都是 507 条口径（`_flight_profile` 只读 id6）→
  **页眉写「1014 条样本」，卡片写「507 条 / 129 条」**，同一页两个数打架。
- 同类盲区：`DATASET_RISK_TYPES`（`constants.py:308-319`）与 `DATASET_POSITIVE_LABELS`
  （`constants.py:271-282`）也以 logical_id 为键，导致 id18 在 `describe()` 里被判
  `is_risk_label: false`（`dashboard_service.py:627`），运行时实测确实为 `false`
  ——**一份标签字段为 `Collision` 的风险数据被判成「非风险标签数据集」**。

### 1.6 一处文档缺口

`docs/首页字段口径说明.md` 被 `AdminProfilePage.vue:4`、`ProfileFlightdeck.vue:4`、
`dashboard_service.py:4,10,900` 反复引用，但仓库 `docs/` 下**不存在该文件**
（仅 5 个 md：Git 规范 / 数据库设计 v2 / 数据库配置指南 / 部署手册 / 路由现状调查）。
推测：该文档已被删除或从未提交。

---

## 2. 组件清单表

口径：每个 `DashKpis` 指标块算 1 个组件，每个 `DashCard` 算 1 个组件；页眉口径条单独列为 #0。
「数据来源」中 `id6` = `carrier_feature2_biaoqian`。

| # | 组件（标题 / 类型） | 数据来源 | C1 | C2 | 结论 |
| --- | --- | --- | --- | --- | --- |
| 0 | 页眉口径条「数据集全量统计 · N 个有效数据集 · M 条样本 · 风险占比 X%」（DashShell subtitle，非图表） | **全部可见数据集**（`_effective_counts` 去重口径） | 满足 | 满足（但去重键有缺陷：M=1014 重复计同一份 507 条） | 满足 |
| 1 | KPI「轨迹样本总量」（DashKpis，`ProfileFlightdeck.vue:87`） | **全部可见数据集**（`data.sample_count`） | 满足 | 满足 | 满足 |
| 2 | KPI「碰撞风险样本」（`:88`） | **仅 id6**（`collision_count`） | 部分满足 | 不满足 | 部分满足 |
| 3 | KPI「碰撞样本占比」（`:89`） | **仅 id6**（`collision_rate`） | 部分满足 | 不满足 | 部分满足 |
| 4 | KPI「最小机间距离」（`:90`） | **仅 id6**（`distance.min.min`） | 不满足 | 不满足 | 不满足 |
| 5 | Card「平均最小间距 / 平均间距（m）」/ DashRows×3（`:95-97`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 6 | Card「接近率均值」/ DashRows×2（`:98-100`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 7 | Card「双机总航程均值（m）」/ DashRows×3（`:101-103`） | **仅 id6** | 部分满足 | 不满足 | 部分满足 |
| 8 | Card「机间距变化曲线」/ DashLine（50 点）（`:106-114`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 9 | Card「碰撞 vs 正常 最小间距对比（m）」/ DashBars×2（`:117-122`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 10 | Card「1/2 号机方向角统计（°）」/ DashBars×4（`:123-125`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 11 | Card「双机方向角对比雷达（°）」/ DashRadar（`:129-131`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 12 | Card「相对角统计」/ DashRows×2（`:132-134`） | **仅 id6** | 不满足 | 不满足 | 不满足 |
| 13 | Card「间距波动」/ DashRows×2（`:135-137`） | **仅 id6** | 不满足 | 不满足 | 不满足 |

**计数**：14 项（13 个图表组件 + 1 条页眉口径）中 —— **满足 2、部分满足 3、不满足 9**；
若只统计图表组件（#1-#13）则为 **满足 1、部分满足 3、不满足 9**。

---

## 3. 逐组件详述

### #0 页眉口径条 —— 满足（口径正确，但数字被去重缺陷污染）

- 代码：`AdminProfilePage.vue:43-47` 拼装 `数据集全量统计 · ${dataset_count} 个有效数据集 ·
  ${sample_count} 条样本 · 风险占比 ${risk_rate}`；数据源 `dashboard_service.py:1068-1072`。
- C1 满足：这是整页唯一的「场景级水位」表达（有效数据集数 / 有效样本量 / 统一风险占比）。
- C2 满足：`sample_count` 由 `_effective_counts`（`:654-662`）**遍历所有可见数据集的分组**累加得出，
  不是单数据集字段。
- 缺陷（见 §1.5）：SCENARIO_ADMIN 实测 `dataset_file_count=4 / dataset_count=2 / sample_count=1014`，
  而 1014 = 507 × 2，即同一份物理文件（id7 与 id18 MD5 相同）被计了两次。
  页眉数字与所有卡片的 507 口径矛盾。

### #1 KPI「轨迹样本总量」= 507/1014 —— 满足（本页唯一站得住的管理指标）

- 代码：`ProfileFlightdeck.vue:87`（`value: data.sample_count`，`sub: '同源文件已去重'`）；
  数据源 `dashboard_service.py:1057` + `:1070`。
- C1 满足：数据资产总量，管理员口径。
- C2 满足：跨数据集合并口径（`_effective_counts` 遍历 groups），且用户 C2 举例中明确列出
  「全场景有效样本总量」。
- 唯一问题：`sub` 文案「同源文件已去重」在 SCENARIO_ADMIN 下**不成立**（1014 说明没去干净）。

### #2 KPI「碰撞风险样本」= 129 —— 部分满足

- 代码：`ProfileFlightdeck.vue:88` ← `dashboard_service.py:1220`
  （`collision_count = sum(... _label_is_risk(value) ...)`，`rows` 来自 `:1191` 的 id6）。
- C1 部分满足：「风险样本量」本身是数据资产/标签分布水位，管理员会看；
  但它与 #0 页眉的 `risk_count`、#3 的 `collision_rate` 表达的是同一件事，且口径比页眉更窄。
- C2 不满足：只读 id6（`_flight_profile` 的 `rows`），完全忽略 id7/id8/id18。
  证据：`sources.dataset = "carrier_feature2_biaoqian"`（`:1256-1259`）。
- 结论：部分满足。

### #3 KPI「碰撞样本占比」= 25.44% —— 部分满足

- 代码：`ProfileFlightdeck.vue:89` ← `dashboard_service.py:1221`（`_percent(collision_count, len(collision_values))`）。
- C1 部分满足：场景风险占比是管理水位指标。
- C2 不满足：分母 `len(collision_values)` 来自 id6 单份文件；且与 #0 页眉的 `risk_rate` 数值相同、
  口径不同（页眉含去重缺陷），属于重复表达。
- 结论：部分满足。

### #4 KPI「最小机间距离」= 33.76 m —— 不满足

- 代码：`ProfileFlightdeck.vue:90`（`data.distance.min?.min`，`sub: '全样本最小值'`）
  ← `dashboard_service.py:1223`（`_stats(_nums(rows, cmap.get("inter_dist_min")))` 的 `min`）。
- C1 不满足：这是**单条样本的极值**，典型执行端关注点（工作台 KPI 直接写「低于 100 m 需关注」，
  `WorkspaceFlightdeck.vue:48`）。管理员不靠一个极值做决策。
- C2 不满足：只读 id6。
- 同款性：与普通用户首页 KPI「最小间距」同指标（用户侧来自事件，`dashboard_service.py:1459`）。

### #5 Card「平均最小间距 / 平均间距（m）」/ DashRows —— 不满足

- 代码：`ProfileFlightdeck.vue:18-25`（`distanceRows()`）+ `:95-97`；
  数据源 `dashboard_service.py:1223-1225`（`inter_dist_min/mean/median` 的均值）。
- C1 不满足：`source` 自述「按全样本统计」，本质是**机间距特征的分布统计**，服务于研判
  （离地多近算危险），不是管理水位。
- C2 不满足：只读 id6。
- 同款性：与工作台「最小间距分布」（`WorkspaceFlightdeck.vue:72-74`）同指标族。

### #6 Card「接近率均值」/ DashRows —— 不满足

- 代码：`ProfileFlightdeck.vue:27-30` + `:98-100`；数据源 `dashboard_service.py:1229-1232`
  （`dist_change_ratio` 的绝对值均值与均值）。
- C1 不满足：接近率是典型的**碰撞研判特征**，属执行端/模型特征工程视角。
- C2 不满足：只读 id6。

### #7 Card「双机总航程均值（m）」/ DashRows —— 部分满足

- 代码：`ProfileFlightdeck.vue:32-36` + `:101-103`；数据源 `dashboard_service.py:1233-1237`
  （`Plane1_total_distance` / `Plane2_total_distance` / `total_dist_diff` 的均值）。
- C1 部分满足：「航程」勉强可读作作业规模；但这里是**逐样本特征列的均值**（每行是一条轨迹样本），
  不是运行台账，管理员看不出作业量水位。
- C2 不满足：只读 id6（`source` 自述「按双机分别统计」，维度是「飞机」不是「数据集」）。

### #8 Card「机间距变化曲线」/ DashLine（50 个时间步）—— 不满足

- 代码：`ProfileFlightdeck.vue:106-114`；数据源 `dashboard_service.py:1199-1202`
  （对 `inter_distance_1..50` 逐列取全样本均值）。
- C1 不满足：单次进近过程的间距时序曲线，是**执行端研判/复盘**视图。
- C2 不满足：只读 id6；维度是「时间步」，与数据集无关。

### #9 Card「碰撞 vs 正常 最小间距对比」/ DashBars —— 不满足

- 代码：`ProfileFlightdeck.vue:55-58` + `:117-122`；数据源 `dashboard_service.py:1204-1217`
  （按 `Collision` 标签配对分组求 `inter_dist_min` 均值）。
- C1 不满足：`source` 自述「碰撞样本的最小间距显著更低，具有区分度」——
  这是**特征区分度分析**（模型/研判视角），不是管理员总览。
- C2 不满足：只读 id6；维度是「标签类别」。

### #10 Card「1/2 号机方向角统计（°）」/ DashBars —— 不满足

- 代码：`ProfileFlightdeck.vue:48-53` + `:123-125`；数据源 `dashboard_service.py:1238-1249`
  （`Plane1/2_dir_mean_deg`、`Plane1/2_dir_std_deg`）。
- C1 不满足：方向角统计是研判特征。
- C2 不满足：只读 id6；维度是「飞机」。

### #11 Card「双机方向角对比雷达（°）」/ DashRadar —— 不满足（**同款组件，最严重的「像普通用户首页」证据**）

- 管理员页：`ProfileFlightdeck.vue:60-81`（`radarSeries()`）+ `:129-131`，
  数据源 `dashboard_service.py:1242,1247`（数据集列 `Plane1/2_dir_mean_deg` 的 `_stats`）。
- 用户页：`WorkspaceFlightdeck.vue:19-40` + `:60-68`，数据源 `dashboard_service.py:1462-1465`
  （事件 `raw_features` 里的同名列）。
- **标题逐字相同**（「双机方向角对比雷达（°）」）、**图表类型相同**（`DashRadar`）、
  **坐标轴相同**（`['均值','最大','最小','标准差']`）、**序列相同**（1 号机 / 2 号机）。
  唯一区别是数据源（数据集全量 vs 本人事件）——这正是用户说的「和普通用户一样，只是统计范围不同」。
- C1 不满足，C2 不满足（只读 id6）。

### #12 Card「相对角统计」/ DashRows —— 不满足

- 代码：`ProfileFlightdeck.vue:38-41` + `:132-134`；数据源 `dashboard_service.py:1250-1253`
  （`relative_angle_mean_deg` 均值、`relative_angle_max_deg` 均值）。
- C1/C2 均不满足（研判特征；只读 id6）。

### #13 Card「间距波动」/ DashRows —— 不满足

- 代码：`ProfileFlightdeck.vue:43-46` + `:135-137`；数据源 `dashboard_service.py:1226-1227`
  （`inter_dist_std`、`inter_dist_range` 的均值）。
- C1/C2 均不满足（特征离散度，不是数据质量；只读 id6）。

### 3.x 与普通用户首页的「同款 / 同思路」总账

| 管理员页组件 | 用户页对应 | 同款程度 |
| --- | --- | --- |
| #11 双机方向角对比雷达 | `WorkspaceFlightdeck.vue:60-68` 同名同型同轴 | **完全同款**（仅数据源不同） |
| #4 最小机间距离 KPI | `WorkspaceFlightdeck.vue:48` 「最小间距」 | 同指标（用户侧取事件、管理侧取数据集） |
| #5/#13 间距统计/波动 | `WorkspaceFlightdeck.vue:72-74` 「最小间距分布」 | 同指标族 |
| #6/#8/#9/#10/#12 特征统计 | 工作台散点图/雷达（`:53-69`）背后的同一批特征 | 同思路（都是「特征 → 研判」） |

**管理员页没有任何一项**工作台没有的管理维度（数据集资产、质量、建模覆盖、成员权限、事件积压）——
这是 C1 不满足的整体表现。

---

## 4. 替代组件方案（每个不满足/部分满足组件一节）

通用前提：下列方案的数据**优先复用已下发的 `ProfileBase.datasets`（`dashboardApi.ts:25-37,95-109`）
与 `groups`**，需要新增聚合的会明确写出后端字段。
现有可复用组件契约：`DashRows`（`rows: {label,value}[]`，`DashRows.vue:5-10`）、
`DashBars`（`items: {value,count}[]`，支持 `percent/percentValue/labelWidth`，`DashBars.vue:9-41`）、
`DashColumns`（`items: {label,value|count}[]`，`DashColumns.vue:12-27`）、
`DashDonut`（`items: {label,value|count}[]`，`DashDonut.vue:9-23`）、
`DashRadar`（`axes + series[]`，支持多序列，`DashRadar.vue:7-17`）、
`DashLine`（`points + value2` 双序列，`DashLine.vue:12-28`）、
`DashCard`（`title + source`，`DashCard.vue:8-17`）、`DashKpis`（`items: KpiItem[]`，`DashKpis.vue:8-20`）。

---

### A2. 替代 #2 KPI「碰撞风险样本」

- **建议标题**：`有效数据集`（大数字 `dataset_count`，副标 `文件 ${dataset_file_count} 份 · 同源已合并`）
- **图表类型**：`DashKpis` 单个指标块（`DashKpis.vue:8-20`）
- **数据来源与聚合口径**：`data.dataset_count` / `data.dataset_file_count`
  （`dashboard_service.py:1068-1069`，来自 `_effective_counts` 的 `len(groups)` 与 `len(datasets)`）。
  实测 SCENARIO_ADMIN = `2 / 4`，SUPER_ADMIN = `1 / 3`。
- **为什么满足 C1**：数据集资产总量与「文件数 vs 有效数据集数」的差值，直接反映重复接入治理水位。
- **为什么满足 C2**：口径就是「把所有可见数据集按同源分组后计数」，维度是数据集清单。
- **可行性证据**：字段已下发（`dashboardApi.ts:102-103`），前端零改动即可渲染。
- **后端新增**：无。

### A3. 替代 #3 KPI「碰撞样本占比」

- **建议标题**：`统一风险标签口径占比`（`risk_rate`，副标 `各数据集 label_field 正类 / 有效样本 · 去重口径`）
- **图表类型**：`DashKpis` 单个指标块
- **数据来源与聚合口径**：`data.risk_count / data.sample_count`（`dashboard_service.py:1071-1072`），
  即把每份数据集在**各自 label_field 下的正类**合并后统一算占比。
- **为什么满足 C1**：场景级风险水位（不是某个数据集内部）。
- **为什么满足 C2**：分子分母都是跨数据集合并值。
- **可行性证据**：字段已下发；实测 = `258/1014 = 25.44%`（去重修正后应为 `129/507`）。
- **后端新增**：无（但需先修 §1.5 的去重键，否则数字仍是重复计数）。

### A4. 替代 #4 KPI「最小机间距离」

- **建议标题**：`建模覆盖数据集`（大数字 = 至少 1 个 PUBLISHED 模型的数据集数，副标 `已发布模型 ${n} 个`）
- **图表类型**：`DashKpis` 单个指标块
- **数据来源与聚合口径**：新增后端聚合 —— 按 `ModelVersion.dataset_id` 分组统计
  `status = PUBLISHED`（`MODEL_STATUS_PUBLISHED`）的条数。
  实测本场景：dataset 6 → 3 个 PUBLISHED + 1 个 DRAFT；dataset 7 → 1 个 DRAFT；dataset 8 → 1 个 DRAFT
  （`model_version` 只读 SELECT）。可复用 `get_scenario_overview` 里已有的分组查询写法
  （`dashboard_service.py:963-969`，现按 `scenario_id` 分组，改为/增加按 `dataset_id` 分组即可）。
- **为什么满足 C1**：「建模覆盖」是管理员核心职责（哪些数据集还没有可用模型）。
- **为什么满足 C2**：每个数据集一行，同一口径（PUBLISHED 计数）。
- **可行性证据**：`ModelVersion` 已导入（`dashboard_service.py:43`），`dataset_id` 字段存在（DB 实测）。
- **后端新增字段**：`modeling: [{ logical_id, published_model_count, draft_model_count, latest_trained_at }]`。

### A5. 替代 #5 Card「平均最小间距 / 平均间距（m）」

- **建议标题**：`各数据集规模与风险占比（统一标签口径）`
- **图表类型**：`DashCard` + `DashRows`（每行一个数据集，值形如 `507 条 · 25.44%`）
  或 `DashCard` + `DashColumns`（柱高 = `record_count`，`percent` 另用 `DashBars` 展示 `risk_rate`）
- **数据来源与聚合口径**：直接消费 `data.datasets`（`dashboard_service.py:1073`，
  字段见 `_DatasetReader.describe`，`dashboard_service.py:618-631`）：
  `name` / `record_count` / `risk_count` / `risk_rate` / `label_field`。
  **所有数据集使用同一口径**：正类 = `DATASET_POSITIVE_LABELS[logical_id]`，占比 = `risk_count / record_count`。
- **为什么满足 C1**：数据集资产与标签分布总览（数据资产 + 数据质量双维度）。
- **为什么满足 C2**：每行一个数据集、口径统一，是标准「按数据集横向对比同一指标」。
- **可行性证据**：字段已在响应里（实测 4 行：`Feature2_Cleaning_biaoqian` / `Feature2_Cleaning_lisan` /
  `paired_TrailData_feature2_biaoqian` / `Feature2_Cleaning_lisan(company)`，均为 507/129/0.2544）。
- **注意**：本场景 4 行数值相同 —— 这恰好把「同一份数据重复接入 4 次」暴露出来，
  是有效的管理信号（见 §1.4 判定二）。
- **后端新增**：无。

### A6. 替代 #6 Card「接近率均值」

- **建议标题**：`数据集同源分组与有效样本口径`
- **图表类型**：`DashCard` + `DashRows`
- **数据来源与聚合口径**：消费 `data.groups`（`dashboard_service.py:1074-1082`）：
  `group_id` / `datasets.length`（份数）/ `record_count` / `deduplicated`。
  实测：`carrier_shared_source`（3 份，507 条，deduplicated=true）、
  `carrier_track_company_v1`（1 份，507 条，deduplicated=false）。
- **为什么满足 C1**：这是**数据资产治理**的核心事实（同源重复接入、存储与口径风险）。
- **为什么满足 C2**：维度是「同源组 / 数据集」，且分组本身就是跨数据集操作。
- **可行性证据**：字段已下发（`dashboardApi.ts:108`）。
- **后端新增（建议）**：`content_fingerprint`（如文件 SHA-256 或 (行数, 标签分布, 首列哈希)），
  并用它替代 `_group_key`（`dashboard_service.py:634-636`）的白名单逻辑 ——
  这样 id18 会并入同源组，`dataset_count` 回到 1、`sample_count` 回到 507，同时 A6 会显示
  「1 组 4 份 / 有效样本 507」。

### A7. 替代 #7 Card「双机总航程均值（m）」

- **建议标题**：`数据集建模覆盖（按数据集）`
- **图表类型**：`DashCard` + `DashBars`（每根条 = 一个数据集的已发布模型数）
- **数据来源与聚合口径**：同 A4 的 `modeling` 聚合，此处展开为完整对比：
  行 = 数据集，指标 = `published_model_count` / `draft_model_count`。
  实测：ds6 = 3 已发布，ds7 = 0，ds8 = 0。
- **为什么满足 C1**：「哪些数据集有可用模型、哪些只有草稿」是管理员发布/治理决策依据。
- **为什么满足 C2**：每行一个数据集、同一统计口径。
- **可行性证据**：DB 只读 SELECT 已确认（`model_version.dataset_id`、`status`）；
  `MODEL_STATUS_PUBLISHED` 常量已导入（`dashboard_service.py:57`）。
- **后端新增字段**：同 A4 的 `modeling`。

### A8. 替代 #8 Card「机间距变化曲线」/ DashLine

- **建议标题**：`各数据集风险事件处置水位（待处置 / 处理中 / 已处置）`
- **图表类型**：`DashCard` + `DashColumns`（每列一个数据集的待处置数）或
  `DashCard` + `DashBars`（`columns=3`，每行一个数据集，三色条）
- **数据来源与聚合口径**：新增后端聚合 —— 按 `RiskEvent.dataset_id` × `RiskEvent.status`
  分组计数，可见范围**必须沿用** `_event_scope`（`dashboard_service.py:670-691`）的角色过滤，
  风险等级一律按查看者阈值重算（文件头口径 8，`dashboard_service.py:24`）。
  实测本场景：仅 ds6 有事件 —— 待处置 85 / 处理中 13 / 已处置 66（`risk_event` 只读 SELECT）。
- **为什么满足 C1**：这就是「流程与积压的总体水位」，是管理员首页应有内容。
- **为什么满足 C2**：行维度是数据集，状态口径统一（`PENDING/PROCESSING/RESOLVED`，
  `constants.py:243-250`；标签映射见 `dashboard_service.py:121`）。
- **可行性证据**：`risk_event` 有 `dataset_id`/`status`（DB 列实测）；`_event_scope` 已存在可复用。
- **后端新增字段**：`event_backlog: [{ logical_id, pending, processing, resolved, backlog_rate }]`。

### A9. 替代 #9 Card「碰撞 vs 正常 最小间距对比」/ DashBars

- **建议标题**：`数据集标签口径一致性`
- **图表类型**：`DashCard` + `DashRows`（每行一个数据集：`label_field` / 是否已登记风险标签 / 正类定义）
- **数据来源与聚合口径**：`data.datasets[].label_field` + `is_risk_label` + `risk_rate`
  （`dashboard_service.py:625-630`）。本场景可直接暴露异常：
  id6/7/8 `label_field=Collision, is_risk_label=true`，而 id18 `label_field=Collision,
  is_risk_label=false`（运行时实测）——**同一标签口径被判成两种性质**。
- **为什么满足 C1**：标签口径一致性是数据质量/建模准入的硬前提，管理员必须看到。
- **为什么满足 C2**：每行一个数据集，同一判定维度。
- **可行性证据**：字段已下发（`dashboardApi.ts:31-33`）；异常值已实测确认。
- **后端新增（建议）**：把 `is_risk_label` 的判定从 logical_id 白名单（`dashboard_service.py:627`）
  改为「`label_field` 命中已登记风险标签字段 + 场景风险类型」，或在响应里追加
  `positive_labels`（来自 `DATASET_POSITIVE_LABELS`，`constants.py:271-282`）。

### A10. 替代 #10 Card「1/2 号机方向角统计（°）」/ DashBars

- **建议标题**：`各数据集样本量与字段规模`
- **图表类型**：`DashCard` + `DashColumns`（柱高 = `record_count`，标签 = 数据集名）
  ＋ 副行 `DashRows` 展示每份数据集的字段数
- **数据来源与聚合口径**：`datasets[].record_count`（已下发）＋ 字段数取 `Dataset.fields_schema`
  的键数（DB 实测非空：id6=37432 / id7=115133 / id8=37698 / id18=119090 / id19=37698 字节的 JSON）。
- **为什么满足 C1**：数据资产规模与结构复杂度（管理员做存储/训练成本决策的依据）。
- **为什么满足 C2**：每列一个数据集、同一口径。
- **可行性证据**：`record_count` 已下发；`fields_schema` 是 `Dataset` 列（DB 列实测，
  `dataset` 表含 `fields_schema`）。
- **后端新增字段**：`datasets[].attribute_count`（或 `quality.attribute_count`）。

### A11. 替代 #11 Card「双机方向角对比雷达（°）」/ DashRadar（同款组件，优先替换）

- **建议标题**：`数据集治理画像雷达（同一口径横向对比）`
- **图表类型**：`DashCard` + `DashRadar`（多序列，`DashRadar.vue:7-17`）——
  每条序列 = 一个数据集，坐标轴 = 同一组治理指标
- **数据来源与聚合口径**：轴建议 `['样本量(归一)','风险占比','字段数(归一)','已发布模型数','待处置积压率','同源重复度']`，
  每轴先做 0-100 归一（沿用电力场景 `device_fault_rates`、地质 `factor_means` 的归一写法，
  `dashboard_service.py:1479-1482`）。序列数据来源：`datasets`（样本量/风险占比/字段数）、
  A4 的 `modeling`、A8 的 `event_backlog`、A6 的 `groups`。
- **为什么满足 C1**：六个轴全部是管理员治理维度（资产/质量/建模/流程），无一是研判特征。
- **为什么满足 C2**：**每条序列是一个数据集**，且所有数据集在同一组归一口径下对比 ——
  这是 C2 最直接的形态。
- **可行性证据**：`DashRadar` 已支持多序列（`DashRadar.vue:7-17`）；`datasets` 已下发；
  `modeling`/`event_backlog` 需按 A4/A8 新增（DB 字段均已实测存在）。
- **后端新增字段**：`modeling` + `event_backlog`（+ 归一后的 `governance_radar` 便于前端直用）。

### A12. 替代 #12 Card「相对角统计」/ DashRows

- **建议标题**：`各数据集样本量占比`
- **图表类型**：`DashCard` + `DashDonut`（每片 = 一个数据集，`DashDonut.vue:9-23`）
- **数据来源与聚合口径**：`datasets[].record_count`，中心文案 = 去重后有效样本总量。
  本场景会得到 4 个等分扇区（各 507）→ 直观显示「同一份数据占了 4 份资产」。
- **为什么满足 C1**：资产构成总览。
- **为什么满足 C2**：维度是数据集，占比在同一分母口径下计算。
- **可行性证据**：字段已下发；`DashDonut` 支持 `label/value/count`（`DashDonut.vue:9-23`）。
- **后端新增**：无。

### A13. 替代 #13 Card「间距波动」/ DashRows

- **建议标题**：`数据集质量与编码一致性`
- **图表类型**：`DashCard` + `DashRows`（每行一个数据集：`行数 / 字段数 / 缺失率 / 区间分箱列数 / 标签正类定义`）
- **数据来源与聚合口径**：每份数据集独立扫描同一组质量项，口径统一：
  - `record_count`：`_DatasetReader.label_stats`（`dashboard_service.py:566-599`，已有进程级缓存）
  - `attribute_count`：`Dataset.fields_schema`（DB 已存）
  - `missing_cell_rate`：ARFF `?` 占比
  - `interval_binned_column_count`：值形如 `'(a-b]'` 的列数（离散化标记）
- **为什么满足 C1**：数据质量是管理员职责；本场景能直接暴露「lisan 是离散化版本、biaoqian 是原始版本」
  的编码差异（实测 lisan 的数值列全部为区间串，biaoqian 为原始数值；两者缺失率均为 0）。
- **为什么满足 C2**：每行一个数据集、同一质量口径。
- **可行性证据**：ARFF 实测 —— 三份文件 `?` 缺失单元格 = 0；lisan 数值列呈
  `'(7055.878574-8059.038169]'` 区间形态（`_mid_of_interval` 已支持解析，`dashboard_service.py:190-199`）；
  `fields_schema` 非空（DB 实测）。
- **后端新增字段**：`quality: [{ logical_id, attribute_count, missing_cell_rate,
  numeric_column_count, interval_binned_column_count }]`。
  （区间分箱列数需扫一遍 ARFF，建议复用 `_DatasetReader` 的进程级缓存机制，
  `dashboard_service.py:372-389` 的缓存说明。）

---

## 5. 整体结论

1. **该场景管理员首页整体上是「数据画像（数据集内部统计）」，不是「管理员总览（跨数据集共性）」。**
   14 项可视元素中，只有页眉口径条与 KPI「轨迹样本总量」是跨数据集口径；
   其余 12 个图表组件的数字**全部出自同一份文件** `carrier_feature2_biaoqian`（dataset_id=6），
   后端在响应里自述 `sources.dataset = "carrier_feature2_biaoqian"`
   （`dashboard_service.py:1256-1259`，运行时实测确认）。

2. **C1 层面**：整页 12 个卡片全部是机间距 / 接近率 / 航程 / 方向角 / 相对角这些**研判特征统计**，
   与普通用户首页（`WorkspaceFlightdeck.vue`）同指标、同思路，其中「双机方向角对比雷达（°）」
   是**逐字同标题、同图表、同坐标轴、同序列的完全同款组件**（`ProfileFlightdeck.vue:129-131`
   vs `WorkspaceFlightdeck.vue:60-68`）。管理员首页缺失全部治理维度：
   无数据集横向对比、无数据质量、无建模覆盖、无成员与权限、无事件积压。

3. **C2 层面**：本场景的「跨数据集共性」有一个特殊事实 —— 5 份数据集登记全部指向
   **同一批 507 条样本**（`Collision` 列 MD5 三份完全一致；biaoqian 与 paired_trail 数值列逐行相同；
   id7 与 id18 物理文件 MD5 相同）。因此「同源只取一份」是**必要且正确**的去重，
   但它**不构成跨数据集共性统计**；真正的共性口径应当建立在**数据集清单维度**上
   （每行一个数据集 / 合并口径），而页面恰恰没用已经下发的 `datasets` 与 `groups`。

4. **最严重的两个具体缺陷**（可直接作为修复工单）：
   - **去重键只认 logical_id 白名单**（`dashboard_service.py:634-636`），
     导致 SCENARIO_ADMIN 下同一份物理文件被计两次：页眉显示 1014 条样本，
     而所有卡片是 507 口径，同页数字自相矛盾；连带 `is_risk_label` 把 company 副本判成非风险标签
     （`dashboard_service.py:627`）。
   - **`_flight_profile` 硬编码单一数据集**（`dashboard_service.py:1190`），
     使 4 份可见数据集中的 3 份（id7/id8/id18）在全部卡片里完全不可见。

5. **最小改造路径**：优先把 12 个特征统计卡片替换为 §4 的 A2-A13（数据集横向对比 / 同源分组 /
   质量与编码 / 建模覆盖 / 事件积压 / 归属可见性 / 治理雷达），
   这些方案的数据**大部分已在 `data.datasets` 与 `data.groups` 里**，
   需要后端新增的只有 `modeling` / `event_backlog` / `quality` 三组聚合
   （对应 DB 字段均已实测存在）。改造后，本页会从「单数据集特征画像」
   变成「以数据集清单为行的场景治理总览」，同时天然满足 C1 与 C2。

6. 附带问题：`docs/首页字段口径说明.md` 被代码四处引用但仓库中不存在（§1.6），
   建议补齐或修正注释。
