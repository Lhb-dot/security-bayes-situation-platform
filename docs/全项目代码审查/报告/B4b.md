# B4b 分区审查报告（风险事件 / 处置记录 / 阈值 / 阈值审计 / risk_view）

> 依据：`docs/全项目代码审查/审查协议.md`（唯一基线）。
> 本分区为 **B4 拆分后的下半区**：B4a 负责 `explanation_service.py` + `schemas/explanation*.py`，
> 本代理**未触碰** B4a 的任何文件（见 §9 `git status`）。
> 首要任务（任务书要求）：**逐个函数核对越权（IDOR）**，结论见 §3-S。

---

## 1. 分区与文件清单（改前 → 改后）

| 文件 | 改前行数 | 改后行数 | 净变化 | git numstat（+/−） | 是否改动 |
|---|---|---|---|---|---|
| `backend/app/services/risk_event_service.py` | 560 | 563 | +3 | +16 / −13 | ✅ |
| `backend/app/services/handling_record_service.py` | 176 | 188 | +12 | +23 / −11 | ✅ |
| `backend/app/services/risk_view.py` | 123 | 125 | +2 | +19 / −17 | ✅ |
| `backend/app/services/risk_threshold_service.py` | 126 | 131 | +5 | +13 / −8 | ✅ |
| `backend/app/services/threshold_audit_log_service.py` | 57 | 50 | −7 | +7 / −14 | ✅ |
| `backend/app/schemas/risk_event.py` | 23 | 23 | 0 | +2 / −2 | ✅ |
| `backend/app/schemas/risk_threshold.py` | 24 | 29 | +5 | +6 / −1 | ✅ |
| `backend/app/models/risk_event.py` | 73 | 73 | 0 | 0 | ⛔ 只审阅（硬约束） |
| `backend/app/models/risk_threshold.py` | 40 | 40 | 0 | 0 | ⛔ 只审阅 |
| `backend/app/models/handling_record.py` | 30 | 30 | 0 | 0 | ⛔ 只审阅 |
| `backend/app/models/threshold_audit_log.py` | 38 | 38 | 0 | 0 | ⛔ 只审阅 |
| **合计（代码）** | **1270** | **1290** | **+20** | **+86 / −66** | |

> 行数勘误：任务书写 `risk_event_service.py` 509 行，实测 **560 行**（`git show HEAD:...` 计数）。
> 口径：`git diff --numstat`（与 `git show` 计数一致）；**不要用 `(Get-Content).Count`**——本仓库文件混用 LF/CRLF，实测对 `risk_view.py` 少算 21 行。
> 净删除**死代码约 20 行**（`ThresholdAuditLogService._get` 7 行、3 处 `logger = get_logger(...)` 定义及空行 5 行、未使用导入 3 行、`risk_view` 函数内 import 8 行中的可上提部分），
> 86 行插入中 **60+ 行是 docstring/注释**（越权与审计完整性说明、文档纠错、阈值层级说明），可执行语句的变化只有 §2 的 5 处常量替换 + 2 处安全修复。

---

## 2. 改动摘要（每项一行）

1. **删** `risk_event_service.py` 未使用导入 `Any`、`ROLE_ADMIN`（`ROLE_ADMIN` 在 `constants.py:33` 只是 `ROLE_SUPER_ADMIN` 的别名，本文件从未引用）。
2. **删** `threshold_audit_log_service.py` 零引用私有方法 `_get()`（7 行）——`get()` 用的是带 `user_id` 归属过滤的独立查询，`_get` 既无归属校验也无人调用。
3. **删** `handling_record_service.py` / `risk_threshold_service.py` / `threshold_audit_log_service.py` 三处未使用的 `get_logger` + `logger`（模块级死变量）。
4. **删** `risk_view.py` 两处**函数内 import**（`row_to_dict`、`RISK_EVENT_STATUS_*`）→ 提到模块顶部（`app.utils.common` 无 app 内部依赖，无循环导入；已实测 import 通过）。
5. **修（安全·审计完整性）** `HandlingRecordService.create`：`status_before`/`status_after` 原先**接受调用方自填**（非 `UPDATE_STATUS` 动作直接落库），可把一条 `ASSIGN` 记录伪造成「已处置→待处置」洗白状态历史；改为**一律以库中事件真实状态为准**（签名不变，参数保留兼容）。
6. **修（安全·边界一致性）** `HandlingRecordService.delete`：原实现只 `require_admin`（SUPER_ADMIN）就删，**不受与查询一致的数据边界约束**（读不到的记录却能删）；补 `_can_access_record`，与 `get`/`get_list` 对齐。
7. **修（魔法字符串）** `"platform"/"company"` → `DATASET_VISIBILITY_PLATFORM/COMPANY`（`risk_event_service` 两处）；`"SUPER_ADMIN"` → `ROLE_SUPER_ADMIN`（`risk_threshold_service`、`threshold_audit_log_service` 各一处）。
8. **修（文档与实现不符）** `update_status` docstring 原写「PENDING → PROCESSING → RESOLVED」线性路径，与 `RISK_EVENT_STATUS_TRANSITIONS`（PENDING 可直达 RESOLVED）矛盾 → 按常量纠正。
9. **修（文档与实现不符）** `schemas/risk_threshold.py` 原写「仅管理员」可改阈值，实际路由 `require_bound_scenario` 不校验角色 → 改为「当前账号」并说明账号级存储语义。
10. **修（文档与实现不符）** `handling_record_service.get_list` docstring 原写「本人处置的**或**本人风险事件的记录」，代码实际只按**事件归属人**过滤 → 按代码纠正。
11. **弃用清理** `typing.Optional/Dict/Tuple/List` 旧式注解 → `X | None` / `dict` / `tuple`（7 个文件；与 B6 已在 `risk_event_routes.py`/`risk_threshold_routes.py` 做的 `Optional → X | None` 现代化口径一致，Python 3.12.4）。
12. **文档补强** `risk_view` 模块 docstring 明确「阈值只有账号级一层，不存在场景级/平台级默认行」；`risk_threshold_service` 类 docstring 明确「任何账号（含 SUPER_ADMIN）都无法改写他人阈值行」。

---

## 3. 逐项审查结论（A / B / C / D / E）

### 3.A 弃用（deprecated）

