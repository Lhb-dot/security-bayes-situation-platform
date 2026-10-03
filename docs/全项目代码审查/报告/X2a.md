# X2a · 后端测试分区审查报告（`backend/tests/**`）

> 分区：X2a = `backend/tests/**`（15 个 `.py` + 1 个 `.json` fixture）
> 写作用域：`backend/tests/**` + 本报告文件。**不含** `__pycache__/**`（未入库，已忽略）。
> 基线：`python -m pytest tests -q` → **177 passed, 6 subtests passed**（Lead 已确认；本代理遵守 §1.3 **未运行 pytest**）。
> 自验：`cd backend && python -m py_compile <改动文件>` → **EXIT=0**。

---

## §0 速览

| 结论 | 数值 |
|---|---|
| 测试文件数 | **15 个 `.py`**（+1 个 fixture JSON），共 **3024 行** |
| 测试函数数 | **177**（与「177 passed」逐一对应；「6 subtests」= `test_explanation_contract.py::test_prediction_snapshot_is_unchanged_by_explanation_contract` 的 6 个 `subTest`，对应 6 个算法） |
| 断言总数 | **462** 条（AST 统计，含 `with assertRaises` 上下文） |
| 无断言的测试 | **0 个** |
| 裸 `assert` 语句 | **0 处**（全部走 `self.assert*`，风格统一） |
| 恒真/放水断言 | **0 处**（无 `assert True`、无 `status_code in (200,400,500)` 式写法、无「只断言 `code == 0`」的空壳测试） |
| 被 skip/xfail/静默吞掉 | **0 处**（全库零 `pytest.mark.*`、零 `try/except: pass`、零 `print`、零 `TODO/FIXME`） |
| **HTTP 功能级覆盖** | **0 个 endpoint**。**全库零 `TestClient`**，没有任何一次真实请求 |
| 路由总数 | **111**（103 个 `/api/v1` + 8 个遗留 `/api/model`、`/china-map.json`） |
| 仅被「路径存在性」断言覆盖 | 23 个 v1 路径 + 8 个遗留路径 = **31** |
| **零覆盖 endpoint（无功能测试也无存在性断言）** | **80 个 v1 endpoint** |
| 零覆盖 service 模块 | **16 个**，合计 **约 4603 行**（含 1837 行的 `dashboard_service.py`） |
| 真测试判定 | **15/15 文件均为真测试**（断言密度高、边界与失败路径齐备） |
| 本次重构导致失效的断言 | **0 条失效**；**1 处潜在脆弱点**（见 §6-D5 / §8-P3） |
| 唯一阻止删除遗留簇的东西 | `test_application_structure.py:11-31`（原文见 §8-P1） |
| 安全删除 | 2 处未使用 import（`test_ai_service.py:12`、`test_discretization_applicability.py:11`），**零断言影响** |
| 改动行数 | **−2 行**（仅删 import，无新增行） |

**一句话**：这是一套**质量意外地高**的单元测试——零 skip、零假测试、462 条断言、失败路径覆盖扎实；但它**完全没有 HTTP 层**，`backend/app/api/**` 与 5 个最大的 service 基本处于裸奔状态。

---

## §1 范围

### 1.1 文件清单（改前行数 → 改后行数）

| # | 文件 | 行数 | 改动 |
|---|---|---|---|
| 1 | `backend/tests/test_ai_service.py` | 176 → **175** | 删未使用 import `AISettingService`（−1） |
| 2 | `backend/tests/test_application_structure.py` | 35 | 无 |
| 3 | `backend/tests/test_batch_inference_async.py` | 316 | 无 |
| 4 | `backend/tests/test_discretization_applicability.py` | 175 → **174** | 删未使用 import `patch`（−1） |
| 5 | `backend/tests/test_explanation_audience.py` | 189 | 无 |
| 6 | `backend/tests/test_explanation_contract.py` | 104 | 无 |
| 7 | `backend/tests/test_model_evaluation.py` | 216 | 无 |
| 8 | `backend/tests/test_report_content.py` | 321 | 无 |
| 9 | `backend/tests/test_report_export_async.py` | 537 | 无 |
| 10 | `backend/tests/test_report_generate_async.py` | 225 | 无 |
| 11 | `backend/tests/test_report_scope.py` | 140 | 无 |
| 12 | `backend/tests/test_scenario_config.py` | 74 | 无 |
| 13 | `backend/tests/test_security_boundaries.py` | 199 | 无 |
| 14 | `backend/tests/test_training_async.py` | 229 | 无 |
| 15 | `backend/tests/test_training_metrics_contract.py` | 88 | 无 |
| — | `backend/tests/fixtures/unified_explanation_samples.json` | 11 | 无（纯数据，被 `test_explanation_contract.py` 读取） |
| | **合计** | **3024 → 3022 行 `.py`** | **−2** |

### 1.2 硬约束遵守情况（协议 §3.E）

- **未削弱、未删除任何断言**：改动仅 2 行 import 删除，`git diff` 只含这两行。
- **未修改 `backend/alembic/**`**（X2b 范围）、**未修改 `backend/app/**`**（其他代理在改）。
- **未新建文件**（除本报告）、未新建目录。
- **未运行 pytest / 未起服务 / 未跑构建**。自验仅 `py_compile`（EXIT=0）。
- `backend/tests/__pycache__/` 存在但**未被 git 跟踪**（`git ls-files tests` 只返回 16 条），属磁盘垃圾，未纳入审查、未删除。

### 1.3 已确认的环境事实（用于交叉核对）

- `git ls-files tests` → **恰好 16 条**（15 `.py` + 1 `.json`），与任务书一致。
- **`backend/` 下没有 `conftest.py`、`pytest.ini`、`setup.cfg`、`pyproject.toml`、`tox.ini`**。
  测试靠每个文件顶部的 `sys.path.insert(0, str(Path(__file__).parents[1]))` 自行解决导入。
- 全库**零 `import pytest`**：15 个文件全是 `unittest.TestCase`，由 pytest 收集 `unittest` 类运行。

---

## §2 测试清单与覆盖矩阵

### 2.1 覆盖矩阵 A：`backend/app/api/**` 的 111 个路由

**关键结论：全库零 `TestClient`。** `grep -r "TestClient\|client\.\(get\|post\|put\|delete\)" backend/tests` → **0 命中**。
因此**没有任何一个 endpoint 有功能级测试**。「覆盖」在本表里只有一种形式：`app.openapi()["paths"]` 的**路径存在性断言**——它只能证明路由被注册，**不能证明鉴权、参数校验、响应结构、错误码、数据范围任何一项**。

| 路由模块 | 路由数 | 功能测试 | 存在性断言 | 备注 |
|---|---|---|---|---|
| `auth_routes.py` | 3 | ❌ 0 | 1/3（`POST /login`） | `GET /me`、`POST /logout` 零覆盖 |
| `ai_setting_routes.py` | 3 | ❌ 0 | **0/3** | 零覆盖；`AISettingService` 的掩码逻辑**只被 service 级测到**（`test_security_boundaries.py:176`） |
| `explanation_routes.py` | 1 | ❌ 0 | **0/1** | `POST /inference/explanation/stream` 零覆盖（SSE 流式，风险最高） |
| `user_routes.py` | 9 | ❌ 0 | **0/9** | **整个用户管理模块零覆盖**（含改密、重置密码、禁用、删号） |
| `scenario_routes.py` | 8 | ❌ 0 | **0/8** | 零覆盖 |
| `dataset_routes.py` | 9 | ❌ 0 | **0/9** | 零覆盖（含 `POST /upload` 文件上传） |
| `algorithm_routes.py` | 5 | ❌ 0 | **0/5** | 零覆盖 |
| `dashboard_routes.py` | 3 | ❌ 0 | 1/3（`/admin/overview`） | **Lead 的 P0 越权修复在此模块，零测试**（见 §2.3） |
| `model_evaluation_routes.py` | 2 | ❌ 0 | **0/2** | 零覆盖（service 层 `ModelEvaluationService` 有覆盖） |
| `model_version_routes.py` | 17 | ❌ 0 | 2/17（`/train`、`/train-async`） | 其余 15 个（publish/offline/disable/enable/set-default/compare/…）零覆盖 |
| `inference_record_routes.py` | 11 | ❌ 0 | 6/11 | 覆盖最好的模块，但仍只到路径层 |
| `risk_event_routes.py` | 7 | ❌ 0 | 1/7（`GET /`） | 处置/评论/隐藏/取消隐藏 全零覆盖 |
| `risk_threshold_routes.py` | 4 | ❌ 0 | 1/4（`GET /`） | `PUT /{scenario_id}`（改阈值）零覆盖 |
| `report_routes.py` | 15 | ❌ 0 | 10/15 | 覆盖第二好；`PUT /{id}/schedule`、`DELETE /{id}` 零覆盖 |
| `situation_routes.py` | 6 | ❌ 0 | 1/6（`/global`） | 快照写入 `POST /scenes/{id}/snapshot` 零覆盖 |
| **v1 小计** | **103** | **0** | **23** | **80 个 v1 endpoint 完全零覆盖** |
| `legacy_model_routes.py`（遗留簇） | 8 | ❌ 0 | **8/8** | **全部 8 条被 `test_application_structure.py` 锁死**（见 §8-P1） |
| **合计** | **111** | **0** | **31** | |

**零覆盖 endpoint 计数 = 80（v1）+ 0（遗留簇全部至少有存在性断言）= 80。**

**被存在性断言覆盖的 31 条路径**（仅此 31 条，逐条可溯源）：

- `test_application_structure.py:13-30`（16 条）：`/api/v1/auth/login`、`/api/v1/dashboard/admin/overview`、`/api/v1/model-versions`、`/api/v1/inference-records/predict`、`/api/v1/risk-events`、`/api/v1/risk-thresholds`、`/api/v1/reports`、`/api/v1/situation/global`、`/china-map.json`、`/api/model/dataset-list`、`/api/model/save-threshold`、`/api/model/train`、`/api/model/infer`、`/api/model/exp-records`、`/api/model/exp/{record_id}`、`/api/model/risk_statistics`
- `test_batch_inference_async.py:304-312`（5 条）：`predict-batch/jobs`、`predict-batch/jobs/{job_id}`、`predict-batch/upload/jobs`、`predict-batch`、`predict-batch/upload`
- `test_training_async.py:220-225`（2 条）：`model-versions/train-async`、`model-versions/train`
- `test_report_export_async.py:525-533`（5 条）：`reports/{report_id}/export/jobs`、`reports/export/jobs`、`reports/export/jobs/{job_id}`、`reports/export/jobs/{job_id}/file`、`reports/{report_id}/export`
- `test_report_generate_async.py:213-221`（3 条）：`reports/generate/jobs`、`reports/generate/jobs/{job_id}`、`reports/generate`（另断言了这两个路径的 `post`/`get` 方法位）

### 2.2 覆盖矩阵 B：`backend/app/services/**` 与其余模块

