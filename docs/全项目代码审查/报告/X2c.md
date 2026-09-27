# X2c 分区报告 · `scripts/**` 全部 `.py`

> 分区范围：`scripts/**` 下**全部 13 个 `.py`**（共 1808 行）。
> **明确排除**：`scripts/build_all_jars.ps1`、`scripts/build_nb_algorithm_jars.ps1`、`scripts/build_pmwnb_jar.ps1`（归 X1b，本代理**未读未改**）。
> 代理：X2c　·　审查基线：`docs/全项目代码审查/审查协议.md` §1/§3/§4
> **结论先行：本分区 0 行代码改动**（原因见 §7），交付物是完整的「脚本存活性台账 + 交叉核对 + A–D 清单 + 跨区提案」。

---

## §0 速览

| 项 | 数值 |
|---|---|
| 分区内 `.py` 文件 | **13**（1808 行） |
| **活**（静态判断仍能跑通、有当前用途） | **6** |
| **部分失效**（有一步必崩 / 换机即失效） | **1**（`seed_test_data.py`） |
| **死 / 一次性历史脚本**（跑不通或与本项目无关） | **6** |
| 本分区内**必须修的正确性缺陷** | **1 个必崩**（`seed_test_data.py:220`，已用内存 SQLite 实证） |
| 本轮其他代理改动导致本分区脚本失效 | **0 个**（逐项核对，见 §2 末与 §4） |
| 代码改动 | **0 文件 / 0 行** |
| `python -m py_compile` | **13/13 EXIT=0** |
| 最危险项 | `seed_test_data.py:260` 覆盖写仓库内 `data/**`；`clean_tasks_history.py:148,153` 原地覆盖 `output/tasks.json`。**本分区无任何 `os.remove` / 无对仓库目录的 `shutil.rmtree`** |
| 跨区提案 | 3 条（§8）：X1b 的 3 个 `build_*.ps1`、`backend/app/services/model_sim.py` 与 `data/nf_unsw/sample_demo.csv` 的耦合、`risk_threshold` 复合主键取值的公共封装 |

---

## §1 范围与文件清单

改前行数 = 改后行数（本分区未改动任何代码）：

| # | 文件 | 行数 | 判定 |
|---|---|---|---|
| 1 | [backfill_dataset_samples.py](scripts/backfill_dataset_samples.py) | 98 → 98 | **活** |
| 2 | [clean_tasks_history.py](scripts/clean_tasks_history.py) | 168 → 168 | 死（异项目遗留） |
| 3 | [mock_openai_server.py](scripts/mock_openai_server.py) | 118 → 118 | **活** |
| 4 | [process_kdd_arff.py](scripts/process_kdd_arff.py) | 53 → 53 | 死（一次性历史） |
| 5 | [run_stage9_smoke.py](scripts/run_stage9_smoke.py) | 187 → 187 | **活** |
| 6 | [seed_production_data.py](scripts/seed_production_data.py) | 724 → 724 | **活**（含 D 类隐患） |
| 7 | [seed_test_data.py](scripts/seed_test_data.py) | 359 → 359 | **部分失效**（第 3 步必崩） |
| 8 | [test_ai.py](scripts/test_ai.py) | 80 → 80 | 死（一次性诊断） |
| 9 | [test_ai_detailed.py](scripts/test_ai_detailed.py) | 128 → 128 | 死（一次性诊断） |
| 10 | [test_api.py](scripts/test_api.py) | 48 → 48 | 死（一次性诊断） |
| 11 | [test_openai_sdk.py](scripts/test_openai_sdk.py) | 33 → 33 | 死（一次性诊断） |
| 12 | [validate_explanation_config.py](scripts/validate_explanation_config.py) | 48 → 48 | **活** |
| 13 | [verify_page_render.py](scripts/verify_page_render.py) | 227 → 227 | **活**（只读审查，未改 CLI/退出码） |

**分区外但同名目录的只读观察**：`scripts/__pycache__/`（13 个 `.pyc`）——`git ls-files scripts/__pycache__` **输出为空**，即**未被 git 跟踪**，只是磁盘垃圾（`.gitignore` 已含 `__pycache__/`、`*.py[cod]`）。按协议 §3-B 不列入「已提交死代码」。

---

## §2 脚本清单与用途（用途 / 入口 / 依赖 / 是否仍能跑通 / 判定）

**依赖存在的核查方式**：对每个被 import 的符号逐一 `grep '^def <name>'`，对每个被写死的路径逐一 `Test-Path`。

### 2.1 存活脚本（6）

| 脚本 | 用途（一句话） | 入口 | 依赖 | 仍能跑通的静态证据 | 判定 |
|---|---|---|---|---|---|
| `backfill_dataset_samples.py` | 用 `data/**` 的 ARFF 源文件回填数据集的 `fields_schema.sample_values` 并同步 `enum_values`（修复 Weka 枚举值带引号口径） | `python scripts/backfill_dataset_samples.py [--dry-run]` | DB（`SessionLocal`）+ `data/**` ARFF + `arff_reader` / `training_executor` | `arff_reader.py:117 read_arff`、`:251 enrich_sample_values`、`:262 sync_enum_values`、`training_executor.py:22 resolve_dataset_path`、`models/dataset.py` 全部存在；文件不存在时 `[skip]` 不崩 | **活**（运维回填） |
| `mock_openai_server.py` | 本地 OpenAI 兼容 mock（`/v1/chat/completions`），供 AI 解释联调/测试 | `python scripts/mock_openai_server.py --port 8765 [--mode ...]` | 仅标准库（`http.server`）；监听 8765 | 无第三方依赖；`X2a.md:165` 记载 `backend/tests/test_ai_service.py` 把它当作**被测依赖** | **活**（测试夹具） |
| `run_stage9_smoke.py` | 阶段 9 真实 API 冒烟：登录 → 选已发布模型 → 预测 → SSE 流式解释 → 读回已保存解释 | `python scripts/run_stage9_smoke.py [--configure-mock]` | 运行中的后端 12312 + `requests` +（可选）8765 mock | 7 个端点逐一核实存在（见 2.3 交叉核对）；响应字段全部存在 | **活**（联调冒烟） |
| `seed_production_data.py` | 灌入接近生产规模的端到端数据：账号→数据集→模型训练/发布→推理+风险事件→处置→快照/报告→时间轴铺开 | `python scripts/seed_production_data.py --all` / `--stage a,b` | 运行中的后端 12312（**全程走真实 HTTP**）+ 7 份 ARFF 源文件 + 时间轴阶段直连 DB | 7 份 ARFF 全部 `Test-Path=True`（`data/network/NF-UNSW-NB15-v2.arff`、`data/network/KDDTrain_20Percent.arff`、`data/power/powergrid_knowledgebase_dataset.arff`、`data/carrier/Feature2_Cleaning_lisan.arff`、`data/carrier/paired_TrailData_feature2_biaoqian.arff`、`data/geological/DIS_Landslides.arff`、`data/geological/DIS_raw_data.arff`）；`is_risk_label` 仍在 `constants.py:327`；5 个模型/报告/处置端点全部存在 | **活**（含 D-01/D-02 隐患） |
| `validate_explanation_config.py` | 部署前校验解释配置：展开特征目录后跑 `validate_scenario_configs`，缺场景字段/特征元数据即非零退出 | `python scripts/validate_explanation_config.py` | `backend/app/data/scenario_configs.json` + 两个纯函数 | `scenario_feature_catalog.py:115 expand_scenario_feature_catalog`、`schemas/scenario_config.py:75 validate_scenario_configs` 存在；`scenario_configs.json` `Test-Path=True`；退出码 0/1 语义正确 | **活**（部署门禁） |
| `verify_page_render.py` | 无头 Chrome + CDP 对**渲染后的真实 SPA** 做 present/absent 断言并截图（hash 路由专用） | `python scripts/verify_page_render.py --route "#/risk" --present ... --absent ... [--shot p]` | `websockets`（**已安装**）+ Chrome/Edge（4 个候选路径）+ 运行中的 12312 | `python -c "importlib.util.find_spec('websockets')"` → True；`sys.exit(main())`，0=全通过 / 1=失败 | **活**（Lead 验收工具，**只读审查，未改 CLI 与退出码**） |

### 2.2 部分失效（1）

| 脚本 | 问题 | 证据 | 判定 |
|---|---|---|---|
| `seed_test_data.py` | 第 1/2 步（账号、数据集注册）可用；**第 3 步 `ensure_thresholds` 必崩**。另默认源目录是本机微信下载绝对路径 | ① `L220 threshold = db.get(RiskThreshold, _sc_id)` —— `RiskThreshold` 是 **`(user_id, scenario_id)` 复合主键**（`backend/app/models/risk_threshold.py:21-26`，`primary_key=True` 各一），传标量主键必抛 `InvalidRequestError`。**已用内存 SQLite 实证**（见 §6 D-01 原始输出）。② `L38-41 DEFAULT_SOURCE = r"D:\001Mine\008NoSpace\007WeChat\..."` 是某台机器的个人目录 | **部分失效**（前 2 步可用、第 3 步必崩） |

### 2.3 死 / 一次性历史脚本（6）

