# 网络安全场景 · 场景管理员首页审查（network_security / `scenario_key=network`）

- 审查对象：路由 `/scenarios/:scenarioId/dashboard` → `frontend/src/views/Home/dashboard/AdminProfilePage.vue:30-32,77` → `frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue`
- 数据接口：`GET /api/v1/dashboard/scenarios/{id}/profile` → `backend/app/services/dashboard_service.py:1038-1094` `get_profile` + `:1100-1145` `_network_profile`
- 对照物（普通用户首页）：`frontend/src/views/Home/dashboard/sections/WorkspaceNetwork.vue`（数据来自 `GET /workspace`，`dashboard_service.py:1298-1348`）
- 权限前提：`get_profile` 先过 `require_scenario_admin_of`（`backend/app/services/base.py:108-116`），只有 SUPER_ADMIN / 本场景 SCENARIO_ADMIN 能进这个页面。

判定标准（用户原话拆解）：

- **C1 管理员总览视角**：服务「场景管理员管好这个场景」（数据资产、数据质量、建模覆盖、成员权限、流程积压的总体水位），不是执行端/个人的研判辅助。
- **C2 跨数据集共性口径**：数字必须是该场景下**多个数据集共同/合并**体现的统计（全场景合并总量、统一口径下的风险占比、各数据集在同一口径上的横向对比），不能是某一个单独数据集内部的分布。判定追到后端：只读某一个 `logical_id` → 不满足；每行一个数据集、口径统一 → 满足。
- 组件级结论规则：C1 与 C2 都满足 → **满足**；其一为部分满足且另一个不满足 → **不满足**；C1、C2 都部分满足、或一项满足一项部分满足 → **部分满足**。

**审查方式：只读。本报告未修改任何 .vue / .py / .ts / 数据库文件。**

---

## 1. 场景与数据集清单（含被 profile 硬编码漏掉的数据集）

### 1.1 场景实际有哪些数据集

| # | logical_id | 展示名 | 可见性 | 注册文件（file_path） | 标签字段 | 样本量（实测） | 正样本（实测） | 来源证据 |
|---|---|---|---|---|---|---|---|---|
| 1 | `nf_unsw_nb15_v2` | NF-UNSW-NB15-v2 | platform | `data/network/NF-UNSW-NB15-v2.arff` | `Label` | 23897 | 945（3.95%） | `scripts/seed_test_data.py:95-101,119-124,248-277`（SUPER_ADMIN 建 → platform，`dataset_service.py:263-272`） |
| 2 | `kdd_train_20_percent` | KDDTrain_20Percent | platform | `data/network/KDDTrain_20Percent.arff` | `class` | 7556 | 3522（46.61%） | `scripts/seed_test_data.py:102-108` |
| 3 | **`net_flow_company_v1`** | NF-UNSW-NB15-v2（同名） | **company** | `data/network_security/NF-UNSW-NB15-v2.arff` | `Label` | 23897（与 #1 同内容） | 945 | `scripts/seed_production_data.py:67,222-238`（场景管理员上传 → company，`dataset_service.py:144-151,354-360`） |
| 4 | `alice_conn_personal_v1` | KDDTrain_20Percent（同名） | personal | `data/network_security/KDDTrain_20Percent.arff` | `class` | 7556 | 3522 | `scripts/seed_production_data.py:68,240-254` |

- `data/network_security/` 目录里只有两份文件（`NF-UNSW-NB15-v2.arff` 3373820 B、`KDDTrain_20Percent.arff` 848086 B），正是 `upload_from_file` 的落盘位置 `data/<scenario.code>/<basename>`（`dataset_service.py:354-360`，network 的 `scenario.code` 就是 `network_security`）。据此推断生产 seed 已执行过 company/personal 上传（**推测**：未直连数据库核对，本机无 .db 文件，`DATABASE_URL` 由 `backend/app/db.py:15-21` 从环境读取）。
- **同源重复的硬证据（MD5 完全一致）**：`data/network/NF-UNSW-NB15-v2.arff` 与 `data/network_security/NF-UNSW-NB15-v2.arff` 均为 `ACE14B102524F8D8F9302DA222FBBA67`；两份 KDD 均为 `734AA90326B3486B4A673BE9306631DC`。即 **#1 与 #3 是同一份数据的两个副本、#2 与 #4 同理**。
- 管理员（SCENARIO_ADMIN）可见集合 = platform + company（`get_profile` 的查询条件 `dashboard_service.py:1045-1053`）→ **3 个数据集（#1 #2 #3）**；SUPER_ADMIN 只见 platform → 2 个（`dashboard_service.py:1049-1050`）；#4 对管理员不可见，属权限设计（`dataset_service.py:153-169`），**不算漏**。

