# B4a · 解释服务与解释契约（后端）

> 分区：`backend/app/services/explanation_service.py`、`backend/app/schemas/explanation_contract.py`、
> `backend/app/schemas/explanation.py`。
> 协议基线：`docs/全项目代码审查/审查协议.md`（已完整阅读）。
> 本报告不含任何对分区外文件的修改；所有跨区事项见 §7「跨区变更提案」。

---

## 1. 分区与文件清单

| 文件 | 改前 | 改后 | 差 | 说明 |
| --- | ---: | ---: | ---: | --- |
| `backend/app/services/explanation_service.py` | 650 | 721 | +71 | 主重构对象；新增 3 个纯函数、1 组常量、兜底加固 |
| `backend/app/schemas/explanation_contract.py` | 268 | 292 | +24 | 新增 SSE/受众契约常量，抽出 2 个归一化子函数 |
| `backend/app/schemas/explanation.py` | 14 | 14 | 0 | 仅现代化类型写法（`typing.Dict/List/Optional` → PEP 585/604） |

行数用 `git show HEAD:<file>` 与工作区逐字节统计（`\n` 计数），非 `Measure-Object -Line`（后者不计空行）。

**与简报的差异**：简报称 `explanation_service.py` 为 575 行，实测 **650 行**（HEAD 版本）。
按 650 行执行，未遗漏尾部函数。

---

## 2. 改动摘要

### 2.1 删除（每项均有零引用证据，见 §4）
| # | 删除项 | 位置 | 理由 |
| --- | --- | --- | --- |
| D1 | `from app.utils.common import ... row_to_dict` 中的 `row_to_dict` | 服务 L35 | 全文件零使用（`get_logger` 保留） |
| D2 | `def public_explanation(...)`（4 行） | 服务 L350-352 | 全仓库零调用，且只是 `explanation_for_role(..., "SCENARIO_USER")` 的一层包装 |
| D3 | `def _finite_number(...)`（7 行） | 服务 L136-141 | 与契约层 `finite_number` 逐字重复；改为导入契约实现，消除双份口径 |
| D4 | `def _availability(reason)`（4 行） | 服务 L144-145 | 无意义间接层，唯一实现体是 `return unavailable(reason)`；11 处调用点直接改用 `unavailable` |
| D5 | `def _raw_value(sample, name)`（3 行） | 服务 L148-149 | 唯一调用点即 `sample.get(name)`，已内联 |
| D6 | `build_unified_explanation` 内联的「算法码 → 载荷」字典字面量（14 行） | 服务 L297-309 | 每次调用都会**急切构造全部 6 个分支**再 `.get()` 取一个；改为 `_algorithm_specific()` 的 if 链，行为逐字等价 |
| D7 | `fallback_markdown` 中未使用的局部变量 `prediction` | 服务 L356（改前行号） | 赋值后从未读取 |
| D8 | `normalize_explanation` 中 `finite_number(...)` 对同一字段的**重复调用**（每字段 2 次 → 1 次） | 契约层 `normalize_explanation` 内（改前 L168-195） | 纯函数重复求值；抽 `_normalize_model_quality` 时顺带消除 |

### 2.2 合并 / 抽象
| # | 改动 | 收益 |
| --- | --- | --- |
| M1 | 抽出 `_resolve_risk_probability(result, prediction, is_prediction_risk)` | `build_unified_explanation` 内联的 15 行三级兜底逻辑独立可测，语义（含 `class_distribution` 覆盖 `probability` 的历史口径）有 docstring 固定 |
| M2 | 抽出 `_algorithm_specific(algorithm_code, result, views)` | 同上，6 个算法的专属载荷集中一处 |
| M3 | 抽出 `_fallback_events(facts)` | `stream_explanation` 两条降级路径（未配置 AI / AI 失败）原本各自重复 3 行「切片 + done」，合并为单一出口，保证两条路径的终态**必然一致** |
| M4 | 契约层抽出 `_normalize_model_quality` / `_normalize_algorithm_details` | `normalize_explanation` 由 86 行降到 43 行，两个子块各自内聚 |
| M5 | `ADMIN_ROLES = EXPLANATION_ROLES[1:]` | 让原本**零引用**的 `EXPLANATION_ROLES` 成为唯一事实源；`explanation_for_role` 不再硬编码 `("SUPER_ADMIN","SCENARIO_ADMIN")` 字面量 |

### 2.3 新增常量（消除魔法值）
| 常量 | 值 | 原魔法值位置 |
| --- | --- | --- |
| `SOURCE_AI` / `SOURCE_FALLBACK` | `"ai"` / `"fallback"` | `stream_explanation` 的 `done.source` 字面量 ×2 |
| `TOP_FEATURE_LIMIT` | 10 | `_top_features` 的 `normalized[:10]` |
| `DEFAULT_RISK_THRESHOLD` | 0.5 | `build_unified_explanation` 的形参默认值与置信度兜底 `0.5` |
| `CONFIDENCE_HIGH_GAP` / `CONFIDENCE_MEDIUM_GAP` | 0.25 / 0.1 | 置信度分档的嵌套三元表达式 |
| `STREAM_CHUNK_SIZE` | 24 | `_chunk_text(size: int = 24)` |
| `EXPLANATION_EVENTS`（契约） | `("start","reasoning","delta","error","done")` | 原先**只存在于前后端代码里**的隐式词表 |
| `EXPLANATION_SOURCES`（契约） | `("ai","fallback")` | 原先只存在于 `inference_record_service.py:891` 的字面量集合 |
| `PUBLIC_TOP_FEATURE_LIMIT`（契约） | 3 | `explanation_for_role` 与 `fallback_markdown` 两处硬编码 `3` |

### 2.4 修的 bug
| # | 级别 | 问题 | 修复 |
| --- | --- | --- | --- |
| B1 | **高** | `fallback_markdown` 对**未经归一化的客户端载荷**会抛异常，导致 SSE 流在没有 `done` 事件的情况下中断（前端永远停在「正在生成」，且拿不到兜底正文）。已复现 4 条崩溃向量，见 §6.3 | 全部字段先判型再取值：`finite_number()` 取概率、`isinstance` 守卫 `top_features` / `conflict` / `scenario` / `risk_types` / `recommended_actions` |
| B2 | **高** | `get_scenario_config` 的「未登记场景」分支**不带** `configuration_available`，而下游 `build_unified_explanation` 用 `config.get("configuration_available", True)` 兜底 → **配置文件缺失/损坏时被报告为「配置可用」** | 该分支显式返回 `configuration_available: False` + `configuration_errors` |
| B3 | 中 | `stream_explanation` 的降级日志只记 `reason_code`，**不记异常类型也不打堆栈**，编程错误被伪装成 provider 故障且无迹可查 | 加 `error=%s`（`type(exc).__name__`）与 `exc_info=(reason_code == "provider_error")`：只有归不了类的错误才打堆栈 |
| B4 | 中 | `_openai_stream` 只靠 GC 关闭上游 HTTP 流；客户端断连时本生成器被 `GeneratorExit` 终止，与 AI 网关的连接何时断开不确定 | 改用 `with client.chat.completions.create(...) as stream:`，退出（含提前终止）时确定性关闭。已实测验证，见 §6.4 |

