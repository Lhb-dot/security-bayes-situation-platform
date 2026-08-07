# Security Bayes Platform — API 接口文档 v2.0

> Base URL: `http://127.0.0.1:12312`
>
> 统一响应格式：
> ```json
> { "code": 0, "data": ..., "message": "success" }
> ```
>
> - `code === 0` → 成功，`data` 为业务数据
> - `code === 400` → 业务/参数校验失败
> - `code === 401` → 未登录或账号禁用
> - `code === 403` → 权限不足
> - `code === 404` → 资源不存在
> - `code === 500` → 服务器内部错误
>
> 鉴权方式：前端在请求头中携带 `X-User-Id: {user_id}`（整数）。

---

## 目录

1. [认证](#1-认证)
2. [用户管理](#2-用户管理)
3. [场景管理](#3-场景管理)
4. [数据集管理](#4-数据集管理)
5. [算法管理](#5-算法管理)
6. [模型版本管理](#6-模型版本管理)
7. [推理记录](#7-推理记录)
8. [风险事件](#8-风险事件)
9. [风险阈值](#9-风险阈值)
10. [态势统计](#10-态势统计)
11. [报告管理](#11-报告管理)
12. [处置记录](#12-处置记录)
13. [PMWNB 贝叶斯模型（兼容旧版）](#13-pmwnb-贝叶斯模型兼容旧版)

---

## 1. 认证

### POST /api/auth/login — 用户登录

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，1-64 字符 |
| password | string | 是 | 密码，1-128 字符 |

**返回值** `data`:
```json
{
  "id": 1,
  "username": "admin",
  "role": "ADMIN",
  "status": "ENABLED",
  "created_at": "2026-08-02T12:00:00+00:00",
  "updated_at": "2026-08-02T12:00:00+00:00"
}
```
> 注：不返回 `password_hash` 字段

**错误码**: 401（用户名或密码错误 / 账号已禁用）

---

### GET /api/auth/me — 获取当前用户信息

**入参**: 无（从 `X-User-Id` 请求头识别用户）

**返回值** `data`: 同上（用户对象）

**错误码**: 401（未登录 / 用户不存在 / 已禁用）

---

### POST /api/auth/change-password — 修改本人密码

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| old_password | string | 是 | 原密码 |
| new_password | string | 是 | 新密码，最少 6 位，最长 128 位 |

**返回值**: `data=null, message="密码修改成功"`

**权限**: 所有登录用户（仅限修改本人密码）

**错误码**: 400（原密码不正确 / 新密码长度不符）

---

## 2. 用户管理

### GET /api/users — 用户列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数（最大 200） |
| keyword | string | — | 搜索用户名（模糊匹配） |

**返回值** `data`:
```json
{
  "items": [{ "id": 1, "username": "admin", "role": "ADMIN", ... }],
  "total": 4,
  "page": 1,
  "page_size": 10
}
```

**权限**: 仅 ADMIN

---

### GET /api/users/{user_id} — 用户详情

**入参**: `user_id` (路径参数, int)

**权限**: 本人或 ADMIN

**错误码**: 404（用户不存在）

---

### POST /api/users — 创建用户

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，1-64 字符，唯一 |
| password | string | 是 | 密码，6-128 字符 |
| role | string | 否 | ADMIN 或 USER（默认 USER） |

**权限**: 仅 ADMIN

**错误码**: 400（必填字段缺失 / 用户名已存在 / 角色非法）

---

### PUT /api/users/{user_id}/password — 修改密码

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| new_password | string | 是 | 新密码，6-128 字符 |

**权限**: 本人或 ADMIN

---

### PUT /api/users/{user_id}/status — 启用/禁用账号

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 是 | ENABLED 或 DISABLED |

**权限**: 仅 ADMIN（不能禁用当前登录账号）

---

### DELETE /api/users/{user_id} — 删除用户

**权限**: 仅 ADMIN（不能删除当前登录账号；存在关联业务数据时禁止删除，建议改用禁用）

**错误码**: 400（不能删除自己 / 存在关联数据）

---

## 3. 场景管理

### GET /api/scenarios — 场景列表

**入参**: 无

**返回值** `data`: 场景对象数组
```json
[
  {
    "id": 1,
    "code": "network_security",
    "name": "网络安全态势",
    "description": "网络入侵流量分类",
    "access_status": "ACTUAL",
    "created_at": "...",
    "updated_at": "..."
  }
]
```
- `access_status`: ACTUAL（实际接入）/ RESERVED（仅预留）
- `code` 取值: `network_security` / `power_system` / `geological_risk` / `flightdeck_operation`

**权限**: 所有登录用户

---

### GET /api/scenarios/{scenario_id} — 场景详情

**入参**: `scenario_id` (路径参数, int)

**权限**: 所有登录用户

---

### POST /api/scenarios — 创建场景

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 场景编码，必须为预定义的 4 个编码之一 |
| name | string | 是 | 场景名称，1-64 字符 |
| description | string | 否 | 场景描述 |
| access_status | string | 否 | ACTUAL 或 RESERVED（默认 ACTUAL） |

**权限**: 仅 ADMIN

---

### PUT /api/scenarios/{scenario_id} — 更新场景

**入参** (JSON Body): name / description / access_status（均可选，code 不可修改）

**权限**: 仅 ADMIN

---

### DELETE /api/scenarios/{scenario_id} — 删除场景

**权限**: 仅 ADMIN（已关联数据集或模型则禁止删除）

---

## 4. 数据集管理

### GET /api/datasets — 数据集列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scenario_id | int | — | 按场景过滤 |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**返回值** `data.items`:
```json
[
  {
    "id": 1,
    "logical_id": "kdd_train_20_percent",
    "version": 1,
    "scenario_id": 1,
    "file_path": "arff/kdd_train_20_percent_0503.arff",
    "fields_schema": [{"name": "duration", "type": "float", "role": "feature"}, ...],
    "label_field": "class",
    "uploaded_by": 1,
    "uploaded_at": "2026-08-02T...",
    "status": "ACTIVE"
  }
]
```

**权限**: 所有登录用户（普通用户仅看到与已发布模型相关且启用的数据集）

---

### GET /api/datasets/{dataset_id} — 数据集详情

**权限**: 所有登录用户

---

### GET /api/datasets/{dataset_id}/fields — 字段预览

**返回值** `data`:
```json
{
  "dataset_id": 1,
  "logical_id": "kdd_train_20_percent",
  "version": 1,
  "label_field": "class",
  "fields_schema": [...]
}
```

---

### POST /api/datasets — 上传数据集

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| logical_id | string | 是 | 数据集逻辑编码，1-64 字符 |
| scenario_id | int | 是 | 所属场景 ID |
| file_path | string | 是 | 文件路径，1-255 字符 |
| fields_schema | array | 是 | 字段定义列表（每个含 name/type/role/enum_values） |
| label_field | string | 是 | 分类标签字段名，1-64 字符 |

**fields_schema 元素**:
```json
{ "name": "duration", "type": "float", "role": "feature" }
```
- `role`: `feature`（输入特征） / `label`（分类标签）
- `enum_values`: 枚举字段时必填

**权限**: 仅 ADMIN

---

### PUT /api/datasets/{dataset_id} — 修改数据集

**入参** (JSON Body): 可选 `file_path` / `fields_schema` / `label_field`
> 已被模型引用时自动创建新版本并保留旧版本

**权限**: 仅 ADMIN

---

### PUT /api/datasets/{dataset_id}/disable — 停用数据集

**权限**: 仅 ADMIN

---

### DELETE /api/datasets/{dataset_id} — 删除数据集

**权限**: 仅 ADMIN（被模型引用时禁止删除，只能停用）

---

## 5. 算法管理

### GET /api/algorithms — 算法列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| only_available | bool | true | 仅返回可用算法 |

**返回值** `data`:
```json
[
  {
    "id": 1,
    "code": "PMWNB",
    "display_name": "PMWNB 矩阵加权贝叶斯",
    "description": "当前项目已接入算法",
    "param_schema": [],
    "status": "AVAILABLE",
    "created_at": "..."
  }
]
```
- `code` 取值: A2WNB / MAWNB / EMAWNB / DIWNB / PMWNB
- `status`: AVAILABLE / DEPRECATED

**权限**: 所有登录用户

---

### GET /api/algorithms/{algorithm_id} — 算法详情

**权限**: 所有登录用户

---

## 6. 模型版本管理

### GET /api/models — 模型版本列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scenario_id | int | — | 按场景过滤 |
| dataset_id | int | — | 按数据集过滤 |
| status | string | — | 按状态过滤（仅 ADMIN 可用） |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**状态值**: TRAINING / FAILED / DRAFT / PUBLISHED / OFFLINE

**权限**: 普通用户仅见 PUBLISHED；管理员可见全部

---

### GET /api/models/default — 默认推荐模型

**入参** (Query):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| scenario_id | int | 是 | 场景 ID |
| dataset_id | int | 是 | 数据集 ID |

**权限**: 所有登录用户

---

### GET /api/models/{model_id} — 模型版本详情

**权限**: 所有登录用户（普通用户仅见已发布模型）

---

### POST /api/models — 启动训练

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| scenario_id | int | 是 | 场景 ID |
| dataset_id | int | 是 | 数据集 ID（必须属于指定场景） |
| algorithm_id | int | 是 | 算法 ID |
| training_parameters | object | 是 | 训练参数 JSON（非空） |

**返回值**: 新模型版本（状态 TRAINING）

**权限**: 仅 ADMIN

---

### POST /api/models/{model_id}/complete — 训练完成

**入参**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| evaluation_metrics | object | 是 | 评估指标 JSON |

> 状态转换: TRAINING → DRAFT

**权限**: 仅 ADMIN

---

### POST /api/models/{model_id}/fail — 训练失败

**入参**: `error_message` (string, 可选)
> 状态转换: TRAINING → FAILED

**权限**: 仅 ADMIN

---

### POST /api/models/{model_id}/publish — 发布模型

> 状态转换: DRAFT → PUBLISHED 或 OFFLINE → PUBLISHED（重新发布）

**权限**: 仅 ADMIN

---

### POST /api/models/{model_id}/offline — 下线模型

> 状态转换: PUBLISHED → OFFLINE（默认模型自动取消默认状态）

**权限**: 仅 ADMIN

---

### POST /api/models/{model_id}/set-default — 设为默认推荐

> 约束：必须已发布；每个"场景+数据集"最多一个默认模型

**权限**: 仅 ADMIN

---

### POST /api/models/compare — 模型版本对比

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_ids | int[] | 是 | 模型版本 ID 列表 |

**权限**: 所有登录用户（普通用户只能比较已发布模型）

---

### DELETE /api/models/{model_id} — 删除模型版本

> 被推理记录或风险事件引用的禁止删除

**权限**: 仅 ADMIN

---

## 7. 推理记录

### GET /api/inference — 推理记录列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| model_version_id | int | — | 按模型版本过滤 |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**权限**: 所有登录用户（普通用户仅本人记录）

---

### GET /api/inference/{record_id} — 推理记录详情

**权限**: 本人或 ADMIN

---

### POST /api/inference — 执行推理

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model_version_id | int | 是 | 模型版本 ID（必须已发布） |
| input_features | object | 是 | 输入特征 JSON |
| prediction_label | string | 是 | 模型预测标签 |
| risk_score | float | 否 | 风险概率 [0,1] |
| executed_at | string | 否 | 推理时间 (ISO 8601) |

> 预测为风险类时自动生成 RiskEvent

**权限**: 所有登录用户

---

### DELETE /api/inference/{record_id} — 删除推理记录

> 已生成风险事件的推理记录禁止删除

**权限**: 仅 ADMIN

---

## 8. 风险事件

### GET /api/risk-events — 风险事件列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scenario_id | int | — | 按场景过滤（仅 ADMIN 可用） |
| status | string | — | 按状态过滤 PENDING/PROCESSING/RESOLVED |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**权限**: 普通用户强制按本人过滤；管理员可查全部

---

### GET /api/risk-events/{event_id} — 风险事件详情

**权限**: 本人或 ADMIN

---

### PUT /api/risk-events/{event_id}/status — 更新处置状态

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| new_status | string | 是 | PENDING / PROCESSING / RESOLVED |
| comment | string | 否 | 处置说明 |

**状态流转规则**: PENDING → PROCESSING / RESOLVED; PROCESSING → RESOLVED

**权限**: 本人事件或 ADMIN

---

### POST /api/risk-events/{event_id}/comment — 追加处置说明

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| comment | string | 是 | 处置说明（非空） |

> 不改状态，仅追加记录

**权限**: 本人事件或 ADMIN

---

## 9. 风险阈值

### GET /api/thresholds/{scenario_id} — 场景阈值配置

**返回值** `data`:
```json
{
  "scenario_id": 1,
  "medium_threshold": 0.5,
  "high_threshold": 0.8,
  "updated_by": 1,
  "updated_at": "2026-08-02T..."
}
```
> 未配置时返回 `data=null`

**权限**: 所有登录用户

---

### PUT /api/thresholds/{scenario_id} — 更新场景阈值

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| medium_threshold | float | 是 | 中风险阈值 [0,1] |
| high_threshold | float | 是 | 高风险阈值 [0,1]（必须大于 medium） |

> 修改后立即生效，自动写入审计日志

**权限**: 仅 ADMIN

---

### GET /api/thresholds/logs/list — 阈值变更日志

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scenario_id | int | — | 按场景过滤 |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**权限**: 仅 ADMIN

---

## 10. 态势统计

### GET /api/situation/my-stats — 个人态势统计

**返回值** `data`:
```json
{
  "total_events": 15,
  "high_count": 3,
  "medium_count": 7,
  "low_count": 5,
  "pending_count": 8,
  "processing_count": 4,
  "resolved_count": 3
}
```

**权限**: 所有登录用户（仅统计本人 RiskEvent）

---

### GET /api/situation/scene-stats — 全局态势统计

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| scenario_id | int | — | 按场景过滤 |

**权限**: 仅 ADMIN（统计全平台 RiskEvent）

---

### GET /api/situation/snapshots — 态势快照列表

**入参** (Query): scenario_id / page / page_size

**权限**: 所有登录用户

---

### GET /api/situation/snapshots/{scenario_id}/latest — 最新态势快照

**权限**: 所有登录用户

---

### POST /api/situation/snapshots/{scenario_id} — 生成态势快照

**权限**: 仅 ADMIN

---

## 11. 报告管理

### GET /api/reports — 报告列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| target_user_id | int | — | 按目标用户过滤（仅 ADMIN） |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**权限**: 普通用户仅本人相关报告；管理员全部

---

### GET /api/reports/{report_id} — 报告详情

**权限**: 生成者本人、目标用户本人或 ADMIN

---

### POST /api/reports — 生成报告

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| report_type | string | 是 | SCENE_SNAPSHOT / USER_SNAPSHOT |
| content | string | 是 | 报告内容 |
| target_user_id | int | 否 | 目标用户（普通用户只能为本人） |
| file_path | string | 否 | 文件路径 |

**权限**: 所有登录用户（普通用户只能基于本人数据）

---

### DELETE /api/reports/{report_id} — 删除报告

**权限**: 生成者本人或 ADMIN

---

## 12. 处置记录

### GET /api/handling-records — 处置记录列表

**入参** (Query):
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| risk_event_id | int | — | 按风险事件过滤 |
| page | int | 1 | 页码 |
| page_size | int | 10 | 每页条数 |

**权限**: 普通用户仅本人相关；管理员全部

---

### GET /api/handling-records/{record_id} — 处置记录详情

**权限**: 本人相关或 ADMIN

---

### POST /api/handling-records — 创建处置记录

**入参** (JSON Body):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| risk_event_id | int | 是 | 风险事件 ID |
| action | string | 是 | ASSIGN / UPDATE_STATUS / ADD_COMMENT |
| comment | string | 否 | 处置说明 |
| status_before | string | 否 | 变更前状态 |
| status_after | string | 否 | 变更后状态（action=UPDATE_STATUS 时必填） |

**权限**: 本人事件或 ADMIN

---

### DELETE /api/handling-records/{record_id} — 删除处置记录

**权限**: 仅 ADMIN

---

## 13. PMWNB 贝叶斯模型（兼容旧版）

> 以下接口兼容旧版前端 `frontend/src/api/modelApi.js`，独立于 v2.0 Service 层。

### GET /api/model/dataset-list — 数据集列表

**返回值**:
```json
{ "code": 200, "data": ["KDDTrain+ 20 Percent", "NF-UNSW-NB15-v2", "PowerGrid Knowledgebase"] }
```

---

### POST /api/model/save-threshold — 保存风险阈值

**入参** (Query):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| high | float | 是 | 高风险阈值 |
| mid | float | 是 | 中风险阈值 |
| low | float | 是 | 低风险阈值 |

**约束**: high > mid > low

---

### POST /api/model/train — 模型训练

**入参** (Query):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| dataset_name | string | 是 | 数据集名称 |
| algo_type | string | 否 | 算法类型（默认 PMWNB） |
| discrete_method | string | 否 | 离散化方式（默认 EWD+MDLP） |

**返回值**: 训练结果（accuracy, f1, recall, train_time_s）

---

### POST /api/model/infer — 单条推理

**入参** (Query):
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| flowLength | float | 是 | 流量总长度 |
| duration | float | 是 | 流量持续时长 |
| accessFreq | float | 是 | 单位时间访问频次 |

> 必须先训练后推理，否则 400

---

### GET /api/model/exp-records — 实验记录列表

---

### DELETE /api/model/exp/{record_id} — 删除实验记录

---

### GET /api/model/risk_statistics — 大屏统计

> 返回硬编码的看板统计数据（兼容旧版大屏视图）。

---

## 附录 A: 权限矩阵速查

| 资源 | 查看 | 创建 | 修改 | 删除 |
|------|------|------|------|------|
| 场景 | 所有用户 | ADMIN | ADMIN | ADMIN |
| 数据集 | 所有用户(限制) | ADMIN | ADMIN | ADMIN |
| 算法 | 所有用户 | 禁止 | 禁止 | 禁止 |
| 模型版本 | 所有用户(限制) | ADMIN | ADMIN | ADMIN |
| 推理记录 | 本人/ADMIN | 所有用户 | — | ADMIN |
| 风险事件 | 本人/ADMIN | 自动生成 | 本人/ADMIN | 禁止 |
| 阈值配置 | 所有用户 | ADMIN | ADMIN | — |
| 阈值日志 | ADMIN | 自动 | — | — |
| 态势快照 | 所有用户 | ADMIN | — | — |
| 报告 | 本人/ADMIN | 所有用户 | — | 本人/ADMIN |
| 处置记录 | 本人/ADMIN | 本人/ADMIN | — | ADMIN |
| 用户账号 | ADMIN(列表) | ADMIN | 本人(密码)/ADMIN | ADMIN |

## 附录 B: 默认管理员账号

首次启动时自动创建：
- 用户名: `admin`
- 密码: `admin123`
- 角色: `ADMIN`

> ⚠️ 首次登录后请立即修改密码。
