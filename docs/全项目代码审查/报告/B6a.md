# B6a 报告：`backend/app/api/**`（API 路由层）

审查范围：`backend/app/api/**`（19 个文件，约 1600 行）+ 只读取证 `main.py` / `deps.py` 依赖的
services / models / utils / tests / frontend api 调用方。
修改权限：仅 `backend/app/api/**` 与本报告。未触碰 `main.py`、`config.py`、`models/**`、
`schemas/**`、`utils/**`、`data/**`、`algorithms/**`、`services/**`、`tests/**`、`frontend/**`。

---

## 0. 一句话结论

**`api/**` 没有发现 IDOR / 越权漏洞（0 个端点有风险）**：103 个 v1 端点全部经过「路由层依赖做
登录/角色闸门 + Service 层做场景归属校验」的两层校验，我逐个核对了 Service 侧的 `require_*`
调用点；唯一真正的授权顺序缺陷（先写文件后鉴权）在 B5 的 `dataset_service.py`，已列入跨区提案。
`legacy_model_routes.py` **是活的**（被 `main.py` 挂载且被 `test_application_structure.py` 断言），
不是死代码，但它与 v1 服务层完全脱钩：无场景隔离、无数据库、`/api/model/risk_statistics` 返回
硬编码假数据。共 34 个端点在前端无调用方（26 个 v1 + 8 个 legacy）。同步 `predict-batch` 系列
**不应单方面删除**（有测试断言 + 项目把同步接口当作异步接口的回退路径），给了三步退役方案。

---

## 1. P0：越权 / IDOR 排查

### 1.1 鉴权架构（先明确判定口径）

本项目的授权是**两层**的，只读路由层会得出错误结论：

1. **路由层**（`app/api/deps.py`）：`get_current_user`（登录 + 账号启用）、`require_admin`
   （仅 SUPER_ADMIN）、`require_scenario_admin`（SUPER_ADMIN 或 SCENARIO_ADMIN）、
   `require_bound_scenario`（路径参数 `scenario_id` 必须等于 `current_user.scenario_id`）。
2. **Service 层**（`app/services/base.py::ServiceBase`）：`require_login` /
   `require_admin` / `require_super_admin` / `require_scenario_admin` /
   `require_scenario_admin_of` / `require_scenario_access` / `is_scenario_admin_of` /
   `require_owner_or_admin`。

因此「路由上只写了 `get_current_user`」**不等于**越权：真正的场景归属判定普遍在 Service 里。
下面每一行都同时核对了两侧。

### 1.2 逐端点核对表（103 个 v1 端点）

`归属` = 是否校验场景归属；`角色` = 是否校验角色。判定标准：只要「读自己/自己场景」或
「写需管理级」任一被 Service 层覆盖即算已校验。

#### auth_routes（3）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| POST | `/auth/login` | 无（匿名） | n/a | n/a | 正常；见 §5 暴力破解/枚举时序 |
| GET | `/auth/me` | get_current_user | n/a | n/a | 安全（只回自己） |
| POST | `/auth/logout` | get_current_user | n/a | n/a | 安全（只撤销自己 session） |

#### users（9）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/users` | require_scenario_admin | ✓ Service 限本场景 | ✓ | 安全 |
| GET | `/users/me` | get_current_user | ✓ 只自己 | n/a | 安全 |
| GET | `/users/{user_id}` | get_current_user | ✓ Service 自我或管理级 | ✓ Service | 安全 |
| POST | `/users` | require_scenario_admin | ✓ Service 强制本场景 | ✓ | 安全 |
| PUT | `/users/{user_id}/scenario` | require_scenario_admin | ✓ | ✓ | 安全 |
| PUT | `/users/{user_id}/password` | get_current_user | ✓ 只自己 + 校验旧密码 | n/a | 安全 |
| PUT | `/users/{user_id}/reset-password` | require_scenario_admin | ✓ | ✓ | 安全 |
| PUT | `/users/{user_id}/status` | require_scenario_admin | ✓ | ✓ | 安全 |
| DELETE | `/users/{user_id}` | require_scenario_admin | ✓ | ✓ | 安全 |

#### scenarios（8）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/scenarios` | get_current_user | ✓ Service `require_login` + 角色分支 | ✓ Service | 安全 |
| GET | `/scenarios/overview` | get_current_user | ✓ Service 角色分支 | ✓ | 安全 |
| GET | `/scenarios/{scenario_id}` | require_bound_scenario | ✓ 双重 | ✓ | 安全 |
| GET | `/scenarios/{scenario_id}/explanation-config` | require_bound_scenario | ✓ 双重 | ✓ | 安全 |
| GET | `/scenarios/{scenario_id}/insights` | require_bound_scenario | ✓ + Service `require_scenario_access` | ✓ | 安全 |
| POST | `/scenarios` | require_admin | n/a | ✓ 双重 | 安全 |
| PUT | `/scenarios/{scenario_id}` | require_admin | n/a | ✓ 双重 | 安全 |
| DELETE | `/scenarios/{scenario_id}` | require_admin | n/a | ✓ 双重 | 安全 |