---

## 3. 逐项审查结论（A / B / C / D / E）

### A. 弃用（deprecated）
| 检查项 | 命令 | 结论 |
| --- | --- | --- |
| `datetime.utcnow()` | `Select-String -Path <本分区 3 文件> -Pattern "utcnow"` | **无**（本分区不处理时间） |
| `asyncio.get_event_loop()` | 同上 `-Pattern "get_event_loop"` | **无**（本分区是同步生成器，不碰事件循环） |
| 旧式 `typing.List/Dict/Optional` | 同上 `-Pattern "typing\.(List\|Dict\|Optional)"` | **`explanation.py` 原有 6 处，已全部改为 `dict[str, Any]` / `list[str]` / `int \| None`，`typing` 仅保留 `Any`**；另两文件原本就是 PEP 585 写法 |
| `pydantic` V1 风格 | 人工阅读 3 文件 | **无**（`Field(default_factory=...)`、`BaseModel` 均为 V2 写法；环境实测 pydantic 2.13.4） |
| `@validator` / `class Config` | 人工阅读 | **无** |

**A 项结论：`explanation.py` 的类型写法已现代化，其余无弃用问题。**

### B. 残留 / 死代码
| 检查项 | 命令 | 结论 |
| --- | --- | --- |
| `print` | `Select-String -Pattern "print\("` | **无** |
| `TODO/FIXME/XXX` | `Select-String -Pattern "TODO\|FIXME\|XXX"` | **无** |
| 注释掉的代码块 | 人工通读 721 行 | **无**（仅有说明性中文注释） |
| 未使用 import | 逐名 grep | 删除 `row_to_dict`（D1）；其余全部在用（`EXPLANATION_CONTRACT_VERSION`→落库版本、`availability`→model_quality 标记、`finite_number`→数值归一、`normalize_explanation`→出口、`unavailable`→降级标记、`PUBLIC_TOP_FEATURE_LIMIT`→模板、`EXPLANATION_SOURCES`→source 域） |
| 零引用私有函数 | `git grep -n "public_explanation" HEAD -- backend` | `public_explanation` 仅自身定义、无调用（D2，证据见 §4） |
| 零引用常量 | `git grep -n "EXPLANATION_ROLES" HEAD -- backend` | 仅自身定义 → 改前是死常量；**保留并使其成为事实源**（M5） |
| 重复定义 | 全后端对比 | ①`finite_number` vs `_finite_number` → 已统一（D3）；②`ALGORITHM_CODES` 在 `services/constants.py:220` 与 `explanation_contract.py` 各一份 → **未动**，因 `tests/test_explanation_contract.py:34` 直接引用契约那份（见 §8 存疑 S2） |
| 死分支（恒真/恒假） | 人工核对上游实际返回值 | 逐支核对，**未发现恒真/恒假分支**：①`_normalize_algorithm_details`（契约 L190-203）的 `if isinstance(marker, dict)` / `else` 两支均可达 —— Java 结果带/不带 `availability` 标记两种情形都存在；②`_algorithm_specific`（服务 L270）中「有 views/feature_evidence」与「返回 `unavailable(原因)`」两支均可达；③`_resolve_risk_probability`（服务 L241）的三级兜底中 `class_distribution` 覆盖分支可达（`risk_probability` 缺失而分布存在时）。`get_scenario_config` 的三个分支（正常/未登记/校验失败）均有真实触发路径 |
| 未使用字段 | `git grep -n "model_version_id"` | `ExplanationStreamRequest.model_version_id` 被前端 `ExplanationStreamParams` 发送，但 `explanation_routes` 从未读取 → **保留**（删字段会改已导出的 schema，见 §8 存疑 S1） |

**B 项结论：删除 8 项残留（D1-D8），另有 2 项按「不确定就不删」原则保留并记录。**

### C. 复杂度（over-complex）
| 指标 | 阈值 | 改前 | 改后 |
| --- | --- | --- | --- |
| 函数 > 80 行 | 协议 §3.C | `build_unified_explanation` **111 行**、`normalize_explanation` **86 行** | `build_unified_explanation` **93 行**（仍超阈值，见下）、`normalize_explanation` **43 行** ✅ |
| 嵌套 > 3 层 | 协议 §3.C | `_normalize_feature_items` 最深层 4 层（for → if → for → if） | 未改动（该函数是 53 行的扁平归一化循环，拆分会破坏「单遍扫描」的语义，见 §8 存疑 S3） |
| 复杂三元链 | 协议 §3.C | 置信度分档：`"高" if gap >= 0.25 else "中" if gap >= 0.1 else "低"` | 改为 `if/elif/else`，阈值提常量 ✅ |
| 魔法数字/字符串 | 协议 §3.C | 10 处（`[:10]`、`[:3]`、`0.5`、`0.25`、`0.1`、`24`、`"ai"`、`"fallback"`、`"length"`、6 个算法码字面量） | 前 8 处已提常量；`"length"` 是 OpenAI SDK 的协议值，保留字面量合理；算法码字面量集中在 `_algorithm_specific` 一处分派，可接受 |
| 重复的 prompt 组装 | 协议 §3.C | `build_prompt` 是唯一组装点（`_EXPLANATION_SYSTEM_BASE` + 可选 `_EXPLANATION_SYSTEM_USER_SUFFIX` + `json.dumps(facts)`） | **无重复** ✅ |

`build_unified_explanation` 剩余 93 行的构成：签名+docstring 约 10 行，其余几乎全是一个**契约形状的返回字典字面量**（每个字段一行、逐字段标注 available/reason）。
再拆只能拆「构造字典」这一步，收益是行数达标、代价是引入一个 10+ 形参的纯转发函数 —— **判定为不值得拆**，已在 §8 记录。
两处抽取（M1/M2）已把其中真正的**逻辑**（概率兜底、算法分派）移出。

**C 项结论：超长函数 2 → 1，且剩余 1 个是数据字面量而非控制流。**