| 模块 | 行数 | 被哪个测试文件覆盖 | 覆盖深度 |
|---|---|---|---|
| `services/explanation_service.py` | 628 | `test_ai_service.py`（`stream_explanation`/`_openai_stream`/`_classify_ai_error`/`_fernet`）、`test_security_boundaries.py:176`（`AISettingService.get` 掩码）、`test_scenario_config.py`（`CONFIG_PATH`/`get_scenario_config`） | **深**（含真实本地 mock OpenAI 服务、reasoning 分流、5 种失败码） |
| `services/inference_record_service.py` | 800 | `test_batch_inference_async.py`、`test_explanation_audience.py`、`test_security_boundaries.py` | **深**（越权矩阵、CSV 口径、受众分格、事实裁剪） |
| `services/model_version_service.py` | 663 | `test_training_async.py`、`test_model_evaluation.py`、`test_discretization_applicability.py`、`test_training_metrics_contract.py` | **深**（训练状态机、参数剔除、指标可见性） |
| `services/report_service.py` | 1084 | `test_report_content.py`、`test_report_scope.py`、`test_report_export_async.py`、`test_report_generate_async.py` | **深**（范围三级角色、章节编号、事件总数口径、异步提交） |
| `services/report_export.py` | 718 | `test_report_export_async.py` | **深**（PDF 渲染调度/竞态/空闲退出/超时、三格式产物形状、图表 SVG 注入与转义） |
| `services/model_evaluation_service.py` | 400 | `test_model_evaluation.py` | **深**（快照新鲜度、缓存、角色化事实） |
| `services/batch_inference_runner.py` | 242 | `test_batch_inference_async.py` | **深**（任务表、TTL 清理、越权可见性、终态释放） |
| `services/export_job_service.py` | 208 | `test_report_export_async.py` | **深** |
| `services/report_generate_runner.py` | 191 | `test_report_generate_async.py` | **深** |
| `services/training_runner.py` | 162 | `test_training_async.py` | **深**（僵尸 TRAINING 兜底、worker 数钳制） |
| `services/training_executor.py` | 146 | `test_training_metrics_contract.py`（仅 `_request_train`） | **浅**（只测指标透传；`requests.post` 与 `os.path.exists` 被打桩） |
| `services/report_nl.py` | 197 | `test_report_content.py`（仅 `build_analysis_nl`） | **中**（只测总数口径相关分支） |
| `services/base.py` | 160 | 间接（`ServiceError`） | 仅异常类型 |
| `services/constants.py` | 277 | 间接（4 个常量） | 仅常量引用 |
| **`services/dashboard_service.py`** | **1837** | **❌ 无** | **零覆盖 —— 全项目最大 service** |
| **`services/risk_event_service.py`** | **512** | **❌ 无** | **零覆盖** |
| **`services/dataset_service.py`** | **488** | **❌ 无** | **零覆盖** |
| **`services/user_service.py`** | **332** | **❌ 无** | **零覆盖（含改密/重置密码）** |
| **`services/scenario_analytics.py`** | **305** | **❌ 无** | **零覆盖** |
| **`services/scenario_service.py`** | **214** | **❌ 无** | **零覆盖** |
| **`services/situation_snapshot_service.py`** | **181** | **❌ 无** | **零覆盖** |
| **`services/handling_record_service.py`** | **169** | **❌ 无** | **零覆盖** |
| **`services/model_sim.py`** | **154** | **❌ 无** | **零覆盖**（协议 §3.A 已列为待清理嫌疑） |
| **`services/risk_threshold_service.py`** | **115** | **❌ 无** | **零覆盖（阈值=风险等级判定口径的源头）** |
| **`services/risk_view.py`** | **87** | **❌ 无** | **零覆盖** |
| **`services/report_scheduler.py`** | **62** | **❌ 无** | **零覆盖（定时报告后台线程）** |
| **`services/algorithm_service.py`** | **56** | **❌ 无** | **零覆盖** |
| **`services/threshold_audit_log_service.py`** | **45** | **❌ 无** | **零覆盖（审计日志）** |
| **`services/algorithm_config.py`** | **14** | **❌ 无** | **零覆盖** |
| **`services/__init__.py`** | **32** | **❌ 无** | — |
| `utils/common.py` | 283 | `test_discretization_applicability.py`（`dataset_has_numeric_features`/`strip_inapplicable_params`/`validate_params_schema`） | **浅**（3 个函数；`paginate`/`row_to_dict`/`hash_password`/`verify_password` **零直接覆盖**） |
| `utils/auth.py` | 35 | `test_security_boundaries.py`（仅 `digest_token`） | **浅** |
| `utils/arff_reader.py` | 252 | **❌ 无** | **零覆盖** |
| `utils/dataset_file_reader.py` | 139 | **❌ 无** | **零覆盖（B6b-1 刚改过）** |
| `api/deps.py` | 106 | `test_security_boundaries.py`（仅 `get_current_session`） | **中**（未登录 / CSRF 两条路径） |
| `api/utils.py` | 15 | **❌ 无** | **零覆盖** |
| `api/legacy_model_routes.py` | 123 | 仅路径存在性 | 零功能覆盖 |
| `api/v1/endpoints/**`（15 文件） | 1991 | 仅路径存在性（23/103） | 零功能覆盖 |
| `config.py` | 37 | 间接（`CONFIG_PATH` 等经 service 读取） | **无直接测试**（B6b-1 刚改过） |
| `main.py` | 120 | 间接（5 个测试文件 `from app.main import app` 只为拿 `openapi()`） | **仅副作用**，无断言 |
| `db.py` | 26 | 间接（`SessionLocal` 被 4 处 `patch`） | 无直接测试 |
| `paths.py` | 7 | 间接 | 无 |
| `algorithms/pmwnb_demo.py` | 40 | **❌ 无** | **零覆盖**（协议 §3.A 已列为待清理嫌疑） |
| `models/**`（14 文件，共 ~400 行） | ~400 | **❌ 无**（全部经 `SimpleNamespace` 桩替代） | **零覆盖**；ORM 映射/关系/约束/级联**完全未验证** |
| `schemas/**` | ~250 | `common`/`explanation_contract`/`scenario_config` 有；其余无 | 部分 |
| `data/scenario_feature_catalog.py` | 121 | `test_scenario_config.py` | **中** |
| `scripts/mock_openai_server.py`（`backend/../scripts`） | — | `test_ai_service.py` 作为**被测依赖**（不是被测对象） | — |

**零覆盖 service/模块行数合计 ≈ 4603 行**（含 `dashboard_service.py` 1837 行）。

### 2.3 覆盖矩阵的决定性结论（给 Lead 的重构决策用）

1. **`dashboard_service.py`（1837 行）零测试，而 Lead 刚在此做了 P0 越权修复。**
   → **这次修复没有任何自动化回归网**。任何后续对 `dashboard_service` 的改动都属裸奔。**建议：这是全项目最高优先级的补测点**（≥3 条：超管看场景画像应 403、场景管理员看他人场景应 403、场景用户只能看自己工作台）。
2. **`backend/app/api/**`（2589 行，111 路由）零功能测试。**
   → 所有鉴权装饰器、请求模型校验、响应字段形状都**只在 OpenAPI schema 层被间接证明存在**。任何 endpoint 的参数改名、`response_model` 改动、依赖注入顺序调整，**测试全绿也发现不了**。
3. **`user_service.py` + `user_routes.py` 零覆盖（改密/重置密码/禁用/删号）。**
   → 这是安全面最大的裸奔区，且**与 `test_security_boundaries.py` 已有的角色越权测试形成反差**：记录读取的越权被测了，用户管理的越权没测。
4. **`risk_threshold_service.py` 零覆盖**，但风险等级判定口径（`test_report_content.py::DataNotesThresholdTests`）被测了——**阈值来源没测，阈值消费测了**。
5. **`utils/arff_reader.py`、`utils/dataset_file_reader.py` 零覆盖**，而 `dataset_file_reader.py` 是 B6b-1 刚改过的文件。
6. **`models/**` 零覆盖**：所有测试用 `SimpleNamespace` 顶替 ORM 行。好处是快、无 DB 依赖；代价是**ORM 字段名写错、关系配错、`nullable` 不匹配都不会被发现**。
7. 相对安全的重构区（有深覆盖护航）：`report_service`、`report_export`、`inference_record_service`、`model_version_service`、`explanation_service`、4 个 runner、`model_evaluation_service`。

---

## §3 A 弃用（deprecated）

**查了什么**（命令与命中数）：

| 检查项 | 命令（在 `backend/` 下） | 命中 |
|---|---|---|
| `datetime.utcnow()` | `grep -rn "utcnow" backend/tests` | **0** ✅ |
| 旧式 `typing.List/Dict/Optional` | `grep -rn "from typing import" backend/tests` | **0** ✅（测试里根本没有 `typing` 导入） |
| `asyncio.get_event_loop()` / `asyncio` | `grep -rn "asyncio\|get_event_loop" backend/tests` | **0** ✅ |
| `pytest` 旧 API / `import pytest` | `grep -rn "import pytest\|pytest\." backend/tests` | **0** ✅ |
| `unittest` 与 `pytest` 混用 | 同上 | **无混用**：15 个文件全为 `unittest.TestCase`，零 `pytest` 特性 |
| `distutils` / `imp` / `pkg_resources` | 未在测试中出现 | **0** ✅ |

**结论 A-1：语言层与框架层弃用 —— 测试分区零命中，无需改动。**

**结论 A-2（项目层弃用，需提案）：`sys.path` 手工注入是 15 次重复的弃用式做法。**
每个测试文件顶部都有
`sys.path.insert(0, str(Path(__file__).parents[1]))`
（`test_explanation_audience.py:11` 与 `test_explanation_contract.py:6` 等用的是 `.resolve().parents[1]`，写法不统一）。
正规做法是 `backend/conftest.py`（pytest）或 `backend/tests/__init__.py` + `pyproject.toml` 的 `pythonpath`。
**但协议 §1.7 禁止新建文件** → 只提案，见 §8-P2。

**结论 A-3（弃用式 API 的残留：`unittest.main()` 入口）。**
15 个文件末尾都有
```python
if __name__ == "__main__":
    unittest.main()
```
这是「`python tests/test_x.py` 单跑」的旧式入口。它**不是死代码**（配合 `running_under_test_runner()` 的 `argv[0]` 兜底分支，见 §6-D7，直接执行单个测试文件时靠它判定），**保留**。此处仅记录：它使测试具备两种运行方式，而两种方式下 `running_under_test_runner()` 的判定路径不同。

**结论 A-4（宽松异常断言，属弃用式写法）：**
`test_security_boundaries.py:162` 与 `:170` 使用
`with self.assertRaisesRegex(Exception, "未登录"):` / `assertRaisesRegex(Exception, "CSRF")`。
捕获裸 `Exception` 而非 `fastapi.HTTPException`（或 `app.services.base.ServiceError`）。详见 §6-D10。**只报告，不改**（改它等于收紧断言语义，属协议 §3.E 禁区）。