### 1.2 被 profile 硬编码漏掉的数据集

`_network_profile` 只按两个写死的 key 取数据集：

- `dashboard_service.py:1103` `by_logical.get("nf_unsw_nb15_v2")`
- `dashboard_service.py:1104` `by_logical.get("kdd_train_20_percent")`

`by_logical` 来自 `dashboard_service.py:1085`（`{item.logical_id: item for item in datasets}`，datasets 是全量），但 6 个单数据集图表（协议 / 端口 / 包长 / 重传 / flag / service）**只消费这两个 key**。后果：

1. **`net_flow_company_v1`（company，管理员可见）不出现在任何图表里**：它只出现在 `ProfileNetwork.vue:67-69` 的「数据集规模对比」（`data.datasets`，后端 `dashboard_service.py:1073` 下发全量）。同源重复的第二份文件对画像毫无信息量，只是把柱子画成两根等高。
2. **新增数据集（管理员后续上传的任意 `logical_id`）同样对画像零贡献**：`logical_id` 由调用方传入（`dataset_service.py:240-250`，前端上传表单填 `dataset_id`，见 `frontend/src/views/Model/DatasetCenter.vue:169`），不可能命中两个写死的字符串。用户上传新数据集后，画像页除「数据集规模对比」一根柱子外不会有任何变化——这是 C2 不满足的直接证据。
3. **KPI 文案与事实脱节**：`ProfileNetwork.vue:32` 的副标题写死「**两数据集合计**」，而管理员实际看到 3 个数据集。
4. **同源重复污染 KPI 口径**：`_effective_counts`（`dashboard_service.py:654-662`）的去重只对航母同源组生效（`_group_key`，`:634-636`，`CARRIER_LOGICAL_IDS`，`:100-104`），网络场景无去重 → #1 与 #3 被各算一次。

实测口径失真（数据来自本次实测的 ARFF 行数/标签数）：

| 指标 | 管理员实际看到（#1+#2+#3） | 去重后真实值（#1+#2） |
|---|---|---|
| `dataset_count` | 3 | 2 |
| `sample_count` | 55350 | 31453（虚高 76%） |
| `risk_count` | 5412 | 4467 |
| `risk_rate` | 9.78% | **14.20%** |

（SUPER_ADMIN 视角因为是 platform-only，恰好是去重后的 2 个数据集，数字反而正确——同一个页面两种角色口径不一致。）

---

## 2. 组件清单表

ProfileNetwork 页面可视组件共 **11 个**（1 个 `DashKpis` 的 4 个指标块各算 1 个 + 7 个 `DashCard`）。

| # | 组件（标题/类型） | 数据来源（logical_id / 全部数据集） | C1 | C2 | 结论 |
|---|---|---|---|---|---|
| 1 | 连接样本总量（DashKpis 指标块，`ProfileNetwork.vue:32`） | 全部数据集（`dashboard_service.py:1057,1070` → `_effective_counts`） | 满足 | 满足（含同源重复瑕疵，见 §3.1） | **满足** |
| 2 | 异常样本数（DashKpis 指标块，`:33`） | 全部数据集（`:1071`） | 满足 | 满足（同 §3.1） | **满足** |
| 3 | 异常样本占比（DashKpis 指标块，`:34`） | 全部数据集（`:1072`） | 满足 | 满足（同 §3.1） | **满足** |
| 4 | 目的端口种类（DashKpis 指标块，`:35`） | **仅 `nf_unsw_nb15_v2`**（`:1113,1128`） | 部分满足 | 不满足 | **不满足** |
| 5 | 协议分布（DashDonut，`:40-42`） | **仅 `nf_unsw_nb15_v2`**（`:1108-1111,1124-1127`） | 不满足 | 不满足 | **不满足** |
| 6 | 目的端口 TOP 8（DashBars，`:43-45`） | **仅 `nf_unsw_nb15_v2`**（`:1113,1129`） | 不满足 | 不满足 | **不满足** |
| 7 | 流量包长五段分布（DashColumns，`:49-51`） | **仅 `nf_unsw_nb15_v2`**（`:1114-1117,1132`） | 不满足 | 不满足 | **不满足** |
| 8 | 连接状态分布（DashBars，`:52-54`） | **仅 `kdd_train_20_percent`**（`:1130`） | 不满足 | 不满足 | **不满足** |
| 9 | 平均入向字节 / 重传占比（DashRows，`:58-63`） | **仅 `nf_unsw_nb15_v2`**（`:1119-1121,1133-1139`） | 部分满足 | 不满足 | **不满足** |
| 10 | 应用服务 TOP（DashBars，`:64-66`） | **仅 `kdd_train_20_percent`**（`:1131`） | 不满足 | 不满足 | **不满足** |
| 11 | 数据集规模对比（DashColumns，`:67-69`） | 全部数据集（`data.datasets`，`:1073`） | 满足 | 满足（含 1 处口径瑕疵，见 §3.11） | **满足** |