| 脚本 | 为什么跑不通 / 为什么与本项目无关（**证据**） | 判定 |
|---|---|---|
| `clean_tasks_history.py` | ① 目标文件 `output/tasks.json` 与目录 `output/` **均不存在**（`Test-Path` 双双 `False`）；② 其数据模型是 `tasks[].{id,name,status,time,articles[].title,intel[].title}`（`L102-125`），与本项目（risk_event / inference_record / dataset）**零交集**；③ 全仓 `grep "tasks\.json"` **只命中本文件自身**（`L8,136,145`）→ 零外部引用 | 死（异项目遗留） |
| `process_kdd_arff.py` | ① 输入 `./data/nf_unsw/KDDTrain+_20Percent0503` **不存在**（`Test-Path=False`；`data/nf_unsw/` 下只有 `sample_demo.csv` 一个文件）；② 输出 `./data/nf_unsw/sample_demo.csv` 的唯一消费者是 `backend/app/services/model_sim.py:19`，而 `model_sim.py` 是协议 §3-A 点名的弃用嫌疑模块；③ 路径全部 CWD 相对（`./data/...`），无 `__file__` 锚定；④ 无 `main()`、无 `if __name__` 守卫 | 死（一次性历史清洗） |
| `test_ai.py` | 硬编码 `http://10.181.2.17:10801/v1/chat/completions`（`L9`）。全仓 `grep "10\.181\.2\.17"` 命中 **仅这 4 个脚本**——`backend/app/config.py`、`.env*`、`docs/**` 全部无引用。该私网地址不在本项目任何部署配置中 | 死（一次性诊断） |
| `test_ai_detailed.py` | 同上（`L9,L21`，另含 `socket.connect_ex(('10.181.2.17', 10801))`）；`sys.exit(1)` 出现在模块顶层 | 死（一次性诊断） |
| `test_api.py` | `10.181.2.17:10801` + `10.181.2.17:10802/v1/embeddings` + `http://localhost:9621/query`（`L5,22,37`）。`9621` 是外部知识库服务，**不是本项目组件**（本项目后端在 12312，无 9621 监听） | 死（一次性诊断） |
| `test_openai_sdk.py` | `base_url="http://10.181.2.17:10801/v1"`（`L10`）。注：`openai>=1.0.0` 在 `backend/requirements.txt` 且**已安装**（`find_spec('openai')=True`），所以「跑不通」的原因**是地址不是依赖** | 死（一次性诊断） |

### 2.4 与本轮重构的交叉核对（**关键，结论：0 个脚本因本轮改动失效**）

| 核对项 | 结论 | 证据 |
|---|---|---|
| `ALGORITHM_STATUS_DEPRECATED` 被 B5 删除 → 脚本是否引用？ | **无影响** | 全仓 `grep "ALGORITHM_STATUS_DEPRECATED"` 的**代码**命中 0 处（唯一命中是 `审查协议.md:64` 与 `B5.md` 的说明文字）。13 个脚本**没有任何一个** import `constants.ALGORITHM_*` |
| `seed_production_data.py` / `seed_test_data.py` 是否引用被删常量或改名字段？ | **无影响** | 两者的 constants 依赖只有 `is_risk_label`（`seed_production_data.py:361`），仍在 `constants.py:327`。`seed_test_data.py` 完全不 import constants |
| `seed_production_data.py` 的 Service/Model 依赖是否还在？ | **在** | `app.db.SessionLocal`、`models.{handling_record,inference_record,model_version,report,risk_event,situation_snapshot}` 全部 `Test-Path=True` |
| `run_stage9_smoke.py` 消费的 7 个端点是否还在？ | **全在** | `auth`(`auth_routes.py:26`) + `/login`；`settings/ai`(`ai_setting_routes.py:12`)；`model-versions`(`model_version_routes.py:23`)；`datasets`(`dataset_routes.py:19`)+`/{id}`；`inference-records`(`inference_record_routes.py:18`)+`/predict`(`:22`)；`inference/explanation/stream`(`explanation_routes.py:27`)；`/{record_id}/explain`(`inference_record_routes.py:223`)。均在 `api_router(prefix="/api/v1")` 下 |
| **响应结构**是否本轮变了？ | **未变** | ① `/model-versions` 列表项走 `_to_dict`（`model_version_service.py:116-121`）= `row_to_dict(model, exclude=(...))`，即**输出全部 ORM 列**，故 `model.get("dataset_id")`、`item.get("status")`（`run_stage9_smoke.py:125,130`）仍取得到；`model_version_id`/`algorithm_code`/`evaluation_metrics` 显式补写（`:138,144,148`）。② `/inference-records/{id}/explain` 的 `generated_explanation` 由 `_saved_explanation_for_role`（`inference_record_service.py:218-234`）产出，键仍为 `available` / `source` / `markdown` / `generated_at`，与 `run_stage9_smoke.py:174-177` 的断言一致。③ `predict` 响应仍含 `id` / `prediction_label` / `risk_score` / `explain_data`（`inference_record_service.py:341-350,379-395`） |
| `validate_explanation_config.py` 引用的 `explanation_contract` 字段？ | **不引用** | 该脚本**不 import** `schemas/explanation_contract.py`；只 import `data/scenario_feature_catalog` 与 `schemas/scenario_config`（`L18-19`），两者签名 `expand_scenario_feature_catalog(configs)` / `validate_scenario_configs(configs) -> list[str]` 未变；读的键 `required_feature_names` / `feature_dictionary` 仍由 `expand_scenario_feature_catalog` 产出（B6b-1.md:84 亦确认） |
| `backfill_dataset_samples.py` 是否受 `dataset_file_reader` CSV `sample_values` 口径改动影响？ | **不受** | 该脚本 import 的是 `app.utils.arff_reader`（ARFF 路径）与 `training_executor.resolve_dataset_path`，**不 import `dataset_file_reader`**；B6b-1 改的是 CSV 分支的 `sample_values` 取值，ARFF 分支的 `enrich_sample_values`/`sync_enum_values` 保留（B6b-1.md:82 明确记为「保留，活引用 = 本脚本」） |
| `seed_test_data.py` 是否受 `dataset_file_reader` 改动影响？ | **签名未变，不受影响** | 它调用 `build_fields_schema(fields, label_field)`（`L152`），`dataset_file_reader.py:148` 签名仍为 `(fields, label_field)` |
| `seed_production_data.py` 的场景管理员模型可见性是否被 B3 收紧到看不见？ | **未收紧** | `model_version_service.py:76 _MANAGED_VISIBILITIES = (platform, company)`，`get_list` 的 SCENARIO_ADMIN 分支 `:651` 用 `Dataset.visibility.in_(_MANAGED_VISIBILITIES)` → 脚本训练用的 4 份 **platform** 数据集仍可见；`get_list` 的 `status` 支持逗号分隔多值（`:635`），脚本传单个 `"PUBLISHED"` 有效 |
| `seed_test_data.py` 的 Service 调用签名是否被改？ | **未变** | `user_service.py:152 create(current_user, username, password, role, scenario_id)`、`dataset_service.py:260 create(current_user, logical_id, scenario_id, file_path, fields_schema, label_field, name=None, visibility=None)`、`risk_threshold_service.py:60 update(current_user, scenario_id, medium_threshold, high_threshold)` —— 与脚本调用点逐一匹配 |

**交叉核对总结：本轮重构（B1–B7）没有让任何一个 `scripts/**.py` 失效。** 唯一失效项（`seed_test_data.py:220`）是**本轮之前就存在的历史缺陷**（`backend/app/models/risk_threshold.py` 最近一次改动是 `c66a21a`，早于本轮；`seed_test_data.py` 最近一次是 `1123b53`）。

---

## §3 A. 弃用（deprecated）

| 检查项 | 结论 | 证据 |
|---|---|---|
| `datetime.utcnow()` | **0 处** | `grep "utcnow" scripts/` → 0。正确写法已在用：`seed_production_data.py:619 datetime.now(timezone.utc)`、`seed_test_data.py:172 datetime.now(timezone.utc)`；`clean_tasks_history.py:9` 的 `datetime.now()` 仅用于**文件名时间戳**（非 UTC 语义），无需改 |
| `distutils` / `imp` / `pkg_resources` | **0 处** | `grep "distutils\|import imp\|pkg_resources" scripts/` → 0 |
| `asyncio.get_event_loop()` | **0 处** | `grep "get_event_loop" scripts/` → 0。`verify_page_render.py:223` 用 `asyncio.run(run(args))`（现代写法） |
| `@app.on_event` / 过时 HTTP 库 | **0 处** | 脚本不建 FastAPI app；HTTP 客户端只有 `requests`（`seed_production_data.py:40`、`run_stage9_smoke.py:18`）+ 标准库 `urllib.request`（`verify_page_render.py:40`），**无 `urllib2`/`httplib`/`requests_toolbelt` 等过时库** |
| **旧式 `typing.List/Dict/Optional`** | **1 处命中（未改，理由见下）** | `clean_tasks_history.py:3 from typing import Any, Dict, List`，并在 `L84,94` 用 `Dict[str, Any]`、`L94,95` 用 `List[Dict[str, Any]]`。**判定：报告不修** —— 协议 §3-A 的条件是「**若项目已统一** `list/dict/X \| None`」，但后端尚未统一（反例：`backend/app/services/dataset_service.py:266` 仍写 `List[Dict]`）。在此文件单点现代化会制造新的口径不一致，且该脚本已判死（§2.3）。已列入 §8 提案 P3 |
| 其余脚本的注解风格 | **已现代** | `run_stage9_smoke.py:16,21,33,50,60` 用 `dict[str, Any]` / `list[...]` / `str \| None` + `from __future__ import annotations`（`L10`）；`seed_production_data.py:28`、`verify_page_render.py:28`、`mock_openai_server.py:10`、`validate_explanation_config.py:7`、`backfill_dataset_samples.py` 亦同 |
| **项目层旧路径** | **0 处** | `grep "deprecated" scripts/*.py` → 0。无脚本 import `backend/deprecated/**`（该目录已由 X1 整体删除，见 §10 的 `D backend/deprecated/...`）；无脚本 import `legacy_model_routes` / `pmwnb_demo` / `model_sim`（唯一与 `model_sim` 的耦合是 `process_kdd_arff.py` 的**输出文件**被 `model_sim.py:19` 读取，非 import） |

---

## §4 B. 残留 / 死代码

### 4.1 死脚本（6 个，零引用证据见 §2.3）

`clean_tasks_history.py`、`process_kdd_arff.py`、`test_ai.py`、`test_ai_detailed.py`、`test_api.py`、`test_openai_sdk.py`。

**零引用证据（原始命令与输出）**：

```
$ git grep -n "tasks\.json"
scripts/clean_tasks_history.py:8:  TASKS_FILE = OUTPUT_DIR / "tasks.json"
scripts/clean_tasks_history.py:136:  print(f"tasks.json not found: {TASKS_FILE}")
scripts/clean_tasks_history.py:145:  print("Invalid tasks.json format")
   → 除本文件自身外 0 命中；且 output/ 目录不存在（Test-Path=False）

$ git grep -n "10\.181\.2\.17"
scripts/test_ai.py:9            scripts/test_api.py:5,22
scripts/test_ai_detailed.py:9,21 scripts/test_openai_sdk.py:10
   → 仅这 4 个脚本命中；backend/app/**、docs/**、*.ps1、.env* 全部 0 命中

$ git grep -n "process_kdd_arff\|KDDTrain+_20Percent0503"
scripts/process_kdd_arff.py:4
   → 除本文件自身外 0 命中；且该输入路径 Test-Path=False
```

