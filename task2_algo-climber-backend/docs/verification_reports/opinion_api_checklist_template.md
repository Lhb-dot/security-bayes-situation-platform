# Opinion API 验证记录模板

> 用途：记录 `GET /api/opinion/tasks`、`POST /api/opinion/tasks`、`POST /api/opinion/events`、`POST /api/opinion/raw` 的完成情况。

## 1. 执行信息

- 执行日期：
- 执行人：
- 服务地址：`http://127.0.0.1:12312`
- 代码版本（commit）：

## 2. 用例结果总览

| 用例ID | 接口 | 场景 | 期望 | 实际 | 结论 |
|---|---|---|---|---|---|
| T1 | GET `/api/opinion/tasks` | 基础成功 | 200 + `success=true` |  |  |
| T2 | POST `/api/opinion/tasks` | 创建任务成功 | 200 + 返回 `task_id` |  |  |
| T3 | POST `/api/opinion/events` | 按任务查询成功 | 200 + `events` 数组 |  |  |
| T4 | POST `/api/opinion/raw` | 按任务查询成功 | 200 + `raw_items` 数组 |  |  |
| T5 | POST `/api/opinion/raw` | 过滤成功(title/keyword/source) | 200 + 过滤生效 |  |  |
| T6 | POST `/api/opinion/raw` | 任务不存在 | 404 |  |  |
| T7 | POST `/api/opinion/raw` | 参数越界(`limit=5001`) | 422 |  |  |

## 3. 详细记录

### T1 - GET /api/opinion/tasks

- 请求参数：`limit=50`
- 响应状态：
- 响应摘要：
- 结论：PASS / FAIL

### T2 - POST /api/opinion/tasks

- 请求体：

```json
{
  "task_name": "API验证任务",
  "keywords": ["舆情", "战争"],
  "subjects": ["中国", "日本", "台湾"],
  "depth": 200,
  "intensity": 75,
  "output_dir": "output"
}
```

- 响应状态：
- `task_id`：
- 结论：PASS / FAIL

### T3 - POST /api/opinion/events

- 请求体：

```json
{
  "task_id": "<task_id>",
  "limit": 20
}
```

- 响应状态：
- `total`：
- 结论：PASS / FAIL

### T4 - POST /api/opinion/raw

- 请求体：

```json
{
  "task_id": "<task_id>",
  "limit": 20
}
```

- 响应状态：
- `total`：
- 结论：PASS / FAIL

### T5 - POST /api/opinion/raw（过滤）

- 请求体：

```json
{
  "task_id": "<task_id>",
  "title": "战争",
  "keyword": "舆情",
  "source": "新浪",
  "limit": 50
}
```

- 响应状态：
- 过滤命中情况：
- 结论：PASS / FAIL

### T6 - POST /api/opinion/raw（任务不存在）

- 请求体：`{"task_id":"t-not-exists"}`
- 响应状态：
- 错误信息：
- 结论：PASS / FAIL

### T7 - POST /api/opinion/raw（limit 越界）

- 请求体：`{"task_id":"<task_id>","limit":5001}`
- 响应状态：
- 错误信息：
- 结论：PASS / FAIL

## 4. 问题与建议

- 问题1：
- 影响范围：
- 建议修复：