**统计：满足 4 个 / 部分满足 0 个 / 不满足 7 个。**

与普通用户首页（`WorkspaceNetwork.vue`）的「同款/同思路」对照：

| 管理员画像组件 | 用户工作台组件 | 关系 |
|---|---|---|
| 流量包长五段分布（`ProfileNetwork.vue:49-51`，DashColumns） | 包长五段分布（`WorkspaceNetwork.vue:68-70`，DashColumns） | **同款同思路**：同一份 `FLOW_BUCKETS` 五段（`dashboard_service.py:112-118`），后端一个按数据集全量行统计（`:1114-1117`）、一个按风险事件特征统计（`:1398-1401`），只是数据范围不同 |
| 目的端口 TOP 8（`:43-45`，DashBars，`L4_DST_PORT`） | 告警端口 TOP（`:54-56`，DashBars，`L4_DST_PORT`） | **同款同思路**：同一字段、同一图表、同一「端口排行」叙事（`:1113,1129` vs `:1380-1381,1394`） |
| 连接状态分布 / 应用服务 TOP（`:52-54,64-66`） | 无对应 | 但同为「数据集内部分布」型统计，与工作台的「风险分区间分布」（`:42-47`）是同一类图表语法 |
| 平均入向字节 / 重传占比（`:58-63`） | 端口偏离度评分（`:57-67`） | 同思路：都是从流量特征里算一个「指标 + 排行/键值行」 |
| （无） | 我的待处置告警 / 今日新增 / 高置信告警（`:22-29`）、近 10 天推理活动趋势（`:31-39`）、处置漏斗（`:48-50`）、最近告警（`:73-75`） | 这些执行端组件画像页没有，方向正确；但画像页也**没有补上**管理员该有的流程/成员/建模覆盖视角（对比 `ProfileGeological.vue:84-104,195-209,252-259`） |

结论：画像页的「研究味道」不在执行端，而在**换了主语的数据集内部统计**——把工作台那张「包长五段分布」「端口 TOP」从「我的告警」换成了「整个数据集」，图表本体与口径语法与用户首页同款。

---

## 3. 逐组件详述

### 3.1 连接样本总量 / 异常样本数 / 异常样本占比（#1 #2 #3）

- 前端：`ProfileNetwork.vue:32`（`data.sample_count`，sub「两数据集合计」）、`:33`（`data.risk_count`）、`:34`（`data.risk_rate`）。
- 后端：`get_profile` 在 `dashboard_service.py:1057` 调 `_effective_counts(reader, datasets)`，`:1070-1072` 写入 `sample_count` / `risk_count` / `risk_rate`；`datasets` 是管理员可见全量（`:1045-1053`）。`_effective_counts`（`:654-662`）对每个同源组取代表数据集后累加，`_representative`（`:646-651`）只在航母组内生效。
- **C1 满足**：数据资产总量 + 全场景标签风险水位，是管理员口径，不是个人研判（工作台对应位置是「我的待处置告警」`WorkspaceNetwork.vue:24`）。
- **C2 满足**：数字由该场景全部可见数据集合并得出（非单个 `logical_id`），风险口径统一走 `_label_is_risk`（`:321-323`，`0/normal/no/false/?` 记负类），NF 的 `Label{0,1}` 与 KDD 的 `class{normal,anomaly}` 被放在同一把尺子上。
- **口径瑕疵（不改变 C2 判定，但必须修）**：
  1. `_group_key`（`:634-636`）只对 `CARRIER_LOGICAL_IDS`（`:100-104`）去重，网络场景的 `net_flow_company_v1` 与 `nf_unsw_nb15_v2` 是同内容副本（MD5 相同）却被各算一次 → 管理员看到的 `sample_count` 55350（真实 31453）、`risk_rate` 9.78%（真实 14.20%）。
  2. `ProfileNetwork.vue:32` 的「两数据集合计」写死，与实际 `dataset_count=3` 矛盾（`data.dataset_count` 已在 `ProfileBase` 里，`frontend/src/api/dashboardApi.ts:102`，却没用）。
  3. 同页对 SUPER_ADMIN 只算 platform（`:1049-1050`），与 SCENARIO_ADMIN 的 3 个数据集不是同一口径，页面没有任何提示。