**不删的理由（按任务要求，只提案不删）**：这 6 个脚本中 `test_ai*.py` / `test_api.py` / `test_openai_sdk.py` 描述的是**外场 AI 服务的连通性诊断流程**，可能仍在运维手册里作为「现场排查工具」使用；`clean_tasks_history.py` / `process_kdd_arff.py` 是一次性数据清洗脚本，删掉会丢失「当时怎么洗的」这段可追溯信息。**处置建议见 §8 提案 P1（移入 `scripts/legacy/` 并加 README 说明，而不是删除）。**

### 4.2 未使用 import

**0 处。** 逐文件核对（13/13）：`backfill_dataset_samples.py`(argparse/os/sys/SessionLocal/Dataset/resolve_dataset_path/3×arff_reader 全用)、`clean_tasks_history.py`(json/Path/Any/Dict/List/datetime 全用)、`mock_openai_server.py`(argparse/json/BaseHTTPRequestHandler/ThreadingHTTPServer 全用)、`process_kdd_arff.py`(pandas/StringIO 全用)、`run_stage9_smoke.py`(argparse/json/os/sys/Any/requests 全用)、`seed_production_data.py`(argparse/json/os/random/sys/time/ThreadPoolExecutor/datetime/timedelta/timezone/Path/requests 全用——`json` 用于 `L719`、`os` 用于 `L49`)、`seed_test_data.py`(argparse/os/shutil/stat/sys 全用)、`test_*.py`(requests/json/sys 全用)、`validate_explanation_config.py`(json/sys/Path 全用)、`verify_page_render.py`(argparse/asyncio/base64/json/os/shutil/subprocess/sys/tempfile/time/urllib.request 全用，`websockets` 为函数内延迟导入 `L61` 且已用)。

### 4.3 未使用参数 / 变量

| 位置 | 内容 | 说明 |
|---|---|---|
| `seed_test_data.py:161` | `def get_or_create_admin(svc_user, db)` —— **`svc_user` 在函数体内零使用**（函数体是纯 ORM：`select(AppUser)` + 直接构造 `AppUser`，`L163-185`） | 参数是历史残留（早期版本走 Service 层，后改为 bootstrap 直连 ORM）。调用点 `L197,316` 仍传 `svc_user`。**属「未使用参数」而非 import/print 残留，按任务边界只报告不改** |
| `seed_production_data.py:167,230,247,522,527,536` | `st, body = cli.post/put(...)` 中 **`st` 在 5 处未被读取**（`L167` 的 `st` 在 `L176` 用到，不算） | 5 处：`L230`、`L247`、`L522`、`L527`、`L536`。同文件其他地方（`L453`、`L460`）确实需要 `st` 拼错误信息，所以这是**局部不一致**而非纯残留。**只报告** |
| `seed_production_data.py:509` | `creator = ev["created_by_user_id"]` 后被 `L518 clients[creator]` 使用 | 无问题，列出以证明逐行读过 |

### 4.4 注释掉的代码块 / `print` 调试 / TODO / `pass` 占位

| 检查项 | 结论 | 证据 |
|---|---|---|
| 注释掉的代码块 | **0 处** | 13 个文件逐行读过；注释全是**解释性中文注释**（如 `seed_production_data.py:56-58,108,186,212-214,324,387-389,447,501,590-594,682-683`、`seed_test_data.py:33,37,93-94,118,257,318`），无被 `#` 屏蔽的可执行语句 |
| `print` 调试残留 | **0 处**（全部 print 都是刻意的 CLI 进度/诊断输出） | `seed_production_data.py` / `seed_test_data.py` / `backfill_dataset_samples.py` / `validate_explanation_config.py` / `run_stage9_smoke.py` / `verify_page_render.py` 的 print 均带语义前缀（`[dataset]`、`[train]`、`[snapshot]`、`VERDICT:`）。`test_ai*.py` / `test_api.py` / `test_openai_sdk.py` 通篇是诊断输出，但**这就是它们的用途**，不是「残留」 |
| `TODO` / `FIXME` / `XXX` | **0 处** | `grep -n "TODO\|FIXME\|XXX" scripts/*.py` → 0 |
| `pass` 占位 | **2 处，均合理** | `mock_openai_server.py:112 except KeyboardInterrupt: pass`（Ctrl-C 优雅退出，`finally` 里 `server_close()`）；`verify_page_render.py:94 except Exception: pass`（devtools 端点轮询重试，`L84 for _ in range(60)` 有次数上限，**不是无限吞异常**） |
| 零引用函数 | **0 处** | 逐文件列出全部函数/方法（§4.6）并核对调用点；`Client.delete`（`seed_production_data.py:148`）虽在脚本内零调用，但它是 `Client` 这个**小 HTTP 客户端的完整接口**（get/post/put/delete），删掉会让该类残缺——**保留，不算死代码** |

### 4.5 重复 helper（**只提案，未新建文件**）

| 重复组 | 位置 | 重复内容 |
|---|---|---|
| 「HTTP 调用 + 拆 `{code,message,data}` 信封」 | `seed_production_data.py:130-156`（`Client.call/get/post/put/delete/data`）与 `run_stage9_smoke.py:21-30`（`_api`） | 同一套信封解析写了两遍；两处都各自处理「非 JSON 响应」与「code != 0 抛错」 |
| 「POST /v1/chat/completions 并打印 `choices[0].message.content`」 | `test_ai.py:19-68`、`test_ai_detailed.py:45-115`、`test_api.py:15-19`、`test_openai_sdk.py:16-29` | 同一段诊断逻辑复制了 **4 份**，差异仅在输出详细程度与是否用 SDK |
| 「取字段样例值 → 构造合法推理输入」 | `run_stage9_smoke.py:33-57`（`_sample_value` + `_build_features`）与 `seed_production_data.py:379-380`（`build_features`）+ `:351-352`（`_clean`） | 两套「从 `fields_schema`/ARFF 造 feature dict」的口径；`_sample_value` 走 `sample_values→enum_values→"0"` 回退，`build_features` 走真实 ARFF 行 |
| 「ARFF 读取 + fields_schema 构建」 | `seed_test_data.py:143-155`（`parse_arff_fields`）与 `backfill_dataset_samples.py:66-73` | 两者都调 `arff_reader.read_arff(path, max_rows=50)`；**注：`seed_test_data.py` 的注释已说明「复用 arff_reader，不再自己实现一遍」，属已做过的去重**，剩余差异（`build_fields_schema` vs `enrich_sample_values`+`sync_enum_values`）语义不同，**不建议合并** |

**按任务要求：只提案，不新建文件**（协议 §1.7）。提案内容见 §8-P2。

### 4.6 函数清单（协议 §4.5「对每个函数都去理解」的交付证据）

> 格式：`函数` — 算什么 / 参数或数据从哪来 / 被谁调用。

**`backfill_dataset_samples.py`（2）**
- `_changed_enum_fields(before, after)`(L32) — 按位 `zip` 对比两版 `fields_schema` 的 `enum_values`，返回 `[(字段名, 首个差异示例)]`；数据来自 DB 现有 `d.fields_schema` 与新解析的 ARFF 字段；只被 `main` 调用于打印差异摘要。⚠️ 用 `zip` 按位置对齐，若上游重排字段会静默错配（`enrich/sync` 均按字段名合并，故当前不会重排）。
- `main()`(L49) — 遍历全部 `Dataset`，`resolve_dataset_path` → `read_arff(max_rows=50)` → `sync_enum_values(enrich_sample_values(before, new), new)`；`merged == before` 即跳过（**幂等**）；`--dry-run` 只打印。异常按数据集粒度捕获并 `skipped += 1`。

**`clean_tasks_history.py`（9）**
- `looks_like_mojibake(text)`(L12) — 两级判据：命中固定拉丁乱码 token 表（L16-20）即真；否则统计 GBK 乱码汉字集命中率 ≥0.18 且 ≥6 个。被 `fix_mojibake` / `is_readable` 调用。
- `text_quality_score(text)`(L30) — 给一段文本打分：`CJK×8 + 可打印率 - 可疑字符×6 - 控制字符×12 - 替换符×10`；被 `fix_mojibake` 用作 `max()` 的 key、被 `is_readable` 用作阈值（≥40）。空串返回 `-10000`。
- `fix_mojibake(text)`(L43) — 枚举 `latin1/cp1252 → utf-8/gb18030` 与 `gbk/gb18030 → utf-8` 共 6 种转码组合，取 `text_quality_score` 最高者；`candidates` 首元素是原文，故**最坏情况退化为恒等**。
- `add_candidate(src, dst, mode)`(L51，嵌套闭包) — 用 `text.encode(src, errors=mode).decode(dst, errors=mode)` 生成一个候选，异常静默 `return`。
- `to_text(value)`(L69) — `None → ""`，否则 `fix_mojibake(str(value).strip())`。
- `is_readable(text)`(L75) — 清洗后非空、不再像乱码、且质量分 ≥40。
- `clean_event_item(item, title_key)`(L84) — 复制 dict，对**所有** str 值做 `to_text`，并强制 `title_key` 存在。
- `clean_tasks(tasks)`(L94) — 逐 task 清洗 `id/name/status/time`；对 `articles[]` / `intel[]` 逐项 `clean_event_item` 后**按 `is_readable(title)` 过滤丢弃**；非 dict 项跳过。
- `main()`(L134) — 读 `output/tasks.json` → 写带时间戳备份 → 原地覆盖写清洗结果 → 打印前后 articles/intel 条数。

