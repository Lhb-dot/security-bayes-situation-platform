# 舆情感知任务接口说明

本文档用于展示后端针对前端任务配置页的适配完成情况。

## 1. 获取当前运行任务列表

- Method: `GET`
- Path: `/api/opinion/tasks`
- Query: `limit`(可选, 默认50)
- Request Body: `{}`

### Response

```json
{
  "success": true,
  "tasks": [
    {
      "id": "t-1773993852",
      "name": "默认任务",
      "status": "completed",
      "progress": 100,
      "depth": 1000,
      "intensity": 70,
      "time": "2026-03-20 16:04:12",
      "keywords": ["装备制造"],
      "subjects": ["主体A"],
      "articles": [],
      "intel": []
    }
  ],
  "running_tasks": [],
  "state": {
    "running": false,
    "task_id": null,
    "task_name": null,
    "started_at": null,
    "finished_at": null,
    "last_error": null
  },
  "total": 1
}
```

---

## 2. 创建舆情感知任务

- Method: `POST`
- Path: `/api/opinion/tasks`

### Request

```json
{
  "task_name": "美伊局势战略推演",
  "keywords": ["伊朗", "红海", "革命卫队"],
  "subjects": ["中央司令部", "伊朗外长"],
  "depth": 1500,
  "intensity": 90,
  "output_dir": "output"
}
```

### Response

```json
{
  "success": true,
  "task_id": "t-1773999999",
  "task_name": "美伊局势战略推演",
  "message": "舆情感知任务已创建并启动"
}
```

---

## 3. 根据任务ID获取感知事件列表

- Method: `POST`
- Path: `/api/opinion/events`

### Request

```json
{
  "task_id": "t-1773999999",
  "keyword": "伊朗",
  "source_type": "公共媒体",
  "level": "STRATEGIC",
  "limit": 200
}
```

### Response

```json
{
  "success": true,
  "task_id": "t-1773999999",
  "task_name": "美伊局势战略推演",
  "events": [
    {
      "event_name": "美伊冲突推动现代化航空装备战略需求",
      "source": "证券之星",
      "source_type": "公共媒体",
      "country": "未知",
      "time": "2026-03-04 10:53",
      "level": "STRATEGIC"
    }
  ],
  "total": 1
}
```

---

## 兼容说明

以下旧接口保持可用：

- `POST /api/start_crawl`
- `GET /api/crawl_status`
- `GET /api/tasks`
- `GET /strategic_events.json`

---

## 4. API 完成情况验证方案（可直接执行）

### 4.1 验证目标

- 覆盖接口：
  - `GET /api/opinion/tasks`
  - `POST /api/opinion/tasks`
  - `POST /api/opinion/events`
  - `POST /api/opinion/raw`
- 每个接口至少验证三类用例：成功、边界、异常。

### 4.2 操作步骤

1. 启动后端服务，确保 `http://127.0.0.1:12312/docs` 可访问。
2. 执行自动化验证脚本：

```powershell
cd d:\huzhiyuan zuhui\task2_algo
powershell -ExecutionPolicy Bypass -File .\scripts\verify_opinion_apis.ps1
```

3. 脚本执行完成后，查看自动生成报告：

`docs/verification_reports/opinion_api_verify_*.md`

4. 将报告结论（PASS/FAIL）同步到联调文档或验收记录。

### 4.3 模板与脚本

- 验证模板：`docs/verification_reports/opinion_api_checklist_template.md`
- 自动化脚本：`scripts/verify_opinion_apis.ps1`

### 4.4 完成判定标准

- 四个接口均有可追溯验证记录。
- 成功/边界/异常三类用例均有结果。
- 结果中包含 `task_id`、状态码、响应关键字段。