#### datasets（9）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/datasets` | get_current_user | ✓ Service 按 visibility+场景过滤 | ✓ | 安全 |
| GET | `/datasets/{dataset_id}` | get_current_user | ✓ `_can_view_dataset` | ✓ | 安全 |
| GET | `/datasets/{dataset_id}/fields-schema` | get_current_user | ✓ 同上 | ✓ | 安全 |
| GET | `/datasets/{dataset_id}/preview` | get_current_user | ✓ 同上 | ✓ | 安全 |
| POST | `/datasets` | require_scenario_admin | ✓ `require_scenario_admin_of` | ✓ | 安全 |
| POST | `/datasets/upload` | require_scenario_admin | ✓（但**鉴权在写文件之后**，见跨区提案 C1） | ✓ | **顺序缺陷（B5）** |
| PUT | `/datasets/{dataset_id}` | require_scenario_admin | ✓ | ✓ | 安全 |
| PUT | `/datasets/{dataset_id}/disable` | require_scenario_admin | ✓ | ✓ | 安全 |
| DELETE | `/datasets/{dataset_id}` | require_scenario_admin | ✓ | ✓ | 安全 |

#### algorithms（5）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/algorithms` | get_current_user | n/a（算法是平台字典） | n/a | 安全 |
| GET | `/algorithms/{algorithm_id}` | get_current_user | n/a | n/a | 安全 |
| POST/PUT/DELETE | `/algorithms[/{id}]` | require_admin | n/a | ✓ | 安全但**恒 403**（Service 恒返回「仅开发人员代码接入」）→ 死接口，见 §8.4 |

#### model-versions（17）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/model-versions` | get_current_user | ✓ Service `_can_view_model` + 角色分支 | ✓ | 安全 |
| GET | `/model-versions/default` | get_current_user | ✓ Service | ✓ | 安全 |
| POST | `/model-versions/compare` | get_current_user | ✓ Service 普通用户仅已发布 | ✓ | 安全 |
| POST | `/model-versions` | require_scenario_admin | ✓ `require_scenario_admin_of` | ✓ | 安全 |
| POST | `/model-versions/train` | require_scenario_admin | ✓ | ✓ | 安全 |
| POST | `/model-versions/train-async` | require_scenario_admin | ✓ | ✓ | 安全 |
| GET | `/model-versions/training-jobs` | get_current_user | ✓ Service 按 user/scenario | ✓ | 安全 |
| GET | `/model-versions/{model_id}` | get_current_user | ✓ `_can_view_model` | ✓ | 安全 |
| POST | `/{model_id}/complete-training` | get_current_user | ✓ `_require_manageable_model` | ✓ | 安全（内部训练回调） |
| POST | `/{model_id}/fail` | get_current_user | ✓ 同上 | ✓ | 安全 |
| POST | `/{model_id}/publish` | require_scenario_admin | ✓ `_require_trainer` | ✓ | 安全 |
| POST | `/{model_id}/offline` | require_scenario_admin | ✓ `_authorize_lifecycle` | ✓ | 安全（与 disable 重复，见 §8.4） |
| POST | `/{model_id}/disable` | require_scenario_admin | ✓ 同上 | ✓ | 安全 |
| POST | `/{model_id}/enable` | require_scenario_admin | ✓ | ✓ | 安全 |
| POST | `/{model_id}/set-default` | require_scenario_admin | ✓ | ✓ | 安全 |
| POST | `/{model_id}/clear-default` | require_scenario_admin | ✓ | ✓ | 安全 |
| DELETE | `/{model_id}` | require_scenario_admin | ✓ | ✓ | 安全 |

#### inference-records（11）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| POST | `/inference-records/predict` | get_current_user | ✓ `_resolve_target` 403「无权限使用该模型」 | ✓ | 安全 |
| POST | `/inference-records/predict-batch` | get_current_user | ✓ 同上 | ✓ | 安全（建议退役，见 §3） |
| POST | `/inference-records/predict-batch/upload` | get_current_user | ✓ 同上 | ✓ | 安全（同上） |
| POST | `/inference-records/predict-batch/jobs` | get_current_user | ✓ `submit_batch_*` 复用 `_resolve_target` | ✓ | 安全 |
| POST | `/inference-records/predict-batch/upload/jobs` | get_current_user | ✓ 同上 | ✓ | 安全 |
| GET | `/inference-records/predict-batch/jobs` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| GET | `/inference-records/predict-batch/jobs/{job_id}` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| GET | `/inference-records` | get_current_user | ✓ 角色分支（普通用户强制 `user_id==self`） | ✓ | 安全 |
| GET | `/inference-records/{record_id}` | get_current_user | ✓ `_require_record_access` | ✓ | 安全 |
| GET | `/inference-records/{record_id}/explain` | get_current_user | ✓ 同上 | ✓ | 安全 |
| DELETE | `/inference-records/{record_id}` | require_admin | ✓ | ✓ | 安全 |

#### risk-events（7）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/risk-events` | get_current_user | ✓ `require_login` + 给了 scenario_id 时 `require_scenario_access` | ✓ | 安全 |
| GET | `/risk-events/{event_id}` | get_current_user | ✓ `_require_event_access`（三分支） | ✓ | 安全 |
| PUT | `/risk-events/{event_id}/handle` | get_current_user | ✓ 同上 | ✓ | 安全 |
| POST | `/risk-events/{event_id}/comment` | get_current_user | ✓ 同上 | ✓ | 安全 |
| DELETE | `/risk-events/{event_id}` | get_current_user | ✓ `require_login`，Service 恒 400 | ✓ | 安全但**恒 400**（死接口） |
| POST | `/risk-events/{event_id}/hide` | get_current_user | ✓ `_require_event_access` | ✓ | 安全 |
| POST | `/risk-events/{event_id}/unhide` | get_current_user | ✓ 同上 | ✓ | 安全 |