---

## §4 B 残留与死测试

### 4.1 已删除（唯一的两处改动，附零引用证据）

**B-1 `test_ai_service.py:12` 未使用 import `AISettingService`**

证据（改动前）：
```
$ grep -n "AISettingService" backend/tests/test_ai_service.py
13:    AISettingService,          <- 仅此一处，import 行本身
```
AST 扫描（`ast.Name`/`ast.Attribute` 全量收集后求差）确认 `AISettingService` 在文件内**零引用**。
`test_security_boundaries.py:15` 另有自己的 `AISettingService` 导入（在那边被真实使用，行 192），两者无关。

**B-2 `test_discretization_applicability.py:11` 未使用 import `patch`**

证据（改动前）：
```
$ grep -n "patch" backend/tests/test_discretization_applicability.py
11:from unittest.mock import Mock, patch     <- 仅此一处
```
该文件只用 `Mock`（`service.db.get = Mock(...)`、`service.db.add = Mock()` 等），从不使用 `patch` / `patch.object`。

**改动后自验**：
```
$ cd backend && python -m py_compile tests/test_ai_service.py tests/test_discretization_applicability.py
EXIT=0
```
两处均为**纯残留**（未使用 import），**不触及任何断言**，符合任务书「可修改」的全部条件。

### 4.2 逐项排查结论（每项都给了命令）

| 残留类型 | 命令 | 命中 | 结论 |
|---|---|---|---|
| 注释掉的测试代码块 | 人工通读 15 个文件全文 | **0** | 无。文件顶部只有说明性 docstring（中文，解释「为什么要测这条」），**不是**注释掉的代码 |
| 调试 `print` | `grep -rn "print(" backend/tests` | **0** | 无 |
| `TODO`/`FIXME`/`XXX` | `grep -rn "TODO\|FIXME\|XXX" backend/tests` | **0** | 无 |
| `try/except: pass` 静默吞断言 | `grep -rn "except.*:$" backend/tests` | **0** | **无任何 `try/except` 包住断言**。仅有的 4 处 `try/finally` 用于关停 mock HTTP 服务（`test_ai_service.py:67-82, 89-112, 119-135, 153-172`），`finally` 里是 `shutdown()/server_close()/join()`，**不吞异常** |
| `pytest.mark.skip/skipif/xfail` | `grep -rn "skip\|xfail" backend/tests` | **0** | **零跳过、零预期失败**。177 个测试函数全部真实执行 → 「177 passed」是 177/177 全绿，无水分 |
| `pass` 占位 | AST + 人工 | **3 处，全部合法** | `test_explanation_audience.py:73`（`AudienceDb.rollback` 桩）、`test_report_content.py:40`（`FakeDb.commit` 桩）、`:43`（`FakeDb.rollback` 桩）。是假 DB 的空实现，**不是残留** |
| 零引用/未被收集的测试文件 | AST 统计测试函数数 = **177**，与 `pytest` 报告 `177 passed` 完全相等 | **0 个死文件** | **15 个文件全部被收集、全部有测试执行**。没有任何文件「存在但不被收集」 |
| 未使用 import（全量） | AST 扫描 15 个文件 | **2 处** | 即 B-1、B-2，已删 |

### 4.3 重复定义（残留的另一种形态）—— 提案，不新建文件

**B-3 会话/DB 桩 `FakeDb` 在 6 个文件里同名重复定义，另有 5 个文件各自造了等价物。**

| 文件 | 桩类名 | 实现的能力 |
|---|---|---|
| `test_ai_service.py:22` | `FakeDb` | `get()` |
| `test_batch_inference_async.py:24` | `FakeDb` | `get/rollback/close` |
| `test_report_content.py:23` | `FakeDb` | `get/scalars/add/commit/rollback` |
| `test_report_export_async.py:27` | `FakeDb` | `rollback/close` |
| `test_report_generate_async.py:23` | `FakeDb` | `get/rollback/close` |
| `test_training_async.py:22` | `FakeDb` | `get/scalars/commit/rollback/close` |
| `test_security_boundaries.py:18/134` | `AccessDb` / `_SessionDb` | 按 `model_type.__name__` 分派 + `scalar/commit` |
| `test_explanation_audience.py:47` | `AudienceDb` | 4 类 `__name__` 分派 |
| `test_model_evaluation.py:21` | `EvaluationDb` | 4 类分派 + `refresh` |
| `test_report_scope.py:17/82` | `ScopeDb` / `CapturingDb` | 捕获 SQL 文本 |
| `test_discretization_applicability.py:127` | `Mock()` | 直接打桩 |

**共 11 个文件各自实现同一件事**，其中 6 个连类名都一样。这是最值得上提 `conftest.py` 的重复，**但 §1.7 禁止新建文件** → 见 §8-P2。

**B-4 `make_model()` 在 3 个文件里同名但形状不同**：`test_report_content.py:64`、`test_training_async.py:54`、`test_model_evaluation.py:49`。同名不同义，阅读时会误以为是共享 fixture。提案见 §8-P2。

**B-5 `sys.path.insert` 在 15 个文件里重复 15 次**（两种写法不统一）。提案见 §8-P2。

**B-6 任务表测试套件重复 3 份**：`JobStoreTests` 分别在 `test_batch_inference_async.py:209`、`test_report_export_async.py:165`、`test_report_generate_async.py:51`，三份结构几乎逐条对应（`_jobs` 清理、越权不可见、TTL 过期清理、进行中不清理、未启动即拒绝）。这是**生产侧 4 个 runner 复制同一套任务表**的镜像。测试侧的重复本身不是缺陷（各自锁各自的模块），但**生产侧的重复才是**——见 §8-P5。

**结论 B：测试分区残留极少（2 个未使用 import，已删）。质量显著高于同类项目——零 skip、零注释代码、零调试输出、零死文件。**

---

## §5 C 复杂度

### 5.1 超长测试函数（> 80 行）

**AST 统计：0 个测试函数超过 60 行，更没有超过 80 行的。**
```
$ cd backend && python -c "AST: 对每个 test* 函数计算 end_lineno-lineno+1，输出 >60 的"
（无输出）
total test funcs 177
```
最长的是 `test_report_export_async.py` 里的时序类测试（约 40-50 行，含多行 `with` 与注释），属合理长度。

**结论：C-1 无超长测试函数。**

### 5.2 超长文件（> 800 行）

无。最长 `test_report_export_async.py` = **537 行**（含 6 个测试类：`PdfRendererTests` 66 行、`ExportJobStoreTests` 95 行、`SubmitExportTests` 84 行、`BuildExportContractTests` 43 行、`ChartExportTests` 137 行、`RouteWiringTests` 14 行）。
**它是唯一接近「该拆」的文件**：537 行里塞了「PDF 渲染线程调度」「导出任务表」「提交入口」「产物形状契约」「图表 SVG 注入」「路由注册」六个正交主题。
**拆分方案（提案，§1.7 禁止新建文件 → 只提案）**：拆成 `test_report_export_renderer.py`（`PdfRendererTests`）、`test_report_export_jobs.py`（`ExportJobStoreTests` + `SubmitExportTests`）、`test_report_export_contract.py`（`BuildExportContractTests` + `ChartExportTests`）、`RouteWiringTests` 并入现有路由测试文件。

### 5.3 重复的 setup 样板

| 样板 | 出现次数 | 说明 |
|---|---|---|
| `sys.path.insert(0, ...)` | **15** | 每文件一次，两种写法 |
| 假 DB 类定义 | **11** | 见 §4-B3 |
| `setUp` 里清 `_jobs`/`_queue` + `tearDown` 再清 | **3 对** | `test_batch_inference_async.py:210-216`、`test_report_export_async.py:166-174`、`test_report_generate_async.py:40-48` |
| `with patch("app.db.SessionLocal", return_value=db)` | **7 次** | 4 个 runner 测试文件 |
| `_response(metrics)` 构造 Mock HTTP 响应 | 1（封装良好，`test_training_metrics_contract.py:14`） | — |

### 5.4 魔法数字 / 魔法字符串

| 值 | 出现位置 | 语义 | 建议 |
|---|---|---|---|
| `"t" * 40` / `"p" * 40` | `test_ai_service.py:32`、`test_security_boundaries.py:148` | `AUTH_SESSION_PEPPER` 的最小长度（40） | 具名 `PEPPER`（值本身无害，重复即风险：若生产把下限从 40 改成 64，测试仍会通过——**测试没有覆盖「pepper 太短应报错」**） |
| `99999` | `test_batch_inference_async.py:282,291`、`test_report_export_async.py:240,249`、`test_report_generate_async.py:131,140` | 「远超 TTL 的过期秒数」 | 具名 `ANCIENT = 99999` |
| `idle_exit_seconds=0` / `=1`、`time.sleep(0.1)`、`deadline = +5`、`timeout=1`、`time.sleep(2)` | `test_report_export_async.py:102,111,116-118,129,142,150,159-162` | 渲染线程空闲退出/超时的时序 | 见 §6-D6（flaky 源） |
| `0.5 / 0.6 / 0.8 / 0.9`（阈值）、`0.91 / 0.948`（概率） | `test_report_content.py:245,264,282-283,286`、`test_security_boundaries.py:101` | 风险等级阈值与概率样例 | 可接受（断言的就是具体口径） |
| `limit=10` | `test_report_content.py:156,166,173,185` | 重点事件截断条数 | 可接受 |
| `80 / 8 / 51 / 280` | `test_scenario_config.py:23,30-32,41` | 4 个场景的特征数 | **重复两遍**（第 30-32 行与第 41 行各写一次）→ 应具名或抽常量；见 §6-D4 |
| `"1.0"` | `test_explanation_audience.py:148`（`prompt_version`）、`test_explanation_contract.py:30`（`contract_version`） | 契约版本 | 可接受，但 `"1.0"` 硬编码使契约版本升级时测试静默通过/失败难以定位 |
| `"network_security"` | `test_report_content.py:76`、`test_security_boundaries.py:119`、`test_explanation_audience.py:82`、`test_model_evaluation.py:61` | 场景 code | 可接受 |
| 模型/数据集 id `34 / 20 / 30 / 7 / 1 / 2 / 3 / 55 / 101` | 遍布 | 桩数据主键 | 可接受（桩数据本就随意） |

### 5.5 深层嵌套 / 复杂三元

无。最深嵌套是 `test_ai_service.py:149-172` 的 `for` + `try/finally` + `with`（3 层），可读。
`test_discretization_applicability.py:126-134` 的 `_service()` 里有一串 `Mock()` 赋值（6 行），属**打桩清单**，可读性可接受但隐藏了「这个测试不验证鉴权」这一事实（见 §6-D9）。