### D. 正确性隐患
| # | 检查项 | 结论 | 证据 |
| --- | --- | --- | --- |
| D-a | **IDOR**：用他人 `record_id` 生成/读取解释 | **已正确防护**。路由在 `inference_record_id` 存在时**完全忽略客户端 `model_result`**，改由 `InferenceRecordService(db).get_explanation_source(current_user, record_id)` 服务端取事实，其内部调 `_require_record_access`（`inference_record_service.py:755-770`）执行 SUPER_ADMIN / SCENARIO_ADMIN / SCENARIO_USER 三级规则；落库前 `save_generated_explanation`（同文件 L872）**再次**校验访问权 | 读 `explanation_routes.py:32-75`、`inference_record_service.py:755-770,838-900`（分区外，只读） |
| D-b | **SSE 断连泄漏** | 客户端断连 → Starlette 停止迭代同步生成器 → `GeneratorExit`（`BaseException`）在 `yield` 处抛出，**不会**被 `except Exception` 误判为 provider 故障去发降级正文（正确）；但上游 OpenAI 流原先只能等 GC 关闭 → **已修**（B4，`with` 上下文管理器） | §6.4 实测：提前 `gen.close()` 后 mock 服务端立即 `ConnectionResetError`，证明连接被确定性关闭 |
| D-c | **超时** | 存在且可配：`AI_REQUEST_TIMEOUT_SECONDS`（默认 60s，下限 5s）传给 `OpenAI(timeout=...)`；`AI_CONNECTIVITY_TIMEOUT_SECONDS`（默认 30s，下限 3s）用于连通性自检。**无**应用级「总时长」上限，但底层 HTTP 超时已能保证不无限挂起 | 服务 L57/L60/L589 |
| D-d | **堆栈泄漏给客户端** | **无泄漏**。`@service_call`（`services/base.py`）对 `Exception` 一律返回 `fail(500, "服务器内部错误")`，`SQLAlchemyError` 返回 500「数据服务暂时不可用」，仅 `logger.exception` 记服务端；`_classify_ai_error` 返回的是**固定非敏感文案**，且 `tests/test_ai_service.py:57-61` 专门断言不回显异常内容 | 读 `services/base.py`（分区外，只读） |
| D-e | **Java / AI 降级是否吞掉真实错误** | AI 侧：`except Exception` 确实宽，但**不是静默** —— 现在会记 `reason_code` + 异常类名 + （无法归类时）完整堆栈，并向前端下发 `error{reason_code}`。真实风险是「编程错误被归类为 `provider_error`」，已通过 `exc_info` 条件化缓解。Java 侧：本文件不直连 Java，事实由调用方传入 | 服务 L703-716 |
| D-f | **除零 / 空集合 / None 访问** | 逐处核对：`_chunk_text` 的 `range(0, len(v), size)` 在空串上安全；`_top_features` 空列表返回 `[]`；`_views` 非 list 返回 `[]`；`conflict_labels` 用集合推导，空视图 → 空集合；`_resolve_risk_probability` 的 `next(..., default)` 有默认值；**未发现除零**（本分区无除法，只有 `* 100` 与 `abs()`）。**唯一发现的 None/类型崩溃点即 B1**，已修 | §6.3 前后对比 |
| D-g | **过宽 except** | 2 处 `except Exception`：①`stream_explanation`（**必须**宽 —— 任何 AI 侧异常都要降级而不是让流断掉，已加类型+堆栈日志）；②`AISettingService.test_connection`（见 §8 存疑 S4） | 服务 L703、L566 附近 |
| D-h | **`@service_call` 把真实错误伪装成 500** | 设计如此且返回体不含细节；`ServiceError` 的业务码会被保留。**未发现**业务错误被误吞 | 读 `services/base.py` |
| D-i | **全局可变状态 / 无锁缓存** | 本分区**无模块级可变状态**（常量全是 tuple/str/float/int；`logger` 是线程安全的）。`_configs()` **每次调用都重新读盘+解析+展开+校验**，无缓存 → 是**性能**问题而非竞态问题（§8 存疑 S5：**故意不加 `lru_cache`**，因为返回的 dict 会被 `_normalize_algorithm_details` 等就地修改，共享缓存会造成跨请求数据污染） | 服务 L106-117 |
| D-j | **`get_scenario_config` 的可用性谎报** | **B2，已修**。改前：配置文件缺失/损坏 → `_configs()` 返回 `{}` → `config is None` 分支不带 `configuration_available` → 下游 `config.get(..., True)` 得到 `True`，把「没有配置」当成「配置齐全」，把空的风险类型与空建议当事实喂给 AI | §6.2 哈希差异 |

**D 项结论：IDOR 与超时/断连防护结论见上；发现并修复 2 个高/中级正确性缺陷（B1、B2），另修复 2 个可观测性缺陷（B3、B4）。**

### E. 硬约束
| 约束 | 结论 |
| --- | --- |
| 不改 `backend/alembic/**` | **未触碰** |
| 不删 `models/**` 表字段 | **未触碰**（本分区不 import models 表定义做修改） |
| 不改 `schemas/**` 已导出字段名 | **未改任何已有字段名**。契约层只**新增** `ADMIN_ROLES` / `EXPLANATION_EVENTS` / `EXPLANATION_SOURCES` / `PUBLIC_TOP_FEATURE_LIMIT` 四个常量（非 schema 字段，不进 JSON）；`ExplanationStreamRequest` 字段名与类型全部保持，仅内部类型注解写法现代化（`Dict[str,Any]` → `dict[str,Any]`，JSON Schema 输出完全一致） |
| 不改 Java 算法逻辑 | **未触碰** `backend/java/**` |
| 写作用域 | 仅上述 3 文件 + 本报告 |
| 不新建文件/目录（报告除外） | 遵守 |
| 不跑 pytest / build / uvicorn / git 写操作 | 遵守（仅 `py_compile` + 只读 `git show/grep/status/diff`） |

**E 项结论：全部硬约束满足。**

---

## 4. 删除证据

### 4.1 `public_explanation` / `_finite_number` / `_availability` / `_raw_value`（D2-D5）

**(a) 三个私有函数的引用范围**——用词界匹配排除同名子串干扰：
```
$ git grep -l -E "\b_raw_value\(|\b_finite_number\(|\b_availability\(" HEAD -- backend
HEAD:backend/app/services/explanation_service.py
```
→ 改前全后端**只有 `explanation_service.py` 一个文件**引用它们（`\b` 词界 + 紧跟 `(` 调用形式）。
对照组：若去掉词界，会命中 `dashboard_service.py` 的 `_raw_values(`、`model_evaluation_service.py` 等处的
`quality_availability`、`_availability_...` 等同名子串 —— **均为无关命中**，特此说明，避免误读为「有外部引用」。
三个函数都是文件私有，删除安全。

**(b) `public_explanation` 是零调用死函数**：
```
$ git grep -n "public_explanation" HEAD -- backend
HEAD:backend/app/services/explanation_service.py:350:def public_explanation(explanation: dict[str, Any] | None) -> dict[str, Any]:
```
→ 全仓库**仅此一行**（即定义本身），零调用点。函数体为：
```
350: def public_explanation(explanation: dict[str, Any] | None) -> dict[str, Any]:
351:     """Return the ordinary-user view while retaining the common contract."""
352:     return explanation_for_role(explanation, "SCENARIO_USER")
```
即 `explanation_for_role(..., "SCENARIO_USER")` 的一层纯转发，调用方直接用它即可。删除安全。