| 检查项 | 结论 | 查法 |
|---|---|---|
| `datetime.utcnow()` | **0 处**（全 `backend/app` 也 0 处） | `grep -rn "utcnow\(" backend/app` → No matches；本分区一律 `datetime.now(timezone.utc)` |
| `distutils` / `imp` / `pkg_resources` / `asyncio.get_event_loop()` | 0 处 | 逐文件通读 import 段 |
| 旧式 `typing.List/Dict/Optional/Tuple` | 本分区原有 **18 处**，已全部改为内建泛型/`X | None` | 改后 `grep -n "Optional\|Dict\[\|List\[\|Tuple\[" <本分区 7 文件>` → No matches |
| `from typing import` 多余导入 | 已删 4 个（`Any`、`Optional`×3 文件的整行、`Dict`、`Tuple`） | 见 §4 |
| 项目层旧路径 | 本分区不涉及（`legacy_model_routes`/`model_sim`/`pmwnb_demo` 属 B3/X1） | 通读 |

### 3.B 残留 / 死代码

| 项 | 结论 | 证据 |
|---|---|---|
| 未使用导入 | `risk_event_service.py`：`Any`、`ROLE_ADMIN` → 已删 | §4-① |
| 未使用模块级变量 | `logger`（`handling_record_service` / `risk_threshold_service` / `threshold_audit_log_service`）→ 已删 | §4-② |
| 零引用私有方法 | `ThresholdAuditLogService._get()` → 已删 | §4-③ |
| 零引用模块 | **`handling_record_service.py` 整文件（188 行）**：无 API 路由、无 service 调用、无测试引用 → **保留但提案删除**（删它必须同时改 `services/__init__.py`，属 B7 写区） | §4-④ + §7-提案1 |
| 零引用私有函数/常量 | 本分区无（`_calc_risk_level`、`_calc_fault_position`、`_build_description`、`_pick`、`_ratio`、`_get_for_user`、`_can_access_event`、`_can_access_record`、`_require_event_access`、`_build_risk_event` 均有调用点，见 §5） | §5 函数清单 |
| 注释掉的代码块 / `print` / TODO / FIXME / XXX | 0 处 | `grep -n "print(\|TODO\|FIXME\|XXX"` 本分区 → No matches |
| 空函数 / `pass` 占位 | 0 处 | 通读 |
| 重复定义 | ① `RiskEventStatus = Literal["PENDING","PROCESSING","RESOLVED"]`（`schemas/risk_event.py:10`）与 `constants.RISK_EVENT_STATUSES` 是**两份值域**（后者另有 `RISK_EVENT_STATUS_TRANSITIONS`）；② `DEFAULT_MEDIUM/HIGH_THRESHOLD`（`constants.py:369-370`）与 `risk_event_service._get_thresholds` 的兜底**共用同一常量**（无第二份硬编码，已核实）；③ 状态机校验逻辑在 `RiskEventService.update_status` 与 `HandlingRecordService.create` **各写一遍**（同一字典、同一错误文案，见 §8-存疑5） | 通读 + grep |
| 构建产物入库 | 本分区无 | — |
| 过期文档 | 3 处（改动摘要 8/9/10） | 已修 |

### 3.C 复杂度

| 检查项 | 结论 |
|---|---|
| >80 行函数 | **1 个**：`RiskEventService.get_list`（96 行，含 docstring）。内含两条分页路径（SQL 分页 / 阈值判级后内存分页），可拆 `_list_by_viewer_level()`；**未拆**（拆它要动返回结构拼装，收益低于回归风险，见 §8-存疑3） |
| 超长文件（>800 行） | 无（最长 563 行） |
| >3 层嵌套 | `_build_description` 的 `if risk_type == ...` 为**平行早返回**（非嵌套）；`_require_event_access` 最深 2 层。无超 3 层 |
| 魔法数字/字符串 | `"platform"/"company"`（2 处）、`"SUPER_ADMIN"`（2 处）、`"ASSIGN"/"UPDATE_STATUS"/"ADD_COMMENT"`（`handling_record_service` 用字面量，`constants.HANDLING_ACTIONS` 已有元组）→ 前两类已修；动作名 2 处字面量保留（与 `HANDLING_ACTIONS` 同文件内一致，改动收益低，记录） |
| N+1 查询 | **本分区无**。`row_to_dict` 只读 `__table__.columns`（`utils/common.py:114`），**不触发 relationship 懒加载**；`risk_view.view_events` 对列表逐条序列化不会额外发 SQL。`_can_access_record` 的懒加载只出现在单条 `get` |
| 循环内 IO | 无 |
| 可内建替代的手写实现 | `risk_view.aggregate` 的 6 次 `sum(1 for ...)` 是清晰写法，不建议改 |

### 3.D 正确性隐患