#### risk-thresholds（4）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/risk-thresholds` | get_current_user | ✓ Service `require_login` + 按 user | ✓ | 安全 |
| GET | `/risk-thresholds/audit-logs` | get_current_user | ✓ 同上 | ✓ | 安全 |
| GET | `/risk-thresholds/{scenario_id}` | require_bound_scenario | ✓ 双重 + `require_scenario_access` | ✓ | 安全 |
| PUT | `/risk-thresholds/{scenario_id}` | require_bound_scenario | ✓ 双重 + `require_scenario_access` | ✓ | 安全 |

#### reports（15）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/reports` | get_current_user | ✓ `_load_visible` | ✓ | 安全 |
| GET | `/reports/scheduled` | get_current_user | ✓ 仅本人生成 | ✓ | 安全 |
| POST | `/reports/{report_id}/export/jobs` | get_current_user | ✓ `_export_inputs` | ✓ | 安全 |
| GET | `/reports/export/jobs` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| GET | `/reports/export/jobs/{job_id}` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| GET | `/reports/export/jobs/{job_id}/file` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| POST | `/reports/generate/jobs` | get_current_user | ✓ `_resolve_generation_scope` 403「只能生成本人绑定场景的报告」 | ✓ | 安全 |
| GET | `/reports/generate/jobs` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| GET | `/reports/generate/jobs/{job_id}` | get_current_user | ✓ 按 current_user.id | ✓ | 安全 |
| GET | `/reports/{report_id}` | get_current_user | ✓ `_load_visible` | ✓ | 安全 |
| GET | `/reports/{report_id}/export` | get_current_user | ✓ `_export_inputs` | ✓ | 安全 |
| POST | `/reports` | get_current_user | ✓ Service 强制本人/本场景 | ✓ | 安全 |
| POST | `/reports/generate` | get_current_user | ✓ 同上 | ✓ | 安全 |
| PUT | `/reports/{report_id}/schedule` | get_current_user | ✓ `_load_visible` | ✓ | 安全 |
| DELETE | `/reports/{report_id}` | get_current_user | ✓ Service 生成者本人或管理员 | ✓ | 安全 |

#### situation（6）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/situation/scenes/{scenario_id}` | get_current_user | ✓ Service `require_scenario_access` | ✓ | 安全 |
| GET | `/situation/me` | get_current_user | ✓ 只自己 | n/a | 安全 |
| GET | `/situation/global` | get_current_user | n/a | ✓ Service `require_admin` | 安全（**角色校验在 Service，路由上无 `require_admin`**，见 §6 备注） |
| GET | `/situation/scenes/{scenario_id}/snapshot/latest` | get_current_user | ✓ | ✓ | 安全 |
| POST | `/situation/scenes/{scenario_id}/snapshot` | get_current_user | ✓ Service `require_scenario_admin_of` | ✓ | 安全 |
| GET | `/situation/snapshots` | get_current_user | ✓ Service 按 user/scenario | ✓ | 安全 |

#### dashboard（3）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/dashboard/admin/overview` | get_current_user | n/a | ✓ Service `require_super_admin` | 安全 |
| GET | `/dashboard/scenarios/{scenario_id}/profile` | get_current_user | ✓ Service `require_scenario_admin_of` | ✓ | 安全 |
| GET | `/dashboard/scenarios/{scenario_id}/workspace` | get_current_user | ✓ Service `require_scenario_access` | ✓ | 安全 |

#### model-versions/评价（2，独立 router）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/model-versions/{model_id}/evaluation` | get_current_user | ✓ Service 按角色裁剪 | ✓ | 安全 |
| POST | `/model-versions/{model_id}/evaluation/stream` | get_current_user | ✓ Service `requested_role` 拒绝普通用户请求 management | ✓ | 安全 |

#### settings / explanation（4）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET/PUT/POST | `/settings/ai[/test]` | get_current_user | ✓ 全部按 current_user 读写自己的 key | n/a | 安全（key 只回掩码） |
| POST | `/inference/explanation/stream` | get_current_user | ✓ `get_explanation_source` → `_require_record_access` | ✓ | 安全 |

#### legacy（8，无 `/api/v1` 前缀）
| 方法 | 路径 | 依赖链 | 归属 | 角色 | 判定 |
|---|---|---|---|---|---|
| GET | `/china-map.json` | **无任何依赖（匿名）** | n/a | n/a | **P2：无鉴权**；但内容只是静态地图 JSON（`OUTPUT_ROOT/china-map.json`），前端 0 调用方 |
| GET | `/api/model/dataset-list` | get_current_user | ✗ 无场景隔离 | n/a | P3：返回**硬编码** 3 条数据集名（非 DB），无真实泄漏 |
| POST | `/api/model/save-threshold` | require_scenario_admin | ✗ | ✓ | P2：改的是**进程级全局阈值**，跨用户生效 |
| POST | `/api/model/train` | require_scenario_admin | ✗ | ✓ | P2：写全局 `_legacy_training_state` |
| POST | `/api/model/infer` | get_current_user | ✗ | n/a | **P2：只要曾经有人训练过，任何登录用户都能推理**（`is_trained` 是进程级、永不重置） |
| GET | `/api/model/exp-records` | get_current_user | ✗ | n/a | P2：实验记录全局共享，任何登录用户可读 |
| DELETE | `/api/model/exp/{record_id}` | require_scenario_admin | ✗ | ✓ | P2：任何场景管理员可删**全局**实验记录 |
| GET | `/api/model/risk_statistics` | get_current_user | ✗ | n/a | **P1：硬编码假数据**（假 IP、假趋势、假指标）当真实接口返回 |

### 1.3 P0 结论

