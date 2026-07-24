# 后端 API 文档（task2_algo）

本文档用于前后端联调，重点覆盖 `opinion` 四个接口。

## 1. 基础信息

- Base URL：`http://127.0.0.1:12312`
- Content-Type：`application/json`
- 服务入口：`server.py`

## 2. 接口清单

### 2.1 获取任务列表

- 方法：`GET`
- 路径：`/api/opinion/tasks`
- Query：
  - `limit`（可选，默认 `50`，范围 `1-500`）

#### 响应示例

```json
{
  "success": true,
  "tasks": [
    {
      "id": "t-1774000682",
      "name": "红海舆情测试任务",
      "status": "completed",
      "progress": 100,
      "depth": 600,
      "intensity": 75,
      "time": "2026-03-20 17:58:02",
      "keywords": ["红海", "航运", "护航", "冲突"],
      "subjects": ["外交部", "联合国"],
      "article_count": 0,
      "intel_count": 2
    }
  ],
  "total": 1
}
```

> 说明：任务列表只返回任务元信息和计数，不返回事件数组。

---

### 2.2 创建任务

- 方法：`POST`
- 路径：`/api/opinion/tasks`

#### 请求体

```json
{
  "task_name": "红海舆情测试任务",
  "keywords": ["红海", "航运", "护航", "冲突"],
  "subjects": ["外交部", "联合国"],
  "depth": 600,
  "intensity": 75,
  "output_dir": "output"
}
```

#### 响应示例

```json
{
  "success": true,
  "task_id": "t-1774000682",
  "task_name": "红海舆情测试任务",
  "message": "舆情感知任务已创建并启动"
}
```

---

### 2.3 按任务查询事件

- 方法：`POST`
- 路径：`/api/opinion/events`

#### 请求体

```json
{
  "task_id": "t-1774000682",
  "keyword": "红海",
  "source_type": "公共媒体",
  "level": "STRATEGIC",
  "limit": 200
}
```

---

### 2.4 按任务查询原始信息流

- 方法：`POST`
- 路径：`/api/opinion/raw`

#### 请求体

```json
{
  "task_id": "t-1774000682",
  "title": "红海",
  "keyword": "航运",
  "source": "新华社",
  "limit": 200
}
```

字段说明：

- `task_id`：必填
- `title`：可选，按标题模糊过滤
- `keyword`：可选，按标题/正文/关键词字段过滤
- `source`：可选，按来源过滤
- `limit`：可选，默认 `200`，范围 `1-5000`

#### 响应示例

```json
{
  "success": true,
  "task_id": "t-1774000682",
  "task_name": "红海舆情测试任务",
  "raw_items": [
    {
      "raw_id": "raw-2f7f3a7d4c52",
      "task_id": "t-1774000682",
      "task_name": "红海舆情测试任务",
      "keyword": "红海",
      "title": "红海航运保费持续上升",
      "content": "......",
      "url": "https://example.com/a",
      "source": "新华社",
      "origin": "新闻网站",
      "publish_time": "2026-03-20 09:12:00",
      "crawled_at": "2026-03-20 09:30:12"
    }
  ],
  "total": 1
}
```

字段说明：

- `task_id`：必填
- `keyword`：可选，事件名/来源/国家关键字过滤
- `source_type`：可选，来源类型过滤
- `level`：可选，等级过滤（如 `STRATEGIC` / `TACTICAL`）
- `limit`：可选，默认 `200`，范围 `1-2000`

#### 响应示例

```json
{
  "success": true,
  "task_id": "t-1774000682",
  "task_name": "红海舆情测试任务",
  "events": [
    {
      "event_name": "伊朗：冲突新阶段已开始_央广网",
      "source": "新华社",
      "source_type": "公共媒体",
      "country": "伊朗",
      "time": "2026-03-19 14:27:40",
      "level": "STRATEGIC",
      "info_type": "国际"
    }
  ],
  "total": 1
}
```

## 3. 事件数据来源说明

`/api/opinion/events` 查询逻辑：

1. 优先读取 `output/task_events/{task_id}.json`
2. 若对应文件不存在或为空，回退兼容路径

这保证了事件与任务的文件级隔离。

## 4. 存储结构约定

- `output/tasks.json`：只存任务元信息 + 计数字段
- `output/task_events/{task_id}.json/.csv`：存任务事件明细
- `output/task_raw/{task_id}.json/.csv`：存任务原始信息流（标题、正文、链接、来源、时间等）

## 5. 常见错误

- `404 任务不存在`：`task_id` 在 `tasks.json` 中未找到
- `422 参数校验失败`：请求体字段类型或范围不合法

## 6. 联调建议

1. 先调用创建任务接口，拿到 `task_id`
2. 轮询任务列表接口，观察 `status/progress`
3. 使用 `task_id` 调用事件接口获取事件明细