- 判定：**满足**（建议顺手修 §4 的替代项 R-4 与 R-9 里的去重/质量提示）。

### 3.2 目的端口种类（#4，`ProfileNetwork.vue:35`）

- 后端：`dashboard_service.py:1113` `port_values = _raw_values(nf_rows, nf.get("L4_DST_PORT"))` → `:1128` `len(set(port_values))`。`nf_rows` 只来自 `:1103` 的 `nf_unsw_nb15_v2`。
- **C1 部分满足**：它是数据资产的一个特征（端口离散度），但不是任何管理决策的输入，也不是质量/覆盖/流程水位。
- **C2 不满足**：只读一个数据集；且**结构上无法统一**——`KDDTrain_20Percent.arff` 的 41 个 `@attribute` 里没有任何端口字段（`duration/protocol_type/service/flag/src_bytes/dst_bytes/.../class`），两份数据集不存在可对齐的端口口径。所以这个组件只能替换，不能「改成跨数据集」。
- 判定：**不满足** → 替代方案 R-4。

### 3.3 协议分布（#5，`ProfileNetwork.vue:40-42`）

- 后端：`:1108-1111` 从 `nf_rows` 取 `PROTOCOL`（数值协议号），用 `PROTOCOL_NAMES`（`:109`）映射成 ICMP/TCP/UDP/GRE/ESP/OSPF，其余 `Proto{n}`；`:1124-1127` 输出。
- **C1 不满足**：这是数据集内部的字段值分布（协议构成），属于数据画像而非管理水位；对「管好这个场景」不产生决策。
- **C2 不满足**：只读 `nf_unsw_nb15_v2`；另一份数据集完全缺席。
  - 备注（可统一但 C1 仍弱）：KDD 有 `protocol_type {tcp,udp,icmp}`，与 NF 的 `PROTOCOL` 数字（6→TCP/17→UDP/1→ICMP）可以对齐成同一口径。若产品坚持保留协议图，可改成「各数据集协议构成对比（统一 tcp/udp/icmp/其他）」，能补上 C2，但 C1 依旧偏弱，不推荐。
- 判定：**不满足** → 替代方案 R-5。

### 3.4 目的端口 TOP 8（#6，`ProfileNetwork.vue:43-45`）

- 后端：`:1113` 取端口 → `:1129` `_top(port_values, 8)`（`_top` 见 `:301-303`）。
- **C1 不满足**：与用户首页「告警端口 TOP」（`WorkspaceNetwork.vue:54-56`）同款同字段同叙事，是「看一眼流量里哪些端口多」的执行端习惯；管理员不需要端口排行。
- **C2 不满足**：只读 `nf_unsw_nb15_v2`；KDD 无端口字段（同 §3.2），不可对齐。
- 判定：**不满足** → 替代方案 R-6。

### 3.5 流量包长五段分布（#7，`ProfileNetwork.vue:49-51`）

- 后端：`:1114-1117` 用 `FLOW_BUCKETS`（`:112-118`，NF 的 `NUM_PKTS_UP_TO_128_BYTES` 等 5 列）对 `nf_rows` 求和；`:1132` 输出 `flow_segments`。
- **C1 不满足**：与用户首页「包长五段分布」（`WorkspaceNetwork.vue:68-70`）是**同一个组件、同一份常量、同一句话**（后端 `:1398-1401` 也复用 `FLOW_BUCKETS`），只是数据源从「我的告警事件」换成「数据集全量行」——正是用户说的「和普通用户一样」。
- **C2 不满足**：只读 `nf_unsw_nb15_v2`；KDD 无包长字段。
- 判定：**不满足** → 替代方案 R-7。