- **v1 端点：0 个存在越权/IDOR 风险**，103/103 逐个核对。
- **legacy 端点：8/8 没有场景隔离**（它们压根不走 Service 层）。这是**架构性缺陷而非可利用漏洞**：
  受影响的只有硬编码数据集名、进程级训练标志、全局实验记录、假统计数据，均不含真实业务数据。
  真正的风险是 `/api/model/risk_statistics` 的**假数据**被当成真实态势展示。
- 未发现任何端点可以通过改 ID 读取他人数据：所有按 ID 取单条的端点（inference-records、reports、
  risk-events、users、datasets、model-versions）都在 Service 层有 `_require_*` / `_load_visible` /
  `_can_view_*` 兜底。

---

## 2. `legacy_model_routes.py`：死代码还是活代码？

**结论：活的，但前端 0 调用方。**

证据：

1. `backend/app/main.py:18` `from app.api.legacy_model_routes import router as legacy_model_router`，
   `main.py:138` `app.include_router(legacy_model_router)` → **已挂载**。
2. `backend/tests/test_application_structure.py` 的 `test_current_and_legacy_routes_are_registered`
   用 `expected.issubset(app.openapi()["paths"])` **逐条断言这 8 个路径存在** → 删路径会直接弄红测试。
3. 前端取证：`frontend/src/api/**` 中不存在 `/api/model/`、`china-map`、`risk_statistics` 任何引用。
4. 全仓 grep：本模块是 `app/services/model_sim.py` 与 `app/algorithms/pmwnb_demo.py`
   **唯一的导入方** → 整条 legacy 链（3 个模块）都只为这 8 个无人调用的端点而活。
5. 模块 docstring 原文自称 *"isolated from application startup and the database-backed API"* ——
   **与事实不符**（它就在启动路径上；且导入它会连带执行 `model_sim.py` 模块级的
   `os.makedirs(TRAINED_MODEL_DIR, exist_ok=True)` 和 `import requests`）。
   **我已修正这段 docstring**（纯注释，见 §7）。

### 处置建议（按性价比排序）

| 方案 | 动作 | 影响 | 建议 |
|---|---|---|---|
| A. 保持现状 + 修文档 | 只改 docstring（已做） | 无 | **本次采用** |
| B. 卸载但保留文件 | 删 `main.py:18,138` 两行 | 需同步改 X2 的 `test_application_structure.py`；前端无感 | 提案给 Lead/B6b |
| C. 彻底删除 | 删 3 个模块 + 2 处 main + 1 个测试 | 同上，且 `pmwnb_demo` 的 `global_threshold` 被 `model_sim` 反向依赖需一并核 | 提案，需 B3 会签 |
| D. 至少止血 | `risk_statistics` 改为 410 或接真实聚合；`china-map.json` 加 `get_current_user` | 会改变对外行为（假数据消失），需产品确认 | **提案给 Lead，本次不改** |

> 我**没有**改任何 legacy 端点的路径/方法/响应字段，也**没有**给它加鉴权依赖：那是行为变更，
> 且 `china-map.json` 可能被浏览器当静态资源取用，不能在本分区单方面决定。

---

## 3. 同步 `POST /predict-batch` 与 `/predict-batch/upload`：该不该退役？

### 事实

- 路由：`inference_record_routes.py`，两个同步端点分别调
  `create_batch_from_dataset` / `create_batch_inference` 与 `create_batch_from_csv`。
- 异步替代：`POST /predict-batch/jobs`、`POST /predict-batch/upload/jobs`（同一文件）。
- 前端调用方：`frontend/src/api/inferenceRecordApi.ts:92,103` 导出了
  `predictInferenceBatch` / `predictInferenceBatchUpload`，但**全 `frontend/src` 无任何 import**；
  页面 `RiskInference.vue` 只用 `submitInferenceBatch` / `submitInferenceBatchUpload`（异步版）。
  → 两个同步端点 + 两个前端包装函数都是孤儿。
- 测试：`backend/tests/test_batch_inference_async.py:311-312` 明确断言
  `predict-batch` 与 `predict-batch/upload` **必须存在**。
- 项目惯例：同步接口被当作异步接口的**一键回退路径**并写进测试注释，例如
  `test_report_generate_async.py:219` 断言 `"/api/v1/reports/generate"` 并注明
  **「老同步接口必须留着做回退」**；`report_routes.py` 的 docstring 也写着
  「老接口一行未改，行为不变，出问题可一键回退」。

### 判定

**后端不应单方面退役这两个同步端点。** 理由：① 有测试把它当契约断言；② 项目把「同步回退路径」
当成明确的设计决策，删掉会破坏一致性；③ 前端零调用是**前端遗留**，不是后端可以据以删接口的证据。

### 精确修复方案（三步，跨区）

1. **前端（F6a 范围）**：删 `frontend/src/api/inferenceRecordApi.ts` 的
   `predictInferenceBatch`（第 92 行起）与 `predictInferenceBatchUpload`（第 103 行起）
   两个导出函数 —— 零引用，删除零风险。
2. **后端（本分区，B6a 范围）**：在两个路由的 docstring 里补一行「已由 `*/jobs` 取代，
   保留作回退，前端无调用方」。**不删路由**。（本次未改，等 Lead 决定是否要我加。）
3. **若要真删**（需 Lead 决策 + X2 会签）：
   - `backend/app/api/v1/endpoints/inference_record_routes.py`：删 `predict_batch` 与
     `predict_batch_upload` 两个函数；
   - `backend/app/services/inference_record_service.py`（B3 范围）：`create_batch_from_dataset`
     与 `create_batch_from_csv` 的唯一调用方就是这两个路由
     （`inference_record_routes.py:68,74,95`），删路由后应一并删这两个方法；
   - `backend/tests/test_batch_inference_async.py:311-312`：删对应两条断言。
   - 三步必须同一个提交，否则测试或接口先红。

