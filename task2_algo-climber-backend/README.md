# task2_algo 后端服务说明

本目录提供舆情采集与事件接口服务，核心目标是：

- 任务列表与事件明细解耦存储
- 事件按 `task_id` 分文件输出
- 提供前端可直接调用的统一 API

## 1. 目录结构

```text
task2_algo/
├─ server.py                      # FastAPI 服务入口（端口 12312）
├─ main.py                        # 爬取与事件生成主流程
├─ config.py                      # 环境变量与模型配置
├─ requirements.txt
├─ output/
│  ├─ tasks.json                  # 任务元信息（不包含事件数组）
│  ├─ task_events/
│  │  ├─ {task_id}.json           # 任务事件明细（JSON）
│  │  └─ {task_id}.csv            # 任务事件明细（CSV）
│  ├─ task_raw/
│  │  ├─ {task_id}.json           # 任务原始信息流（JSON）
│  │  └─ {task_id}.csv            # 任务原始信息流（CSV）
│  └─ equipment_events.json       # 兼容输出
└─ scripts/
   └─ auto_restart_and_verify_backend.ps1
```

## 2. 快速启动

### 2.1 环境准备

1. Python 3.10+
2. 配置 `.env`（见下文关键变量）
3. 安装依赖：

```bash
pip install -r requirements.txt
```

### 2.2 启动方式

- 直接启动接口服务：

```bash
python server.py
```

- 启动采集任务（离线执行）：

```bash
python main.py
```

服务默认地址：`http://127.0.0.1:12312`

## 3. 关键环境变量

`config.py` 依赖以下配置（至少保证这些可用）：

- `RISK_FACTORS_FILE`
- `MAX_PAGES`
- `MAX_EVENTS_PER_RUN`
- `MAX_ASYNC`
- `PORT`
- `LLM_BINDING_API_KEY`
- `LLM_BINDING_HOST`
- `LLM_MODEL`
- `MAX_TOKENS`
- `EMBEDDING_BINDING_API_KEY`
- `EMBEDDING_BINDING_HOST`
- `EMBEDDING_MODEL`
- `DIFY_BACKEND`
- `DIFY_API_KEY`

## 4. API 概览

核心联调接口：

- `GET /api/opinion/tasks`：返回任务列表（仅元信息）
- `POST /api/opinion/tasks`：创建并启动任务
- `POST /api/opinion/events`：按任务查询事件
- `POST /api/opinion/raw`：按任务查询原始信息流（支持标题/关键词过滤）

更多字段示例请见 [BACKEND_API.md](BACKEND_API.md)。

## 5. 数据存储约定（重要）

### 5.1 `tasks.json`

`output/tasks.json` 仅保存任务元信息，不保存事件数组：

- 保留：`id/name/status/progress/depth/intensity/time/keywords/subjects`
- 保留计数：`article_count/intel_count`
- 不保留：`articles/intel`

### 5.2 `task_events`

每个任务事件独立存储在：

- `output/task_events/{task_id}.json`
- `output/task_events/{task_id}.csv`

事件接口会优先读取对应 `task_id` 的事件文件。

### 5.3 `task_raw`

每个任务的原始信息流独立存储在：

- `output/task_raw/{task_id}.json`
- `output/task_raw/{task_id}.csv`

原始信息用于根据标题追溯正文、来源链接和采集时间，接口 `POST /api/opinion/raw` 会按任务读取该目录。

## 6. 常见联调命令（Windows）

```powershell
# 查看任务列表
curl http://127.0.0.1:12312/api/opinion/tasks

# 创建任务
curl -X POST http://127.0.0.1:12312/api/opinion/tasks \
  -H "Content-Type: application/json" \
  -d "{\"task_name\":\"红海测试任务\",\"keywords\":[\"红海\",\"航运\"],\"subjects\":[\"外交部\"],\"depth\":600,\"intensity\":75}"

# 查询某任务事件
curl -X POST http://127.0.0.1:12312/api/opinion/events \
  -H "Content-Type: application/json" \
  -d "{\"task_id\":\"t-1774000682\"}"
```

## 7. 验收建议

建议每次改动后按以下顺序验收：

1. `GET /api/opinion/tasks`：确认无 `articles/intel` 字段
2. `POST /api/opinion/events`：确认能按 `task_id` 返回事件
3. 检查 `output/task_events/{task_id}.json` 是否存在

可使用 `scripts/auto_restart_and_verify_backend.ps1` 一键重启和基础校验。