**`mock_openai_server.py`（7）**
- `MockOpenAIHandler.log_message(...)`(L20) — 覆写为**不打印任何请求 URL/头/体**（避免测试夹具泄漏），`return` 空。
- `_json_body()`(L24) — 读 `Content-Length` → `json.loads`，非 dict 或异常一律返回 `{}`（`except (OSError, ValueError, TypeError)`，**收窄的 except，写法正确**）。
- `_send_json(status, payload)`(L32) — 补 `Content-Type`/`Content-Length` 后写响应。
- `do_POST()`(L40) — 路径白名单 `{"/v1/chat/completions","/chat/completions"}`，否则 404；按 `server.response_mode` 分派 `rate_limited/authentication_failed/model_not_found`（429/401/404）；`empty` 清空正文；`reasoning` 额外吐思维链；`payload["stream"]` 走 SSE 分支。
- `_send_stream(content, reasoning)`(L73) — 按 12 字符切片成 `data: {...}\n\n` 序列 + `data: [DONE]`，`reasoning_content` 先于 `content` 下发（模拟推理型模型）。
- `serve(host, port, mode)`(L91) — 构造 `ThreadingHTTPServer` 并把 `response_mode` 挂到 server 实例上（`do_POST` 用 `getattr(self.server, ...)` 取回）。
- `main()`(L97) — argparse（host/port/mode）→ `serve_forever()`，Ctrl-C 优雅退出。

**`process_kdd_arff.py`（1 + 模块级脚本体）**
- `map_risk_by_row(row_data)`(L32) — 取最后一列为 label、第 2 列为 protocol：`normal → 低风险`；否则 `tcp/udp → 高风险`、其余（含 `icmp`）`→ 中风险`。被 `df.apply(..., axis=1)` 逐行调用（**行级 apply，慢**）。⚠️ `row_data.iloc[-1].strip()` 在末列为 NaN（float）时抛 `AttributeError`。
- 模块级体（L1-53，**无 `main()` 守卫**）：读 ARFF 文本 → 定位 `@DATA` 之后的行 → `pd.read_csv(StringIO, header=None, sep=",")` → 取第 0/4/5 列重命名为 `duration/flowLength/accessFreq` → 加 `risk_level` → `to_csv` 覆盖写 `./data/nf_unsw/sample_demo.csv`。

**`run_stage9_smoke.py`（5）**
- `_api(session, base_url, method, path, **kwargs)`(L21) — 发请求，非 JSON 响应抛 `RuntimeError`（带 HTTP 码），`status>=400` 或 `code != 0` 抛 `RuntimeError`（取 `message`/`detail`），否则返回 `body["data"]`；`timeout` 从 kwargs 弹出，默认 30。
- `_sample_value(field)`(L33) — 取 `sample_values[0]`，回退 `enum_values[0]`，再回退 `"0"`；`type == "numeric"` 时转 int（整数）或 float，转换失败返回 `0`。
- `_build_features(fields_schema)`(L50) — 跳过 `role == "label"` 的字段，其余按 `name` 组成 feature dict；全空则抛错。
- `_consume_sse(response)`(L60) — 逐行解析 SSE（`event:` / `data:` / 空行提交），收集事件名序列与 `done` 事件的 payload；**末尾残留事件也会补收**（`L79-82`）。
- `main()`(L86) — 登录取 CSRF（回退读 `bayes_csrf` cookie）→ 可选 `--configure-mock` 写 AI 设置 → 取 `PUBLISHED` 模型 → 取数据集 `fields_schema` 造输入 → `predict` → 校验 `explain_data.prediction_label` 与预测标签一致 → SSE 流式解释（要求 `start/delta/done` 三个事件齐备）→ `GET /{id}/explain` 校验已落库解释（`--configure-mock` 时要求 `source == "ai"`）。返回 0；`__main__` 捕获 `RequestException/RuntimeError` → 打印到 stderr → `SystemExit(1)`。

**`seed_production_data.py`（18 具名 + 3 嵌套闭包）**
- `Client.__init__(username, password=PASSWORD)`(L118) — 建 `requests.Session`（`trust_env=False` 绕系统代理）→ `POST /auth/login` → 校验 `code == 0` → 存 `self.user` 与 `X-CSRF-Token`。
- `Client.call(method, path, **kw)`(L130) — 默认 `timeout=300`；JSON 解析失败时退化为 `{"_raw": text[:400]}`（`except Exception` + `noqa: BLE001`）；返回 `(status_code, body)`。
- `Client.get/post/put/delete`(L139/142/145/148) — `call` 的四个薄封装。`delete` 脚本内零调用（保留为完整接口）。
- `Client.data(method, path, **kw)`(L151) — `code != 0` 抛 `RuntimeError`，否则返回 `body["data"]`。**脚本内所有写操作都走它**（这是「失败即中止」的设计选择，见 D-04）。
- `stage_accounts(state)`(L162) — 超管建 4 场景管理员 + 16 用户（`ensure` 闭包 L166：`code==0` 记 created，`"已存在" in message` 记 skipped，其余打印失败）；随后每个成员在自己场景写一套阈值（`zip(members, pairs)`），最后超管给 4 个场景写 `0.50/0.80`。
- `stage_datasets(state)`(L209) — `have(cli)` 闭包 L218 按上传者视角取 `/datasets?page_size=200` 的 `logical_id` 集合；company 由场景管理员上传（显式 `visibility="company"`）、personal 由指定用户上传（服务端强制 personal）；已存在则跳过。**这是脚本里唯一为「重跑幂等」做的显式判断**（注释 L212-214 记录了不判断会 19→27 的实测）。
- `_param_variants(schema, index)`(L264) — 以算法 `param_schema` 的 default 为基线，再按 `index` 轮换 `discrete_method`（equal_width/equal_freq）与 `discrete_bins`（5/10/20），使同数据集多算法版本参数不同。
- `stage_models(state)`(L281) — 取算法表与数据集表 → 逐场景、逐 `(logical_id, algo_codes)` 训练（跳过已存在的 `(dataset_logical_id, algorithm_code)`）→ `POST /{id}/publish` → 每个 `(场景,数据集)` 选 `accuracy` 最高的 `PUBLISHED` 模型 `set-default`（已有 default 则跳过）。
- `_clean(value)`(L351) — `str(value).strip().strip("'\" \t\r\n")`，剥 ARFF 的引号与空白。
- `load_pool(dataset)`(L355) — `read_arff(max_rows=None)` 整份读；**先校验 ARFF 字段名与库内 `fields_schema` 完全一致**（不一致抛错）；按 `constants.is_risk_label(logical_id, 清洗后的标签)` 分正/负类池。注释 L357-359 记录了「NF-UNSW-NB15-v2 前 6000 行全是负类，必须整份读」的实测教训。
- `build_features(names, label_field, row)`(L379) — 跳过标签列，其余 `_clean` 后组成 `{字段名: 值}`。
- `stage_inference(state, total_hint, only_accounts=None)`(L383) — **逐场景管理员**取各自可见的 `PUBLISHED` 模型（注释 L387-389 记录了「超管只看得到自己训练的模型」这一 `get_list` 语义）→ 建采样池 → 按 `INFERENCE_PLAN` 与 `--inferences` 缩放生成 `plan` → `ThreadPoolExecutor(max_workers=6)` 并发跑 `run_account` 闭包（L427：按 35% 概率取正类样本、`rng.choice(pool)`、`POST /inference-records/predict`、统计 ok/risk/fail）→ 汇总。
- `stage_handling(state, max_events=400)`(L496) — 逐场景取 `PENDING` 事件 200 条 → 用固定种子 shuffle → 每个场景配额 `max_events // 4 = 100` 条 → **用事件创建者本人账号**处置（`clients` 缓存，未命中时**在循环内**拉一次 `/users?page_size=200` 反查用户名，见 C-04）→ 按 `roll` 分派 RESOLVED(45%)/PROCESSING(30%，其中 60% 再转 RESOLVED)/仅追加 comment(25%)。
- `stage_reports(state)`(L549) — 每场景 `POST /situation/scenes/{id}/snapshot`（**有 try/except**）→ 超管 3 份全平台/场景聚合报告 → 每场景管理员 1 份本场景报告并 `PUT /{id}/schedule`（`scheduled=True, interval_days=7`）。
- `_spread(rng, days, recent_share=0.45, recent_window=7)`(L590) — 45% 概率落在近 7 天内、其余摊到 7~`days` 天；**返回小数天而不额外加随机秒**（注释 L592-594 记录：加秒会把整体时间轴前推半天，导致「今天」那根柱子塌掉）。
- `stage_timeline(state, days=60)`(L601) — **唯一直连 DB 的阶段**（`SessionLocal` + `select()`）：风险事件 `occurred_at` 与其推理记录 `executed_at` 同值 → 未产事件的推理记录独立铺开 → 处置记录晚事件 20~2880 分钟 → 模型 `trained_at` 落在 30~120 天前、`published_at` 晚 1~72 小时 → 报告 0~20 天、快照 0~5 天；一次 `db.commit()`。
- `main()`(L687) — argparse（`--stage` / `--all` / `--inferences` / `--accounts` / `--days`）；`ALL_STAGES` 显式列出依赖顺序（注释 L682-683：`--all` 若用 dict 顺序会把 handling 排到 inference 前，空库上静默跳过）；逐阶段分派；最后把 `state` 写成 `tmp/seed_production_report.json`。

**`seed_test_data.py`（6）**
- `parse_arff_fields(path, label_field)`(L143) — 复用 `arff_reader.read_arff(path, max_rows=50)` + `dataset_file_reader.build_fields_schema`，返回 `(fields_schema, count_arff_rows(path))`；docstring 记录了「原先本地实现会剥掉 ARFF 转义引号，导致入库值域与样本库对不上、推理输入校验必报错」的根因。
- `get_or_create_admin(svc_user, db)`(L161) — 按用户名查 `admin`，无则**直接构造 ORM**（`hash_password` + `datetime.now(timezone.utc)`）并 commit；绕过 Service 层的「SUPER_ADMIN 不可经接口创建」限制。⚠️ `svc_user` 参数未使用（§4.3）。
- `ensure_user(svc_user, db, username, password, role, scenario_code)`(L188) — 已存在则跳过；否则解析 `scenario_code → scenario_id`（场景不存在则跳过）→ `svc_user.create(...)` → 打印 `resp.code`。
- `ensure_thresholds(svc_threshold, db, admin, scenario_map)`(L215) — 逐场景、逐 `THRESHOLDS` 项：`db.get(RiskThreshold, _sc_id)` 判存在 → 不存在则 `svc_threshold.update(...)`。**⚠️ 必崩点，见 D-01。**
- `register_dataset(svc_dataset, db, admin, logical_id, cfg, scenario_map, source_dir, skip_copy)`(L231) — 已存在则跳过 → 解析源路径（per-dataset `source` 优先，否则 `source_dir + file`）→ 不存在则跳过 → `clean_name = file.split("(")[0] + ".arff"` → `shutil.copy` 到 `data/<场景目录>/`（覆盖前先 `chmod S_IWRITE`）→ `parse_arff_fields` → 校验标签字段确实存在 → `svc_dataset.create(...)`（不传 `visibility`，故超管建的是 platform）。
- `main()`(L290) — 建 3 个 Service → 建测试账号 → 按 `Scenario.code` 查库建 `scenario_map`（不写死 id）→ 逐数据集注册 → 配阈值 → 打印每场景数据集计数汇总。