| # | 结论 |
|---|---|
| D1 | **分母为 0 / 空集合**：本分区无除法。`risk_view.aggregate` 空列表 → 全 0，语义正确。`handling_record_service.get_list` 空结果 → `paginate` 返回 `total=0`。 |
| D2 | **`None` 访问**：`risk_view.level_of` 用 `score is None` 判定（**不是 falsy**）→ `risk_score=0` 正确判 LOW；`score=None` 时回退落库 `risk_level`，非法值回退 LOW（不凭空造数）。`_calc_fault_position._ratio` 对 `float(None)`/`float("?")` 捕 `(TypeError, ValueError)` → 返回 None，不虚构坐标。**无 `int(None)`/越界**。 |
| D3 | **过宽 except / 静默吞异常**：本分区**无 `except`**（0 处）。异常一律经 `@service_call`（`base.py:45`）→ 400/403/404/500，且**每条异常路径都 rollback**。`base.py` 已把 `TypeError/ValueError/KeyError/AttributeError/IndexError` 单列「编程错误」分支并打完整堆栈，不再与基础设施抖动混淆 → **不存在「`TypeError` 被静默掩盖」**（对外仍是 500，但日志可区分，符合协议要求）。 |
| D4 | **SQL 拼接**：本分区 0 处字符串拼 SQL；全部 `select()` + 参数绑定。 |
| D5 | **权限校验缺失**：见 §3-S 越权核对表（**逐函数**）。 |
| D6 | **状态机被真正校验**：`update_status` 与 `handling_record_service.create(UPDATE_STATUS)` 都查 `RISK_EVENT_STATUS_TRANSITIONS` 白名单，**非法跳转确实被拒**（`ServiceError(400)`）。**「待处置→已处置」不是非法跳转**：`constants.py:279-285` 注释明确「需求 §5.2：新事件默认待处置，后续可变为处理中**或**已处置」，`schemas/risk_event.py:4` 同口径 → 后端合法；前端 `nextStatus` 只给线性路径属**功能缺口**（F5 报告 D6 已记录），**非越权、非死分支**。 |
| D7 | **状态机边界缺陷（新发现·低危）**：若某行 `status` 落在值域之外（历史脏数据/人工改库），`RISK_EVENT_STATUS_TRANSITIONS.get(status, ())` → 空元组 ⇒ **该事件永久卡死，无任何修复路径**（`RISK_EVENT_STATUSES` 未参与校验）。当前 674 行数据由 `RISK_EVENT_STATUS_PENDING` 起始写入，**不可达**；记录，未改（改它要引入新状态或兜底放行，属行为变更）。 |
| D8 | **全局可变状态 / 无锁缓存**：本分区 0 处模块级可变状态、0 处缓存（`risk_view.load_thresholds` 每请求一查，无缓存也无失效问题）。 |
| D9 | **一致性**：`risk_view` 是唯一判级入口（7 个外部调用点全部经它，见 §5），**无第二份判级实现**；`risk_event_service._get_thresholds` 与 `risk_view.thresholds_for` 兜底值同源同常量（0.5/0.8），不会出现「一处判 HIGH 一处判 LOW」。 |
| D10 | **审计完整性（新发现·已修）**：`HandlingRecordService.create` 的 `status_before/status_after` 曾由调用方自填 → 审计凭据可伪造。已修为以事件真实状态为准。 |
| D11 | **存在性探针（低危·未改）**：`RiskEventService.delete` 先 `_get`（不存在→404）再恒抛 400（存在→400），可区分「该 id 是否存在」；`get()` 本身已有同型 `404 vs 403` 探针，**修 `delete` 无法关闭该信息面**，故未改（见 §8-存疑2）。 |
| D12 | **`get_list` 阈值判级路径全量载入内存**：传 `risk_level` 时把**符合角色过滤的全部事件**（当前 674 行）拉成投影再 Python 侧判级分页（`risk_event_service.py:412-424`）。当前规模无碍，10^5 量级会明显变慢。docstring 已声明该取舍；记录，未改（改用 SQL 判级需把阈值下推成 `CASE`，属结构性改动）。 |
| D13 | **潜在不一致（不可达）**：`_build_risk_event` 用 `record.user_id` 作事件归属人，却用 `current_user.id` 取阈值。当前唯一入口 `inference_record_service.py:388` 保证两者恒等（`user_id=current_user.id`），**不可达**；记录以备未来新增「代他人推理」入口时踩坑。 |
| D14 | **审计记录只写不读（可达性）**：`handling_record` 由 `update_status`/`add_comment` 写入，但**全仓无任何读取路由**（`HandlingRecordService` 零调用），前端 `types/security.ts` 也无处置记录列表消费 → 处置说明写进去后**用户看不到**。属功能缺口，报告（§7-提案1 一并裁决）。 |

### 3.E 硬约束遵守

- `backend/alembic/**`：**未改**（`git status` 无 alembic 条目）。
- `models/**`：**表字段零删改**（`git status` 中 `models/risk_event.py`、`models/risk_threshold.py`、`models/handling_record.py`、`models/threshold_audit_log.py` 均**未修改**）。索引缺失只报告（§7-提案3）。
- `schemas/**` 已导出字段名：`RiskEventHandle.new_status/comment`、`RiskEventComment.comment`、`RiskThresholdUpdate.medium_threshold/high_threshold`、`RiskEventStatus` **全部未改名、未改类型语义**（仅 `Optional[str]` → `str | None`，运行时等价）。
- 跨文件公共接口：`risk_view` 的 7 个公开函数与 `ThresholdPair` 类型**签名全部未变**（B1/B2/B3/B5 的调用点无需同步改）。

---

## 3-S. 【P0】越权（IDOR）逐函数核对表

判定口径：**场景归属** = 事件/记录所属 `scenario_id` 是否等于调用者绑定场景（SUPER_ADMIN 视为全场景）；
**角色** = 是否校验了角色白名单；**所有者** = 是否校验 `created_by_user_id`（USER 视角）。