**(c) 完整引用清单（改前）**——所有命中都在本文件内：
```
$ git grep -n -E "_finite_number|_availability|_raw_value" HEAD -- backend/app/services/explanation_service.py
（该文件内 L136 定义 _finite_number、L144 定义 _availability、L148 定义 _raw_value，
  L166-184 / L251-267 / L297-309 / L320 / L330-331 为文件内调用点；L350 为 public_explanation 定义）
```

删除后工作区复搜同名（应只剩无关子串命中）：
```
$ git grep -l -E "\b_raw_value\(|\b_finite_number\(|\b_availability\(" -- backend
（空）
$ git grep -l -E "_finite_number|_availability|_raw_value" -- backend
HEAD:backend/app/services/dashboard_service.py          ← 仅 _raw_values（不同名）
HEAD:backend/app/services/model_evaluation_service.py   ← 仅 quality_availability（不同名）
（其余同前，均为子串误匹配）
```

### 4.2 `row_to_dict` 未使用 import（D1）
```
$ git grep -n "row_to_dict" HEAD -- backend
HEAD:backend/app/services/explanation_service.py:35:from app.utils.common import get_logger, row_to_dict
   ← 本文件唯一一处，之后 650 行内无任何 row_to_dict 调用
HEAD:backend/app/api/v1/endpoints/auth_routes.py:25,31   ← 其他文件，均真实使用
HEAD:backend/app/services/algorithm_service.py:21,43,52
... （其余文件均 import 且有调用，不逐一列举）
```
→ 本文件内 `row_to_dict` 导入后零使用，删除。`get_logger` 保留（L39 在用）。

### 4.3 `EXPLANATION_ROLES` 改前零引用（M5 的依据）
```
$ git grep -n "EXPLANATION_ROLES" HEAD -- backend
HEAD:backend/app/schemas/explanation_contract.py:15:EXPLANATION_ROLES = ("SCENARIO_USER", "SCENARIO_ADMIN", "SUPER_ADMIN")
```
→ 改前只有定义、零引用（`explanation_for_role` 自己硬编码了 `("SUPER_ADMIN","SCENARIO_ADMIN")`）。
**未删除**，而是让 `ADMIN_ROLES = EXPLANATION_ROLES[1:]` 由它派生，使其成为单一事实源。

---

## 5. 函数清单

### 5.1 `backend/app/services/explanation_service.py`

#### 模块级常量 / 对象
| 名称 | 行 | 算什么 / 数据从哪来 | 被谁调用 |
| --- | --- | --- | --- |
| `logger` | 39 | `get_logger("explanation")` | 本文件全部日志 |
| `CONFIG_PATH` | 40 | `app/data/scenario_configs.json` 绝对路径 | `_configs()` 读盘；`tests/test_scenario_config.py:10` 直接引用 |
| `AI_REQUEST_TIMEOUT_SECONDS` | 57 | 环境变量 `AI_EXPLANATION_TIMEOUT_SECONDS`，默认 60.0，下限 5.0 | `_openai_stream` → `OpenAI(timeout=...)` |
| `AI_CONNECTIVITY_TIMEOUT_SECONDS` | 60 | 默认 30.0，下限 3.0 | `AISettingService.test_connection` |
| `AI_MAX_OUTPUT_TOKENS` | 65 | 默认 0 = 不下发 `max_tokens`（把预算留给服务端） | `_openai_stream` |
| `EXPLANATION_PROMPT_VERSION` | 68 | `"1.0"`，提示词版本 | `inference_record_service.py:885` 落库（**分区外，勿删**） |
| `SOURCE_AI, SOURCE_FALLBACK` | 71 | 解包契约 `EXPLANATION_SOURCES` → `"ai"`/`"fallback"` | `stream_explanation` 的两处 `done.source` |
| `TOP_FEATURE_LIMIT` | 74 | 10，喂 AI / 展示的特征条数上限 | `_top_features` |
| `DEFAULT_RISK_THRESHOLD` | 76 | 0.5，概率缺失时估置信度的中性值 | `build_unified_explanation` 形参默认值 + 置信度兜底 |
| `CONFIDENCE_HIGH_GAP` / `CONFIDENCE_MEDIUM_GAP` | 78 / 79 | 0.25 / 0.1，`\|p − 阈值\|` 分档 | `build_unified_explanation` |
| `STREAM_CHUNK_SIZE` | 81 | 24，SSE 切片字符数 | `_chunk_text` 默认值（**分区外 `model_evaluation_service.py:33` 也调 `_chunk_text`**） |
| `_EXPLANATION_SYSTEM_BASE` | 83 | system 提示词基础段：只许用给定事实、不许改预测/概率、固定五段输出 | `build_prompt` |
| `_EXPLANATION_SYSTEM_USER_SUFFIX` | 93 | 普通用户追加约束：不得提算法内部细节与原始快照 | `build_prompt`（audience 为 user 时） |