**`test_ai.py` / `test_ai_detailed.py` / `test_api.py` / `test_openai_sdk.py`（各 0 个函数）**
- 全部是**模块级线性脚本**（无 `main()`、无 `if __name__ == "__main__"` 守卫），import 即执行。`test_ai_detailed.py` 额外在顶层用 `socket.connect_ex` 做端口可达性预检并在不可达时 `sys.exit(1)`。

**`validate_explanation_config.py`（1）**
- `main()`(L22) — 读 `backend/app/data/scenario_configs.json`（`OSError`/`JSONDecodeError` → stderr + 返回 1）→ `expand_scenario_feature_catalog` → `validate_scenario_configs`（有错逐条打印并返回 1）→ 通过则逐场景打印「N 个输入字段 / M 个字段说明」并返回 0。

**`verify_page_render.py`（3 具名 + 2 嵌套闭包）**
- `_find_chrome()`(L53) — 按 `CHROME_CANDIDATES`（Chrome ×2 + Edge ×2）顺序返回首个存在者，全无则 `SystemExit`。
- `run(args)`(L60) — 起无头 Chrome（`--headless=new --remote-debugging-port=<port> --user-data-dir=<tempdir> --no-proxy-server`）→ 轮询 `/json/list` 取页面 `webSocketDebuggerUrl`（60 次 × 0.5s）→ `websockets.connect` 建 CDP 会话 → 依次：`Page.enable`/`Runtime.enable`/`Emulation.setDeviceMetricsOverride` → 载入 `/#/login` → 页面内 `fetch` 逐个试候选口令登录 → `location.reload()` 让 `bootstrap()` 认到会话 → 用 `location.hash` 做**客户端**跳转（docstring L11-14 解释了为什么不直接硬加载 `/#/xxx`：守卫在 `bootstrap()` 之前跑，会被弹回 roleLanding）→ 轮询 `document.body.innerText` 直到 `--ready` 出现或 20 秒超时 → 逐条判 ABSENT/PRESENT → 可选 `Page.captureScreenshot` 写文件 → 打印 `VERDICT: PASS/FAIL` 并返回 0/1。`finally` 里 `proc.kill()` + `rmtree(profile)`。
- `send(method, params)`(L107，嵌套) — 自增 `msg_id` 发 CDP 命令，循环 `recv` 直到匹配 `id`；带 `error` 则抛 `RuntimeError`。
- `js(expr, await_promise=False)`(L119，嵌套) — `Runtime.evaluate` + `returnByValue`，返回 `result.value`。
- `main()`(L204) — argparse（`--base/--route/--username/--passwords/--absent/--present/--ready/--shot/--port/--width/--height`）→ `asyncio.run(run(args))`；`__main__` 里 `sys.exit(main())`（**0 = 全断言通过；1 = 有断言失败或环境/登录失败** —— 已按任务要求原样保留）。

---

## §5 C. 复杂度

### 5.1 超长文件（> 800 行）

**0 个。** 最长 `seed_production_data.py` **724 行**（< 800 阈值）。按任务要求重点看了它：**结构本身是健康的**——`Client`(L115-156) 与 7 个 `stage_*` 阶段函数 + 4 个纯工具函数（`_param_variants`/`_clean`/`load_pool`/`build_features`/`_spread`）职责清晰，阶段由 `STAGES`/`ALL_STAGES` 表驱动，**没有需要拆分的理由**。唯一可拆点是 `stage_inference`（见 5.2）。

### 5.2 超长函数（> 80 行）

| 位置 | 行数 | 说明 / 拆分方案（**只报告，未改**） |
|---|---|---|
| `verify_page_render.py:60 run(args)` | **142 行** | 一个函数同时负责：起浏览器、建 CDP 连接、实现两个 CDP 原语（`send`/`js`）、登录、跳转、断言、截图。建议拆 `_launch_chrome()` / `_connect_cdp()` / `_login()` / `_navigate_and_assert()`。**注：本脚本是 Lead 的验收工具，任务要求只读审查，故未动** |
| `seed_production_data.py:383 stage_inference` | **96 行** | 混合了「取模型」「建采样池」「生成 plan」「并发执行」「汇总」五件事。建议把 `L427-461` 的 `run_account` 闭包提为模块级 `_run_account(username, role, count, scenario_id, by_scenario, pools, datasets)` |
| `seed_production_data.py:601 stage_timeline` | 68 行 | 可接受（五类实体各一段，注释分段清晰） |
| `seed_production_data.py:281 stage_models` | 65 行 | 可接受 |
| `seed_production_data.py:209 stage_datasets` | 50 行 | 可接受 |
| `seed_production_data.py:496 stage_handling` | 48 行 | 可接受 |

### 5.3 深层嵌套（> 3 层）

| 位置 | 深度 | 说明 |
|---|---|---|
| `test_ai_detailed.py:44-115` | **6 层**（`try` → `try` → `if "choices"` → `elif/else` → `if "message"` → `if "content"` → `if content is None`） | 这是**最典型的「深层嵌套 + 每层只 print」**。建议改为「提前 return / 用小函数逐层校验」或直接断言。属死脚本，只报告 |
| `test_ai.py:18-68` | 5 层 | 同上（少一层） |
| `verify_page_render.py:103-198` | 5 层（`try` → `async with` → 语句块 → `for` → `if`） | 由 §5.2 的拆分一并解决 |
| `seed_production_data.py:288-337` | 4 层（`for sc` → `for (logical_id, algo_codes)` → `for index, code` → `if/else`） | 建议把内层两个循环提为 `_train_one(cli, sc, dataset, code, index)` |
| `seed_production_data.py:502-538` | 4 层（`for sc` → `for ev` → `if cli is None` → `if name is None`） | 建议 `_client_for_creator(admin, creator, clients)` 提前返回 |
| `clean_tasks_history.py:94-131` | 4 层 | 可接受（两段对称的 articles/intel 循环） |

### 5.4 魔法数字 / 字符串

| 位置 | 值 | 建议具名（**未改**） |
|---|---|---|
| `seed_production_data.py:448` | `0.35`（正类采样概率） | `RISK_SAMPLE_SHARE = 0.35` |
| `seed_production_data.py:521,526,531` | `0.45` / `0.75` / `0.6`（处置状态分派概率） | `RESOLVE_SHARE` / `PROCESS_SHARE` / `PROCESS_TO_RESOLVE_SHARE` |
| `seed_production_data.py:590` | `recent_share=0.45, recent_window=7` | 已有参数名，建议提为模块常量以便与前端「近 7 天趋势」对齐 |
| `seed_production_data.py:618` | `random.Random(20260920)` | `TIMELINE_SEED`（注释说明该值对应项目里程碑日期） |
| `seed_production_data.py:647,651,654,659,661` | `20~2880` 分钟 / `30~120` 天 / `1~72` 小时 / `0~20` 天 / `0~5` 天 | 提为 `_HANDLE_DELAY_MIN/_TRAIN_AGE_DAYS/_PUBLISH_DELAY_HOURS/_REPORT_AGE_DAYS/_SNAPSHOT_AGE_DAYS` |
| `seed_production_data.py:464` | `max_workers=6` | `INFERENCE_WORKERS` |
| `seed_production_data.py:496` | `max_events=400` 与 `L507` 的 `// len(SCENARIOS)` | 语义是「每场景 100 条」，建议直接写 `PER_SCENARIO_EVENT_QUOTA = 100` |
| `seed_production_data.py:49` | `"http://127.0.0.1:12312/api/v1"` | 已支持 `WB_BASE` 环境变量覆盖（**写法正确**），仅端口字面量可提常量 |
| `seed_production_data.py:59-104` | 4 场景 × (code/id/5 组阈值对) | 阈值对 `(0.50,0.80)` 等 20 组魔法数；语义是「同分不同级」的刻意设计（注释 L56-58 已说明），建议加一条 `# 刻意不同，勿统一` 的显式告警 |
| `seed_test_data.py:38-41` | `D:\001Mine\008NoSpace\007WeChat\...` | 见 D-03（硬编码绝对路径） |
| `seed_test_data.py:97,104,111` | 3 个 `source` 绝对路径 | 同上 |
| `seed_test_data.py:127` | `THRESHOLDS = [(0.5, 0.8)]` | **单元素列表却写成可迭代形式**（`L219 for medium, high in THRESHOLDS`）——过度设计残留，等价于两个常量 |
| `run_stage9_smoke.py:88-91` | `12312` / `8765` / `alice` / `alice123` | 均已可用 `SMOKE_*` 环境变量覆盖（写法正确） |
| `run_stage9_smoke.py:123,147,163` | `page_size=200` / `timeout=120` / `timeout=(10,180)` | 提为 `MODEL_PAGE_SIZE` / `PREDICT_TIMEOUT` / `SSE_TIMEOUT` |
| `verify_page_render.py:140,165,168,175,219` | `sleep(4)` / `sleep(5)` / `range(20)` / `text[:3000]` / `9333` | 提为 `_NAV_WAIT` / `_READY_POLL` / `_TEXT_PREVIEW` / `DEFAULT_CDP_PORT` |
| `verify_page_render.py:104` | `max_size=64*1024*1024` | `_CDP_MAX_MSG` |
| `mock_openai_server.py:75,77` | 切片长度 `12` | `_CHUNK = 12` |
| `mock_openai_server.py:57` | `"### 研判结论\nMock 服务已生成解释。"` | 可提为 `MOCK_CONTENT`（该串与前端 markdown 渲染契约相关，改动需谨慎） |
| `process_kdd_arff.py:27-29` | 列号 `4/0/5`、`:33` 的 `-1`、`:34` 的 `1` | 纯魔数（注释里的 `# src_bytes` 只说明来源）；`df[4]`/`df[5]` 按位置取值极脆弱 |
| `backfill_dataset_samples.py:66` | `max_rows=50` | 与 `seed_test_data.py:154` 同值，语义是「前 50 行足够取样例」→ 建议两处共用常量（跨文件，走 §8-P2） |