**结论 C：测试分区无复杂度问题。唯一值得拆的是 `test_report_export_async.py`（537 行 / 6 主题），但受 §1.7 限制只能提案。**

---

## §6 D 测试自身的正确性隐患

### D1 硬编码凭据

**存在硬编码测试凭据字面量，但均为测试专用假值，仓库中无真实密钥。**（按协议 §3.D「不要打印密钥内容」，以下只给位置与性质，不复制字面量。）

| 位置 | 性质 |
|---|---|
| `test_ai_service.py:32` | `setUp` 中把 `AUTH_SESSION_PEPPER` 环境变量设为 40 字符的重复字符假值 |
| `test_security_boundaries.py:148` | `setUp` 中设 `AUTH_SESSION_PEPPER` 为另一个 40 字符假值 |
| `test_ai_service.py:69, 91, 124, 158` | `_fernet().encrypt(...)` 加密一段固定的假 API key 字面量 |
| `test_security_boundaries.py:177` | 加密一段形如 `sk-...` 的假 key，用于断言掩码格式（`"sk-t...1234"`） |

**真正的隐患不是「有凭据」，而是「环境变量被写入后不还原」**：
两个文件在 `setUp` 里 `os.environ["AUTH_SESSION_PEPPER"] = ...`，**没有任何 `tearDown` 恢复原值**。这是**进程级全局可变状态**（见 D8）。当前靠「按文件名排序时后跑的文件会覆盖前一个」侥幸不出问题，但**任何执行顺序变化（`-p no:randomly` 之外的插件、`-k` 过滤、单文件单跑）都可能让 fernet 密钥与加密时的密钥不一致**，从而让 `_openai_stream` 相关断言失败。

### D2 硬编码端口 —— **无风险，这是本分区的一个正面结论**

`grep -rn "12312\|12313\|localhost:\|127.0.0.1" backend/tests` → 只有 4 处 `http://127.0.0.1:{port}/v1`，其中 `port` 来自 `server.server_address[1]`。
所有 mock HTTP 服务都用 `serve(port=0)`（`test_ai_service.py:64, 86, 116, 150`）→ **由内核分配临时端口**。
**不存在与生产 `12312` / 备用 `12313` 抢端口的风险，也不存在并发测试互相抢端口的问题。** 这是教科书式做法。

### D3 依赖真实 DB —— **无**

没有任何测试连接真实数据库。全部通过以下两种方式隔离：
- 手写会话桩（11 处，见 §4-B3）；
- `patch("app.db.SessionLocal", return_value=db)`（4 个 runner 测试文件共 7 处）或 `patch("app.services.training_runner.SessionLocal", ...)`（`test_training_async.py:183, 196, 203`）。

**副作用**：`models/**`（约 400 行 ORM 定义）因此**零覆盖**——字段名写错、关系配错、`nullable` 不匹配都不会被发现。这是隔离的代价，见 §2.3-6。

### D4 依赖真实文件路径

| 位置 | 依赖 | 风险 |
|---|---|---|
| `test_scenario_config.py:17` | `CONFIG_PATH.read_text()` —— 读取**生产**场景配置文件，并断言 `network_security` 有 80 个必需特征、`power_system` 8 个、`geological_risk` 51 个、`flightdeck_operation` 280 个 | **中**：这是对**生产配置内容**的锁定，不是对行为的锁定。运维/产品增删一个特征就会红，而测试名（`test_registered_scenario_configs_are_complete`）看起来像在测「配置完整性校验」 |
| `test_explanation_contract.py:22` | `tests/fixtures/unified_explanation_samples.json` | **无风险**：fixture 就在测试目录内，随测试一起版本化 |
| `test_discretization_applicability.py:144` | `file_path="data/x.arff"` | **无风险**：`_validate_dataset_file` 已被打桩，路径从不被打开 |
| `test_training_metrics_contract.py:39, 56` | `patch("app.services.training_executor.os.path.exists", return_value=True)` | **无风险**：显式打桩 |

### D5 依赖系统时间 —— **低风险**

`time.time()`（6 处）、`time.monotonic()`（`test_report_export_async.py:116-117`）、`datetime.now(timezone.utc)`（`test_training_async.py:189, 201`、`test_security_boundaries.py:156`）。
全部用于**相对**时间运算（`now() - timedelta(hours=3)`、`time.time() - 99999`、`monotonic() + 5`），**没有一处依赖「今天是几号」或跨时区**。`test_report_content.py` 里的固定日期 `datetime(2026, 9, 1, ...)` 是桩数据，只被格式化输出，不参与比较。**无时间炸弹。**

### D6 `sleep()` 等待 —— **2 处，是唯一的 flaky 源**

| 位置 | 写法 | 风险 |
|---|---|---|
| `test_report_export_async.py:116-120` | `deadline = time.monotonic() + 5`，然后 `while renderer.is_ready() and time.monotonic() < deadline: time.sleep(0.1)`，最后 `assertFalse(renderer.is_ready(), "空闲超时后渲染线程应已退出")` | **中**：`idle_exit_seconds=1` 与 5 秒上限之间余量 4 秒。CI 满载时若渲染线程的 `select`/`Event.wait` 被调度延迟超过 4 秒，该断言会**假失败**。属「轮询等待」而非「固定 sleep」，已是较优写法，但仍有时序依赖 |
| `test_report_export_async.py:158-162` | `patch.object(FakePage, "pdf", side_effect=lambda **_kw: time.sleep(2))` 配合 `renderer.render("<html/>", timeout=1)` → 断言 `TimeoutError` | **低**：故意制造超时，逻辑正确。副作用是**测试结束后仍有约 1 秒的渲染线程在 `sleep`**（daemon 线程，随进程结束回收，不影响其他测试） |

另有真实线程与真实 HTTP 服务：`test_ai_service.py` 的 4 个测试各自起 `HTTPServer` + `Thread`，并在 `finally` 里 `shutdown()/server_close()/join(timeout=2)` —— **清理完整**，属良好实践。

### D7 `TestClient` / 应用启动副作用 —— **本分区最重要的一条**

**事实 1：全库零 `TestClient`**（`grep -rn "TestClient" backend/tests` → 0 命中），因此「未用 context manager 导致 lifespan 不触发」这一常见问题**在此不适用**——没有任何 ASGI 请求被发出。

**事实 2：但 `app.main` 的 import 期副作用确实被触发，且有 5 个测试文件会触发它。**
`backend/app/main.py:157` 是 `app = create_app()`（**模块级调用**），而 `create_app()`（`main.py:134-154`）依次执行：
```
_warm_dataset_caches_async()      # 预热线程
_start_report_scheduler()         # 定时报告调度器
_start_training_runner()          # 训练执行器
_start_batch_inference_runner()   # 批量研判执行器
_start_export_job_runner()        # 导出渲染执行器
_start_report_generate_runner()   # 报告生成执行器
```
`test_application_structure.py:7`、`test_batch_inference_async.py:305`、`test_training_async.py:221`、`test_report_export_async.py:526`、`test_report_generate_async.py:214` 都写 `from app.main import app` → **import 即启动上述 6 个后台组件**。

**事实 3：守卫的实际行为（已逐行核对 `app/utils/common.py:35-47`）**

```python
def running_under_test_runner() -> bool:
    spec = getattr(sys.modules.get("__main__"), "__spec__", None)
    if getattr(spec, "name", None) in ("unittest.__main__", "pytest", "pytest.__main__"):
        return True
    argv0 = os.path.basename(sys.argv[0] or "")
    return argv0.startswith("test_") and argv0.endswith(".py")
```

| 调用方式 | `__main__.__spec__.name` | `argv[0]` 基名 | `running_under_test_runner()` | 后台 runner |
|---|---|---|---|---|
| `python -m pytest tests -q`（**Lead 的基线**） | `"pytest"` | `.../pytest/__main__.py` | **True** ✅ | 全部不起 ✅ |
| `python -m unittest discover` | `"unittest.__main__"` | `.../unittest/__main__.py` | **True** ✅ | 全部不起 ✅ |
| `python tests/test_x.py` | `None` | `test_x.py` | **True** ✅（argv 兜底） | 全部不起 ✅ |
| **`pytest tests -q`（console script）** | `None`（脚本 `__main__` 无 spec） | `pytest.exe` / `pytest` | **False** ❌ | **6 个组件全部启动** ❌ |

`main.py:69-74` 额外检查了 `"pytest" in sys.modules`，所以**预热线程**在 console script 下仍被拦住；
但 **5 个 runner 只检查 `running_under_test_runner()`**（`batch_inference_runner.py:283`、`export_job_service.py:250`、`report_generate_runner.py:227`、`report_scheduler.py:63`、`training_runner.py:182`），**在 `pytest` console script 下会真的起来**。

**后果（若以 `pytest` 而非 `python -m pytest` 运行）**：
1. `test_batch_inference_async.py:298`、`test_training_async.py:211`、`test_report_export_async.py:256`、`test_report_generate_async.py:68` 的 `assertFalse(<runner>.is_running())` **会失败**（4 条断言）。
2. 更严重：`report_scheduler` 与 `training_runner` 会连**真实数据库**；`training_runner.reap_stale()` 会把真实 DB 里停留超时的 `TRAINING` 行**改成 FAILED**（`test_training_async.py:188-192` 正是这条逻辑的测试）。**这会真的改数据。**

**判定**：这不是测试代码的 bug（守卫实现在 `app/**`，属其他代理范围），而是**测试套件的运行方式约束**。
**当前基线（`python -m pytest`）下守卫有效，177 passed 可信。** 但套件**对调用方式敏感**——这正是「换个方式跑就崩」的典型形态。
**处置：只报告，不改**（修 `running_under_test_runner()` 属 `app/utils/common.py`，在 B6b-1 写作用域内）→ 见 §8-P4。
**同时给出零风险建议（在测试写作用域内、但会改断言语义故不实施）**：在 4 个 `test_submit_is_rejected_before_start` 断言前显式 `patch(...is_running, return_value=False)`，或由 Lead 在文档中固定「必须 `python -m pytest`」。

### D8 测试之间共享可变状态

| 状态 | 位置 | 是否清理 | 评估 |
|---|---|---|---|
| `os.environ["AUTH_SESSION_PEPPER"]` | `test_ai_service.py:32`（`setUp`）、`test_security_boundaries.py:149`（`setUp`） | **❌ 从不恢复** | **隐患**：进程级全局；见 D1 |
| `batch_inference_runner._jobs` / `_queue` | `test_batch_inference_async.py:210-216` | ✅ `setUp`+`tearDown` 双清 | 但 **`SubmitTests`（同文件 178-206 行）与 `RouteWiringTests` 不清**——`SubmitTests` 不读全局队列，目前无害；`test_batch_inference_async.py:204` 用字面量 `"nope"` 查任务，安全 |
| `export_job_service._jobs` / `_queue` | `test_report_export_async.py:166-174`、`265-272` | ✅ 两个类都清 | 良好 |
| `report_generate_runner._jobs` / `_queue` | `test_report_generate_async.py:40-48`（`JobStoreCase` 基类） | ✅ 全部子类继承清理 | 良好（唯一用了共享基类的文件） |
| `sys.path` | 15 个文件各 `insert` 一次 | 不清理（无需） | 无害（插入幂等，只增不删） |
| 真实 DB | 无 | — | ✅ 无污染风险 |
| 真实文件 | 仅 `CONFIG_PATH` 只读 | — | ✅ 无写入 |
| 模块级 `_PdfRenderer` 实例 | 均为测试内局部变量 | 随函数回收 | 但会派生真实线程；`idle_exit_seconds=0` 使其立即退出，`=1` 时 1 秒后退出 |