#### 函数 / 类
| 名称 | 行 | 算什么 / 数据从哪来 | 被谁调用 |
| --- | --- | --- | --- |
| `_env_float(name, default, minimum)` | 43 | 读环境变量转 float 并夹下限；非法值回默认 | 模块级两次（L57/L60） |
| `_env_int(name, default, minimum)` | 50 | 同上，int 版 | 模块级一次（L65） |
| `class AIOutputTruncated(RuntimeError)` | 99 | 「模型在自身长度上限处停下、正文没写完」的信号异常 | 抛：`_openai_stream` L618；识别：`_classify_ai_error` L623；`tests/test_ai_service.py` |
| `_configs()` | 106 | 读 `CONFIG_PATH` → `json.loads` → `expand_scenario_feature_catalog` 展开 → `validate_scenario_configs` 校验 → `{code: config}`；异常时返回 `{}` 并 `logger.exception` | 仅 `get_scenario_config` |
| `get_scenario_config(code)` | 120 | 取单场景配置；**未登记/加载失败** → 降级 dict（现含 `configuration_available: False`）；**校验不通过** → 降级 dict + `False`；正常 → 原配置 + `True` | `scenario_routes.py:76`、`model_evaluation_service.py:85`、`inference_record_service.py:853`、`build_unified_explanation` L328、`tests/test_scenario_config.py` |
| `_normalize_feature_items(source, sample, ...)` | 156 | 把 Java 的 `top_features` / `feature_evidence` 统一成契约形状：名字/显示名、`raw_value` 回填、`contribution` 符号归一（`signed_contribution` 优先）、`direction` 文案、`supports_predicted` | `build_unified_explanation` |
| `_top_features(result, sample)` | 211 | 从 Java 结果里挑「存在正向贡献」的特征，取前 `TOP_FEATURE_LIMIT` 个；无正向贡献则 `[]` | `build_unified_explanation` |
| `_views(result)` | 236 | 安全取 `result["views"]`，非 list 返回 `[]` | `build_unified_explanation` |
| `_resolve_risk_probability(result, prediction, is_prediction_risk)` | 241 | **新增**。风险概率三级取值：`risk_probability` → 仅当预测为风险类时 `probability` → `class_distribution` 中该类概率**覆盖**前者（历史口径） | `build_unified_explanation` |
| `_algorithm_specific(algorithm_code, result, views)` | 270 | **新增**。按 A2WNB/MAWNB/EMAWNB/CAVWNB/PMWNB/DIWNB 分派专属载荷；数据缺失返回 `unavailable(原因)`，未知算法返回兜底文案 | `build_unified_explanation` |
| `build_unified_explanation(*, scenario_code, sample, model_result, algorithm_code, is_prediction_risk, model_metrics=None, risk_threshold=DEFAULT_RISK_THRESHOLD)` | 303 | **核心归一化**：Java 原始输出 → 契约 explanation。算出 prediction / risk_probability / 视图一致性 `conflict` / 置信度分档 / `top_features` / `algorithm_details` / `model_quality` / `input_snapshot`，最后交 `normalize_explanation` 固定形状 | `inference_record_service.py:333`（分区外） |
| `fallback_markdown(explanation)` | 398 | 规则模板正文（AI 不可用时的兜底，必须永远能出结果）：研判结论 / 主要依据 / 场景分析 / 风险规避建议 / 注意事项；**已全字段判型加固** | `_fallback_events` |
| `_fernet()` | 456 | 由 `AI_SETTINGS_ENCRYPTION_KEY`（缺失则退回 `AUTH_SESSION_PEPPER`）经 SHA256 派生 Fernet | `AISettingService`、`_openai_stream`、`tests/test_ai_service.py`、`tests/test_security_boundaries.py` |
| `_mask_key(value)` | 466 | API key 打码（`>8` 字符取前 4 后 4，否则全星号） | `AISettingService.get` |
| `class AISettingService(ServiceBase)` | 472 | AI 设置服务（当前用户维度） | `ai_setting_routes.py:20/29/37` |
| `AISettingService.get(current_user)` | 474 | 返回当前用户 AI 配置（key 打码 + provider 名）；未配置返回 `{configured: False}` | 同上 |
| `AISettingService.update(current_user, payload)` | 491 | 加密保存 base_url/model/key/enabled | 同上 |
| `AISettingService.test_connection(current_user)` | 530 | 用 `max_tokens=1` 发一次最小请求做连通性自检 | 同上 |
| `_openai_stream(setting, messages)` | 580 | **真流式**：解密 key → `OpenAI(...)` → `stream=True`；逐块产出 `("reasoning"\|"content", 文本)`；`finish_reason=="length"` 时抛 `AIOutputTruncated`。现用 `with` 管理上游流 | `stream_explanation`；`tests/test_ai_service.py:75`；**`model_evaluation_service.py:34` 也 import `_classify_ai_error`** |
| `_classify_ai_error(exc)` | 621 | 异常 → `(reason_code, 非敏感中文文案)`，覆盖截断/超时/限流/认证/模型不存在/连接失败 | `stream_explanation`、`AISettingService.test_connection`、`model_evaluation_service.py:432`（分区外） |
| `build_prompt(facts, audience)` | 638 | 组装 messages：system（基础段 + 普通用户追加段）+ user（`facts` 的 JSON） | `stream_explanation` |
| `build_explanation_facts(explanation)` | 650 | 请求信封 → 扁平事实 dict（`model_result` 展开 + `scenario` + `sample` + `algorithm_details` + `recommended_actions`） | `stream_explanation`、`explanation_routes.py:52`（分区外） |
| `_fallback_events(facts)` | 661 | **新增**。降级事件序列：逐块 `delta` + 唯一终态 `done{source: fallback}` | `stream_explanation` 两条降级路径 |
| `stream_explanation(db, current_user, explanation)` | 668 | **SSE 事件生成器**：`start` → （未配置 AI）`error` + 降级序列 /（已配置）`reasoning`*+`delta`* → `done{source: ai}`；异常 → `error{reason_code}` + 降级序列 | `explanation_routes.py:58`（分区外）；`tests/test_ai_service.py:35/48/127/161` |
| `_chunk_text(value, size=STREAM_CHUNK_SIZE)` | 719 | 定长切片，供 SSE 分块下发 | `_fallback_events`；**`model_evaluation_service.py:33` import（分区外，勿改名/勿删）** |

### 5.2 `backend/app/schemas/explanation_contract.py`
| 名称 | 行 | 算什么 / 数据从哪来 | 被谁调用 |
| --- | --- | --- | --- |
| `EXPLANATION_CONTRACT_VERSION` | 14 | `"1.0"`，契约版本，随解释落库 | `explanation_service`（写入 `contract_version`） |
| `EXPLANATION_ROLES` | 17 | 三级受众，按可见度升序 | **本文件** `ADMIN_ROLES` 派生（改前零引用） |
| `ADMIN_ROLES` | 21 | **新增**，`EXPLANATION_ROLES[1:]` | `explanation_for_role` |
| `ALGORITHM_CODES` | 22 | 6 个算法码 | `tests/test_explanation_contract.py:34`（**分区外，勿删**；与 `services/constants.py:220` 重复，见 S2） |
| `EXPLANATION_EVENTS` | 28 | **新增**。SSE 事件词表（权威定义） | 目前仅文档性/自检用；建议前端与路由后续引用 |
| `EXPLANATION_SOURCES` | 30 | **新增**。`done.source` 取值域 | `explanation_service` 解包为 `SOURCE_AI/SOURCE_FALLBACK` |
| `PUBLIC_TOP_FEATURE_LIMIT` | 32 | **新增**，3 | `explanation_for_role`、`fallback_markdown` |
| `PUBLIC_FIELDS` / `ADMIN_FIELDS` | 34 / 47 | 普通用户可见字段 / 管理员额外字段 | `explanation_for_role`、`validate_explanation_contract` |
| `unavailable(reason)` | 54 | `{available: False, reason}` 降级标记 | 服务层多处、契约内部 |
| `availability(is_available, reason=None)` | 59 | 可用性标记 | 服务层、`_normalize_model_quality`、`_normalize_algorithm_details` |
| `finite_number(value)` | 67 | 安全转 float（拒 NaN/Inf/非数值） | 服务层（D3 后统一用它）、契约内部 |
| `prediction_snapshot(result)` | 75 | 只保留预测相关字段的快照，**保证解释不反过来影响预测** | `tests/test_explanation_contract.py:52`；服务层 `input_snapshot` |
| `_list(value)` / `_dict(value)` | 95 / 99 | 类型守卫（非目标类型返回空容器；**dict 原样返回，会就地改**） | 契约内部 |
| `algorithm_specific_template(algorithm_code)` | 103 | 每个算法的专属字段骨架（+ `available/reason`） | `merge_algorithm_specific`、`tests/test_explanation_contract.py:46` |
| `merge_algorithm_specific(algorithm_code, value)` | 142 | 把 Java 的 `specific` 合并进模板，缺字段标 unavailable | `_normalize_algorithm_details`、`tests` |
| `_normalize_model_quality(value)` | 156 | **新增**（从 `normalize_explanation` 抽出）。固定 `model_quality` 形状 + 每指标 available/reason | `normalize_explanation` |
| `_normalize_algorithm_details(value)` | 177 | **新增**（同上）。固定 `algorithm_details` 形状并把 `specific` 合进模板 | `normalize_explanation` |
| `normalize_explanation(explanation)` | 207 | **契约归一化总入口**：固定全部字段形状、深拷贝、补 `contract_version` | 服务层 `build_unified_explanation` 出口、`explanation_for_role`、`tests` |
| `explanation_for_role(explanation, role)` | 252 | 三级可见性裁剪：管理员拿全量；普通用户只留 `PUBLIC_FIELDS` 且 `top_features` 截到 `PUBLIC_TOP_FEATURE_LIMIT` | `inference_record_service.py:181/848/918`（分区外）、`tests` |
| `validate_explanation_contract(explanation)` | 275 | 校验归一化结果，返回错误列表（空 = 通过） | `tests/test_explanation_contract.py:62` |