### 5.5 N+1 / 循环内 IO（**真问题，只报告**）

| 位置 | 问题 | 影响 |
|---|---|---|
| `seed_production_data.py:513` | `users = admin.data("GET", "/users", params={"page": 1, "page_size": 200})["items"]` **写在 `for ev in events[:quota]` 循环体内**（虽然被 `if cli is None` 挡住，但每个**新** creator 都会重拉一次全量 200 用户） | 400 条事件最多触发 ~20 次全量用户表拉取。应把 `username_by_id` 提到循环外建一次 |
| `seed_production_data.py:655` | `stats["models"] = len(db.scalars(select(ModelVersion)).all())` —— 在 `L650` 已经遍历过同一批 `ModelVersion` 之后，**又整表查一遍只为计数** | 一次多余的整表查询（DB 中 `model_versions 31`，当前代价小，但属明显冗余）。应用 `L650` 循环里的计数器 |
| `seed_production_data.py:633,634` | `event_record_ids` 建集合后 `others = db.scalars(select(InferenceRecord)).all()` 全量拉取再逐条 `if record.id in event_record_ids` | 可改为 `where(InferenceRecord.id.notin_(...))` 下推到 DB。属 §3-C「对同一集合的重复遍历」 |
| `process_kdd_arff.py:46` | `df.apply(map_risk_by_row, axis=1)` —— 逐行 Python 调用 | 对 2 万+ 行明显慢；可向量化（`np.where` / `map`）。属死脚本 |

---

## §6 D. 正确性隐患

### D-01【**必崩·最高优先**】`seed_test_data.py:220` 用标量主键调 `db.get()`，而 `RiskThreshold` 是复合主键

```python
# scripts/seed_test_data.py:215-228
def ensure_thresholds(svc_threshold, db, admin, scenario_map):
    from app.models.risk_threshold import RiskThreshold
    for code, _sc_id in scenario_map.items():
        for medium, high in THRESHOLDS:
            threshold = db.get(RiskThreshold, _sc_id)      # ← L220
```

模型侧（`backend/app/models/risk_threshold.py:21-26`）：

```python
user_id:     Mapped[int] = mapped_column(BigInteger, ForeignKey("app_user.id"), primary_key=True)
scenario_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("scenario.id"),  primary_key=True)
```

`user_id + scenario_id` **两个 `primary_key=True`** → `Session.get` 需要 `(user_id, scenario_id)` 元组。

**实证（内存 SQLite，不碰仓库 DB）**：

```
$ python -c "...同构复合主键模型 + create_all + session.get(Model, 1)..."
scalar get RAISED: InvalidRequestError Incorrect number of values in identifier to formulate primary key for session.get(); primary key columns are 'rt.user_id','rt.scenario_id'
tuple  get -> True
```

`sqlalchemy/orm/session.py:3803` 亦有对应分支 `"Incorrect number of values in identifier to formulate ..."`。

**影响**：`seed_test_data.py` 的 `[3/3] 风险阈值` 步骤在**第一个场景**上即抛 `InvalidRequestError` 并终止整个脚本（该异常不是 `ServiceError`，无任何兜底）。前两步（账号、数据集注册）在崩之前已完成，所以现象是「数据集建好了、阈值一个没配上」——**容易被误判为「阈值服务有问题」**。

**正确写法（提案，未应用）**：`db.get(RiskThreshold, (admin.id, _sc_id))`。

**归因**：**本轮之前的历史缺陷**（`risk_threshold.py` 最后一次改动 `c66a21a`，`seed_test_data.py` 最后一次 `1123b53`，均早于本轮 HEAD `2a3c029`）。按任务边界「只报告，不改这些脚本的逻辑」→ **未改**。

### D-02 `seed_production_data.py` 的 4 个未防护崩溃点

| 位置 | 隐患 | 触发条件 |
|---|---|---|
| `L449` | `row = rng.choice(pool)`，而 `pool = pos if (pos and rng.random() < 0.35) else (neg or pos)` —— **当 `pos` 与 `neg` 都为空时 `rng.choice([])` 抛 `IndexError`** | ARFF 全表 0 行、或标签列清洗后全部落入「非风险」且负类池也为空 |
| `L370` | `label_index = names.index(dataset["label_field"])` —— **`ValueError` 未被捕获** | 库内 `label_field` 与 ARFF 实际字段名不一致（`L368` 只校验了 `names == schema_names`，不校验标签字段存在） |
| `L574-579` | 场景管理员的 `POST /reports/generate` 与 `PUT /{id}/schedule` **没有 try/except**（对比 `L555-561` 的快照**有**） | 任一场景报告生成失败 → 整个 `reports` 阶段中断，后面的阶段（`timeline`）不再执行 |
| `L627` | `db.get(InferenceRecord, ev.inference_record_id)` —— 若该外键为 `None`（历史脏数据），SQLAlchemy 对 `None` 主键的行为未定义/可能抛错 | 风险事件表存在 `inference_record_id IS NULL` 的行 |

**注**：`L411-414` 的 `scale = total_hint / sum(...) if total_hint else 1.0` **不是**零分母隐患——`SCENARIOS` 是 4 元素字面量，分母恒为 `4 × (120 + 4×85) = 1840`。逐项核过，此处**无问题**。

### D-03 硬编码凭据 / 绝对路径（**只列位置，不打印口令内容**）

| 位置 | 类型 | 说明 |
|---|---|---|
| `seed_production_data.py:50` | **硬编码统一口令** | 全脚本所有账号共用同一口令字面量（`L118` 作为默认参数）。属「存在硬编码凭据」 |
| `seed_production_data.py:117` | 默认口令参数 | `Client.__init__(username, password=PASSWORD)` |
| `seed_test_data.py:131-137` | **硬编码凭据表** | `TEST_USERS` 5 条 `(username, password, role, scenario)`，明文口令 |
| `seed_test_data.py:175` | **硬编码口令** | `get_or_create_admin` 内直接 `hash_password(...)` 一个明文字面量 |
| `run_stage9_smoke.py:90` | 默认口令 | `--password` 默认值（明文，可用 `SMOKE_PASSWORD` 覆盖） |
| `run_stage9_smoke.py:117` | 占位 API key | `"api_key": "local-smoke-key"` 写入本机 mock 的 AI 设置（非真实密钥） |
| `verify_page_render.py:212` | **候选口令列表** | `--passwords` 默认值含两个真实种子口令 |
| `test_openai_sdk.py:9` | 占位 API key | `api_key="EMPTY"`（非真实密钥） |
| `seed_test_data.py:38-41, 97, 104, 111` | **硬编码绝对路径** | 默认 ARFF 源目录与 3 个 per-dataset `source` 全是某台机器的 `D:\001Mine\...` 个人目录 → 换机即全部 `[dataset] ...: 找不到源文件 ...，跳过` |
| `verify_page_render.py:42-47` | 硬编码浏览器路径 | 4 个 Windows 绝对路径（有回退链，缺则 `SystemExit`）—— 属合理设计 |

### D-04 被吞的异常 / 过宽 `except`

| 位置 | 写法 | 评估 |
|---|---|---|
| `seed_production_data.py:135` | `except Exception:  # noqa: BLE001` → `body = {"_raw": r.text[:400]}` | 过宽，但**后果是良性的**（把非 JSON 响应降级为可诊断的 `_raw`，而不是吞掉）。可收窄为 `(ValueError, json.JSONDecodeError)` |
| `verify_page_render.py:93` | `except Exception: pass`（devtools 轮询） | 吞异常，但**有 60 次上限**（`L84`）+ 超时后走 `FATAL` 分支，不是无限静默。可接受 |
| `backfill_dataset_samples.py:67` | `except Exception as exc:  # noqa: BLE001` → 打印 + `skipped += 1` | 逐数据集粒度、有输出、不中断整体。**写法合理** |
| `clean_tasks_history.py:56` | `except Exception: return`（`add_candidate` 内） | 局部收窄到「某个转码组合不可用」，无副作用 |
| `test_ai.py:75` / `test_ai_detailed.py:123` / `test_api.py:18,33,47` / `test_openai_sdk.py:28` | `except Exception as e` | 诊断脚本兜底打印，**符合其用途**；但 `test_ai_detailed.py` 用 `except requests.exceptions.Timeout/ConnectionError` **之后**又接一个 `except Exception`，顺序正确（具体在前） |
| `mock_openai_server.py:29` | `except (OSError, ValueError, TypeError)` | **正面案例**：收窄的 except |
| `seed_production_data.py` 全脚本 | **无任何 `except: pass`** | 逐行核过 |

### D-05 写 DB 前的事务 / 幂等性

| 脚本 | 幂等性 | 证据 |
|---|---|---|
| `seed_production_data.py` | **部分幂等**（脚本 docstring `L23-26` 已如实声明） | 账号：`"已存在" in message` 跳过（`L173`）✅；数据集：显式查 `logical_id` 跳过（`L226,243`，注释记录了「不判断会 19→27」）✅；模型：按 `(dataset_logical_id, algorithm_code)` 跳过（`L298`）✅；处置：只挑 `PENDING`，天然收敛 ✅；**推理 / 报告 / 快照：追加式，重跑会再生成一批** ❌（`L26` 原文：「要重跑先清库」） |
| `seed_test_data.py` | 声明幂等，实际**账号/数据集幂等、阈值步骤崩**（D-01） | `L193` 查用户、`L235` 查 `Dataset.logical_id`、`L220` 查阈值（崩） |
| `backfill_dataset_samples.py` | **幂等** | `L74 if merged == before: continue`；`--dry-run` 完全不写库（`L90-91`）；`db.commit()` 在全部循环之后一次提交（`L93`） |
| `seed_production_data.py:663` | `stage_timeline` 单次 `db.commit()`，无显式事务包裹 | 中途异常 → 整个 `with SessionLocal()` 块回滚，**不会留半截状态**（SQLAlchemy Session 上下文语义），可接受 |
| `seed_test_data.py:183,260` | `db.commit()` 分散在各 helper 内 | 每个实体独立提交 → **失败时留下部分结果**（这正是 D-01 现象「数据集在、阈值不在」的成因） |