**结论**：**没有测试依赖「另一个测试先跑」**（无顺序耦合）。唯一的全局泄漏是环境变量，且它恰好不改变结论（两个文件各自设定、各自使用）。**「177 passed」的可信度不因共享状态打折。**

### D9 mock 掉了被测对象本身 / 打桩隐藏了守卫

**没有「测 mock 而非测代码」的假测试。** 逐一核对全部 `patch` 目标（共 60+ 处）：打桩对象一律是**协作者**（`_openai_stream`、`requests.post`、`SessionLocal`、`html_to_pdf`、`build_export`、`_run_algorithm_training`、`row_to_dict`），**没有一处 patch 掉被测函数本身再断言该 patch**。

但有 **2 处打桩顺带关掉了安全守卫**，使「鉴权」在这些测试里从未被执行：

| 位置 | 被打桩的守卫 | 后果 |
|---|---|---|
| `test_discretization_applicability.py:132` | `service.require_scenario_admin_of = Mock()` | `ModelVersionService.create` 的**场景管理员校验从未在测试中执行**。该测试只验证「离散化参数该不该落库」，这是合理的单元测试边界；但**「谁能调 create」无人验证** |
| `test_batch_inference_async.py:53-56` `target_patch()` | `InferenceRecordService._resolve_target` | 同上：**目标解析里的场景/数据集权限判定未被覆盖**。`test_security_boundaries.py` 覆盖的是 `_require_record_access`（读取），**创建/推理路径的权限判定无覆盖** |

**这不是缺陷，是覆盖边界**——但正因为它们被打桩，「权限」这一块在 service 层也并非全覆盖。建议 Lead 知悉：**创建/推理路径的越权测试缺失**。

### D10 宽松异常断言

`test_security_boundaries.py:162`：
```python
with self.assertRaisesRegex(Exception, "未登录"):
    get_current_session(_Request({}), _SessionDb(self.session), None)
```
`test_security_boundaries.py:170`：
```python
with self.assertRaisesRegex(Exception, "CSRF"):
    get_current_session(request, db, "wrong-token")
```
捕获裸 `Exception`。若 `get_current_session` 因**其他**原因（如 `AttributeError: 'NoneType' object has no attribute ...`，或 `TypeError`）抛出且消息恰好含该子串，断言仍通过。
**实际风险低**（消息串很具体），但比 `assertRaises(HTTPException)` 弱。
**只报告，不改**：收紧为 `HTTPException` 会改变断言语义，属协议 §3.E 禁区。

### D11 只断言 `code` 不断言内容的「空壳断言」—— **仅 2 处，且均为合理**

| 位置 | 断言 | 评估 |
|---|---|---|
| `test_batch_inference_async.py:187` | `assertEqual(resp.code, 503)`（runner 未启动） | 合理：该分支的语义就是「拒绝」，无 data 可断言。可补 `resp.message` 但非必需 |
| `test_report_export_async.py:308` | `assertEqual(resp.code, 503)`（PDF 需要 runner） | 同上 |

**没有「只断言 `code == 0`」的壳测试**：全部 177 个测试函数中，凡是断言 `code == 0` 的，都同时断言了 `data[...]` 的具体内容（例如 `test_batch_inference_async.py:88-95` 连 `items` 的逐条 `error` 都断言了）。

### D12 断言恒真 / 放水 —— **0 处**

AST 全量扫描确认：
- **0 处** `assert True` / `self.assertTrue(True)`；
- **0 处** `assert x is not None` 且 x 由字面量构造（所有 `assertIsNotNone` 的对象都来自可能返回 `None` 的查表：`_jobs[...]`、`validate_params_schema(...)`、`get_job(...)`）；
- **0 处** `status_code in (200, 400, 500)` 式「失败也放过」的写法（全库无 `status_code` 断言，因为无 HTTP 测试）；
- 反向证据：`test_batch_inference_async.py:92-95` 断言 `[i["error"] for i in items] == [None, "预测服务不可用", None]`、`test_report_content.py:179-180` 同时断言 `assertIn("共 12 起")` **与** `assertNotIn("共 10 起")`、`test_explanation_audience.py:107-108` 断言 `assertIn("先确认输入事实", reasoning)` **与** `assertNotIn(..., content)` —— 这类「正反双向断言」在套件里反复出现，是高质量测试的标志。

### D13 与本次重构的交叉核对（任务书 C 项）

**结论：0 条断言因本次重构而失效。** 但存在一批「行为保持型重构也会踩到的绊线」。B1–B7 必须把它们当作契约。

| 测试文件 | 锁死的东西 | 对哪个重构代理是约束 |
|---|---|---|
| `test_report_content.py:81-89, 94-102` | `_build_report_data(title=, scenario_id=, scope=, role=, current_user=, events=, records=)` **全部关键字名**；`_render_content(report_data)`、`_data_notes(..., thresholds=, scenario_id=)`、`_key_events(events, records, limit=, thresholds=)` 的签名 | **B2**：私有方法参数名不可改 |
| `test_report_content.py:107-109, 179, 191, 202-204, 215, 251-252, 268-270, 282-284` | **精确 Markdown 文案**：`## 七、态势分析`、`## 八、风险规避指导`、`## 九、数据说明`、`重点风险事件（共 12 起，下列为概率最高的 10 起）`、`风险样本平均概率：0.948`、`中危 ≥ 0.6`、`高危 ≥ 0.9`、`系统默认值` | **B2**：**任何文案改动立即红** |
| `test_report_scope.py:117-118, 125-127, 134-136` | **`str(stmt)` 的 SQL 片段**：`dataset.visibility`、`model_version.status`、`inference_record.user_id`；以及「个人 scope 下语句数恰好为 2」 | **B2**：把 `_gather_events/_gather_records` 改成 `join(alias)` 或用 `Dataset.visibility` 经子查询别名，即使行为完全一致也会红。**这是最脆弱的一条** |
| `test_model_evaluation.py:126` | `assertEqual(db.commits, 2)  # model attributes + evaluation` | **B1/B3**：评估路径上任何 `commit()` 的增删（即使语义等价）都会红 |
| `test_batch_inference_async.py:105, 117, 127, 184-202, 246, 248` | `create_inference(..., input_features=)` 的 **kwarg 名**、`_run_batch(..., on_progress=)`、`run_batch_job(..., on_progress=)`、`create_job(user_id=, model_version_id=)`、`_jobs[job_id].samples`（**私有 dataclass 字段名**）、`STATUS_*` 常量名 | **B3** |
| `test_training_async.py:87-90, 103, 120, 133, 156-157, 167, 177, 184, 212-218` | 精确消息 3 条；`evaluation_metrics` 的**整字典相等**（`{"source":"error","error":"java 不可达"}` → 不可加键）；`reap_stale(minutes)`、`_worker_count(n)`、`submit(model_id)`；`patch("app.services.training_runner.SessionLocal")` 要求 `SessionLocal` 保持为**模块级名字** | **B3**：若改成 `from app import db` + `db.SessionLocal()`，测试直接 error |
| `test_training_metrics_contract.py:39-40, 56-57, 71, 82-84` | `patch("app.services.training_executor.os.path.exists")` / `.requests.post` → 要求 `os`/`requests` 保持模块级名字；`ModelVersionService.__new__(...)` + `_visible_metrics(model, user)` 必须**不依赖 `__init__` 状态** | **B3** |
| `test_ai_service.py:40, 43, 53-55, 141, 167-168` | 事件元组的**整字典相等**：`("start", {"status": "开始分析"})`、`("done", {"status": "已使用规则模板完成", "source": "fallback"})`、`error["reason_code"]` 的 4 个字面量 | **B2/B6b-1**：事件 payload **不可加字段** |
| `test_ai_service.py:47, 137, 172` 等 | `patch("app.services.explanation_service._openai_stream")` → `_openai_stream` 必须保持模块级名字 | **B4** |
| `test_security_boundaries.py:25-29, 111-116`、`test_explanation_audience.py:57-67`、`test_model_evaluation.py:28-38`、`test_training_async.py:33-39`、`test_discretization_applicability.py:154-160` | 假 DB 按 **`model_type.__name__` 字符串** 分派：`"ModelVersion"`、`"Dataset"`、`"InferenceRecord"`、`"UserAISetting"`、`"Algorithm"`、`"Scenario"`、`"AppUser"` | **B6b-2**：**ORM 类不可改名**（否则 5 个文件的桩全部失效） |
| `test_security_boundaries.py:89-93`、`test_explanation_audience.py:132-140` | `InferenceRecordService._saved_explanation_for_role(record, role)` 的**方法名与调用形态**（一个当静态方法调、一个当实例方法调） | **B3** |
| `test_explanation_audience.py:148` | `artifact["prompt_version"] == "1.0"` | **B3/B4** |
| `test_discretization_applicability.py:163` | `service.db.add.call_args[0][0].training_parameters` → 要求 `db.add()` **位置传参**且属性名不变 | **B3** |
| `test_model_evaluation.py:209` | `patch("app.services.model_version_service.row_to_dict")` → 该名字必须仍在 `model_version_service` 命名空间 | **B3** |
| `test_scenario_config.py:10` | `from app.services.explanation_service import CONFIG_PATH, get_scenario_config` → **`CONFIG_PATH` 必须继续从 `explanation_service` 再导出** | **B4/B6b-1**：若把 `CONFIG_PATH` 移回 `config.py` 而不保留再导出，测试 import 失败 |
| `test_discretization_applicability.py:21-25` | `from app.utils.common import dataset_has_numeric_features, strip_inapplicable_params, validate_params_schema` → 这 3 个函数**必须留在 `app.utils.common`** | **B6b-1** |
| `test_security_boundaries.py:14, 149` | `from app.utils.auth import digest_token` + 运行时改 `AUTH_SESSION_PEPPER` 环境变量 → **pepper 必须在调用时读环境变量，不能在 import 期缓存成常量** | **B6b-1** |
| `test_application_structure.py:11-31` | 16 条路由路径必须存在（含 8 条遗留） | **B6a/X1**：见 §8-P1 |
| 5 个文件的 `from app.main import app` | `app.main` 必须能在**无 DB、无网络**的进程里 import 成功，且 import 期副作用必须被守卫拦住 | **B6b-1**：见 D7 |

