# 全项目审查 · Lead 独立核验记录

> 代理的自述不算证据。此文件记录 Lead **亲自复算/复验**的结果。只记结论 + 证据，不重复代理报告。

---

## V-00 模板等价性提取器的自我纠错（**重要，先看这条**）

首版提取器用「第一个 `<template>` → 第一个 `</template>`」截取模板块，遇到**嵌套的内层 `<template>`**（`v-for`/`v-slot`/具名插槽）会提前终止，把「少截一段」误判成「等价」。四个页面因此全部得到**假阳性 `equal=True`**。

**修正口径**：取**列 0 的 `<template>` 开头** → **列 0 的最后一个 `</template>`** 结尾。

重跑后四个页面**全部 `equal=False`**，且每个差异都**恰好等于代理自述的删除项** —— 说明「行为不变」的声明依然成立，但**结论必须用修正后的版本**。下表 V-01…V-04 均为修正后结果。

---

## V-01 ProfileNetwork.vue（R1 重构）— **通过**

| 核验项 | 方法 | 结果 |
|---|---|---|
| 模板渲染等价 | 修正提取器，去空白归一化逐行比对 HEAD vs 工作区 | 56 行 vs 56 行，**2 处差异**，均与自述一致 ✓ |
| 差异 1 | `v-if="modelingReady"` 被删 | `modelingReady` 是恒真计算属性（R1 已删）→ 删 `v-if` 渲染等价 ✓ |
| 差异 2 | `join('、')` → `join(LIST_SEPARATOR)` | `LIST_SEPARATOR = '、'`（`:52`）字面量一致 ✓ |
| 删除项零引用 | 全仓 grep `rowsOrEmpty` / `modelingReady` / `caliber` / `dimensionCoverage` | 4 页内 **0 命中** ✓（R1/R2/R3/R4 声称的清除已复核） |
| 行数 | `482 + 73 − 71 = 484` | LF 实际 **484** ✓ |

---

## V-02 ProfilePower.vue（R2 重构）— **通过**

| 核验项 | 方法 | 结果 |
|---|---|---|
| 模板渲染等价 | 修正提取器，去空白归一化逐行比对 HEAD vs 工作区 | 54 行 vs 51 行，**2 处差异**，均为属性改名 ✓ |
| 差异 1 | 多行 `source="…"` → `:source="BASELINE_SOURCE"` | `BASELINE_SOURCE`（`:71-72`）与旧内联串**逐字符一致** ✓ |
| 差异 2 | `:rows="s2Rows"` → `datasetRows` | 新定义是旧定义的**超集**（原 10 字段全在，新增 `models`）✓ |
| `SCENARIO_KEY` 值 | 读 `:54` | `'power'`，与被替换的字面量一致 ✓ |
| 删除 `?? '—'` 是否等价 | 读 `DashTable.vue` `asText()` | `null`/`undefined`/`''` → `'—'`，页面级 `?? '—'` 冗余 ✓ |
| 行数 | `459 + 104 − 110 = 453` | LF 实际 **453** ✓（R2 摘要写「421」是算术笔误，`--numstat` 正确） |

---

## V-03 ProfileFlightdeck.vue（R3 重构）— **通过**

| 核验项 | 方法 | 结果 |
|---|---|---|
| 模板渲染等价 | 修正提取器，去空白归一化逐行比对 HEAD vs 工作区 | 63 行 vs 62 行，**1 处差异** ✓ |
| 差异 1 | 删 `<p v-else-if="!modelingKnown" class="d-src">…</p>` | `modelingKnown` 恒真（R3 已删该计算属性）→ 该分支**不可达**，删除等价 ✓ |
| 行数 | `537 + 94 − 129 = 502` | LF 实际 **502** ✓ |

---

## V-04 ProfileGeological.vue（R4 重构）— **通过**

| 核验项 | 方法 | 结果 |
|---|---|---|
| 模板渲染等价 | 修正提取器，去空白归一化逐行比对 HEAD vs 工作区 | 63 行 vs 63 行，**1 处差异** ✓ |
| 差异 1 | `<p v-if="modelingReady" …>` → `<p …>` | `modelingReady` 恒真 → 等价 ✓ |
| 行数 | `460 + 58 − 59 = 459` | LF 实际 **459** ✓ |

**结论（V-01…V-04）**：四个页面的「渲染不变」声明**全部成立**。每处模板差异都对应一个**恒真条件**或**字面量常量替换**，无一处改变可见输出。

---

## V-05 行数口径（**别再踩**）

| 方法 | ProfileFlightdeck 实测 | 判定 |
|---|---|---|
| `(Get-Content).Count` | 465 | ❌ LF-only 文件**丢行** |
| `Measure-Object -Line` | 更少 | ❌ **不计空行** |
| `git diff --numstat` | 94/129 | ✅ 与下列一致 |
| `([regex]::Matches($text,"`n")).Count` | **502** | ✅ **权威** |
| `[System.IO.File]::ReadAllLines($p).Length` | **502** | ✅ **权威** |