### 5.3 `backend/app/schemas/explanation.py`
| 名称 | 行 | 算什么 / 数据从哪来 | 被谁调用 |
| --- | --- | --- | --- |
| `ExplanationStreamRequest` | 9 | 解释流请求体：`scenario` / `sample` / `model_result` / `algorithm_details` / `recommended_actions` / `inference_record_id` / `model_version_id`。**仅当 `inference_record_id` 为空时其 `model_result` 才会被使用** | `explanation_routes.py`（分区外）；前端 `ExplanationStreamParams` |

---

## 6. 行为不变证明

### 6.1 协议 §1.4 自验命令与退出码
```
$ cd backend && python -m py_compile app/services/explanation_service.py app/schemas/explanation_contract.py app/schemas/explanation.py
PY_COMPILE exit=0
```
（未运行 pytest —— 按协议由 Lead 统一跑全量。）

### 6.2 黄金输出哈希对比（改前 vs 改后，逐键 sha256）
方法：改动**之前**对 45 个输出点做规范化 JSON（`sort_keys=True, ensure_ascii=False, default=str`）取 sha256 前 16 位与字节长度；
改动后重跑同一脚本逐键比对。覆盖面：6 个算法 + 未知算法的 `build_unified_explanation`（有/无 `algorithm_details`、有/无场景配置）、
三种角色的 `explanation_for_role`、`fallback_markdown`（全量/普通用户/空输入）、7 个场景码的 `get_scenario_config`、
`build_prompt`（两种受众）、`build_explanation_facts`、`_chunk_text`、`_mask_key`、`_classify_ai_error`、
`prediction_snapshot`、`algorithm_specific_template`、`merge_algorithm_specific`、`stream_explanation` 的完整事件序列。

**结果：42 / 45 键哈希与长度逐字节一致；3 键为预期变更。**

| 键 | 改前 | 改后 | 判定 |
| --- | --- | --- | --- |
| 其余 42 键（含 `unified:*`、`unified_algdetails:*`、`role:*`、`fallback*`、`prompt*`、`events`、`cfg:network_security` 等） | — | — | **完全一致** |
| `cfg:` / `cfg:None` / `cfg:__nope__` | `56dea85f…`(196) / 同 / `8eaa71ba…`(207) | `551cf4fc…`(281) / 同 / `3ce25157…`(295) | **预期变更**：B2 修复，未登记场景现返回 `configuration_available: False` + `configuration_errors` |
| `unified_nodetails:*`（7 个算法） | 各 1241–1394 字节 | 各 **+1 字节**（如 MAWNB `1424c02a…`(1307) → `a86a26f3…`(1308)） | **预期变更**：`scenario_code=None` 走降级分支，`configuration_available` 由 `true` 变 `false`（+1 字节即 `true`→`false`） |

> 这 3 类键的变更**正是 B2 的修复目标**：改前把「没有场景配置」报成可用，改后如实报不可用。
> 其余所有输出（包括 AI 提示词全文、SSE 事件序列、三种角色的可见字段）**逐字节不变**。

### 6.3 B1 崩溃向量：改前 / 改后
改前（`stream_explanation` 在无 `inference_record_id` 时把客户端 `model_result` 直接喂给 `fallback_markdown`）：
```
RAISE non-numeric risk_probability        ValueError  could not convert string to float: 'abc'
RAISE top_features missing direction      KeyError    'direction'
RAISE top_features is a string            AttributeError 'str' object has no attribute 'get'
RAISE conflict is a string                AttributeError 'str' object has no attribute 'get'
OK    scenario is a string                ['start','error','delta'×9,'done']
```
改后（同样输入）：
```
OK    non-numeric risk_probability        terminal=done source=fallback
OK    top_features missing direction      terminal=done source=fallback
OK    top_features is a string            terminal=done source=fallback
OK    conflict is a string                terminal=done source=fallback
OK    recommended_actions is a string     terminal=done source=fallback
```
> 说明：`scenario` 为字符串时改前也未崩，因为 `build_explanation_facts` 会用**信封层**的 `scenario` 覆盖 `model_result` 里的同名键，
> 而信封层的 `scenario` 在路由里来自 `get_scenario_config`（必为 dict）。该向量经 API 不可达，仅为完整性列出。

### 6.4 B4 `with` 上下文管理器实测
用本地临时 mock SSE 服务（`port=0`，不触碰 12312 上运行的后端）验证真实 openai SDK 流：
```
Stream supports context manager: True True
stop   -> [('content','Mock '), ('content','服务')]          # 正常流不受影响
length -> AIOutputTruncated: ...（finish_reason=length）      # 截断拦截仍然生效
first chunk: ('content','Mock ')
early close OK
[stderr] ... ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。
```
→ 提前 `gen.close()`（模拟客户端断连）后，mock 服务端**立刻**收到连接重置，证明上游 HTTP 流被确定性关闭，
而非等到 GC 才断开。（日志里的 `TypeError: 'str' object is not callable` 是我临时 mock 覆盖了
`BaseHTTPRequestHandler.finish` 导致的测试脚手架瑕疵，与被测代码无关。）