> 我**没有**动 `test_batch_inference_async.py`（X2 范围），也**没有**削弱任何断言。

---

## 4. 孤儿端点反向清单（前端 `frontend/src/api/**` 零调用方）

统计口径：对每个已注册端点，在 `frontend/src/api/**` + 全 `frontend/src` grep 其路径片段；
零命中即孤儿。**34 个**（26 v1 + 8 legacy）。F6a 出的是「正向/死包装」清单，本节是反向清单。

### 4.1 v1 孤儿（26）

| # | 端点 | 备注 |
|---|---|---|
| 1 | `GET /users/me` | 前端用 `/auth/me` 拿当前用户 |
| 2 | `GET /users/{user_id}` | 无详情页 |
| 3 | `DELETE /users/{user_id}` | 前端无删用户入口 |
| 4 | `GET /scenarios/{scenario_id}` | 前端只调列表与 overview |
| 5 | `GET /scenarios/{scenario_id}/explanation-config` | 前端内置场景配置 |
| 6 | `GET /scenarios/{scenario_id}/insights` | 大屏未接（`dashboard/*` 取代） |
| 7 | `POST /scenarios` | 前端无建场景入口 |
| 8 | `PUT /scenarios/{scenario_id}` | 同上 |
| 9 | `DELETE /scenarios/{scenario_id}` | 同上 |
| 10 | `GET /algorithms/{algorithm_id}` | 前端只调列表 |
| 11-13 | `POST/PUT/DELETE /algorithms[/{id}]` | **Service 恒 403「仅开发人员代码接入」→ 恒失败** |
| 14 | `POST /model-versions` | 前端走 `/train` 与 `/train-async` |
| 15 | `POST /model-versions/{id}/complete-training` | 内部训练回调（供后台 runner 调） |
| 16 | `POST /model-versions/{id}/fail` | 同上 |
| 17 | `POST /reports` | 前端走 `/reports/generate[/jobs]` |
| 18 | `PUT /reports/{id}/schedule` | 前端无定时报告编辑入口（只读 `/reports/scheduled`） |
| 19 | `DELETE /risk-events/{event_id}` | **Service 恒 400（禁止删除风险事件）→ 恒失败** |
| 20 | `GET /situation/me` | 前端用 `/situation/scenes/{id}` |
| 21 | `GET /situation/global` | 测试用（`test_application_structure.py` 断言） |
| 22 | `GET /situation/scenes/{id}/snapshot/latest` | 前端未接快照 |
| 23 | `POST /situation/scenes/{id}/snapshot` | 同上 |
| 24 | `GET /situation/snapshots` | 同上 |
| 25 | `POST /inference-records/predict-batch` | 包装函数存在但零 import（§3） |
| 26 | `POST /inference-records/predict-batch/upload` | 同上 |

### 4.2 legacy 孤儿（8）

`/china-map.json`、`/api/model/dataset-list`、`/save-threshold`、`/train`、`/infer`、
`/exp-records`、`/exp/{record_id}`、`/risk_statistics` —— 全部零前端调用方（§2）。

### 4.3 「前端不用但被测试/脚本/后台消费」的区分

不能按「前端零调用」就删：

- **测试契约**：`/situation/global`、`/api/v1/reports/generate`、`/predict-batch*`、
  `/model-versions/train`、全部 8 个 legacy 路径（`test_application_structure.py`、
  `test_batch_inference_async.py`、`test_report_generate_async.py`、`test_training_async.py`）。
- **脚本**：`scripts/run_stage9_smoke.py` 用 `auth/login`、`settings/ai`、
  `model-versions?page&page_size`、`datasets/{id}`、`inference-records/predict`、
  `inference/explanation/stream`、`inference-records/{id}/explain`；
  `scripts/seed_production_data.py` 用 `PUT /risk-thresholds/{id}`。
- **后台/内部回调**：`/model-versions/{id}/complete-training`、`/{id}/fail`（训练 runner 回写）、
  报告导出/生成 jobs 轮询端点（前端有轮询，属已用）。
- **恒失败接口**：`POST/PUT/DELETE /algorithms`（恒 403）、`DELETE /risk-events/{id}`（恒 400）
  —— 建议按「不可用功能」处理（下线或实现），而不是简单删除。

---

## 5. `auth_routes.py` 安全复核

| 检查项 | 结论 | 证据 |
|---|---|---|
| 密码校验是否常数时间 | **是** | `app/utils/common.py:332-341` `verify_password` 用 `hmac.compare_digest`，畸形 hash 直接返回 False（不抛异常、不短路比较） |
| 会话令牌是否密码学安全 | **是** | `app/utils/auth.py` `new_token()` = `secrets.token_urlsafe(32)`；**不是** `random` |
| 令牌落库形式 | **摘要** | 只存 `digest_token(token)` = HMAC-SHA256(`AUTH_SESSION_PEPPER`)；pepper 强制 ≥32 字符否则 RuntimeError |
| CSRF | **已做（双提交 + 常数时间比较）** | `deps.py::get_current_session`：非安全方法（POST/PUT/PATCH/DELETE）要求 `X-CSRF-Token` 同时等于 CSRF cookie 与 `session.csrf_token_digest`，比较用 `hmac.compare_digest` |
| Cookie 属性 | 合规 | session cookie `httponly=True`，CSRF cookie 故意 `httponly=False`；`secure=cookie_secure()`（默认 true）、`samesite=cookie_samesite()`（默认 lax）、`path="/"` |
| 暴力破解防护 | **缺失（P2）** | `main.py` 无任何限流/锁定中间件；`/auth/login` 无失败计数、无验证码、无指数退避 |
| 用户名枚举时序侧信道 | **存在（P3）** | `if user is None or user.status != ENABLED or not verify_password(...)` 短路：未知用户名**跳过** PBKDF2（10 万次迭代），响应显著更快 |
| 会话固定 | 无风险 | 登录时新建 `AuthSession` 与新 token，不复用旧 token |
| 登出 | 正确 | `revoked_at` 置位 + 删两个 cookie；`get_current_session` 拒绝 `revoked_at is not None` |
| 改密后会话失效 | 正确（在 `user_service`） | 改密会 revoke 该用户全部 `AuthSession` |
| 错误信息 | 合规 | 统一「用户名或密码错误」，不区分「用户不存在 / 密码错 / 账号停用」（**但时序仍可区分**） |