| # | 函数 | 操作 | 校验场景归属 | 校验角色 | 校验所有者 | 风险判定 |
|---|---|---|---|---|---|---|
| 1 | `RiskEventService.get_list` | 列表读 | ✅ SUPER_ADMIN 限 `Dataset.visibility=platform`；SCENARIO_ADMIN 限本人场景 + `platform/company`；USER 强制 `created_by_user_id` | ✅ 三分支 | ✅ | **安全**（三条边界都写了 SQL WHERE，无「先查后滤」） |
| 2 | `RiskEventService.get` | 详情读 | ✅ `_require_event_access` | ✅ | ✅ | **安全** |
| 3 | `RiskEventService.update_status` | 状态改 | ✅ | ✅ | ✅ | **安全**；状态白名单同时生效 |
| 4 | `RiskEventService.add_comment` | 追加处置说明 | ✅ | ✅ | ✅ | **安全** |
| 5 | `RiskEventService.set_hidden`（hide/unhide 同一函数） | 可见性改 | ✅ | ✅ | ✅ | **安全** |
| 6 | `RiskEventService.delete` | 删除 | ❌ 仅 `require_login` + `_get` | ❌ | ❌ | **低危**：**无真删除**（恒 400），但 404/400 差异构成 id 存在性探针（同型探针已存在于 `get()` 的 404/403）→ 未改，§8-存疑2 |
| 7 | `RiskEventService.create_from_inference` / `_build_risk_event` | 生成事件 | 由唯一调用方 `InferenceRecordService.predict` 校验（`_can_infer_from_model` + `require_login`） | ✅ `require_login` | ✅ 归属人取 `record.user_id`（= 调用者） | **安全**（本分区内无公开 HTTP 入口） |
| 8 | `HandlingRecordService.create` | 处置记录写（含改状态） | ✅ `_can_access_event` | ✅ | ✅ | **安全**；状态字段伪造面已修（D10） |
| 9 | `HandlingRecordService.get_list` | 处置记录读 | ✅ 按 `RiskEvent` 归属过滤（三分支与风险事件同口径） | ✅ | ✅ | **安全** |
| 10 | `HandlingRecordService.get` | 处置记录读 | ✅ `_can_access_record` | ✅ | ✅ | **安全** |
| 11 | `HandlingRecordService.delete` | 处置记录删（审计凭据） | ⚠️ 原实现**无**边界 → 已补 `_can_access_record` | ✅ `require_admin`(SUPER_ADMIN) | ❌ 未校验 handler | **中危（潜在）**：平台管理员可删任意处置记录且**删除本身无留痕**。当前**无 API 路由暴露 ⇒ 不可达**（§4-④）；修完与读边界一致 |
| 12 | `RiskThresholdService.get_list` | 阈值读 | ✅ SQL 强制 `user_id=本人` | ⚠️ SUPER_ADMIN 不限场景（合理：阈值随账号） | ✅ | **安全**（不可能读到他人行） |
| 13 | `RiskThresholdService.get_by_scenario` | 阈值读 | ✅ `require_scenario_access` | ✅ | ✅ 只查本人行 | **安全** |
| 14 | `RiskThresholdService.update` | 阈值写（upsert + 审计） | ✅ `require_scenario_access` | ❌ **不校验角色**（任何登录角色均可） | ✅ **upsert 的 `user_id` 恒为 `current_user.id`** | **设计使然，非越权**：阈值是「账号级」设置（`risk_view` 口径），普通用户可改**自己**的阈值；**无法**改他人（无 user_id 入参）、**无法**改场景级/平台级（**该层级不存在**）。原 `schemas` 文档写「仅管理员」与实现不符 → 已修文档 |
| 15 | `ThresholdAuditLogService.get_list` | 审计读 | ✅ 强制 `user_id=本人` | ⚠️ SUPER_ADMIN 也只读自己的 | ✅ | **安全但功能缺口**：**任何角色都看不到他人的阈值变更**，`operator_id` 因此恒等于 `user_id`（见下） |
| 16 | `ThresholdAuditLogService.get` | 审计读 | ✅ `id + user_id=本人` 联合过滤 | ✅ | ✅ | **安全** |
| 17 | （审计日志的写/改/删） | — | — | — | — | 本服务**不提供** update/delete 入口 ✅；全仓无第二处写 `threshold_audit_log`（§4-⑤）。DB 层无触发器/不可变约束 → 报告（§7-提案3 同类） |

**越权核对表结论：17 个受核函数中，0 个存在「可用他人 id 直接读写」的真实越权；2 个函数判定为有风险/待收敛 —— `HandlingRecordService.delete`（中危·潜在，当前无路由不可达，已修边界）与 `RiskEventService.delete`（低危·存在性探针，未改）。**

### 阈值层级与审计覆盖结论

1. **阈值层级**：`risk_threshold` 主键 = `(user_id, scenario_id)`，**只有账号级一层**；**不存在**场景级 / 平台级默认阈值行，也没有任何「管理员为他人设阈值」的入口。因此任务书问的「用户级 vs 场景级 vs 平台级优先级」在本实现中**不成立**——解析只有两步：`thresholds[scenario_id]` 命中则用之，否则 `DEFAULT_MEDIUM/HIGH_THRESHOLD = 0.5/0.8`。
2. **审计覆盖（是否有遗漏写点）**：**完整**。全仓 `RiskThreshold(` 构造仅 1 处（`risk_threshold_service.py:95`），该路径在**值真正变化**时必写 `ThresholdAuditLog`（唯一不写的情形是「值未变化」的幂等早返回，此时也没有变更可审）。不存在「改了阈值没记审计」的旁路。
3. **审计日志能否被篡改/删除**：服务层**不能**（无 update/delete）；DB 层无保护（普通 UPDATE/DELETE 即可改）→ 属 schema 加固议题，见 §7-提案3。
4. **审计日志能否越权读取**：**不能**（`user_id == current_user.id` 硬过滤）；但反向问题是**没人能审计他人**（SUPER_ADMIN 也只看自己），且 `operator_id` 因「写入恒为本人」而**永远等于 `user_id`**——该列当前是**冗余列**（若未来引入代改阈值才需要）。记录，未改（删列属 schema 变更）。

---

## 4. 删除证据（零引用 grep）

> 命令均在仓库根执行；输出为改动**前**的实测结果。

**① `risk_event_service.py` 未使用导入**
```
$ grep -n "ROLE_ADMIN" backend/app/services/risk_event_service.py
43:    ROLE_ADMIN,                       # ← 仅出现在 import 列表，正文 0 引用
$ grep -n "\bAny\b" backend/app/services/risk_event_service.py
18: from typing import Any, Dict, Optional   # ← 仅导入行
$ grep -n "ROLE_ADMIN =" backend/app/services/constants.py
33: ROLE_ADMIN = ROLE_SUPER_ADMIN            # ← 别名，本文件用 ROLE_SUPER_ADMIN
```

**② 三处未使用 `logger`**
```
$ grep -n "logger" backend/app/services/risk_threshold_service.py
12: from app.utils.common import get_logger, row_to_dict
14: logger = get_logger("risk_threshold")          # ← 定义后全文 0 次使用
$ grep -n "logger" backend/app/services/threshold_audit_log_service.py
9:  from app.utils.common import get_logger, paginate, row_to_dict
11: logger = get_logger("threshold_audit_log")    # ← 同上
$ grep -n "logger" backend/app/services/handling_record_service.py
29: from app.utils.common import get_logger, paginate, row_to_dict, validate_enum
31: logger = get_logger("handling_record")        # ← 同上
（对照：risk_event_service.py 的 logger 在 :108 真被使用 → 保留）
```

**③ `threshold_audit_log_service._get` 零引用**
```
$ grep -n "_get" backend/app/services/threshold_audit_log_service.py
17:    def _get(self, log_id: int) -> ThresholdAuditLog:   # ← 全文件唯一命中（定义本身）
$ grep -rn "_get(" backend/app/api backend/app/services | grep threshold
（无输出）
```
另注：`_get` 用 `db.get()` **不带归属过滤**，而 `get()` 用的是带 `user_id` 过滤的 `select`；保留它反而是越权隐患，故删除而非保留。