**最可能因「正确的重构」而误红的三条**（建议 Lead 在 B2/B3 提交后优先复核）：
1. `test_report_scope.py` 的 SQL 片段断言（`str(stmt)` 变化）；
2. `test_model_evaluation.py:126` 的 `db.commits == 2`；
3. `test_training_async.py:103/167` 的 `evaluation_metrics` 整字典相等。

**特别注意 `dataset_file_reader.py`（B6b-1 刚改）：零测试覆盖，改动完全无网。**

---

## §7 E 硬约束遵守

### 7.1 协议 §3.E「绝不允许削弱或删除任何仍然有效的测试断言」

**遵守。改动仅 2 行，均为未使用 import 的删除，零断言影响。**

```diff
diff --git a/backend/tests/test_ai_service.py b/backend/tests/test_ai_service.py
@@ -10,7 +10,6 @@ sys.path.insert(0, str(Path(__file__).parents[1]))
 from app.services.explanation_service import (
-    AISettingService,
     _classify_ai_error,
     _fernet,
     _openai_stream,
diff --git a/backend/tests/test_discretization_applicability.py b/backend/tests/test_discretization_applicability.py
@@ -8,7 +8,7 @@ import sys
 from types import SimpleNamespace
-from unittest.mock import Mock, patch
+from unittest.mock import Mock
```

```
$ git diff --stat -- backend/tests
 backend/tests/test_ai_service.py                   | 1 -
 backend/tests/test_discretization_applicability.py | 2 +-
 2 files changed, 1 insertion(+), 2 deletions(-)
```

- **删除项性质**：均为**纯残留**（未使用 import），符合任务书允许修改的全部条件（「删的是纯残留…且不影响任何断言的执行」）。
- **零引用证据**：见 §4.1（`grep` 输出 + AST 全量引用扫描）。
- **凡涉及断言本身的判断，一律只提案**：§8-P1（遗留路由断言改写）、§8-P3（脆弱绊线）、§6-D10（宽松异常断言）**均未改动一行**。
- **断言计数前后一致**：改前 462 条、改后 462 条（AST 统计）；测试函数数 177 前后一致。

### 7.2 写作用域边界

| 约束 | 状态 |
|---|---|
| 只改 `backend/tests/**` 的 15 个 `.py` + 本报告 | ✅ 只改了 2 个 `.py`（`test_ai_service.py`、`test_discretization_applicability.py`）+ 本报告 |
| 不改 `backend/alembic/**`（X2b） | ✅ 未触碰 |
| 不改 `backend/app/**`（其他代理） | ✅ 未触碰（`git status` 中 `backend/app/**` 的 M 全部来自其他代理，非本代理） |
| 不新增文件（报告除外）、不新增目录 | ✅ 未新增 |
| 不忽略 `__pycache__` 误判 | ✅ `__pycache__` 未入库（`git ls-files tests` = 16 条，不含 pyc），未删除、未纳入审查 |
| 不新建 `conftest.py` | ✅ 虽然识别出强需求（§4-B3/B5、§5.3），**遵守 §1.7 只提案**（§8-P2） |

### 7.3 禁止命令

| 禁止项 | 状态 |
|---|---|
| `pytest`（§1.3，Lead 统一跑） | ✅ **未运行**。基线 177 passed 直接引用 Lead 的确认值 |
| `npm run build` / `vite` / `npm run dev` / `preview` | ✅ 未运行 |
| 起/停服务（`uvicorn`、Java） | ✅ 未运行。测试内 `serve(port=0)` 的 mock HTTP 服务**未被本代理启动**（只在 pytest 执行时才起） |
| 写 `frontend/dist` / `node_modules/.vite` / 数据库 / `backend/lib/*.jar` | ✅ 未运行 |
| `git commit` / `checkout` / `stash` / `reset` / `clean` | ✅ 未运行（只跑了只读的 `git status` / `git diff` / `git ls-files`） |

### 7.4 允许的自验命令（协议 §1.4）

```
$ cd backend && python -m py_compile tests/test_ai_service.py tests/test_discretization_applicability.py
EXIT=0
```
**`py_compile` EXIT 码 = 0。**（改动的两个文件；其余 13 个文件未改动，无需编译。）

### 7.5 并发噪声说明（协议 §1.5）

`git status --short` 显示约 130 个文件被其他代理修改（`backend/app/**`、`frontend/src/**`、`backend/deprecated/**` 的删除）。
**这些均非本代理所为**，且**不影响本分区结论**——本报告的覆盖矩阵是按**当前工作区**的路由/模块清单统计的（111 路由、`app/**` 行数），若其他代理继续增删路由，§2 的计数需在收尾时刷新一次。已在 §9 记录。

### 7.6 未使用的工具与未做的事（诚实声明）

- **未运行 pytest**，因此**未实测**任何断言的通过/失败。所有「断言会/不会失效」的判断均为**静态阅读 + AST 分析**结论，非实测。
- **未启动服务**，因此未做端到端验证。
- §6-D7 的「console script 下守卫失效」结论来自 `app/utils/common.py:35-47` 的逐行阅读与 Python `__main__.__spec__` 语义推理，**未实测**（实测需以 `pytest` 运行，属禁止命令）。**建议 Lead 在收尾时用 `python -m pytest` 跑基线，不要用裸 `pytest`。**

---

## §8 跨区提案

> 协议 §1.2：本代理**不动手**，仅提案，由 Lead 串行裁决。
> 协议 §1.6：不改变跨文件公共接口。

### P1（最高优先，直接决定遗留簇能否下线）—— 改写 `test_application_structure.py` 的遗留路由断言

**这是唯一阻止删除遗留簇的东西。** 与本结论一致的独立取证：`B6a.md:202-209`、`B6b-1.md:365`（「唯一『保活』者是 `backend/tests/test_application_structure.py:11-27`」）、`B3.md:549`。

**原文（`backend/tests/test_application_structure.py:10-31`，逐字引用）：**

```python
class ApplicationStructureTests(unittest.TestCase):
    def test_current_and_legacy_routes_are_registered(self):
        paths = app.openapi()["paths"]
        expected = {
            "/api/v1/auth/login",
            "/api/v1/dashboard/admin/overview",
            "/api/v1/model-versions",
            "/api/v1/inference-records/predict",
            "/api/v1/risk-events",
            "/api/v1/risk-thresholds",
            "/api/v1/reports",
            "/api/v1/situation/global",
            "/china-map.json",
            "/api/model/dataset-list",
            "/api/model/save-threshold",
            "/api/model/train",
            "/api/model/infer",
            "/api/model/exp-records",
            "/api/model/exp/{record_id}",
            "/api/model/risk_statistics",
        }
        self.assertTrue(expected.issubset(paths))
```

**该断言锁定的是哪条产品行为**：它锁定的**不是**遗留接口的可用性，而是**「这 16 条路由在 FastAPI 应用里被注册了」这一结构性事实**。其中 9 条（8 个 v1 + `/china-map.json`）当前仍在服务，7 条 `/api/model/*` 是遗留兼容层。

**为什么「遗留簇」这条产品行为可能不再成立**：
- `frontend/src` 对 `/api/model/`、`china-map`、`risk_statistics` 的 grep → **0 命中**（本代理独立复核，与 `B6b-1.md:365`、`B6a.md:233` 一致）；
- `B6a` 已判定其中 `GET /api/model/risk_statistics` **返回硬编码假数据**当真实接口（P1 级问题）、`POST /api/model/infer` **任何登录用户可调**（P2）、`POST /api/model/save-threshold` 改的是**进程级全局阈值**；
- 与 v1 链路存在**两套阈值来源 + 两套等级词表**（`B3.md:220`）。

**删除它会失去什么保护（这是不能直接删的原因）**：
`self.assertTrue(expected.issubset(paths))` 是**整个测试套件里唯一**证明以下 9 条现行路由被注册的自动化证据：
`/api/v1/auth/login`、`/api/v1/dashboard/admin/overview`、`/api/v1/model-versions`、`/api/v1/inference-records/predict`、`/api/v1/risk-events`、`/api/v1/risk-thresholds`、`/api/v1/reports`、`/api/v1/situation/global`、`/china-map.json`。
**直接删掉整条断言 = 连现行路由的注册保护一起丢掉。** 所以**必须拆，不能删**。

**提案（若产品决定下线遗留簇）：把一条断言拆成两条，一条保现行、一条反向锁遗留必须消失。**

```python
class ApplicationStructureTests(unittest.TestCase):
    def test_current_routes_are_registered(self):
        paths = app.openapi()["paths"]
        expected = {
            "/api/v1/auth/login",
            "/api/v1/dashboard/admin/overview",
            "/api/v1/model-versions",
            "/api/v1/inference-records/predict",
            "/api/v1/risk-events",
            "/api/v1/risk-thresholds",
            "/api/v1/reports",
            "/api/v1/situation/global",
        }
        self.assertTrue(expected.issubset(paths))

    def test_legacy_compat_routes_are_gone(self):
        """遗留兼容簇已下线：前端零调用，且存在假数据与越权问题（见 B6a/B6b-1）。"""
        paths = set(app.openapi()["paths"])
        legacy = {
            "/china-map.json",
            "/api/model/dataset-list",
            "/api/model/save-threshold",
            "/api/model/train",
            "/api/model/infer",
            "/api/model/exp-records",
            "/api/model/exp/{record_id}",
            "/api/model/risk_statistics",
        }
        self.assertFalse(legacy & paths, f"遗留接口应已下线，但仍注册: {sorted(legacy & paths)}")
```

**若产品决定保留遗留簇**：则**保留原文不动**，并在 `legacy_model_routes.py` 顶部注明「由 `tests/test_application_structure.py` 显式锁定，删除需产品裁决」。两条路都**不需要删除任何断言**。

**风险与替代方案**：
- 风险：`/china-map.json` 可能被浏览器当静态资源直接取用（`B6a.md:251` 已提示）。若保留它，把它从 `legacy` 集合移到 `expected` 集合即可。
- 不改的替代方案：维持现状（遗留簇继续挂着，接受 `B6a` 记录的 P1/P2 风险）。
- **本代理未实施**：改动涉及断言语义（拆分/反向断言），属协议 §3.E 禁区。

### P2（测试基建）—— 上提 `backend/tests/conftest.py`，消除 15 次 `sys.path` 注入 + 11 个重复假 DB

**问题**（§4-B3/B4/B5、§5.3）：`sys.path.insert` 重复 15 次（两种写法）；11 个文件各自实现会话桩（6 个连类名都叫 `FakeDb`）；`make_model()` 在 3 个文件同名不同义。

**提案**：新建 `backend/tests/conftest.py`（或 `backend/tests/__init__.py` + `pyproject.toml` 的 `[tool.pytest.ini_options] pythonpath = ["."]`），内容为：

```python
# backend/tests/conftest.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
```