### 建议（均为提案，本次未改）

1. **P2 登录限流**：在 `main.py`（B6b 范围）加按 `(client_ip, username)` 的滑动窗口限流 +
   连续失败 N 次锁定 M 分钟（可复用 `AuthSession` 表或新增轻量计数表）。无中间件时，
   至少可在 `auth_routes.login` 内做基于 `AuthSession` 失败记录的退避。
2. **P3 消除时序差异**：用户不存在时也跑一次 `verify_password(dummy_hash, password)`
   （固定假 hash），使两条路径耗时一致。这是 3 行改动，但会**略微增加**未知用户名的 CPU 开销
   （正是防枚举的代价），需 Lead 确认是否纳入。

---

## 6. `deps.py`：鉴权单一事实来源

### 各函数职责（文档化）

| 函数 | 作用 | 失败行为 |
|---|---|---|
| `get_current_session` | 从 cookie 取 token → 摘要 → 查 `AuthSession`；校验未撤销、未过期、CSRF；节流刷新 `last_seen_at`（60s） | 401「未登录或账号不可用」/ 403「CSRF 校验失败」 |
| `get_current_user` | 基于 `get_current_session` 载入 `AppUser`（`joinedload(scenario)`），校验 `status == USER_STATUS_ENABLED` | 401 |
| `require_admin` | 仅 `ROLE_SUPER_ADMIN` | 403「无权限操作」 |
| `require_scenario_admin` | `SUPER_ADMIN` 或 `SCENARIO_ADMIN` | 403 |
| `require_bound_scenario` | `SUPER_ADMIN` 直接放行，否则要求 `current_user.scenario_id == scenario_id` | 403 |

### 是否存在可绕过的分支？

- `get_current_session` 的早退路径只有「无 cookie / 摘要不匹配 / 已撤销 / 已过期」四种，全部 401，
  **没有**「跳过校验」的旁路。CSRF 只对 `_UNSAFE_METHODS` 生效（GET/HEAD/OPTIONS 免 CSRF 是
  标准做法，且所有读接口本身有 Service 层授权）。
- `require_bound_scenario` 的 SUPER_ADMIN 放行是**有意设计**（平台管理员可管所有场景），
  且它依赖 FastAPI「按同名路径参数解析 `scenario_id`」—— 隐式耦合，**目前只被
  `scenario_routes.py` / `risk_threshold_routes.py` 使用**，两处都有 `scenario_id: int` 路径参数。
  如果将来有路由复用该依赖但路径参数叫别的名字，FastAPI 会把它当 **query 参数**，
  届时 `require_bound_scenario` 会因缺参报 422 而不是静默放行 —— **失败方向是安全的**（fail-closed）。
  仍建议（提案）：把参数名改成 `require_bound_scenario(scenario_id: int = Path(...))` 显式声明，
  或在依赖里加注释说明该隐式约定。

### 本次修复的一个真实缺陷（跨库兼容）

`get_current_session` 里 `session.expires_at <= now` 直接比较，而同一函数**只对 `last_seen_at`
做了 naive→aware 归一化**。生产库是 PostgreSQL（`DateTime(timezone=True)` 回来即 aware）所以不炸，
但 SQLite / MySQL 驱动会返回 naive datetime，比较将抛 `TypeError` → 500。
已抽出 `_as_utc()` 统一归一化，两处共用（**在 PostgreSQL 上行为完全不变**）。

---

## 7. 本次实际改动（`backend/app/api/**`，16 个文件）

`git diff --stat`：**146 insertions(+), 97 deletions(-)**，净 +49 行。