**权威口径 = LF 换行符计数**（`git diff --numstat` 同源）。本文件所有行数均用此口径。

---

## V-06 P0 越权修复（`_geological_workspace` 泄漏他人 personal 数据集）— **通过（实测）**

**来源**：B1 报告 §6 B1-P4 + §5.2 T3。B1 因「行为不变」未实施，Lead 采纳并实施**合并方案**。

**改动**（`backend/app/services/dashboard_service.py`，4 处）：
1. `get_workspace`：`scalar(select(Dataset)…)` → `scalars(…).all()` 取回**全部可见数据集**（`status=ACTIVE` ∧ `visibility ∈ {platform, company}`），`dataset = visible_datasets[0]`。
2. 地质分支：`self._geological_workspace(events, dataset, visible_datasets)`。
3. 签名加 `siblings: list[Dataset]` 形参。
4. 删除 `_geological_workspace` 内用 `dataset.scenario.datasets` 的 relationship 遍历（该路径**只过滤 status、不过滤 visibility**）。

**为何是安全缺陷而非设计选择**：`get_workspace` 准入为 `require_scenario_access`（`ROLE_SCENARIO_USER` 亦可调）；同一文件其余 4 处（`get_profile` / `get_scenario_overview` / `get_workspace` 自身取代表数据集 / `_event_scope`）**全部**按角色收窄可见性，唯独此处遗漏。

**实测证据**（`tmp/_verify_p0.py`，退出码 **0**，`RESULT: ALL OK`）：

| 断言 | 结果 |
|---|---|
| scenario 4 存在 personal 数据集（证明断言非空转） | ✓ `id=21 logical_id=carol_slope_personal_v1 visibility=personal status=ACTIVE 风险类型已登记=True` |
| 其中「修复前确会被 `describe()` 下发」的 | ✓ **1 个**（即该缺陷在当前数据下**真实可复现**） |
| SCENARIO_ADMIN(`geo_admin`) `dataset_prior` 不含 personal | ✓ 5 行 `[dis_raw_data, dis_landslides, dis_causative_factors, dis_guaruja_random, geo_slope_company_v1]`，可见性取值 `{platform, company}` |
| SCENARIO_ADMIN `dataset_prior` == 「可见∧已登记∧active」集合 | ✓ 完全一致 |
| SCENARIO_USER(`carol`) 同上两项 | ✓ 同样通过 |
| 数据集查询 SQL 条数 | ✓ **1 条**（T3 合并后不再有 2 条 relationship lazy-load） |
| 响应结构完整（13 个字段 + `scenario_key=='geological'`） | ✓ 全部存在 |

**探针自身的两个 bug（已修，记录以免误判）**：
1. 首版按复数表名 `FROM datasets` 匹配 → 0 命中。**本表名是单数 `dataset`**（`models/dataset.py:15`）。
2. 首版按「命中即失败」判定，未先打印全部语句，导致误报 2 个 FAIL。

**未修改任何分区外文件**；`python -m py_compile` 退出码 0。

---

## V-07 待核验 / 未决

- [x] **`DashRows` 第二处命中 —— 已解决：不是死导入**。4 个 Profile 文件各 2 处命中，第 2 处均为**真实使用**：`ProfileFlightdeck.vue:500 <DashRows :rows="memberRows" />`、`ProfileGeological.vue:457 <DashRows v-else :rows="memberRows" />`、`ProfileNetwork.vue:482 <DashRows v-else :rows="memberRows" />`、`ProfilePower.vue:451 <DashRows :rows="memberRows" />`。`DashRows` 在 4 页均**必需**，不得删。
- [ ] B6b-1 是否删掉 `config.py:343-344` 的 `print(DEEPSEEK_CONFIG)`（B2-P4 提出；`config.py` 属 B6b-1 写区）。
- [ ] B4b 越权核对表结论（风险事件/阈值/审计日志的 IDOR）。
- [ ] B4a 关于 `source='fallback'` 后端契约的结论 → 用于裁决 D-21。
- [ ] 全量验收：`tmp/verify_all.ps1`（pytest + vue-tsc + build + 4 场景浏览器复验 + DB 探针）。

## V-08 全模块导入扫描 `tmp/import_sweep.py` — **通过（96/96）**
- 背景：`python -m py_compile` **抓不到 `NameError`**（已实证两次：B2 与 B4b 都在自己分区里改出过同类问题）。
- 工具：`tmp/import_sweep.py`（Lead 自建）遍历 `backend/app/**/*.py`，对每个模块做 `importlib.import_module`，失败即打印完整 traceback。
- 结果：`扫描模块数：96` / `RESULT: ALL OK —— 96 个模块全部导入成功` / `SWEEP_EXIT=0`。
- **已升格为强制验收门**，`tmp/verify_all.ps1` 第 2 阶段（`py_compile` 不能替代它）。