**④ `HandlingRecordService` 零调用点（整文件 188 行，**保留并提案**）**
```
$ grep -rn "HandlingRecordService" backend --include=*.py
backend/app/services/__init__.py:22:    "HandlingRecordService": ("handling_record_service", "HandlingRecordService"),
backend/app/services/handling_record_service.py:34: class HandlingRecordService(ServiceBase):
backend/app/services/handling_record_service.py:93: # 与 RiskEventService.update_status 保持同一状态机口径（需求 5.2）：   ← 注释
$ grep -rn "handling_record\|handling-record" backend/tests frontend/src
（backend/tests：No matches；frontend/src 仅 4 处中文注释提到「处置记录」文案）
$ grep -rn "handling" backend/app/api
（无输出）
```
⇒ **无 API 路由、无 service 调用、无测试、前端无 API 封装**。唯一「引用」是 `services/__init__.py` 的惰性导出表（B7 写区）→ 未删文件，走 §7-提案1。

**⑤ `threshold_audit_log` 无第二写点（审计覆盖证明）**
```
$ grep -rn "RiskThreshold(\|ThresholdAuditLog(" backend/app --include=*.py
backend/app/models/risk_threshold.py:13: class RiskThreshold(Base):          ← 模型定义
backend/app/models/threshold_audit_log.py:13: class ThresholdAuditLog(Base): ← 模型定义
backend/app/services/risk_threshold_service.py:95:  threshold = RiskThreshold(   ← 唯一构造点
backend/app/services/risk_threshold_service.py:111: audit = ThresholdAuditLog(   ← 唯一构造点（紧随其后）
```

**⑥ `risk_view` 函数内 import（8 行）**
```
$ grep -n "^    from " backend/app/services/risk_view.py   （改前）
89:    from app.utils.common import row_to_dict
107:    from app.services.constants import (
（两处均为可上提的延迟 import；app.utils.common 的 import 段只有 stdlib + sqlalchemy，
 不 import app.*，无循环风险；上提后 import 实测通过，见 §6）
```

---

## 5. 函数清单（分区内每个函数/方法/常量一行）

### `backend/app/services/risk_view.py`（判级共享口径，7 个外部调用点：B1/B2/B3/B5）

| 位置 | 名称 | 算什么 / 数据从哪来 / 被谁调用 |
|---|---|---|
| 30 | `ThresholdPair`（类型别名） | `(medium, high)` 二元组；纯类型标注，被本文件 5 个函数使用 |
| 33 | `classify(risk_score, medium, high)` | **唯一判级实现**：`score>=high→HIGH`，`>=medium→MEDIUM`，否则 LOW（闭区间下界）。入参来自调用方（阈值来自 `risk_threshold` 行或兜底常量，分数来自 `RiskEvent.risk_score`）。被 `RiskEventService._calc_risk_level`、`inference_record_service:170` 调用 |
| 46 | `load_thresholds(db, user)` | 一次查出该账号**全部场景**的阈值 → `{scenario_id: (medium, high)}`；`user` 为 None 或无 id 时返回 `{}`（不查库）。被 B1 `dashboard_service:1290,1987`、B2 `report_service:429`、B3 `inference_record_service:165,821`、B5 `situation_snapshot_service:63,85,108,143`、本区 `risk_event_service:410,455` 调用 |
| 63 | `thresholds_for(thresholds, scenario_id)` | 取账号在该场景的阈值；**未配置 → 兜底常量 0.5/0.8**；`scenario_id` 为 None 也走兜底。被 B1:1058、B2:784、B3:169、本区 `risk_event_service:107` 调用 |
| 74 | `level_of(event, thresholds)` | 按**当前账号**阈值算单事件等级；`risk_score` 为 None（历史脏数据）→ 回退落库 `risk_level`，非法值 → LOW。支持 ORM 对象与 `Row`（只用 `getattr`）。被 B1:1070,1087,1300、B2:764、本区 `risk_event_service:423` 调用 |
| 87 | `view_of(event, thresholds)` | `row_to_dict(event)` + 覆盖 `risk_level` 为本人视角；**不改其它字段名**（前端 `types/security.ts` 依赖）。被 `view_events` 与 `risk_event_service:456` 调用 |
| 96 | `view_events(events, thresholds)` | 批量 `view_of`。被 `risk_event_service:436,444`、B5 `situation_snapshot_service:114` 调用 |
| 101 | `aggregate(events, thresholds)` | 按账号阈值聚合等级计数 + 按落库值聚合三态计数（`total/high/medium/low/pending/processing/resolved`）。被 B2 `report_service:505`、B5 `situation_snapshot_service:49` 调用 |

### `backend/app/services/risk_event_service.py`

| 位置 | 名称 | 算什么 / 数据从哪来 / 被谁调用 |
|---|---|---|
| 52 | `class RiskEventService` | 风险事件服务 |
| 55 | `_get(event_id)` | 主键取事件，无 → 404。被 get/update_status/add_comment/delete/set_hidden 调用 |
| 61 | `_require_event_access(current_user, event)` | **本区核心越权闸门**：SUPER_ADMIN→数据集须 platform；SCENARIO_ADMIN→场景须绑定且数据集 platform/company；其余（含 SCENARIO_USER 与未知角色）→ 须为事件归属人。被 5 个写/读入口调用 |
| 87 | `_calc_risk_level(risk_score, medium, high)` | 需求 5.4 判级，**委托** `risk_view.classify`（唯一调用点 `_build_risk_event`） |
| 94 | `_get_thresholds(user_id, scenario_id)` | 查 `risk_threshold` 单行；缺失 → `risk_view.thresholds_for({}, scenario_id)` 兜底 + `logger.warning`。仅 `_build_risk_event` 调用（与 `risk_view` 查询逻辑重复，见 §8-存疑4） |
| 115 | `_calc_fault_position(dataset_logical_id, input_features)` | 仅航母场景算甲板红点坐标：两机航向角 `(角%360)/360*1000`；缺值/非法/负值 → `(None, None)`。仅 `_build_risk_event` 调用 |
| 146 | `_build_description(...)` | 按场景（电力/网络/地质/航母）拼中文风险说明，含评分百分比；内嵌 `_pick`（别名回退，避免 `or` 吞掉 0）与两处 `try/except (TypeError, ValueError)`。仅 `_build_risk_event` 调用 |
| 266 | `create_from_inference(...)` | 公开生成入口：`require_login` + `risk_score` 必填校验 → `_build_risk_event`。被 B3 `inference_record_service:405` 调用 |
| 291 | `_build_risk_event(...)` | 组装 ORM（冗余字段拷自主表、`raw_features` 去标签列、状态恒 PENDING、`flush` 取 id）。仅 `create_from_inference` 调用 |
| 350 | `get_list(...)` | 列表：角色三分支过滤 + 状态/场景/隐藏过滤；传 `risk_level` 时**按查看者阈值重算后内存分页**。被 `risk_event_routes.py:46` 调用 |
| 447 | `get(...)` | 详情：`_get` + `_require_event_access` + `view_of`。被 `risk_event_routes.py:67` 调用 |
| 461 | `update_status(...)` | 状态流转：白名单校验 → 改状态 + 写 `HandlingRecord(UPDATE_STATUS)`。被 `risk_event_routes.py:83` 调用 |
| 500 | `add_comment(...)` | 追加处置说明（不改状态）；空串拒绝。被 `risk_event_routes.py:104` 调用（前端封装 `commentRiskEvent` 目前零调用，D-15） |
| 524 | `delete(...)` | 恒抛 400（需求 5.2 禁止真删）。被 `risk_event_routes.py:123` 调用 |
| 534 | `set_hidden(...)` | 软隐藏开关：写/清 `hidden_at`+`hidden_by_user_id`，权限同处置。被 `risk_event_routes.py:138,155` 调用 |