| 文件 | 改动 | 类别 |
|---|---|---|
| `deps.py` | `import hmac` 提到模块级；新增 `_as_utc()`；`expires_at` / `last_seen_at` 统一归一化；`_constant_time_digest_equal` 收成一行 | 正确性 + 可读性 |
| `report_routes.py` | 抽出 `_file_download_response()`，消除 2 处逐字重复的下载响应块（原 124-135 与 226-237） | 去重 |
| `legacy_model_routes.py` | 修正与事实不符的 docstring（自称「与启动隔离」实际已挂载） | 文档纠错 |
| `explanation_routes.py` | `db=Depends(get_db)` → `db: Session = Depends(get_db)`；超长行折行 | 类型 + 风格 |
| `model_evaluation_routes.py` | 同上 + 超长 `ResponseModel(...)` 折行 | 类型 + 风格 |
| `ai_setting_routes.py` | 同上（3 个端点） | 类型 + 风格 |
| `dashboard_routes.py` | 3 个超长签名折行（原 16/21/26 行均 >100 字符） | 风格 |
| `auth_routes.py` | 删未使用的 `from app.api.utils import unwrap`；登录返回 dict 折行（**键值完全不变**） | 清理 |
| `dataset_routes.py` | 删整个 `from typing import Any, Dict, List, Optional`（全部未用）；删未使用的 `require_admin`；3 处 `Optional[X]` → `X \| None` | 清理 |
| `user_routes.py` | 删 `from typing import Optional` + 未使用 `require_admin`；5 处 `Optional[X]` → `X \| None` | 清理 |
| `model_version_routes.py` | 删 `from typing import Optional` + 未使用 `require_admin`（确认该文件里 `require_admin` 只出现在 import 行）；3 处 `Optional[X]` → `X \| None` | 清理 |
| `inference_record_routes.py` | 删 `from typing import Optional`；1 处 `Optional[int]` → `int \| None` | 清理 |
| `risk_event_routes.py` | 删 `from typing import Optional`；3 处 `Optional[X]` → `X \| None` | 清理 |
| `risk_threshold_routes.py` | 同上（1 处） | 清理 |
| `scenario_routes.py` | 删 `from typing import Optional`；`HTTPException` 从函数内 import 提到模块级；1 处 `Optional[int]` → `int \| None` | 清理 |
| `situation_routes.py` | 删 `from typing import Optional`；2 处 `Optional[int]` → `int \| None` | 清理 |

### 接口契约未被触碰（自证）

```
$ git diff -U0 -- backend/app/api | Select-String '^[+-]\s*@router|^[+-]\s*router\s*=|^[+-]\s*response_model|^[+-]\s*summary='
NO route decorator / response_model / router= lines changed
```

→ **路径、方法、`response_model`、`summary` 一律未改**；响应体字段名未改（`unwrap` 的
`{code,data,message}` 结构未动）。`api/**` 内没有 `alembic/**` 或 `models/**` 表字段改动。

### 自检结果

```
$ cd backend && python -m py_compile <19 个 api 文件 + utils.py>   # 20 个文件
PY_COMPILE OK: 20 files
```

（未运行 pytest —— 按协议由 Lead 在最后统一跑全量。）

### 未改动但已确认无需改动

- `api/utils.py`（20 行）：`from typing import Any` **在用**（返回注解），保留。
- `api/__init__.py`（空）、`api/v1/__init__.py`、`endpoints/__init__.py`：无问题。
- `algorithm_routes.py`：无未使用 import、无风格问题；恒 403 是 Service 设计，见 §4.3。

---

## 8. 残留问题（按严重度）

### 8.1 P1 — legacy `GET /api/model/risk_statistics` 返回硬编码假数据
`legacy_model_routes.py:113-139` 直接返回写死的 IP（`110.25.33.12` 等）、写死的攻击趋势、
写死的 `model_metric`。**任何登录用户**都能拿到，且与项目「页面不含静态示例数据」的口径冲突。
→ 提案（未改）：返回 410 Gone，或接真实聚合，或随 legacy 整体下线。

### 8.2 P2 — legacy 进程级全局状态与跨用户影响
- `_legacy_training_state`（模块级 dict）：`train` 置 `is_trained=True` 后**永不重置**，
  于是**任何登录用户**都能调 `/api/model/infer`；`current_dataset` 也是全局共享。
- `/api/model/save-threshold` 改的是 `pmwnb_demo.global_threshold` 全局阈值；
  `/api/model/exp-records` 全局可读；`DELETE /api/model/exp/{id}` 任何场景管理员可删全局记录。
→ 提案：给 legacy 端点加 `require_admin`，或整体下线（§2 方案 B/C）。

### 8.3 P2 — `/auth/login` 无暴力破解防护（§5）

### 8.4 P2 — 重复接口面：`offline` 与 `disable` 暴露同一功能
`model_version_routes.py` 同时注册 `POST /{model_id}/offline` 与 `POST /{model_id}/disable`；
Service 侧 `offline`（543 行）与 `disable`（560 行）都是私有 `_disable_model`（550 行）的薄别名；
**前端两个都调**（`modelVersionApi.ts:102,106`）。
→ 不能删任何一个（会断前端）。提案：前端收敛到 `/disable`，`/offline` 标记为 deprecated 别名
（保留路由，仅在 docstring 标注）。同类还有 `algorithm_routes` 的恒 403 三件套。

### 8.5 P3 — SSE 生成器异常会静默断流
`explanation_routes.py::generate()` 与 `model_evaluation_routes.py::generate()` 直接迭代
Service 生成器，**没有 try/except**：中途抛错时 SSE 连接直接断，前端收不到 `error` 事件
（而 `explanation_routes.py:73` 已证明前端认 `error` 事件契约）。
→ 提案（未改，属行为变更）：`try: ... except Exception: yield _sse("error", {...})`。
附带说明：SSE 生成器在整个流期间**持有请求级 DB session**，长流会长期占用连接池连接，
高并发下可能耗尽连接池 —— 这是设计取舍，仅记录。

### 8.6 P3 — 分页边界
- `le=200` 是 **HTTP 422 拒绝**，不是静默截断；`utils/common.py::paginate` 的 `total` 来自
  COUNT 子查询，是**权威总数**，无截断问题。
- 但存在「默认值 == 上限」的冗余写法：`dataset_routes.py` 预览 `Query(50, ge=1, le=50)`、
  `risk_threshold_routes.py:33` `Query(200, ge=1, le=200)`。无害，仅记录（未改，避免无意义 diff）。
- `user_routes.py:37` `Query(10, ge=1, le=200)`：**正常**，返回 `total`。