### D-06 删除 / 覆盖目标路径（**重点排查项**）

**`os.remove` / `os.unlink`：本分区 0 处。**

**`shutil.rmtree`：2 处，均在 `verify_page_render.py`，目标都是系统临时目录，安全**：

```
verify_page_render.py:66   profile = tempfile.mkdtemp(prefix="cdp-profile-")   ← 目标来源
verify_page_render.py:99   shutil.rmtree(profile, ignore_errors=True)          ← 安全
verify_page_render.py:201  shutil.rmtree(profile, ignore_errors=True)          ← 安全
```

**结论：本分区不存在「`rmtree`/`os.remove` 可能指向仓库重要目录」这类最危险的问题。**

**但存在 3 处「覆盖写」风险（非删除，仍需 Lead 知悉）**：

| 位置 | 目标 | 风险 |
|---|---|---|
| `seed_test_data.py:260` | `shutil.copy(src_path, dest_path)`，`dest_path = PROJECT_ROOT/data/<scenario_dir>/<clean_name>`（`L252-253`） | 目标在**仓库内 `data/`**。`clean_name` 由 `cfg["file"].split("(")[0] + ".arff"` 推出（`L249`），全部是字面量、**不含 `..`，无路径穿越**；但若同名的不同来源文件再次传入，会**静默覆盖** `data/` 下已被数据库引用的 ARFF。`data/` 被 `.gitignore` 忽略（`/data/` 锚定仓库根），所以覆盖不会污染版本库，但会**改变运行态数据源**。另 `L259,261 os.chmod(dest_path, stat.S_IWRITE)` 会**修改仓库内文件的权限位** |
| `process_kdd_arff.py:49` | `df_clean.to_csv("./data/nf_unsw/sample_demo.csv")` | 该 CSV 是 `backend/app/services/model_sim.py:19` 的**输入**。脚本当前跑不通（输入缺失），但**一旦有人补上输入文件就会覆盖 model_sim 的数据源** |
| `clean_tasks_history.py:148,153` | 先写 `output/tasks.backup.<时间戳>.json`，再**原地覆盖** `output/tasks.json` | 有备份，但备份与原文在**同一目录**（`output/`），且该目录当前不存在。若该脚本将来被复用于本项目数据，属高风险写模式 |

### D-07 `sys.exit` 与退出码语义

| 位置 | 语义 | 评估 |
|---|---|---|
| `run_stage9_smoke.py:184,187` | `raise SystemExit(main())`；捕获 `(RequestException, RuntimeError)` → stderr + `SystemExit(1)` | **正确**：0 = 全链路通过，1 = 联调未通过 |
| `validate_explanation_config.py:48` | `raise SystemExit(main())`；`main` 返回 0/1 | **正确**：可作部署门禁 |
| `verify_page_render.py:227` | `sys.exit(main())`；`main` 返回 `asyncio.run(run(args))`，`run` 返回 0/1 | **正确且已按任务要求原样保留**：0 = 全部断言通过，1 = 有断言失败或环境/登录失败 |
| `test_ai_detailed.py:27,30` | 模块顶层 `sys.exit(1)`（端口不可达 / 网络测试失败） | 作为脚本可接受；作为「被 import 的模块」会直接杀进程（无 `__main__` 守卫） |
| `seed_production_data.py` / `seed_test_data.py` / `backfill_dataset_samples.py` / `clean_tasks_history.py` | **无 `sys.exit`**，失败靠异常冒泡 → 进程退出码 1 | `seed_production_data.py:715` 对未知阶段只 `print("! 未知阶段")` 而**不报错退出** → 退出码 0。CI/脚本链式调用时**会把「参数拼错」当成成功**。建议改为 `parser.error(...)` 或非零退出（只报告） |
| `test_ai.py` / `test_api.py` / `test_openai_sdk.py` | 无 `sys.exit` | 全部失败路径只 print → **永远返回 0**，不适合做门禁（符合其「人工诊断」定位） |

### D-08 其他已核但**无问题**的项（证明逐项查过）

- `seed_production_data.py:411-414` 缩放分母：**无零分母**（分母恒 1840，已算）。
- `seed_production_data.py:334` `max(pub, key=... or 0)`：被 `L332 if not pub` 保护，**空序列安全**。
- `seed_production_data.py:646` `ev.occurred_at if ev is not None and ev.occurred_at else ...`：**None 访问已防护**。
- `seed_production_data.py:632,633` 集合推导含可能为 `None` 的 `inference_record_id`：仅用于 `in` 判断，**不抛错**。
- `mock_openai_server.py:26` `int(Content-Length)`：非数字被 `ValueError` 捕获 → `{}`，**安全**。
- `run_stage9_smoke.py:100` `session.cookies.get("bayes_csrf")`：`RequestsCookieJar.get` 缺键返回 `None`，**安全**（随后 `L101` 显式判空抛错）。
- `run_stage9_smoke.py:129` `model.get("model_version_id") or model.get("id")`：**双键回退，安全**。
- `run_stage9_smoke.py:66` `raw_line.decode(...)`：`iter_lines(decode_unicode=True)` 可能返回 `str` 或 `bytes`，**两种都已处理**。
- `validate_explanation_config.py:41-42` `config.get('required_feature_names') or []`：**None 已防护**。
- `backfill_dataset_samples.py:35 zip(before, after)`：`merged` 由 `before` 派生，长度一致；`enrich_sample_values`/`sync_enum_values` 按**字段名**合并（不重排）→ 当前**不会错配**。
- `verify_page_render.py:155` `print("login %s/%s -> HTTP %s" % (args.username, pwd, status))`：**会把候选口令明文打到 stdout**（诊断需要，但口令会进终端日志/CI 日志）。属「凭据经日志外泄」隐患，**只报告**。
- `clean_tasks_history.py:66` `max(candidates, key=text_quality_score)`：`candidates` 首元素是原文 → **最坏退化为恒等**，不会写坏数据。
- SQL 拼接 / 路径穿越 / 越权：**本分区 0 处**。所有 DB 访问走 ORM（`select()` / `db.get`），无字符串拼 SQL；唯一文件路径构造是 `seed_test_data.py:249-253`（字面量派生，无 `..`）。

---

## §7 已改动清单

**本分区改动：0 个文件 / 0 行。**

**理由（逐条对应任务边界）**：

1. 任务明确要求「**只报告，不改这些脚本的逻辑**（除非是纯粹的未使用 import / `print` 调试残留）」。
2. 按 §4.2 逐文件核对，**13 个脚本的 import 全部在用 → 没有可删的未使用 import**。
3. 按 §4.4 核对，**没有 `print` 调试残留**（所有 print 都是刻意的 CLI 输出），**没有注释掉的代码块、没有 TODO/FIXME、没有 `pass` 占位（2 处均合理）**。
4. 因此**唯一可动的只有 §4.3 的「未使用参数 `svc_user`」与「5 处未读取的 `st`」** —— 二者都不在任务给出的例外清单内（不是 import、不是 print），故**按边界不动**。
5. §3-A 的 `typing.Dict/List` 现代化**故意不做**：协议 §3-A 的前置条件是「若项目已统一 `list/dict/X | None`」，而后端**尚未统一**（反例 `backend/app/services/dataset_service.py:266` 仍写 `List[Dict]`）。单点改动会制造新的口径不一致，且该文件已判死。→ 列入 §8-P3。
6. D-01（`seed_test_data.py:220` 必崩）是**逻辑修改**，明确在「不改」范围内 → 只报告（且它是本轮之前的历史缺陷，不由本轮引入）。

**验证（§1.4 允许的自验命令，原始输出）**：

```
$ python -m py_compile scripts/<每个 .py>
EXIT=0  scripts\backfill_dataset_samples.py
EXIT=0  scripts\clean_tasks_history.py
EXIT=0  scripts\mock_openai_server.py
EXIT=0  scripts\process_kdd_arff.py
EXIT=0  scripts\run_stage9_smoke.py
EXIT=0  scripts\seed_production_data.py
EXIT=0  scripts\seed_test_data.py
EXIT=0  scripts\test_ai.py
EXIT=0  scripts\test_ai_detailed.py
EXIT=0  scripts\test_api.py
EXIT=0  scripts\test_openai_sdk.py
EXIT=0  scripts\validate_explanation_config.py
EXIT=0  scripts\verify_page_render.py
```

**13/13 EXIT=0**（协议 §1.4 允许的自验命令；未运行任何脚本本体、未跑 `pytest`、未执行任何 `git` 写操作）。

**未做的事（按约束）**：未运行任何脚本（它们会写 DB / 写文件 / 起服务）、未跑 `pytest`、未执行 `git commit/checkout/stash/reset/clean`、未改 `scripts/build_*.ps1`（3 个）、未改 `backend/**`、未改 `frontend/**`、未改 `docs/全项目代码审查/**` 下除本报告外的任何文件、未新建文件（除本报告）。

---

## §8 跨区提案（**均未应用**）

### P1【X1b 区】`scripts/*.py` 中 6 个死脚本的处置：**建议移入 `scripts/legacy/` + 加 README，不建议删除**

**涉及文件**（全部在 X2c 写作用域内，但处置方式需要 Lead/X1b 统一决策，故作为提案）：

```
scripts/clean_tasks_history.py      168 行  ← 目标 output/tasks.json 不存在；schema 与本项目零交集
scripts/process_kdd_arff.py          53 行  ← 输入 data/nf_unsw/KDDTrain+_20Percent0503 不存在
scripts/test_ai.py                   80 行  ← 硬编码 10.181.2.17:10801
scripts/test_ai_detailed.py         128 行  ← 同上
scripts/test_api.py                  48 行  ← 10.181.2.17:10801/10802 + localhost:9621（外部知识库）
scripts/test_openai_sdk.py           33 行  ← 同上
                                    ─────
                                    510 行
```

**精确 diff（提案，未应用）**：