### `backend/app/services/handling_record_service.py`

| 位置 | 名称 | 算什么 / 数据从哪来 / 被谁调用 |
|---|---|---|
| 34 | `class HandlingRecordService` | 处置记录服务（**当前全仓零调用**） |
| 37 | `_get(record_id)` | 主键取记录，无 → 404。被 get/delete 调用 |
| 43 | `_can_access_event(current_user, event)` | 与风险事件同口径的**布尔版**边界判断（不抛异常）。被 create/get 经 `_can_access_record` 调用 |
| 60 | `_can_access_record(current_user, record)` | 先取父事件（`record.risk_event` 懒加载或 `db.get`）再判边界。被 get/delete 调用 |
| 68 | `create(...)` | 登记处置动作：边界校验 + `HANDLING_ACTIONS` 枚举 + `UPDATE_STATUS` 时白名单校验并同步改事件状态；**状态字段以事件真实值落库**（本次修复）。无调用方 |
| 122 | `get_list(...)` | 处置记录列表：角色三分支按父事件过滤 + 可选 `risk_event_id`。无调用方 |
| 157 | `get(...)` | 单条详情：`_get` + `_can_access_record`。无调用方 |
| 169 | `delete(...)` | SUPER_ADMIN 删除（本次补数据边界校验）；无留痕。无调用方 |

### `backend/app/services/risk_threshold_service.py`

| 位置 | 名称 | 算什么 / 数据从哪来 / 被谁调用 |
|---|---|---|
| 17 | `class RiskThresholdService` | 阈值服务 |
| 22 | `_get_for_user(user_id, scenario_id)` | 按业务主键取阈值行（可 None）。被 get_by_scenario/update 调用 |
| 30 | `get_list(current_user)` | 本人全部阈值行（join `Scenario` 过滤孤儿行）；非 SUPER_ADMIN 限绑定场景。被 `risk_threshold_routes.py:24` 调用 |
| 44 | `get_by_scenario(current_user, scenario_id)` | `require_scenario_access` + 只查本人行；未配置 → `data=None` + 提示文案。被 `risk_threshold_routes.py:56` 调用 |
| 56 | `update(...)` | `require_scenario_access` + `[0,1]` 与 `high>medium` 校验 + upsert + 值变化时写审计。被 `risk_threshold_routes.py:74` 调用 |

### `backend/app/services/threshold_audit_log_service.py`

| 位置 | 名称 | 算什么 / 数据从哪来 / 被谁调用 |
|---|---|---|
| 14 | `class ThresholdAuditLogService` | 阈值审计只读服务 |
| 20 | `get_list(...)` | 本人变更记录（`user_id=本人` 硬过滤；非 SUPER_ADMIN 再限绑定场景）。被 `risk_threshold_routes.py:36` 调用 |
| 40 | `get(...)` | 单条（`id + user_id=本人` 联合过滤）。无路由调用（前端 `riskThresholdApi` 无对应封装） |

### `backend/app/schemas/*.py` 与 `models/*.py`

| 位置 | 名称 | 说明 |
|---|---|---|
| `schemas/risk_event.py:10` | `RiskEventStatus` | `Literal["PENDING","PROCESSING","RESOLVED"]`（请求体校验；与 `constants.RISK_EVENT_STATUSES` 重复） |
| `schemas/risk_event.py:13` | `RiskEventHandle` | PUT `/{id}/handle` 请求体：`new_status` + `comment` |
| `schemas/risk_event.py:20` | `RiskEventComment` | POST `/{id}/comment` 请求体：`comment`（`min_length=1`） |
| `schemas/risk_threshold.py:9` | `_max_2_decimals(v)` | 两位小数校验（`round(v,2)!=v` 即拒）；被 `RiskThresholdUpdate` 的 field_validator 调用 |
| `schemas/risk_threshold.py:15` | `RiskThresholdUpdate` | PUT `/{scenario_id}` 请求体：两个 `[0,1]` 浮点 + 两位小数校验（**跨字段 `high>medium` 未在此校验**，由 service + DB CheckConstraint 兜底） |
| `models/risk_event.py:16` | `RiskEvent` | 19 列 + 6 relationship；唯一索引 `idx_re_user_scenario_status(created_by_user_id, scenario_id, status)`；`hidden_at/hidden_by_user_id` 为软隐藏 |
| `models/risk_threshold.py:13` | `RiskThreshold` | 复合主键 `(user_id, scenario_id)` + `chk_rt_threshold(high>medium)`；`Numeric(4,2)` |
| `models/handling_record.py:13` | `HandlingRecord` | 处置/审计行：`risk_event_id/handler_id/action/status_before/status_after/comment/created_at` |
| `models/threshold_audit_log.py:13` | `ThresholdAuditLog` | 阈值变更行：`user_id/scenario_id/operator_id/old_medium/new_medium/old_high/new_high/operated_at` |

---

## 6. 行为不变证明（自验原始输出）