## V-09 P0 线上故障 —— `schemas/report.py` 的 `NameError`（**B2 引入，Lead 修复**）
- 现象：`import app.main` 直接崩，整个后端不可用。
- 根因：B2 把 `from typing import Literal, Optional` 改成只留 `Literal`，并转换了 `ReportCreate`/`ReportScheduleUpdate` 的用法，**但漏了 `ReportGenerate.scenario_id`(L47) 与 `ReportGenerate.interval_days`(L55)**。
- 修复：两处改为 `int | None`（与文件其余部分风格一致），文件 57 行。
- **教训（已制度化）**：任何删除 typing 导入的重构，必须全文件 grep 该名字；`py_compile` 通过 ≠ 可导入。这就是 V-08 存在的理由。

## V-10 X2a-P4 —— `running_under_test_runner()` 在裸 `pytest` 下失效（**Lead 修复**）
- 危害：5 个后台 runner 会真启动并连**真实数据库**，`training_runner.reap_stale()` 会把真实库超时的 TRAINING 行改成 FAILED。
- 修复：`utils/common.py::running_under_test_runner()` 追加 `if "pytest" in sys.modules: return True`（生产不 import pytest，线上行为不变）。
- **纪律**：最终验收用 `python -m pytest`，禁止裸 `pytest`。
- 已由 V-11 的 `py_compile` + `import_sweep` 复核。

## V-11 B5-P1 —— `dashboard_service._label_is_risk` 正类口径统一（**Lead 应用，黄金快照证明**）
- 违规点：原实现用「非 `0/normal/no/false/none/?/空` 即风险」**自动推断正类**，违反需求 §6.4.1 与 `constants.py:269-270`。
- 工具：`tmp/_golden_profiles.py`（Lead 自建）—— 对 4 个场景管理员的 `get_profile` + `get_workspace` 做**全字段扁平化哈希**，支持 `save` / `diff`。
- 改动前基线哈希：network `6a0a95f96bf76d6e`、power `28d9a4ee9c48d5fd`、flightdeck `c0b676f96f604858`、geological `469ff145e921fcff`。
- 改动后：**network / power / flightdeck 三个哈希逐字节不变**；geological `bcfc15b28b24b7fa`。
- geological 的 5 处变化全部是**修复**：`dis_global_catalog` 的 `risk_count` 1000→0、`risk_rate` 1.0→0.0（改前把 1000 行多分类编目数据全算成风险事件）；`profile.risk_count` 4594→3594、`risk_rate` 0.2804→0.2193；`roles[3].risk_rate` 1.0→0.0。
- 复核：`py_compile` EXIT=0、`import_sweep` 96/96 OK、`_verify_profiles.py` `RESULT: ALL OK`、`_verify_p0.py` `RESULT: ALL OK`。
- 7 个调用点全部更新（B5 报告只找到 2 个）。

## V-12 三处 `Profile*.vue` 漏传 `scenario_id`（**Lead 修复**，D-05/D-16 根因）
- `ProfileNetwork.vue` / `ProfilePower.vue` / `ProfileFlightdeck.vue` 的 `getUserList` 补 `scenario_id`。
- 依据：B5 证明后端 `user_routes.py:45` 早已支持、`user_service` 只对 SCENARIO_ADMIN 自动收窄 ⇒ 根因在前端。
- 需 `vue-tsc` + 浏览器复验（已并入 `tmp/verify_all.ps1`）。

## V-13 `tmp/verify_all.ps1` 自身的一个坑 —— **无 BOM 的 `.ps1` 会被 PS 5.1 按 GBK 解码**
- 现象：脚本报 `Unexpected token '娴侀噺缁熻'`、`The string is missing the terminator`，看起来像语法错误，实为**编码**问题。
- 根因：Windows PowerShell 5.1 对**无 BOM** 的 `.ps1` 按系统 ANSI（本机 GBK）解码；脚本内含中文断言字符串 ⇒ 乱码 ⇒ 解析崩。
- 修复：`[System.IO.File]::WriteAllText($p, $txt, (New-Object System.Text.UTF8Encoding($true)))` 加 BOM；`Parser::ParseFile` errors 归 0。
- **教训**：本仓库所有含中文的 `.ps1` 必须存为 **UTF-8 with BOM**；`edit` 工具写出的文件无 BOM，改完 `.ps1` 要补。

---

## 环境事实（复核用）

- 控制台默认 **GBK**：比对中文源码必须 `[Console]::OutputEncoding = [Text.Encoding]::UTF8` + `[System.IO.File]::ReadAllText(path, UTF8)`，否则会把 UTF-8 当 GBK 解码，产出**假差异**。
- 模板等价性判定口径：**去空白归一化后逐行相等**（源码字节相等过严——缩进/换行重排不改变渲染）。
- `git show "HEAD:<path>"` 的路径**必须用正斜杠**；反斜杠报 `fatal: path … exists on disk, but not in 'HEAD'`。
- 表名易错：`dataset`（单数）、`model_version`、`risk_event`、`app_user`、`scenario`。
- 后端 12312 端口的 uvicorn **无 `--reload`** → 改了后端代码必须**重启**才生效；改前跑 HTTP 探针会测到**陈旧代码**。