### 3.6 连接状态分布（#8，`ProfileNetwork.vue:52-54`）

- 后端：`:1130` `_top(_raw_values(kdd_rows, kdd.get("flag")), 8)`，`kdd_rows` 只来自 `:1104` 的 `kdd_train_20_percent`。
- **C1 不满足**：TCP 连接状态（SF/S0/REJ…）的构成是数据集内部字段分布，属执行端研判素材。
- **C2 不满足**：只读一个数据集；NF 的 `TCP_FLAGS` 是**数值位掩码**（ARFF 中为 real，实测样例值 27/24/0），与 KDD 的枚举 `flag{OTH,REJ,RSTO,...}` 不是同一口径，无法直接合并（要做映射需自行定义语义，属于新增口径，不在现状范围内）。
- 判定：**不满足** → 替代方案 R-8。

### 3.7 平均入向字节 / 重传占比（#9，`ProfileNetwork.vue:58-63`）

- 前端：`ProfileNetwork.vue:18-26` `trafficRows()` 渲染 4 行：`avg_in_bytes` / `avg_retrans_in_bytes` / `retransmission_ratio` / `in_bytes_stats.median`。
- 后端：`:1119-1121` 从 `nf_rows` 取 `IN_BYTES`、`RETRANSMITTED_IN_BYTES` 求均值；`:1133-1139` 输出，含 `_stats`（`:285-298`）。
- **C1 部分满足**：重传率勉强算「数据/链路质量」信号，但它算的是训练数据集里历史流量的平均值，不反映平台运行质量，管理员拿不到可执行结论。
- **C2 不满足**：只读 `nf_unsw_nb15_v2`；KDD 只有 `src_bytes/dst_bytes`，与 NF 的 `IN_BYTES/OUT_BYTES` 语义不同、量纲不同，强行合并会得出无意义数字。
- 判定：**不满足** → 替代方案 R-9。

### 3.8 应用服务 TOP（#10，`ProfileNetwork.vue:64-66`）

- 后端：`:1131` `_top(_raw_values(kdd_rows, kdd.get("service")), 8)`。
- **C1 不满足**：应用服务排行是「数据集里哪些服务流量多」，属数据画像/执行端素材。
- **C2 不满足**：只读 `kdd_train_20_percent`；NF 无 `service` 字段（其 `L7_PROTO` 是数值，且不在 `_network_profile` 的读取范围）。
- 判定：**不满足** → 替代方案 R-10。

### 3.9 数据集规模对比（#11，`ProfileNetwork.vue:67-69`）

- 前端：`data.datasets.map((item) => ({ label: item.name || item.logical_id, value: item.record_count }))`，`DashColumns` 渲染。
- 后端：`dashboard_service.py:1073` `"datasets": [reader.describe(item) for item in datasets]`，`describe` 在 `:618-631` 给出 `record_count`（标签列全量行数，`:628`）、`risk_count`（`:629`）、`risk_rate`（`:630`）、`label_field`（`:625`）、`is_risk_label`（`:627`）。
- **C1 满足**：每行一个数据集的规模，正是数据资产视角（哪份数据大、哪份小），且它**能覆盖到硬编码漏掉的新数据集**。
- **C2 满足**：每行一个数据集、口径统一（同一「标签列全量行数」口径），符合用户给出的 C2 正面样例。
- **口径瑕疵（不改变判定）**：它用的是**逐文件**的 `data.datasets`，而非去重后的 `groups`（`:1074-1082`，同样已下发到前端 `frontend/src/api/dashboardApi.ts:108`）。网络场景因此会画出两根等高的 NF 柱（#1 与 #3，MD5 相同），与 KPI 的 `dataset_count=3` 一起误导读者；而 `AdminProfilePage.vue:46` 的副标题又用 `dataset_count` 说「3 个有效数据集」，「有效」二字与逐文件口径冲突。
- 判定：**满足**（建议按 R-7/R-9 的口径同时收敛到 `groups`）。

### 3.10 页头副标题（非组件，附记）