```
$ cd backend && python -m py_compile app/services/risk_event_service.py app/services/risk_view.py \
    app/services/risk_threshold_service.py app/services/threshold_audit_log_service.py \
    app/services/handling_record_service.py app/schemas/risk_threshold.py app/schemas/risk_event.py \
    app/models/risk_event.py app/models/risk_threshold.py app/models/handling_record.py \
    app/models/threshold_audit_log.py
EXIT=0
```
```
$ cd backend && python -m py_compile app/services/risk_event_service.py app/services/risk_view.py \
    app/services/risk_threshold_service.py app/services/threshold_audit_log_service.py \
    app/services/handling_record_service.py app/schemas/risk_threshold.py app/schemas/risk_event.py
EXIT=0
```
```
$ cd backend && python -m py_compile app/services/risk_event_service.py app/services/risk_view.py \
    app/services/risk_threshold_service.py app/services/threshold_audit_log_service.py \
    app/services/handling_record_service.py app/schemas/risk_threshold.py app/schemas/risk_event.py
FINAL_PY_COMPILE_EXIT=0
```
> 说明：共跑 **3 次** `py_compile`（改动中途 / 全部改完 / 报告写完后复跑），**三次均 EXIT=0**，无任何输出。
> **未运行 pytest**（协议 §1.3 禁止，Lead 统一跑全量）。

额外自验（`py_compile` 只查语法，**不查 `NameError`**；本次删除 `typing` 导入时曾有 1 处 `Optional` 残留，已修）：
```
$ cd backend && python -c "import importlib; [importlib.import_module(m) for m in [
   'app.services.risk_view','app.services.risk_event_service','app.services.risk_threshold_service',
   'app.services.threshold_audit_log_service','app.services.handling_record_service',
   'app.schemas.risk_event','app.schemas.risk_threshold','app.models.risk_event',
   'app.models.risk_threshold','app.models.handling_record','app.models.threshold_audit_log']]"
OK app.services.risk_view
OK app.services.risk_event_service
OK app.services.risk_threshold_service
OK app.services.threshold_audit_log_service
OK app.services.handling_record_service
OK app.schemas.risk_event
OK app.schemas.risk_threshold
OK app.models.risk_event
OK app.models.risk_threshold
OK app.models.handling_record
OK app.models.threshold_audit_log
EXIT=0
```
> 只做 import，**不连数据库、不起服务**（协议 §1.3 允许的自验范围内）。

行为不变性论证：
1. `risk_view` 7 个公开函数签名与返回值结构未变（仅内部 import 位置与注解写法变化）→ B1/B2/B3/B5 调用点零改动。
2. `"platform"/"company"` → 常量替换为**同值**；`"SUPER_ADMIN"` → `ROLE_SUPER_ADMIN`（`constants.py:27` 值即 `"SUPER_ADMIN"`）。
3. `current_user.scenario_id` → `getattr(current_user, "scenario_id", None)`：真实 `AppUser` 有该属性 → 行为相同（仅对无该属性的替身对象更健壮，测试用 SimpleNamespace 时同值）。
4. HTTP 响应字段/状态码/文案：**除下述 2 处外零变化** ——
   - `HandlingRecordService.create`：非 `UPDATE_STATUS` 动作写入的 `status_before/status_after` 由「调用方值或 NULL」变为「事件当前状态」。**该方法当前零调用方**（§4-④），无运行时可见影响。
   - `HandlingRecordService.delete`：新增 403 分支，仅当「SUPER_ADMIN 且记录属非 platform 数据集」时触发。**该方法当前零调用方**（无路由）。
   - `RiskThresholdService.update` / `RiskEventService.*`：**零行为变化**。
5. 未改任何 Alembic 迁移、未改模型字段、未改已导出 schema 字段名、未新增依赖。

---

## 7. 跨区变更提案（**未实施**）

### 提案 1【残留·建议删除】`handling_record_service.py` 整文件 + `services/__init__.py` 惰性导出条目
- **零引用证据**：§4-④（无路由 / 无 service 调用 / 无测试 / 前端无封装）。
- **影响面**：删除 `backend/app/services/handling_record_service.py`（188 行）+ `backend/app/services/__init__.py:22` 的映射条目。
- **为什么必须一起改**：`services/__init__.py` 用惰性 `__getattr__` 映射导出，单独删文件会让 `services.HandlingRecordService` 变成 `ImportError`。
- **为什么非改不可 / 不改的替代方案**：**可以不改**。保留该文件的唯一成本是 188 行阅读噪声，**不影响运行**。故本代理**未动手**（`services/__init__.py` 属 B7 写区，§派发进度 D-29）。
- **附带议题（需 Lead 一并裁决）**：若认为「处置记录应当可读」，则本文件**不该删**，而应补 `GET /api/v1/handling-records` 路由 —— 这是**新功能**，超出本轮「行为保持型重构」范围。两条路互斥，请 Lead 择一。

### 提案 2【记录·本轮不做】DB 索引补齐（需新建 Alembic 迁移，属 X2/Lead 写区）
| 表 | 现有索引 | 建议 | 依据 |
|---|---|---|---|
| `risk_event` | `(created_by_user_id, scenario_id, status)` | 追加 `(hidden_at, occurred_at DESC)` 与 `(dataset_id)` | `get_list` 恒带 `hidden_at IS NULL` + `ORDER BY occurred_at DESC`；B1/B2 按 `dataset_id` 聚合 |
| `handling_record` | 仅 PK | 追加 `(risk_event_id)` | `get_list` 按父事件过滤/join |
| `threshold_audit_log` | 仅 PK | 追加 `(user_id, operated_at DESC)` | `get_list` 恒按 `user_id` 过滤 + `operated_at` 排序 |
- **风险**：新建迁移会改 DB schema；`risk_event` 当前 674 行，收益近似 0（与 D-32 同判）。

### 提案 3【记录·schema 加固】审计表不可篡改
`threshold_audit_log` / `handling_record` 在 DB 层可被任意 UPDATE/DELETE 改写，无触发器/权限约束。属安全加固议题（需迁移 + 运维配合），**记录**。

### 提案 4【重复定义·低价值】`RiskEventStatus` Literal 与 `constants.RISK_EVENT_STATUSES` 二份值域
- **位置**：`backend/app/schemas/risk_event.py:10`（本区）vs `backend/app/services/constants.py:273`（**B5 写区**）。
- **候选**：`constants.py` 增 `RiskEventStatusLiteral = Literal[...]` 由 schema 导入；或反过来在 schema 定义、constants 从它派生。
- **不改的替代方案**：保持两份 + 各自注释交叉引用（当前状态）。**风险**：值域漂移（新增状态时漏改一处，Pydantic 会在请求入口 422）。**本代理未动**（改它必须改 `constants.py`）。