（假 DB 桩因各文件形状不同，**不建议**强行合并成一个——合并会引入 5 个未用方法的胖桩，反而更难读。建议只上提 `sys.path` 这一段，以及一个 `make_session_stub(**capabilities)` 工厂。）

**为什么非改不可**：当前每个文件都靠「自己插路径」才能 import `app`，任何新测试文件漏写就 error；两种写法不统一；且**没有 `conftest.py` 意味着没有任何全局 fixture/teardown 钩子**，这正是 §6-D1（环境变量不还原）无法优雅修复的原因。

**不改的替代方案**：保持现状（可用，但每新增一个测试文件都要复制 1 行样板）。

**协议冲突**：§1.7「不新建文件」——**本代理不能实施**，需 Lead 裁决后统一创建。

### P3（测试健壮性，纯提示）—— 3 条「行为保持型重构也会误红」的绊线

**问题**（§6-D13）：
1. `test_report_scope.py:117-118, 125-127, 134-136` 断言 `str(stmt)` 里的 SQL 片段（`dataset.visibility` 等）；
2. `test_model_evaluation.py:126` 断言 `db.commits == 2`；
3. `test_training_async.py:103, 167` 用**整字典相等**断言 `evaluation_metrics`。

**提案（仅提示，不建议本次改）**：这三条都是**有效的**断言（它们锁的是真实口径），但会在 B2/B3 **行为等价**的查询/事务重写时误红。建议：
- 把 1 改为断言**行为**（用 `CapturingDb` 捕获后检查结果集过滤，或直接断言 `_gather_records` 的返回内容）——**但这是削弱断言强度，需 Lead 判断是否值得**；
- 把 2 改为 `assertGreaterEqual(db.commits, 2)` ——**同样是削弱**；
- 把 3 改为断言子集 ——**同样是削弱**。

**本代理的立场**：**不建议改**。这三条绊线是**特性不是缺陷**：它们能在 B2/B3 无意的语义漂移时立刻报警，代价只是重构时要同步确认。**仅要求 B1–B7 知悉：看到这三条红，先确认行为是否真的没变，再决定改代码还是改测试。**

### P4（`app/**`，B6b-1 写作用域）—— `running_under_test_runner()` 在 `pytest` console script 下失效

**问题**（§6-D7 实测推理）：
`backend/app/utils/common.py:35-47` 的 `running_under_test_runner()` 只认 `__main__.__spec__.name` 与 `sys.argv[0]` 基名。
在 **`pytest tests -q`（console script）** 下，`__main__.__spec__` 为 `None`、`argv[0]` 基名为 `pytest.exe` → **返回 `False`**。
而 5 个后台 runner 只检查它（`batch_inference_runner.py:283`、`export_job_service.py:250`、`report_generate_runner.py:227`、`report_scheduler.py:63`、`training_runner.py:182`）→ **会真的启动并连真实 DB**；`training_runner.reap_stale()` 会把真实库里超时的 `TRAINING` 行改成 `FAILED`。

**精确 diff 提案**（`app/utils/common.py:35-47`）：

```diff
 def running_under_test_runner() -> bool:
     """当前进程是否由测试框架启动（``python -m unittest`` / ``python -m pytest``）。"""
     spec = getattr(sys.modules.get("__main__"), "__spec__", None)
     if getattr(spec, "name", None) in ("unittest.__main__", "pytest", "pytest.__main__"):
         return True
+    # ``pytest`` 以 console script 方式启动时 ``__main__`` 是入口脚本、无 ``__spec__``，
+    # 且 ``sys.argv[0]`` 基名是 ``pytest``/``pytest.exe``，走不到下面的文件名兜底。
+    # 只看 ``"pytest" in sys.modules`` 是安全的：测试进程必然已导入 pytest。
+    if "pytest" in sys.modules:
+        return True
     argv0 = os.path.basename(sys.argv[0] or "")
     return argv0.startswith("test_") and argv0.endswith(".py")
```

**影响面**：`app/utils/common.py` 是 6 个调用点的唯一判定源；新增分支只会在「pytest 已导入」时返回 True，**生产环境（uvicorn/gunicorn）不会导入 pytest，行为不变**。与 `main.py:71` 现有的 `"pytest" in sys.modules` 判断口径一致。
**为什么非改不可**：不改则「177 passed」这个结论**依赖调用方式**；换个跑法不仅 4 条断言红，还会**真改数据库**。
**不改的替代方案**：在团队/CI 文档里硬性规定「必须 `python -m pytest`」（零代码改动，但靠纪律）。**Lead 二选一即可**；若选文档方案，建议同时在本报告 §6-D7 处留档。

### P5（`app/services/**`，B3/B5 写作用域）—— 4 个 runner 复制同一套任务表

**问题**：`batch_inference_runner`（242 行）、`export_job_service`（208 行）、`report_generate_runner`（191 行）、`training_runner`（162 行）各自实现 `_jobs` / `_jobs_lock` / `_queue` / `STATUS_*` / `create_job` / `get_job` / `list_jobs` / `_purge_expired` / `is_running` / `start`。
**测试侧的镜像**：`JobStoreTests` 被复制 3 份（§4-B6）。

**提案**：抽出 `app/services/job_store.py`（泛型任务表），4 个 runner 复用之。
**影响面**：4 个 runner 的**公开函数签名必须保持不变**（`create_job` / `get_job` / `list_jobs` / `is_running` / `submit` / `_execute` / `STATUS_*` 常量名），因为测试直接断言它们（§6-D13 已列全）。
**不改的替代方案**：保持 4 份复制（当前测试各自锁各自的模块，风险可控）。
**本代理立场**：**中优先级**。收益是消掉约 300 行重复；风险是触碰 4 个有深覆盖的模块。若 B3 时间紧，**建议不做**。

### P6（测试覆盖，最高业务价值）—— 为 `dashboard_service` 的 P0 越权修复补回归网

**问题**（§2.3-1）：`dashboard_service.py` **1837 行、全项目最大 service、零测试**，而 Lead 刚在此做了 **P0 越权修复**。当前**没有任何自动化证据**能防止该修复被回退。

**提案**：至少补 3 条断言（**注意：新增断言属新测试，本代理无权实施，只能提案**；且 §1.7 禁止新建文件 → 需 Lead 决定追加到现有文件还是新建）：
1. `SUPER_ADMIN` 请求 `/api/v1/dashboard/scenarios/{id}/profile` 且该场景不属于自己可见范围 → 期望 403（**这正是 P0 修复点**）；
2. `SCENARIO_ADMIN` 请求非绑定场景的 `profile` → 期望 403；
3. `SCENARIO_USER` 请求 `workspace` → 只能看到本人数据（断言返回的计数/列表不含他人记录）。

**影响面**：纯新增，不改任何现有断言。
**不改的替代方案**：无（当前是裸奔）。

### P7（测试耦合，低优先）—— `test_scenario_config.py` 锁的是生产配置内容

**问题**（§6-D4）：`test_scenario_config.py:17` 读**生产** `CONFIG_PATH`，并硬编码 4 个场景的特征数（80 / 8 / 51 / 280，且在第 30-32 行与第 41 行**重复两遍**）。
**提案**：把 4 个数字抽成模块级常量（消除重复），并在测试 docstring 里写明「本测试锁定场景配置的特征数量口径，增删特征须同步更新此处」。
**不改的替代方案**：保持现状（能起「配置被误改」的哨兵作用，只是名字容易误导）。
**本代理立场**：**低优先，可选**。

### P8（覆盖缺口通报，供 Lead 排优先级）

零覆盖且与安全/数据正确性强相关的模块（§2.2），按风险排序建议补测顺序：
1. `services/dashboard_service.py`（1837 行，P0 修复点）← **P6**
2. `services/user_service.py`（332 行，改密/重置密码/禁用/删号）
3. `services/risk_threshold_service.py`（115 行，风险等级判定口径的**源头**）
4. `services/dataset_service.py`（488 行，含上传与可见性）
5. `utils/dataset_file_reader.py`（139 行，**B6b-1 刚改，改动完全无网**）
6. `utils/arff_reader.py`（252 行）
7. `models/**`（约 400 行 ORM 定义，因全部用 `SimpleNamespace` 桩替代而零覆盖）
8. `api/v1/endpoints/**`（2589 行，111 路由，**零功能测试**）

**特别提示**：第 5 项是**本次重构直接触碰且零覆盖**的文件，**B6b-1 的改动没有任何回归网**。若 B6b-1 改了 `dataset_file_reader.py` 的解析口径，**没有任何测试会红**。

---

## §9 未及细查

> 按任务书要求：「若步数不够，把剩下的放进 §9 并写清楚下一轮该查什么」。
> **本轮实际完成了 A→B→C→D→E 全五项**，无被迫中断的项。以下为**主动记录的边界与下一轮建议**。

### 9.1 本轮明确未做（附原因）

| # | 未做的事 | 原因 | 下一轮该查什么 |
|---|---|---|---|
| 1 | **未运行 pytest** | 协议 §1.3 明令禁止（Lead 统一跑基线）。基线 `177 passed, 6 subtests passed` 为**引用值** | Lead 收尾时以 **`python -m pytest tests -q`** 运行（**不要用裸 `pytest`**，见 §6-D7 / §8-P4）。若用裸 `pytest` 跑出 4 条 `assertFalse(...is_running())` 失败，那是 D7 的守卫漏洞，不是新回归 |
| 2 | **未实测 §6-D7 的守卫失效** | 实测需以 `pytest` console script 运行，属禁止命令。结论为**静态推理**（`app/utils/common.py:35-47` + Python `__main__.__spec__` 语义） | 若 Lead 想确证：`python -c "import sys; print(sys.modules['__main__'].__spec__)"` 对比 `python -m pytest --collect-only` 与 `pytest --collect-only` 下的取值 |
| 3 | **未验证 111 路由计数在其他代理改动后是否仍成立** | 其他代理正在并发修改 `backend/app/api/**`（`git status` 显示 15 个 endpoint 文件 + `legacy_model_routes.py` 均为 M） | 收尾时重跑一次 AST 路由提取（本报告 §2.1 的计数基于**审查当时**的工作区快照） |
| 4 | **未逐行审读 `app/**` 的实现正确性** | 越界（属 B1–B6 各代理）。本报告只从**测试视角**引用 `app/**` 的签名与守卫行为 | 各分区报告 |
| 5 | **未审 `scripts/mock_openai_server.py`** | 它在 `backend/../scripts/`，不在 X2a 写作用域（`backend/tests/**`），且它是**测试依赖**而非被测对象 | 若无其他分区认领，下一轮可补：该 mock 服务的响应是否真的覆盖 `_openai_stream` 需要的 SSE 格式（`test_ai_service.py:64-82` 依赖它） |
| 6 | **未审 `backend/tests/__pycache__/`** | 未入库的构建产物，任务书明示忽略 | 无需查。**建议 Lead 在收尾时确认它没有被误 `git add`** |
| 7 | **未检查测试覆盖率数字（line coverage）** | 需 `coverage`/`pytest-cov`（可能未安装，且运行 pytest 属禁止） | 若需要精确行覆盖率，Lead 在收尾跑 `python -m pytest tests --cov=app -q`（**会写 `.coverage` 文件，注意勿入库**） |
| 8 | **未验证 `test_scenario_config.py` 依赖的生产配置内容当前是否匹配** | 需运行 pytest | 该测试读**真实** `CONFIG_PATH`（§6-D4），若产品近期改过场景特征，这条会红——**这是它唯一可能的失败原因，且与本次重构无关** |
| 9 | **未审 `frontend/`** | 不在 X2a 写作用域 | 其他分区 |
| 10 | **未测 `models/**` 的 ORM 映射** | 零覆盖（§2.2）。本代理只能报告缺口，补测属新增断言（越界） | 见 §8-P8 第 7 项 |