`AdminProfilePage.vue:43-47`：`数据集全量统计 · {dataset_count} 个有效数据集 · {sample_count} 条样本 · 风险占比 {risk_rate}`。字段本身来自 `_effective_counts`（合并口径，C2 无问题），但「有效」二字在存在同源重复时名不副实（同 §3.9）。

---

## 4. 替代组件方案

原则：只替换**不满足**的 7 个组件，保留 #1 #2 #3 #11 的「数据资产 + 统一风险口径」骨架；全部方案优先复用已有组件库（`frontend/src/components/dashboard/`），且都在本仓库已有实现先例（`ProfileGeological.vue` 是同一套 `ProfileBase` 上的管理端参考实现）。

### R-4（替代 #4 目的端口种类 KPI）

- **建议标题 / 类型**：「**数据集（去重口径）**」KPI 指标块（`DashKpis`，与 #1-#3 同一组）。
- **数据来源与聚合口径**：`data.dataset_count`（`dashboard_service.py:1068`，由 `_effective_counts` 的 `len(groups)` 得出，`:654-662`）+ `data.dataset_file_count`（`:1069`）作副标题「含 N 份文件，其中 M 份为同源副本」。这两个字段**已经在 `ProfileBase` 里下发**（`frontend/src/api/dashboardApi.ts:102-103`），不需要后端改动。
- **为什么满足 C1**：数据集总量是场景数据资产的第一水位指标，直接对应管理员职责。**为什么满足 C2**：该数字由该场景全部可见数据集合并、按同源键去重得出（`_group_key`，`:634-636`），不是任何单个数据集内部统计。
- **可行性**：字段已存在（`dashboardApi.ts:102-103`）；同款 KPI 用法见 `ProfileGeological.vue:102`（`{ label: '数据集', value: props.data.dataset_count }`）。**若要让去重覆盖网络场景**，需后端扩展：把 `_group_key`（`:634-636`）的判定从「logical_id ∈ CARRIER_LOGICAL_IDS」升级为「内容指纹（file_path 的 size+mtime 或内容哈希）相同即同源」，这是新增逻辑，需在报告中标注为后端改动项。

### R-5（替代 #5 协议分布 DashDonut）

- **建议标题 / 类型**：「**数据集资产明细**」键值行列表（`DashRows`）。
- **数据来源与聚合口径**：`data.datasets`（`ProfileBase.datasets`，`dashboardApi.ts:25-37`：`name/logical_id/label_field/record_count/risk_count/risk_rate/is_risk_label`），每行一个数据集，值拼成「`record_count` 条 · 标签 `label_field` · 风险 `risk_rate` · 模型 N 个」；模型数由 `getModelVersionList({ scenario_id, page_size: 100 })` 按 `dataset_logical_id` 归集（`frontend/src/api/modelVersionApi.ts:18,69-75`）。
- **为什么满足 C1**：数据资产 + 建模覆盖同屏（哪份数据白躺着没人用），是管理端最核心的决策面。**为什么满足 C2**：每行一个数据集、所有数据集用同一组字段同一口径并列，正是用户给出的 C2 正面样例；且它对**新增数据集自动生效**（不再依赖写死的 `logical_id`）。
- **可行性**：完全可复制 `ProfileGeological.vue:176-192`（`datasetRows`）+ `:151-162`（`modelCountByDataset`）+ `:61-75`（三接口 `Promise.allSettled` 静默降级）；字段全部来自 `reader.describe`（`dashboard_service.py:618-631`）与已有模型接口，**无需后端新增字段**。
- **注意**：`is_risk_label` 是常量映射（`dashboard_service.py:627`，`DATASET_RISK_TYPES` `constants.py:308-319`），对未登记的新数据集会判 false，不要据此写「是否可建模」，只展示真实 `label_field`（`ProfileGeological.vue:171-174` 已有同样的告诫）。

### R-6（替代 #6 目的端口 TOP 8 DashBars）