```diff
- scripts/clean_tasks_history.py
- scripts/process_kdd_arff.py
- scripts/test_ai.py
- scripts/test_ai_detailed.py
- scripts/test_api.py
- scripts/test_openai_sdk.py
+ scripts/legacy/clean_tasks_history.py
+ scripts/legacy/process_kdd_arff.py
+ scripts/legacy/test_ai.py
+ scripts/legacy/test_ai_detailed.py
+ scripts/legacy/test_api.py
+ scripts/legacy/test_openai_sdk.py
+ scripts/legacy/README.md          # 说明：这 6 个脚本为何已失效、历史上做什么用
```

**影响面**：`git grep` 证明这 6 个文件**零外部引用**（§4.1 的三组 grep 输出），移动后不会打断任何构建/测试/文档流程。`scripts/` 下无 `__init__.py`，不是 Python 包，移动不影响 import。

**为什么非改不可**：1808 行的 `scripts/` 里有 510 行（28%）是跑不通的异项目/一次性脚本，混在 7 个活脚本中间，会让「哪个脚本能用来初始化环境」这件事无法从目录看出。这正是协议 §0「残留（dead / leftover）」要消除的问题。

**不改的替代方案（**推荐优先**）**：只在 `scripts/README.md` 里加一张「脚本存活性台账」表（即本报告 §2 的内容），**一个文件都不动**。这样零风险、零跨区，且效果等价。**我倾向此方案** —— 因为协议 §1.7 禁止新建文件，且这 6 个脚本可能仍写在运维手册里。

**决策请求**：Lead 二选一（台账 vs 移目录）。**若选台账，请在 X3（docs 区）落地**，因为 `scripts/README.md` 属新建文件、且 X3 拥有 `docs/**`。

---

### P2【B6b-1 / B3 区】`model_sim.py` 与 `data/nf_unsw/sample_demo.csv` 的隐性耦合

**现状**：`scripts/process_kdd_arff.py`（已判死）唯一产出物 `data/nf_unsw/sample_demo.csv` 是 `backend/app/services/model_sim.py:19` 的输入常量：

```python
# backend/app/services/model_sim.py:19
"net_attack_2024": str(DATA_ROOT / "nf_unsw" / "sample_demo.csv"),
```

而 `model_sim.py` 是协议 §3-A 点名的弃用嫌疑模块（B3 分区）。**两者是同一条死链的两端**。

**提案**：若 B3 裁决删除 `model_sim.py`，则 `data/nf_unsw/sample_demo.csv`（以及 `data/power_data/sample_demo.csv`、`data/carrier_sim/sample_demo.csv`，见 `model_sim.py:20-21`）成为**无消费者的孤儿文件**，应一并清理；反之若保留 `model_sim.py`，则**不要**让任何人「修好」`process_kdd_arff.py`（它一旦能跑就会覆盖这份 CSV）。**X2c 无法裁决，因为 `model_sim.py` 不在本分区。**

**不改的替代方案**：在 `process_kdd_arff.py` 顶部加一行警示注释 `# 已失效：输入文件不存在；若补上输入，本脚本会覆盖 model_sim.py 读取的 sample_demo.csv`。**但这属改脚本内容，按边界未做。**

---

### P3【跨区·全项目口径】`typing.List/Dict/Optional` 的统一现代化

**现状**：协议 §3-A 要求清理旧式 `typing.List/Dict/Optional`，但前置条件「项目已统一」**不成立**：

```
$ grep -rn "List\[" backend/app/services/dataset_service.py
backend/app/services/dataset_service.py:266:        fields_schema: List[Dict],
```

**提案**：把「`typing.List/Dict/Optional` → 内建泛型」作为**一个统一批次**由 Lead 串行执行，覆盖 `backend/app/**` + `scripts/**`。**不要分区各自为战**，否则中间态比现状更乱。

**本分区待改点（1 处，等统一批次一起做）**：

```diff
--- scripts/clean_tasks_history.py
+++ scripts/clean_tasks_history.py
@@
+from __future__ import annotations
+
 import json
 from pathlib import Path
-from typing import Any, Dict, List
+from typing import Any
 from datetime import datetime
@@
-def clean_event_item(item: Dict[str, Any], title_key: str) -> Dict[str, Any]:
+def clean_event_item(item: dict[str, Any], title_key: str) -> dict[str, Any]:
@@
-def clean_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
-    result: List[Dict[str, Any]] = []
+def clean_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
+    result: list[dict[str, Any]] = []
```

**为什么不改不行**：这是协议 §3-A 的明文条目。**不改的替代方案**：既然该脚本已判死（§2.3），可在统一批次中**直接跳过**它 —— 我建议跳过。

---

## §9 未及细查 / 存疑

1. **`seed_production_data.py` 未做运行时验证**。任务禁止运行脚本（会写 DB / 打后端）。因此「活」的判定是**静态的**：端点存在 + 字段存在 + 源文件存在 + 依赖符号存在。**响应体的具体字段值**（如 `res['evaluation_metrics'].get('accuracy')` 是否真为数字、`/reports/generate` 返回的 `data.id` 是否存在）未做运行时确认。风险等级：低（这些字段在 B6a 的端点台账与本报告的交叉核对中都有对应代码证据）。
2. **`seed_production_data.py` 的「重跑会重复生成推理/报告/快照」只按 docstring 采信**（`L23-26` 原文自称「实测确认」），我未独立复现（需跑脚本）。**这是本分区最大的未验证行为假设。**
3. **`db.get(InferenceRecord, ev.inference_record_id)`（`seed_production_data.py:627`）在 `inference_record_id IS NULL` 时的行为未实证**。我只在 D-02 中标注为隐患，未构造用例（需要真实 DB）。若 `risk_events` 表存在 NULL 外键，这里可能抛错。
4. **`seed_test_data.py` 的第 1/2 步是否真能跑通，我只做了静态核对**（Service 签名匹配、场景 code 在 `SCENARIO_DIR` 与库种子中一致）。`DEFAULT_SOURCE` 指向的本机微信目录**未验证是否存在**（`Test-Path` 未执行，因该路径属分区外个人目录，且不影响结论：该路径不存在时脚本会打印 `[dataset] ...: 找不到源文件 ...，跳过` 而不崩）。
5. **`data/network_security/`、`data/geological_risk/`、`data/power_system/`、`data/flightdeck_operation/` 这些「场景 code 同名目录」的存在原因未追查**。`seed_test_data.py` 用 `SCENARIO_DIR` 映射到短名（`network`/`power`/`geological`/`carrier`），但仓库里两套目录都存在（`Test-Path` 确认 `data/network`、`data/network_security` 等 8 个都在）。推断后者是 `DatasetService` 上传落盘时按场景 code 建的（与 `docs/场景管理员首页审查/network.md:26` 记载的 `data/network_security/NF-UNSW-NB15-v2.arff` 一致），但**我未读 `DatasetService` 的落盘逻辑来证实**（该文件属 B5 分区，且不影响本分区结论）。
6. **`test_ai*.py` 的 `10.181.2.17` 是否曾出现在某份未提交的本地 `.env` 中**，我无法核实（协议禁止读 `.env`，且 `.env` 被 `.gitignore` 忽略）。我的「零引用」证据限于**已提交内容**。
7. **`clean_tasks_history.py:24` 的 `gbk_mojibake_chars` 字符串**在读取时显示为一串汉字，我未验证这些字是否本身已被二次编码损坏（不影响「脚本已死」的结论，故未深追）。
8. **`scripts/__pycache__/` 只含 13 个 `.pyc` 中的 7 个**（`clean_tasks_history`/`process_kdd_arff`/`test_ai`/`test_ai_detailed`/`test_api`/`test_openai_sdk`/`validate_explanation_config`/`run_stage9_smoke`/`seed_test_data`/`backfill_dataset_samples`/`mock_openai_server`），说明 `seed_production_data.py` 与 `verify_page_render.py` 在本机从未被编译过 —— 这是「这两个脚本在本机没跑过」的旁证，**但不能证明它们跑不通**（它们是最新写的工具）。仅记录。
9. **本报告未做**：`grep` 全仓确认 `scripts/` 是否被任何 `.ps1`/CI/文档当作启动入口调用（只做了 `scripts/*.py` 文件名级 grep，见 §2.3 与 §4.1）。`start_all.ps1`/`start_all.bat`/`docker-compose.yml` 属 X3 分区，我未读。

---

## §10 `git status --short`

原始输出（本代理执行时段）：

```
 M README.md
 M backend/alembic/env.py
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
 M backend/tests/test_ai_service.py
 M backend/tests/test_discretization_applicability.py
 M "docs/\346\225\260\346\215\256\345\272\223\350\256\276\350\256\241\346\226\207\346\241\243v2.md"
 M "docs/\350\267\257\347\224\261\347\216\260\347\212\266\350\260\203\346\237\245.md"
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
 M scripts/build_pmwnb_jar.ps1
?? "docs/\345\205\250\351\241\271\347\233\256\344\273\243\347\240\201\345\256\241\346\237\245/"
?? "docs/\345\234\272\346\231\257\347\256\241\347\220\206\345\221\230\351\246\226\351\241\265\345\256\241\346\237\245/\351\207\215\346\236\204\346\212\245\345\221\212/"
```

**与本分区的相关性核对**：

| 本分区应出现的行 | 是否出现 | 说明 |
|---|---|---|
| `M scripts/backfill_dataset_samples.py` 等 13 个 `.py` | **一条都没有** ✅ | 本分区 0 行代码改动，符合预期 |
| `?? docs/全项目代码审查/` | **出现** ✅ | 本报告 `docs/全项目代码审查/报告/X2c.md` 所在目录（该目录整体未被 git 跟踪，故显示为目录级 `??`） |
| `M scripts/build_pmwnb_jar.ps1` | 出现，但**不是我的改动** | 属 **X1b** 分区（任务明确排除，我未读未改） |
| `D backend/deprecated/**`（13 项） | 出现，但**不是我的改动** | 属 **X1** 分区（协议 §5 注明该目录经 Lead 预检零引用、可整体删除） |
| 其余 `M backend/**`、`M frontend/**`、`M docs/**` | 均**不是我的改动** | 属 B1–B7 / F1–F7 / X3 等其他并行代理 |

**本分区新增/修改的文件仅 1 个**：`docs/全项目代码审查/报告/X2c.md`（本报告）。

---

我未修改任何分区外文件。