### 8.7 P3 — `@service_call` 的异常吞并（仅记录，属 B5/base.py 范围）
`app/services/base.py:33,45-90`：`TypeError/ValueError/KeyError/AttributeError/IndexError`
被归为「编程错误」并转成 `fail(code=500, message="服务器内部错误")`。
**不是静默吞异常**：`logger.exception` 打了完整堆栈，且 `unwrap` 把 code=500 映射成 HTTP 500，
对外语义正确。唯一副作用是「参数写错」和「真实 bug」对客户端长得一样 —— 但日志已分开标记。

### 8.8 无问题项（已核对）
- **响应模型与 `schemas/**` 一致**：`ResponseModel.data: Any`（`schemas/common.py:25`），
  FastAPI 不会裁字段；不存在「response_model 静默剥字段」的经典坑。
- **无 `print`**、**无 `TODO/FIXME`**、**无注释掉的死代码块**、**无重复函数定义**
  （唯一重复是 `_sse()` 在 `explanation_routes.py:22` 与 `model_evaluation_routes.py:19`
  各写一份 —— 跨分区去重，见 §9）。
- **无 `@app.on_event`**（`main.py` 用 lifespan，属 B6b）。
- **无 `datetime.utcnow()`**：`api/**` 内没有任何时间获取调用（都在 Service 层）。
- **路由顺序注释齐全**：`report_routes.py:54,91`、`model_version_routes.py`（`/training-jobs`）、
  `inference_record_routes.py`（`predict-batch` 先于 `/{record_id}`）都有说明，顺序正确。
- **零引用私有函数**：无（`_file_download_response` 为本次新增，2 处调用）。
- `legacy_model_routes.py` 的 7 处 `# noqa: ARG001` 是为未使用的 `current_user` 加的，
  属于「依赖只为鉴权副作用而存在」的既有写法，保留。

---

## 9. 跨区变更提案（需 Lead 裁决 / 其他分区执行）

| ID | 位置 | 精确改动 | 影响 | 为什么必须跨区 | 替代方案 |
|---|---|---|---|---|---|
| **C1** | `backend/app/services/dataset_service.py::upload_from_file`（约 323-360 行） | 把 `require_scenario_admin_of(...)` 校验**前移**到写文件之前（第 354-360 行的 `PROJECT_ROOT/"data"/<scenario.code>/<safe_name>` 落盘之前） | 消除「先产生副作用（落盘）后鉴权」的顺序缺陷；未授权请求不再能写入任意场景目录 | 文件属 B5 分区 | 只读校验（先算目标路径做一次权限判断）成本相同，不如前移 |
| **C2** | `backend/tests/test_application_structure.py`（X2） | 若要卸载 legacy：删 `expected` 中 8 条 legacy 路径断言，并删 `main.py:18,138` | 去掉 8 个无人调用的端点 | 测试属 X2，`main.py` 属 B6b | 保留 legacy 仅修文档（本次采用） |
| **C3** | `backend/tests/test_batch_inference_async.py:311-312`（X2）+ `inference_record_service.py`（B3） | 若要退役同步批量接口：删 2 条断言 + 删 `create_batch_from_dataset` / `create_batch_from_csv` | 减少重复实现 | 测试属 X2，Service 属 B3 | **保持现状**（推荐，见 §3） |
| **C4** | `frontend/src/api/inferenceRecordApi.ts:92,103`（F6a） | 删零引用的 `predictInferenceBatch` / `predictInferenceBatchUpload` | 清掉 2 个死包装 | 前端属 F 分区 | 无 |
| **C5** | `backend/app/main.py`（B6b） | 加登录限流中间件（按 IP+username 滑动窗口 + 失败锁定） | 补上 P2 暴力破解防护 | `main.py` 属 B6b | 在 `auth_routes.login` 内做基于 `AuthSession` 的退避 |
| **C6** | `backend/app/api/v1/endpoints/explanation_routes.py` ↔ `model_evaluation_routes.py` | `_sse()` 完全重复（2 份）；建议抽到 `app/api/utils.py` 由两处共用 | 去重 2 行 ×2 | 两边虽都在 `api/**`，但抽到 `utils.py` 需改两文件共享点，且 `utils.py` 是公共接口 → 交 Lead 决定 | 保持重复（代价仅 2 行） |
| **C7** | `backend/app/services/base.py`（B5） | 建议给 `ServiceBase` 增加 `require_bound_scenario` 的服务层等价物文档，或在 `deps.require_bound_scenario` 用 `Path(...)` 显式声明 `scenario_id` | 消除 FastAPI 同名路径参数的隐式耦合 | `deps.py` 属本分区，但改签名会影响调用方语义，需 Lead 同意 | 仅在依赖里加注释说明隐式约定（零风险） |

---

## 10. 未详细检查的部分（诚实边界）

- `api/**` 之外的一切（services / models / schemas / algorithms / utils / frontend / tests）
  只作为取证读过相关片段，未做全量审查 —— 那些属其他分区。
- `model_version_routes.py` 中 `/{model_id}/complete-training`、`/{model_id}/fail` 的
  **后台 runner 调用方**（`app/services/training_runner.py` 一类）未逐行核对，
  仅确认路由侧鉴权（`_require_manageable_model`）成立。
- SSE 两个端点的**真实并发行为**未做压测（协议禁止起服务），连接池耗尽是静态推断。
- legacy 8 个端点的**外部集成方**（项目外调用者）无法从仓库判断，§2 的「可下线」结论
  以「仓库内零调用方」为前提。
- 未运行 `pytest`（协议要求由 Lead 统一跑），因此本次改动**未经运行时验证**，
  仅通过 `py_compile` 与「路由装饰器零变更」的 diff 自证。