### 6.5 与既有测试期望的兼容性核对（静态核对，未运行 pytest）
| 测试 | 断言 | 结论 |
| --- | --- | --- |
| `tests/test_ai_service.py:40-43` | `events[0]==("start",…)`；`events[1][0]=="error"`；存在 `delta`；`events[-1]==("done",{"status":"已使用规则模板完成","source":"fallback"})` | ✅ `_fallback_events` 逐字保持该终态 |
| `tests/test_ai_service.py:53-55` | `events[1][1]["reason_code"]=="provider_error"`；`events[-1][1]["source"]=="fallback"` | ✅ 空响应 `RuntimeError` 仍归为 `provider_error` |
| `tests/test_ai_service.py:58-61` | `_classify_ai_error` 不回显 `api_key`/`prompt` | ✅ 未改 |
| `tests/test_ai_service.py:75-78` | `_openai_stream` 对本地 mock 返回 `{"content"}` 且含「Mock 服务」 | ✅ §6.4 实测通过 |
| `tests/test_scenario_config.py:26-27` | 已登记场景 `configuration_available` 为真、`recommended_actions` 非空 | ✅ 已登记场景走正常分支，哈希逐字节不变 |
| `tests/test_explanation_contract.py` | `algorithm_specific_template` / `prediction_snapshot` / `normalize_explanation` / `validate_explanation_contract` / `explanation_for_role` | ✅ 输出哈希全部一致 |
| `tests/test_security_boundaries.py:15,192` | `AISettingService`、`_fernet` 可导入且行为不变 | ✅ 未改 |

---

## 7. 跨区变更提案（**未应用**，请 Lead 裁决）

### 7.1 【最高价值】F1 前端 bug 的后端契约结论 + 前端修法建议
> 前端 `frontend/src/views/Model/RiskInference.vue` 属 F 区，**我未改动**。以下为后端侧权威契约描述与建议修法。

**① `source` 的完整取值域**
后端 `source` **只有两个取值**：`"ai"` 与 `"fallback"`，且**只在终态 `done` 事件上出现**（`explanation_service.py:702` 与 `_fallback_events` L665）。
不存在第三个取值；`start`/`reasoning`/`delta`/`error` 事件**都不带** `source`。
现已把该取值域提为契约常量 `explanation_contract.EXPLANATION_SOURCES = ("ai","fallback")`（纯新增，不影响前端类型）。

**② `fallback` 的触发条件（穷举，仅两处）**
| # | 条件 | 位置 |
| --- | --- | --- |
| 1 | `db.get(UserAISetting, current_user.id)` 为 `None`，或 `setting.enabled` 为假 | L682 |
| 2 | `_openai_stream` 抛任何 `Exception`（含 `AIOutputTruncated`、`RuntimeError("empty AI response")`、各类 `openai.*Error`） | L703 |

两条路径都**必然**以 `done{source:"fallback"}` 收尾。**不存在**「有 `error` 但没有 `done`」的正常情形。

**③ SSE 事件词表（后端权威定义）**
正常序列 `start → reasoning* → delta* → done`；降级序列 `start → error → delta* → done`。
事件名现已提为 `explanation_contract.EXPLANATION_EVENTS = ("start","reasoning","delta","error","done")`。
**关键结论：`error` 不是终态，且语义被重载** —— 它同时表示「账号未配置 AI」（L683）与「AI 调用失败已降级」（L715），
两者后面都还会跟规则模板正文和 `done`。客户端**不能**把 `error` 当作流结束或当作致命错误。

**④ 前端 bug 的后端侧根因（两条，互相独立）**
- **根因 A（语义倒置）**：`onError` 把 `explanationFallback=true` 且 `explanationStatus='fallback'`，同时 `explanationError=msg`、`markdown=''`；
  但模板只在 `explanationLoading` / `'stopped'` / `'failed'` / `explanationError` / `explanationMarkdown` / `explanationFallback` 上分支，
  **`'fallback'` 这个状态值从未被读取**，而 `explanationError` 非空又会渲染红色错误文案 —— 于是「已降级、正文可用」被渲染成「出错了」，
  真正的兜底提示（`explanationFallback`）反而被错误文案盖住。外层 `catch` 更把 `explanationFallback=true` 与 `explanationStatus='failed'` 同时置位，
  但此时**根本没有渲染任何模板正文** —— 自相矛盾。
- **根因 B（后端导致前端卡死）**：无 `inference_record_id` 时，客户端 `model_result` 被直接喂给 `fallback_markdown`；
  改前只要 `risk_probability` 非数值 / `top_features` 缺 `direction` / 类型不对，就会在生成器里抛异常 →
  **既没有 `error` 也没有 `done`** → 前端 `inferenceRecordApi.ts` 的 `while` 读到流结束即 `break`，`onDone` 永不触发，
  `explanationLoading` 永久停在 `true`，页面永远显示「正在生成」且拿不到任何兜底正文。**此根因已在本分区修复（B1）**，
  后端现在保证任何输入都走完 `done{source:"fallback"}`。

**⑤ 建议前端修法（供 F 区/Lead 参考，精确到行为）**
1. `onError` **不要**清空 `markdown`、**不要**置 `explanationStatus='fallback'`：`error` 只是降级通知，
   真正的终态判定统一放在 `onDone`（`data.source === 'fallback' ? 'fallback' : 'completed'`）—— 该逻辑 L627-630 已经正确。
   若要在流中途给用户反馈，用独立的 `explanationNotice`（非错误色），并在 `done` 到达后清除。
2. 外层 `catch` 置 `explanationFallback=true` 时必须**同时**渲染兜底文案，或干脆只置 `explanationStatus='failed'`（二选一，不能都置）。
3. 模板需要真正读取 `explanationStatus === 'fallback'`（当前该状态值写了但没人读）。
4. `inferenceRecordApi.ts` 的 reader 循环建议在 `done` 之外补一个**兜底终态**：流自然结束而未见 `done` 时，合成一次 `onDone`
   或 `onError`（否则任何后端/网络异常都会让 UI 永久 loading）。这是防御性改进，与 B1 互补。

### 7.2 其余提案（精确 diff，**均未应用**）
**(a) `backend/app/services/inference_record_service.py:891`** —— 落库校验用字面量集合：
```diff
-        if source not in {"ai", "fallback"}:
+        from app.schemas.explanation_contract import EXPLANATION_SOURCES
+        if source not in EXPLANATION_SOURCES:
```
影响面：把 `done.source` 的取值域收敛到契约单一事实源，避免前端/契约/落库三处各写一份。
替代方案：不改（当前值恰好一致，风险仅在将来新增 source 时漏改一处）。**该文件属 B3 分区，请勿由我改。**

**(b) `backend/app/api/v1/endpoints/explanation_routes.py:54,61`** —— `source = "fallback"` / `str(data.get("source") or source)` 同样建议改用 `SOURCE_FALLBACK` / `EXPLANATION_SOURCES`。
影响面同上；该文件属 B6 分区。