- **建议标题 / 类型**：「**各数据集风险样本占比（%）**」横向条形（`DashBars`，`percent-value` + `label-width="250"`）。
- **数据来源与聚合口径**：`data.datasets[].risk_rate`（= `risk_count / record_count`，后端 `:618-631` 计算，逐数据集），每行一个数据集；只统计 `is_risk_label` 为真的数据集，非风险标签的数据集单列说明（`ProfileGeological.vue:42-43` 的 `riskDatasets()` 写法）。
- **为什么满足 C1**：一眼看出「哪份数据的正样本比例健康、哪份极不平衡」，直接影响能否训练、要不要补数据。**为什么满足 C2**：同一把风险尺子（`_label_is_risk`，`:321-323`）横向比较多个数据集，每行一个数据集。
- **可行性**：`ProfileGeological.vue:306-312` 是同款实现；网络场景实测两个数据集的风险占比差异极大（NF 3.95% vs KDD 46.61%，本次实测），这个对比有真实信息量。**无需后端改动**。

### R-7（替代 #7 流量包长五段分布 DashColumns）

- **建议标题 / 类型**：「**各数据集样本量**」+「**各数据集正样本量**」两张纵向柱图（`DashColumns`，统一 Y 轴单位「条」）。
  （不要试图用 `DashBars` 的 `value2` 做双序列：`DashBars.vue:93` 模板只渲染 `item.count`，`value2` 虽在 props（`:11`）里但未参与渲染。）
- **数据来源与聚合口径**：`data.datasets[].record_count` 与 `data.datasets[].risk_count`（`:628-629`），每行一个数据集，两个图共用同一「标签列全量计数」口径，可直接对照（谁大谁小、谁正样本多）。
- **为什么满足 C1**：样本量与正样本量是建模可行性的两个前置水位。**为什么满足 C2**：多数据集同口径并列，而非某一数据集的字段分布。
- **可行性**：`ProfileGeological.vue:262-268` 已用同款（`各数据集样本量` + `DashBars`）；字段来自 `describe`，**无需后端改动**。

### R-8（替代 #8 连接状态分布 DashBars）

- **建议标题 / 类型**：「**各数据集建模覆盖**」横向条形（`DashBars`，值 = 该数据集的模型版本数，标签 = 数据集名）。
- **数据来源与聚合口径**：`getModelVersionList({ scenario_id, page_size: 100 })`（`modelVersionApi.ts:69-75`）按 `dataset_logical_id`（`:18`）归集，每个数据集一行，区分「模型 N 个（已发布 M）」与「未训练」；数据来源为 `data.datasets` 的数据集清单（保证「未训练」的数据集也出现）。
- **为什么满足 C1**：建模覆盖 = 数据资产有没有被用起来，纯管理端问题。**为什么满足 C2**：每行一个数据集、同一「模型数」口径横向对比。
- **可行性**：`ProfileGeological.vue:151-162`（归集）+ `:176-192`（渲染）已实现同款；接口已存在，**无需后端新增字段**（模型记录自带 `dataset_logical_id`，`modelVersionApi.ts:11-37`）。

### R-9（替代 #9 平均入向字节 / 重传占比 DashRows）

- **建议标题 / 类型**：「**数据质量提示**」键值行列表（`DashRows`）。
- **数据来源与聚合口径**：只用 `data.datasets`（`record_count / risk_count / risk_rate / label_field`）做跨数据集比对，两条规则：
  1. **类别极不平衡**：`record_count > 0 && risk_count > 0 && risk_rate < 0.05` → 「正样本 x / y 条（z%），类别极不平衡」（网络场景会命中 NF 3.95%）。
  2. **疑似同源重复**：按 `label_field|record_count|risk_count` 三元组分组，组内 ≥2 条即报「标签、样本量、正样本数完全一致，疑似同源重复」——**这条会自动把 `net_flow_company_v1` 与 `nf_unsw_nb15_v2`（都是 23897 条 / 945 正样本）抓出来**，正好治 §1.2 第 4 点的重复计数。
- **为什么满足 C1**：数据质量直接影响统计口径与训练偏向，是管理员独有的信息（执行端不需要）。**为什么满足 C2**：判定依据是跨数据集的同口径三元组比对，不读任何单一数据集的字段分布。
- **可行性**：`ProfileGeological.vue:215-246` 是逐行同款实现，**无需后端改动**。

### R-10（替代 #10 应用服务 TOP DashBars）