### 9.2 本报告结论的可信度分级（诚实标注）

| 结论 | 证据强度 |
|---|---|
| 15 个测试文件 / 3024 行 / 177 个测试函数 / 462 条断言 / 0 跳过 / 0 死文件 | **强**（AST 全量扫描 + 与 Lead 的 `177 passed` 交叉一致） |
| 零 `TestClient`、零功能级 endpoint 覆盖、80 个 v1 endpoint 零覆盖 | **强**（`grep` 零命中 + `app.openapi()` 断言逐条溯源） |
| 16 个 service 模块零覆盖、约 4603 行 | **强**（AST 提取测试文件的 import 集合，与 `app/**` 模块清单求差） |
| 111 路由（103 v1 + 8 遗留） | **中强**（AST 提取 `@router.*` 装饰器；并发改动可能已使其变化，见 9.1-3） |
| §6-D13 的「绊线清单」 | **中强**（逐条 grep 断言文本，非实测） |
| §6-D7 的守卫失效结论 | **中**（静态推理，未实测，见 9.1-2） |
| §6-D6 的 flaky 风险评估 | **中**（基于 `time.sleep`/deadline 的数值分析，未在满载 CI 上复现） |
| 「零假测试」的判定 | **强**（60+ 处 `patch` 目标逐一核对 + 断言双向性抽样） |

### 9.3 下一轮（若有）建议的最短路径

1. **先跑 `python -m pytest tests -q` 确认 177 passed 未被本次 2 行改动破坏**（预期：仍然 177 passed）。
2. **确证 §6-D7**（一条命令，见 9.1-2）。
3. **刷新 §2.1 路由计数**（其他代理改完后）。
4. **裁决 §8-P1**（遗留簇去留）——这是唯一影响「能否删 600 行」的测试侧决策点。
5. **裁决 §8-P4**（守卫补丁 or 文档约定）。
6. **补 §8-P6**（`dashboard_service` P0 回归网）——业务价值最高。

---

## §10 `git status --short`

**执行位置**：仓库根 `D:\001Mine\009Code\project\security-bayes-situation-platform`
**执行命令**：`git status --short`

### 10.1 本代理改动（仅 2 个文件，均在 `backend/tests/**`）

```
 M backend/tests/test_ai_service.py
 M backend/tests/test_discretization_applicability.py
```

`git diff --stat -- backend/tests`：
```
 backend/tests/test_ai_service.py                   | 1 -
 backend/tests/test_discretization_applicability.py | 2 +-
 2 files changed, 1 insertion(+), 2 deletions(-)
```

**本代理新增的未跟踪文件**（报告，落在 `?? docs/全项目代码审查/` 之内）：
```
?? "docs/\345\205\250\351\241\271\347\233\256\344\273\243\347\240\201\345\256\241\346\237\245/"
```
（该目录整体未跟踪，内含 `审查协议.md`、`待裁决.md`、`报告/*.md` 等；本报告 `X2a.md` 在其中。）

### 10.2 完整输出（含其他代理的并发改动，**非本代理所为**）

```
 M README.md
 M backend/app/algorithms/pmwnb_demo.py
 M backend/app/api/deps.py
 M backend/app/api/legacy_model_routes.py
 M backend/app/api/v1/endpoints/ai_setting_routes.py
 M backend/app/api/v1/endpoints/auth_routes.py
 M backend/app/api/v1/endpoints/dashboard_routes.py
 M backend/app/api/v1/endpoints/dataset_routes.py
 M backend/app/api/v1/endpoints/explanation_routes.py
 M backend/app/api/v1/endpoints/inference_record_routes.py
 M backend/app/api/v1/endpoints/model_evaluation_routes.py
 M backend/app/api/v1/endpoints/model_version_routes.py
 M backend/app/api/v1/endpoints/report_routes.py
 M backend/app/api/v1/endpoints/risk_event_routes.py
 M backend/app/api/v1/endpoints/risk_threshold_routes.py
 M backend/app/api/v1/endpoints/scenario_routes.py
 M backend/app/api/v1/endpoints/situation_routes.py
 M backend/app/api/v1/endpoints/user_routes.py
 M backend/app/config.py
 M backend/app/main.py
 M backend/app/models/__init__.py
 M backend/app/models/app_user.py
 M backend/app/models/auth_session.py
 M backend/app/models/dataset.py
 M backend/app/models/report.py
 M backend/app/schemas/explanation.py
 M backend/app/schemas/explanation_contract.py
 M backend/app/schemas/report.py
 M backend/app/schemas/risk_event.py
 M backend/app/schemas/risk_threshold.py
 M backend/app/services/algorithm_service.py
 M backend/app/services/base.py
 M backend/app/services/batch_inference_runner.py
 M backend/app/services/constants.py
 M backend/app/services/dashboard_service.py
 M backend/app/services/dataset_service.py
 M backend/app/services/explanation_service.py
 M backend/app/services/export_job_service.py
 M backend/app/services/handling_record_service.py
 M backend/app/services/inference_record_service.py
 M backend/app/services/model_evaluation_service.py
 M backend/app/services/model_version_service.py
 M backend/app/services/report_export.py
 M backend/app/services/report_generate_runner.py
 M backend/app/services/report_scheduler.py
 M backend/app/services/report_service.py
 M backend/app/services/risk_event_service.py
 M backend/app/services/risk_threshold_service.py
 M backend/app/services/risk_view.py
 M backend/app/services/scenario_analytics.py
 M backend/app/services/scenario_service.py
 M backend/app/services/threshold_audit_log_service.py
 M backend/app/services/training_executor.py
 M backend/app/services/user_service.py
 M backend/app/utils/auth.py
 M backend/app/utils/common.py
 M backend/app/utils/dataset_file_reader.py
D  backend/deprecated/multi_source_crawler.py
D  backend/deprecated/scripts/add_dify_client.py
D  backend/deprecated/scripts/auto_restart_and_verify_backend.ps1
D  backend/deprecated/scripts/convert_events_to_structured.py
D  backend/deprecated/scripts/generate_events_network.py
D  backend/deprecated/scripts/replace_ai_client.py
D  backend/deprecated/scripts/run_rerun_check.py
D  backend/deprecated/scripts/test_dify.py
D  backend/deprecated/scripts/test_dify_simple.py
D  backend/deprecated/scripts/test_frequency.py
D  backend/deprecated/scripts/test_main_dify.py
D  backend/deprecated/scripts/update_llm_client.py
D  backend/deprecated/scripts/verify_opinion_apis.ps1
 M backend/tests/test_ai_service.py                       <-- 本代理
 M backend/tests/test_discretization_applicability.py      <-- 本代理
 M frontend/src/App.vue
 M frontend/src/api/datasetApi.ts
 M frontend/src/api/inferenceRecordApi.ts
 M frontend/src/api/reportApi.ts
 M frontend/src/api/riskThresholdApi.ts
 M frontend/src/api/scenarioApi.ts
 M frontend/src/api/situationApi.ts
 M frontend/src/components/common/DataPreviewTable.vue
 M frontend/src/components/dashboard/DashBars.vue
 M frontend/src/components/dashboard/DashEvents.vue
 M frontend/src/components/dashboard/DashKpis.vue
 M frontend/src/components/dashboard/DashScatter.vue
 M frontend/src/components/dashboard/DashTable.vue
 M frontend/src/components/dashboard/dash.css
 M frontend/src/router/guards.ts
 M frontend/src/router/index.ts
 M frontend/src/stores/batchJobStore.ts
 M frontend/src/stores/riskEventStore.ts
 M frontend/src/stores/trainingJobStore.ts
 M frontend/src/style.css
 M frontend/src/utils/request.js
 M frontend/src/utils/scrollAnchor.ts
 M frontend/src/utils/scrollChain.ts
 M frontend/src/views/Alert/AlertsView.vue
 M frontend/src/views/Event/RiskEventDetailView.vue
 M frontend/src/views/Home/dashboard/sections/ProfileFlightdeck.vue
 M frontend/src/views/Home/dashboard/sections/ProfileGeological.vue
 M frontend/src/views/Home/dashboard/sections/ProfileNetwork.vue
 M frontend/src/views/Home/dashboard/sections/ProfilePower.vue
 M frontend/src/views/Home/dashboard/sections/WorkspaceFlightdeck.vue
 M frontend/src/views/Login.vue
 M frontend/src/views/Model/DatasetCenter.vue
 M frontend/src/views/Model/InferenceRecords.vue
 M frontend/src/views/Model/ModelCenter.vue
 M frontend/src/views/Model/ReportCenter.vue
 M frontend/src/views/Model/RiskAnalysis.vue
 M frontend/src/views/Model/RiskInference.vue
 M frontend/src/views/Model/ScenarioCenter.vue
 M frontend/src/views/Model/Settings.vue
 M frontend/src/views/Model/UserManagement.vue
?? "docs/\345\205\250\351\241\271\347\233\256\344\273\243\347\240\201\345\256\241\346\237\245/"
?? "docs/\345\234\272\346\231\257\347\256\241\347\220\206\345\221\230\351\246\226\351\241\265\345\256\241\346\237\245/\351\207\215\346\236\204\346\212\245\345\221\212/"
```

### 10.3 说明

- **`backend/tests/**` 下只有 2 个文件被本代理修改**，diff 已逐字附于 §7.1。
- `backend/app/**`（约 55 个文件）与 `frontend/src/**`（约 45 个文件）的 `M` 状态**全部来自其他代理**，本代理未触碰。
- `backend/deprecated/**` 的 13 个 `D`（已暂存删除）来自其他代理。
- `git diff` 提示 `LF will be replaced by CRLF`：这是 Windows 换行符警告，**非错误**，不影响内容。
- **本代理未执行 `git add` / `git commit`**（协议 §1.3 禁止）。

---

**报告结束。X2a 已按协议完成 A→B→C→D→E 全部五项，改动 2 行（均为删除未使用 import），`py_compile` EXIT=0，未运行 pytest，未触碰任何分区外文件。**