**(c) `backend/app/services/model_evaluation_service.py:33-34,398,413,443`** —— 跨模块导入**私有**函数 `_chunk_text` / `_classify_ai_error`：
```diff
-from app.services.explanation_service import (
-    _chunk_text,
-    _classify_ai_error,
+from app.services.explanation_service import (
+    chunk_text,
+    classify_ai_error,
```
影响面：需要在本分区把两个函数**改名去下划线**（成为公开 API）并同步 `tests/test_ai_service.py:14` 的导入。
**我没有改名**（会破坏分区外调用点），因此**保留了下划线名**。建议 Lead 在串行阶段统一：要么公开化，要么把这两个函数下沉到共享模块。
该文件属 B5 分区。

**(d) `backend/app/services/constants.py:37` 与 `explanation_contract.ADMIN_ROLES`** —— 同一集合（`("SCENARIO_ADMIN","SUPER_ADMIN")`）存在两份定义。
`constants.ADMIN_ROLES` 基于角色常量、被 `inference_record_service.py:33` 使用；契约那份由 `EXPLANATION_ROLES` 派生。
因 `explanation_contract` 是**零依赖**的 schema 模块（不得反向 import `services`），我选择各留一份并加注释互指。
若要真正统一，建议把角色常量下沉到 schema 层。`constants.py` 属其他分区。

**(e) `frontend/src/types/security.ts` 无需改动** —— 已 grep 确认前端全仓库**不存在** `configuration_available`，
故 B2 新增的该字段对前端零影响（既不会渲染也不会类型报错）。

---

## 8. 未解决 / 存疑（如实列出）

| # | 事项 | 我的判断与处理 |
| --- | --- | --- |
| S1 | `ExplanationStreamRequest.model_version_id` 被前端发送但**路由从未读取**（`explanation_routes.py` 只读 `inference_record_id`） | **未删**。删字段属于「改已导出 schema」，且可能有前端/文档依赖。建议 Lead 裁决：要么路由真正使用它，要么在契约层标记 deprecated。 |
| S2 | `ALGORITHM_CODES` 在 `services/constants.py:220` 与 `explanation_contract.py:25` **重复定义** | **未删**。`tests/test_explanation_contract.py:34` 直接引用契约那份；删任一份都会破坏引用。建议收敛到一处（跨分区，见 §7.2d 同类问题）。 |
| S3 | `_normalize_feature_items`（53 行）最深层嵌套 4 层 | **未重构**。它是一个「单遍扫描 + 就地归一」的循环，拆函数需要传递 4-5 个累加器，反而降低可读性。判定为可接受的复杂度。 |
| S4 | `AISettingService.test_connection` 的 `except Exception`（L566 附近）会吞掉异常细节 | **未改**。它是「连通性自检」接口，语义上就该把任何失败翻译成「连接失败」结论；已通过 `_classify_ai_error` 给出 `reason_code`。若 Lead 要求更细，可在返回体加 `error` 类名。 |
| S5 | `_configs()` 每次调用都**重新读盘 + JSON 解析 + 特征目录展开 + 全校验**（无缓存）；`get_scenario_config` 的 3 个外部调用方（`scenario_routes.py:80`、`model_evaluation_service.py:85`、`inference_record_service.py:853`）会各自触发一次 | **故意不加 `lru_cache`**。`_configs()` 返回的 dict 会被下游**就地修改**（`_normalize_algorithm_details` 直接改 `details`；`build_unified_explanation` 会读 `config` 并在其基础上组装），共享缓存会造成**跨请求数据污染**。这是性能问题不是正确性问题（配置文件很小：network_security 约 25KB）。安全提案：若确需缓存，必须返回 `deepcopy` 或改为不可变结构 —— 属跨分区改动，见 §7.2。 |
| S6 | `build_unified_explanation` 仍有 93 行（>80 阈值） | 见 §3.C：剩余部分几乎全是契约形状的返回字典字面量，再拆只会引入 10+ 形参的转发函数。**判定为不值得拆**，如实记录。 |
| S7 | `_mask_key`：长度 9 的 key 会暴露 8 个字符（`len>8` 时取前 4 后 4） | **未改**。这是**用户可见文案**（设置页展示），改阈值会改变已上线展示效果，且 API key 通常远超 9 字符。记录为 nit。 |
| S8 | `_fernet()` 每次调用重建 `Fernet`；加密密钥在 `AI_SETTINGS_ENCRYPTION_KEY` 缺失时**回退到 `AUTH_SESSION_PEPPER`** | **未改**。后者意味着**轮换 `AUTH_SESSION_PEPPER` 会静默让所有已存 AI key 无法解密**（表现为「AI 不可用」）。这是运维风险而非代码缺陷，且修它需要产品决策（是否强制要求独立密钥）。已在 §3.D 记录。 |
| S9 | `AISettingService.update` 中 `enabled = bool(payload.get("enabled", True))`：**未传 `enabled` 时会被重置为 True**（前端若只改 base_url 会意外重新启用 AI） | **未改**。这是行为语义问题，改了会改变接口行为（可能正是设计意图）。建议 Lead 与前端确认后统一，属跨分区（路由/B 区）。 |
| S10 | `build_prompt` 把整个 `facts`（含 `sample` 原始输入快照）`json.dumps` 后发给 AI，**无长度上限** | **未改**。截断会改变 AI 可见事实（违反「不得改变预测相关事实」的约束），且需要产品决定截断策略。记录为成本/提示词注入面风险（见下）。 |
| S11 | 无 `record_id` 时接受任意客户端 `model_result` → **提示词注入面** + **无速率限制的 AI token 消耗** | **未改**（属路由/限流分区）。B1 已确保此类请求不会让流断掉，但「接受任意事实」这一设计本身仍存在。建议 Lead 评估是否要求该路径必须携带 `inference_record_id`，或加限流。 |
| S12 | 置信度分档用 `build_unified_explanation` 的形参 `risk_threshold`（默认 `0.5`），而 `inference_record_service.py:333` 调用时**不传该参数** → 实际总按 0.5 算 `confidence`，**与场景配置的真实阈值口径可能不一致** | **未改**。真实阈值由 B4b 分区的阈值服务提供，跨分区。这是「同一口径多处实现不一致」的隐患，建议 Lead 让 B3/B4b 确认 `confidence` 是否应以场景阈值为准。 |
| S13 | `fallback_markdown` 对畸形输入的**行为有微小变化**：`recommended_actions` 若为非 list 的真值（如字符串 `"ab"`），改前会逐字符渲染成 `1. a` / `2. b`，改后按「无建议」处理并给出提示文案 | 这是 B1 加固的**有意**副作用，仅影响非法输入（合法输入哈希逐字节不变，见 §6.2）。记录备查。 |

---

## 9. `git status --short`（仅本分区）

```
 M backend/app/schemas/explanation.py
 M backend/app/schemas/explanation_contract.py
 M backend/app/services/explanation_service.py
?? docs/全项目代码审查/报告/B4a.md
```
（`git status --short` 全量输出中还有大量其他代理正在修改的文件，属并发噪声，与 B4a 无关，未逐一列举。）

---

**我未修改任何分区外文件。**