- **建议标题 / 类型**：「**风险事件处置进度**」漏斗（`DashFunnel`）+ KPI 组补「**待处置积压**」「**已处置率**」（`DashKpis`）。
- **数据来源与聚合口径**：`getScenarioWorkspace(scenario_id)`（`dashboard_service.py:1298-1348`）返回的 `summary.pending / resolved / total / status_funnel`；SCENARIO_ADMIN 走的 `_event_scope`（`:679-686`）按 `RiskEvent.scenario_id == 本人场景` 取**全场景**事件，`scope.self_only=false`（`:1334`），即「大家的共性」而非个人。管理员可再叠加 `getUserList({ page_size: 200 })` 过滤本场景成员做「场景成员」卡（`ProfileGeological.vue:72-75,195-209`）。
- **为什么满足 C1**：流程与积压水位、成员与权限，正是用户列举的管理员总览维度。**为什么满足 C2**：该口径是**事件级全场景聚合**（覆盖该场景全部数据集产生的事件），不涉及任何单一数据集内部字段分布；与 R-4~R-9 的数据资产口径互补，共同构成「管理员总览」。
- **可行性**：`ProfileGeological.vue:59-79`（三接口并行 + 静默降级）、`:107-109`（漏斗）、`:252-259`（渲染）、`:195-209`（成员）已实现同款；`getUserList`（`frontend/src/api/userApi.ts`）与 `getScenarioWorkspace`（`dashboardApi.ts`）均已有，**无需后端新增字段**。

### 附：口径收敛建议（跨方案）

1. 把「逐文件」与「去重」两套口径统一到 `groups`（`dashboard_service.py:1074-1082`，前端 `dashboardApi.ts:108` 已可用）：数据集规模/样本量类图表一律用 `groups`，KPI 用 `dataset_count`，并在卡片 `source` 里写明「同源副本已合并」。
2. `_group_key`（`:634-636`）的去重范围从航母扩展到「同内容文件」，否则网络场景的 `sample_count` 会持续虚高 76%。
3. `ProfileNetwork.vue:32` 的「两数据集合计」改成由 `data.dataset_count` 动态生成。

---

## 5. 整体结论

**该场景首页整体上是「数据画像（数据集内部统计）」，不是「管理员总览（跨数据集共性）」。**

判定依据：

1. **结构证据**：11 个组件里，**6 个只读一个 `logical_id`**（`dashboard_service.py:1103` 的 `nf_unsw_nb15_v2`、`:1104` 的 `kdd_train_20_percent`），占比 55%；1 个 KPI（目的端口种类）也只看 NF。只有 4 个组件真正落在「全部数据集合并」口径上（3 个 KPI + 数据集规模对比），其中 KPI 还带同源重复污染。
2. **硬编码证据**：管理员可见的 `net_flow_company_v1`（company）以及**任何后续上传的新数据集**，在画像的 6 张图里完全没有出现——`_network_profile` 用两个写死的 `logical_id` 取数（`:1103-1104`），用户上传新数据集不会改变画像内容（除「数据集规模对比」多一根柱子）。这正是 C2 不满足的直接证据。
3. **对照证据**：画像页的「流量包长五段分布」「目的端口 TOP 8」与用户首页的「包长五段分布」「告警端口 TOP」是同一组件、同一字段、同一叙事（`ProfileNetwork.vue:43-51` vs `WorkspaceNetwork.vue:54-70`，后端 `:1114-1117,1129` vs `:1398-1401,1394`），只是把主语从「我的告警」换成「整个数据集」——与用户诉求「不能和普通用户一样」正面冲突。
4. **口径证据**：`_effective_counts` 的同源去重只覆盖航母（`:634-636,100-104`），网络场景把同内容的 NF 副本计了两次：管理员看到的 `sample_count` 55350 / `risk_rate` 9.78%，去重后应为 31453 / 14.20%。
5. **正面对照**：同一套 `ProfileBase` 上，`ProfileGeological.vue` 已经实现了用户要的形态（数据集资产明细、各数据集样本量、各数据集风险占比、建模覆盖、数据质量提示、处置进度、场景成员），说明替代方案在本仓库**已被验证可行**，不需要新的图表组件。

修复方向：保留 4 个满足组件（并修去重口径），把 7 个不满足组件按 §4 的 R-4~R-10 替换——「数据集资产明细 / 各数据集样本量 / 各数据集正样本量 / 各数据集风险占比 / 各数据集建模覆盖 / 数据质量提示 / 风险事件处置进度 + 场景成员」，即可同时满足 C1（管理员总览）与 C2（跨数据集共性口径）。