### 提案 5【跨区·前端孤儿端点】`POST /risk-events/{id}/comment` 前端零调用
`RiskEventService.add_comment` 与路由都健在，但 `frontend/src/api/riskEventApi.ts:commentRiskEvent` **全库零调用**（F6a 已列入 D-15 清单）。**这是 D-15「前后端接口面收敛」的 B4b 侧证据**：请 Lead 在 B6a 反向核对后统一裁决（删前端封装 / 删后端端点 / 保留）。
另：`riskThresholdApi.getRiskThreshold`（→ `GET /risk-thresholds/{scenario_id}`）同样零调用（D-15 已列），后端 `RiskThresholdService.get_by_scenario` 因此也是孤儿读路径。

---

## 8. 未解决 / 存疑（如实列出）

1. **未及细查的项（时间/步数取舍）**：`risk_event_service._build_description` 的四套场景文案**逐字**业务正确性未与需求文档 §5.7.2 原文逐条比对（只核了「不虚构数据」「不用算法术语」「0 值不被 `or` 吞掉」三点）；`_calc_fault_position` 的坐标映射注释自称「占位，待与业务方确认正式映射」，**其业务正确性无法在本仓库内验证**。
2. **`RiskEventService.delete` 的存在性探针未修**：修它需要「不存在也返回 400」（把 404 语义吞掉）或「先查权限再查存在」，而 `get()` 的 404/403 差异本就暴露同一信息，单独修 `delete` 无收益且改变对外状态码 → **留给 Lead 裁决**（若要求绝对无探针，需 `get`/`update_status`/`add_comment`/`set_hidden`/`delete` **统一**改为「无权限与不存在同响应」）。
3. **`get_list`（96 行）未拆分**：两条分页路径（SQL 分页 / 阈值判级内存分页）可抽 `_list_by_viewer_level()`，但会改动返回拼装顺序（`items/total/page/page_size` 的构造位置），属可被 review 但收益有限的结构改动 → 未动。
4. **`_get_thresholds` 与 `risk_view.load_thresholds` 查询逻辑重复**：前者按 `(user_id, scenario_id)` 单行查 + 缺配 warning，后者一次查全部场景。可合并（两文件都在本区写作用域内），但合并会**丢失 warning 日志**或需要给 `risk_view` 加参数 → 未动，记录。
5. **状态机校验逻辑双写**：`RiskEventService.update_status` 与 `HandlingRecordService.create` 各写一遍「取白名单 + 比对 + 同一错误文案」。抽取 `_assert_status_transition(event, new_status)` 到 `risk_view` 或 `base` 会更干净，但 `base.py` 属 B5 写区，且 `HandlingRecordService` 零调用 → 未动。
6. **`schemas/risk_threshold.py` 未做跨字段 `high > medium` 校验**：非法组合会走到 service 才 400（而非 422）。属**有意分层**（service + DB `chk_rt_threshold` 双兜底），未改；若要求请求期拦截需加 `model_validator`（会改变错误码 400→422，属对外行为变化）。
7. **阈值「场景级/平台级」缺层**：`risk_view` 的账号级口径是**明确的设计决定**（模块 docstring 写明「用户明确要求」），但需求 §5.4.1 是否要求「未配置时用场景默认值」**无法在本仓库内判定**（`constants.py:367-370` 的注释只说「正式阈值应通过 risk_threshold 表配置」）。若需求确有此层，则属**功能缺口**而非 bug，需产品确认。
8. **并发**：`RiskThresholdService.update` 的 upsert 是「先查后插/改」，**无唯一键冲突重试**；并发首配同一 `(user_id, scenario_id)` 时，后者会因 PK 冲突抛 `IntegrityError` → `@service_call` 转 500。当前场景下（单用户点「保存」）不可达，记录。
9. **`risk_view.aggregate` 的 `total_events` 与三态计数之和可能不等**：若 `status` 落在值域外，`total` 计入而三态都不计。与 D7 同源（脏数据不可达），未改。

---

## 9. `git status --short`（本分区相关行）

```
 M backend/app/services/risk_event_service.py
 M backend/app/services/handling_record_service.py
 M backend/app/services/risk_view.py
 M backend/app/services/risk_threshold_service.py
 M backend/app/services/threshold_audit_log_service.py
 M backend/app/schemas/risk_event.py
 M backend/app/schemas/risk_threshold.py
?? docs/全项目代码审查/          （本报告 B4b.md 所在目录，其他代理同时在写）
```
- `models/risk_event.py` / `models/risk_threshold.py` / `models/handling_record.py` / `models/threshold_audit_log.py` **不在 `git status` 中 ⇒ 未改**（硬约束遵守）。
- `backend/alembic/**` **不在 `git status` 中 ⇒ 未改**。
- B4a 的文件（`services/explanation_service.py`、`schemas/explanation*.py`）虽在全局 `git status` 中显示为 `M`，但那是 **B4a 自己改的**；本代理的 `git diff` 中**不含**这些文件（已用 `git diff -- <本区 6 文件>` 单独核对）。
- 工作树里其余 ~85 个 `M` 文件来自其他并行代理，非本代理所改。

---

## 10. 一句话结论

**越权核对表 17 个函数：0 个真实越权，2 个有风险（`HandlingRecordService.delete` 中危·当前无路由不可达·已补边界；`RiskEventService.delete` 低危·存在性探针·未改）；阈值审计写点覆盖完整（唯一写路径必写审计），审计日志服务层不可篡改、不可越权读取，但**任何角色都看不到他人的阈值变更**且 `operator_id` 恒等于 `user_id`（冗余列）；状态机经白名单真校验，「待处置→已处置」是需求允许的合法直达（前端只给线性路径属 F5-D6 功能缺口）；`risk_view` 判级口径唯一、只有「账号级阈值 → 兜底常量 0.5/0.8」两步、无场景级/平台级层、无 None 导致全判 HIGH/LOW 的风险；`py_compile` 与 11 模块 import 均 EXIT=0；跨区提案 5 条（1 条建议删死模块，其余为记录型）。**

---

我未修改任何分区外文件。
